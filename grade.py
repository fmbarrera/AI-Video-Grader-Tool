"""Score reflection transcripts against rubric.md using Claude.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    .venv/bin/python grade.py [--transcripts transcripts] [--out grades]

Writes one feedback file per student to grades/<name>.md plus a summary
grades/grades.csv you can sort or paste into the gradebook. Transcripts that
already have a feedback file are skipped (use --force to regrade).
"""
import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"
MAX_POINTS = 40
# Points taken off per prompt. Edit these to make grading stricter or more lenient.
DEDUCTIONS = {"thoughtful": 0, "thin": 2, "missing": 2}
RUBRIC = Path(__file__).with_name("rubric.md")
CRITERIA = [
    ("perception", "Change in perception"),
    ("readings", "Readings / assigned materials"),
    ("experiential", "In-class experiential learning"),
    ("next_phase", "Next-phase priorities"),
    ("personal", "Personal & specific"),  # thoughtful = their own experience comes through; thin = generic
]
AI_SCRIPT_FLAG = "Possible AI script"


class CriterionScore(BaseModel):
    status: Literal["thoughtful", "thin", "missing"]
    evidence: str = Field(description="Short quote(s) from the transcript supporting the judgment")
    rationale: str = Field(description="One or two sentences written to the student ('You ...'). For thin or missing, "
                                       "say exactly what was missing so the student understands why points came off.")


class Grade(BaseModel):
    student_name: str = Field(description="Name if the student says it, otherwise 'Unknown'")
    perception: CriterionScore
    readings: CriterionScore
    experiential: CriterionScore
    next_phase: CriterionScore
    personal: CriterionScore = Field(description="thoughtful if the student's own experience, interviews, or venture details come through; thin if it is a generic, polished summary that anyone could have written. Never 'missing'.")
    possible_ai_script: bool = Field(description="True if the reflection shows strong signs of being read from an AI-written script")
    ai_script_reason: str = Field(description="If possible_ai_script, the specific signs (quote them). Otherwise empty.")
    overall_comment: str = Field(description="1-2 sentences to the student on what they did well, specific to their reflection. "
                                             "Deductions are explained separately, so don't repeat them here.")
    flags: list[str] = Field(description="Anything the TA should double-check (off-topic, very short, unclear audio, etc.). Empty if none.")


def read_transcript(path: Path) -> tuple[float, str]:
    raw = path.read_text(encoding="utf-8")
    m = re.search(r"# Duration: ([\d.]+) min", raw)
    return (float(m.group(1)) if m else 0.0), raw


def grade(client: anthropic.Anthropic, system: str, transcript: str) -> Grade:
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        # Server-side fallback: if a safety classifier declines, the API retries on another model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=system,
        messages=[{"role": "user", "content": f"<transcript>\n{transcript}\n</transcript>\n\nJudge each prompt in this reflection."}],
        output_format=Grade,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"no grade returned (stop_reason={response.stop_reason})")
    return response.parsed_output


def write_feedback(path: Path, source: str, minutes: float, g: Grade) -> int:
    total = MAX_POINTS - sum(DEDUCTIONS[getattr(g, key).status] for key, _ in CRITERIA)
    lines = [f"# {g.student_name} — {total}/{MAX_POINTS}", "", f"Video: {source} ({minutes:.1f} min)", ""]
    for key, label in CRITERIA:
        c = getattr(g, key)
        off = DEDUCTIONS[c.status]
        lines += [f"## {label}: {c.status} ({f'-{off}' if off else 'no deduction'})", "", c.rationale, "", f"> {c.evidence}", ""]
    lines += ["## Overall", "", g.overall_comment, ""]
    flags = ([f"{AI_SCRIPT_FLAG} (not deducted; watch the video to confirm): {g.ai_script_reason}"]
             if g.possible_ai_script else []) + g.flags
    if flags:
        lines += ["## Check", ""] + [f"- {f}" for f in flags] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcripts", default="transcripts")
    ap.add_argument("--out", default="grades")
    ap.add_argument("--force", action="store_true", help="regrade transcripts that already have feedback")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    transcripts = sorted(Path(args.transcripts).glob("*.txt"))
    if not transcripts:
        sys.exit(f"No transcripts in {args.transcripts}/ — run transcribe.py first.")

    system = (
        "You are helping a teaching assistant grade student video reflections for an "
        "undergraduate entrepreneurship course. Apply this rubric fairly and consistently; "
        "be specific and quote the student.\n\n" + RUBRIC.read_text(encoding="utf-8")
    )
    client = anthropic.Anthropic()

    for i, path in enumerate(transcripts, 1):
        feedback = out_dir / f"{path.stem}.md"
        if feedback.exists() and not args.force:
            print(f"[{i}/{len(transcripts)}] skip (already graded): {path.name}")
            continue
        print(f"[{i}/{len(transcripts)}] grading: {path.name}", flush=True)
        minutes, text = read_transcript(path)
        try:
            g = grade(client, system, text)
        except (anthropic.APIError, RuntimeError) as e:
            print(f"    !! {e}", file=sys.stderr)
            continue
        total = write_feedback(feedback, path.stem, minutes, g)
        print(f"    -> {total}/{MAX_POINTS}  {feedback}")

    rebuild_csv(out_dir)


def read_feedback(md: Path) -> dict:
    """Parse a feedback file written by write_feedback()."""
    text = md.read_text(encoding="utf-8")
    labels = {label: key for key, label in CRITERIA}
    statuses = {labels[label]: status for label, status in
                re.findall(r"^## (.*): (thoughtful|thin|missing) \(", text, re.M)}
    section = lambda title: (re.search(rf"^## {title}\n\n(.*?)(?=\n## |\Z)", text, re.M | re.S) or [None, ""])[1].strip()
    return {
        "name": re.match(r"# (.*) — ", text).group(1),
        "total": int(re.match(r"# .* — (\d+)/", text).group(1)),
        "minutes": float(re.search(r"\(([\d.]+) min\)", text).group(1)),
        "statuses": statuses,
        "comment": section("Overall"),
        "flags": [line[2:] for line in section("Check").splitlines() if line.startswith("- ")],
        "deductions": [(label, int(off), section(re.escape(f"{label}: {status} (-{off})")).split("\n\n")[0])
                       for label, status, off in re.findall(r"^## (.*): (thin|missing) \(-(\d+)\)$", text, re.M)],
    }


def rebuild_csv(out_dir: Path) -> None:
    """Rebuild grades.csv from every feedback file so it always reflects the full set."""
    rows = []
    for md in sorted(out_dir.glob("*.md")):
        fb = read_feedback(md)
        rows.append([md.stem, fb["name"], fb["minutes"], *[fb["statuses"][k] for k, _ in CRITERIA],
                     fb["total"], "yes" if fb["flags"] else ""])
    with open(out_dir / "grades.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["video", "student", "minutes", *[label for _, label in CRITERIA], f"total_{MAX_POINTS}", "needs_check"])
        w.writerows(rows)
    print(f"Summary: {out_dir / 'grades.csv'} ({len(rows)} students)")


if __name__ == "__main__":
    main()
