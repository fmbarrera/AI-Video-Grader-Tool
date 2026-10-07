"""Merge AI feedback and the late policy into the TA's gradebook spreadsheet.

Usage:
    .venv/bin/python gradebook.py "Reflection 1 Grades_claude.xlsx" [--grades grades]

Reads the roster (header row starting with "Name"), matches each grades/<video>.md
to a student by the "Last, First" prefix of the video file name, and writes a copy
of the workbook named "<original> - AI review.xlsx" with extra columns to the right.
The TA's own columns are never changed, except that blank Length cells are filled
in from the video duration.

Prompt columns use the TA's scale: 3 = thoughtful, 2 = thin (-1), 1 = missing (-2), so Points = 40 minus what the four columns fall short of 3.
"""
import argparse
import re
import sys
import unicodedata
from datetime import datetime, time
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill

from grade import CRITERIA, DEDUCTIONS, read_feedback
from late import apply_late_policy, days_late

PROMPT_SCALE = 3  # what the TA enters for full credit on a prompt
NEW_COLUMNS = [
    "AI: perception", "AI: readings", "AI: experiential", "AI: next phase",
    "AI points", "Days late", "Late deduction", "Final points", "Final based on",
    "TA vs AI", "AI notes",
]
AI_FILL = PatternFill("solid", fgColor="EAF1FB")


def key(name: str) -> str:
    """'Doe, Jane\\n' and 'Doe,Jane' -> 'doe,jane'."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", name)).casefold()


def find_header(ws) -> int:
    for row in ws.iter_rows(min_col=1, max_col=1):
        if isinstance(row[0].value, str) and row[0].value.strip() == "Name":
            return row[0].row
    sys.exit("Couldn't find a header row with 'Name' in column A.")


def short_key(name: str) -> tuple[str, str]:
    """('ortega', 'nina') from 'Ortega Vidal,Nina' or 'Ortega, Laia_Reflection1.mov'."""
    last, _, first = unicodedata.normalize("NFKC", name).partition(",")
    word = lambda s: (re.findall(r"[^\W\d_]+", s) or [""])[0].casefold()
    return word(last), word(first)


def match_feedback(grades_dir: Path, roster_keys: list[str], roster_names: dict[str, str]) -> dict[str, Path]:
    """Map roster key -> feedback file.

    First tries the full roster name as a prefix of the file name; if that fails, falls back to
    first word of last name + first word of first name, so 'Ortega, Nina' finds 'Ortega Vidal,Nina'.
    """
    short = {}
    for k in roster_keys:
        short.setdefault(short_key(roster_names[k]), []).append(k)
    matched, unmatched = {}, []
    for md in sorted(grades_dir.glob("*.md")):
        stem = key(md.stem)
        hits = [k for k in roster_keys if stem.startswith(k)] or short.get(short_key(md.stem), [])
        if len(set(hits)) == 1 or (hits and stem.startswith(max(hits, key=len))):
            matched[max(hits, key=len)] = md
        else:
            unmatched.append(md.name)
    for name in unmatched:
        print(f"  !! no roster match for {name} (file name should start with 'Last, First')", file=sys.stderr)
    return matched


def as_date(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                pass
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workbook")
    ap.add_argument("--grades", default="grades")
    args = ap.parse_args()

    src = Path(args.workbook)
    wb = openpyxl.load_workbook(src)
    ws = wb.active
    header = find_header(ws)
    cols = {str(c.value).strip(): c.column for c in ws[header] if c.value}
    name_col, status_col, date_col, length_col, points_col = (
        cols["Name"], cols["Graded"], cols["Date Submitted"], cols["Length"], cols["Points"])
    prompt_cols = list(range(length_col + 1, points_col))  # the four prompt columns, in order
    max_points = float(ws["B2"].value or 40)

    rows = {key(ws.cell(r, name_col).value): r
            for r in range(header + 1, ws.max_row + 1) if ws.cell(r, name_col).value}
    names = {k: ws.cell(r, name_col).value for k, r in rows.items()}
    feedback = match_feedback(Path(args.grades), list(rows), names)

    first = ws.max_column + 2  # leave one blank column as a divider
    for i, title in enumerate(NEW_COLUMNS):
        cell = ws.cell(header, first + i, title)
        cell.font, cell.fill = Font(bold=True), AI_FILL
        ws.column_dimensions[cell.column_letter].width = 60 if title == "AI notes" else 14
    c = {title: first + i for i, title in enumerate(NEW_COLUMNS)}

    counts = {"ai": 0, "ta": 0, "ai_only": 0, "late": 0}
    for k, r in rows.items():
        status = ws.cell(r, status_col).value
        if isinstance(status, str) and "not submitted" in status.lower():
            ws.cell(r, c["Final points"], 0)
            ws.cell(r, c["Final based on"], "not submitted")
            continue

        ai_points = ai_scores = None
        if k in feedback:
            fb = read_feedback(feedback[k])
            ai_scores = [PROMPT_SCALE - DEDUCTIONS[fb["statuses"][key_]] for key_, _ in CRITERIA]
            ai_points = max_points - sum(DEDUCTIONS[fb["statuses"][key_]] for key_, _ in CRITERIA)
            for col, score in zip([c[t] for t in NEW_COLUMNS[:4]], ai_scores):
                ws.cell(r, col, score)
            ws.cell(r, c["AI points"], ai_points)
            ws.cell(r, c["AI notes"], " | ".join(filter(None, [fb["comment"], *fb["flags"]])))
            if ws.cell(r, length_col).value is None:
                ws.cell(r, length_col, fb["minutes"])
            counts["ai"] += 1

        ta_points = ws.cell(r, points_col).value
        ta_scores = [ws.cell(r, col).value for col in prompt_cols]
        if ai_scores and all(isinstance(s, (int, float)) for s in ta_scores):
            diffs = [f"{label}: TA {t}, AI {a}" for (_, label), t, a in zip(CRITERIA, ta_scores, ai_scores) if t != a]
            ws.cell(r, c["TA vs AI"], "; ".join(diffs) or "agree")

        base, basis = (ta_points, "TA") if isinstance(ta_points, (int, float)) else (ai_points, "AI (not yet TA-graded)")
        if base is None:
            continue
        counts["ta" if basis == "TA" else "ai_only"] += 1

        submitted = as_date(ws.cell(r, date_col).value)
        late_days = deduction = 0
        if submitted:
            # Dates in the sheet have no time; count them as end of that day.
            submitted = datetime.combine(submitted.date(), time(23, 59))
            late_days = days_late(submitted)
            deduction = round(base - apply_late_policy(base, max_points, submitted), 2)
            counts["late"] += late_days > 0
        else:
            basis += ", no submit date"
        ws.cell(r, c["Days late"], late_days)
        ws.cell(r, c["Late deduction"], -deduction if deduction else 0)
        ws.cell(r, c["Final points"], max(0, base - deduction))
        ws.cell(r, c["Final based on"], basis)

    out = src.with_name(f"{src.stem} - AI review.xlsx")
    wb.save(out)
    print(f"Wrote {out}")
    print(f"  {counts['ai']} students with AI feedback, {counts['ta']} with TA points, "
          f"{counts['ai_only']} using AI points until TA grades, {counts['late']} late")


if __name__ == "__main__":
    main()
