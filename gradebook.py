"""Write Claude's points and student-facing comments into the TA's gradebook.

Usage:
    .venv/bin/python gradebook.py "Reflection 1 Grades_claude new template.xlsx" [--sheet "Reflections 1"]

Close the workbook in Excel first. The sheet needs a header row with "Student" (or
"Name") in column A, plus "Graded by", "Grader's Assigned Points", and "Date Submitted".
The script matches each grades/<video>.md to a student by the "Last, First" start of the
video file name and fills these columns to the right of the TA's (re-running updates them):

  Claude Points             40 minus 2 for each thin / missing check
  Late Policy               points removed by the 80% late cap, if any
  Final Points              Claude's points after the late policy; the grader's points if
                            there's no video; 0 if not submitted
  Comment for Student       why points came off, then what they did well
  TA Notes                  for the TA only: possible AI script, length, transcript glitches,
                            and where Claude differs from the grader

The TA's own columns are never changed. A copy of the workbook from before the first
run is saved as "<name> (before Claude).xlsx".
"""
import argparse
import re
import shutil
import sys
import unicodedata
from datetime import datetime, time
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from grade import MAX_POINTS, read_feedback
from late import LATE_CAP_PCT, days_late

COLUMNS = {  # header -> width
    "Claude Points": 12, "Late Policy": 11, "Final Points": 11,
    "Comment for Student": 80, "TA Notes (not for students)": 55,
}
STUDENT_LABELS = {
    "Change in perception": "Change in perception",
    "Readings / assigned materials": "Specific takeaway from readings / class material",
    "In-class experiential learning": "In-class experiential learning",
    "Next-phase priorities": "Next-phase priority for your venture",
    "Personal & specific": "Personal & specific reflection",
}
HEADER_FILL = PatternFill("solid", fgColor="EAF1FB")
WRAP = Alignment(wrap_text=True, vertical="top")


def key(name: str) -> str:
    """'Doe, Jane\\n' and 'Doe,Jane' -> 'doe,jane'."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", name)).casefold()


def find_header(ws) -> int:
    for row in ws.iter_rows(min_col=1, max_col=1):
        if isinstance(row[0].value, str) and row[0].value.strip() in ("Student", "Name"):
            return row[0].row
    sys.exit("Couldn't find a header row with 'Student' or 'Name' in column A.")


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


def student_comment(fb: dict, final: float, late_off: float) -> str:
    if final == MAX_POINTS:
        return f"{final:g}/{MAX_POINTS} (full marks). {fb['comment']}"
    lines = [f"{final:g}/{MAX_POINTS}. Points deducted:"]
    lines += [f"\u2022 \u2212{off} {STUDENT_LABELS.get(label, label)}: {reason}" for label, off, reason in fb["deductions"]]
    if late_off:
        lines.append(f"\u2022 \u2212{late_off:g} Late: submitted after the Sep 24 grace period; late work is capped at "
                     f"{MAX_POINTS * LATE_CAP_PCT / 100:g}/{MAX_POINTS}.")
    lines.append(f"What you did well: {fb['comment']}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workbook")
    ap.add_argument("--sheet", default="Reflections 1")
    ap.add_argument("--grades", default="grades")
    args = ap.parse_args()

    src = Path(args.workbook)
    backup = src.with_name(f"{src.stem} (before Claude).xlsx")
    if not backup.exists():
        shutil.copy2(src, backup)
    wb = openpyxl.load_workbook(src)
    ws = wb[args.sheet]
    header = find_header(ws)
    cols = {str(c.value).strip(): c.column for c in ws[header] if c.value}
    name_col, by_col, grader_col, date_col = (
        cols[ws.cell(header, 1).value.strip()], cols["Graded by"], cols["Grader's Assigned Points"], cols["Date Submitted"])

    # Reuse our columns on a re-run; otherwise add them after a blank divider column.
    if "Claude Points" in cols:
        c = {h: cols["Claude Points"] + i for i, h in enumerate(COLUMNS)}
    else:
        c = {h: max(cols.values()) + 2 + i for i, h in enumerate(COLUMNS)}
    for h, width in COLUMNS.items():
        cell = ws.cell(header, c[h], h)
        cell.font, cell.fill, cell.alignment = Font(bold=True), HEADER_FILL, WRAP
        ws.column_dimensions[cell.column_letter].width = width

    rows = {key(ws.cell(r, name_col).value): r
            for r in range(header + 1, ws.max_row + 1) if ws.cell(r, name_col).value}
    names = {k: ws.cell(r, name_col).value for k, r in rows.items()}
    feedback = match_feedback(Path(args.grades), list(rows), names)

    finals = []
    for k, r in rows.items():
        for h in COLUMNS:
            ws.cell(r, c[h]).value = None
            ws.cell(r, c[h]).alignment = WRAP
        by, grader = ws.cell(r, by_col).value, ws.cell(r, grader_col).value
        grader = grader if isinstance(grader, (int, float)) else None
        if isinstance(by, str) and "not submitted" in by.lower():
            ws.cell(r, c["Final Points"], 0)
            ws.cell(r, c["Comment for Student"], "Not submitted.")
            continue

        submitted = as_date(ws.cell(r, date_col).value)
        late = submitted and days_late(datetime.combine(submitted.date(), time(23, 59))) > 0
        notes = []
        if k in feedback:
            fb = read_feedback(feedback[k])
            points = fb["total"]
            final = min(points, MAX_POINTS * LATE_CAP_PCT / 100) if late else points
            late_off = points - final
            ws.cell(r, c["Claude Points"], points)
            ws.cell(r, c["Late Policy"], -late_off if late_off else None)
            ws.cell(r, c["Comment for Student"], student_comment(fb, final, late_off))
            if grader is not None and grader != final:
                notes.append(f"Grader gave {grader:g}; Claude gives {final:g}.")
            notes += fb["flags"]
            if not submitted:
                notes.append("No submission date, so the late policy wasn't checked.")
        elif grader is not None:
            final = grader
            notes.append("No video found here; Final Points uses the grader's points.")
        else:
            continue
        ws.cell(r, c["Final Points"], final)
        ws.cell(r, c["TA Notes (not for students)"], "\n".join(f"\u2022 {n}" for n in notes) or None)
        finals.append(final)

    wb.save(src)
    print(f"Updated '{args.sheet}' in {src} (original saved as {backup.name})")
    if finals:
        avg = sum(finals) / len(finals)
        print(f"  {len(feedback)} graded by Claude; class average of {len(finals)} submissions: "
              f"{avg:.2f}/{MAX_POINTS} = {avg / MAX_POINTS:.1%}")


if __name__ == "__main__":
    main()
