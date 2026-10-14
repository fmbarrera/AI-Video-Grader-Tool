"""Write Claude's points and student-facing comments into the TA's gradebook.

Usage:
    .venv/bin/python gradebook.py "Reflection 1 Grades_claude new template.xlsx" [--sheet "Reflections 1"]

Close the workbook in Excel first. The sheet needs a header row with "Student" (or
"Name") in column A, plus "Graded by", "Grader's Assigned Points", and "Date Submitted".
The script matches each grades/<video>.md to a student by the "Last, First" (or Canvas's
"lastfirst_...") start of the video file name and fills these columns to the right of the TA's (re-running updates them):

  Claude Points             40 minus 4 per thin check, 5 per missing check
  Late Policy               points removed by the 80% late cap, if any
  Final Points              Claude's points plus any TA Adjustment, after the late policy;
                            the grader's points if there's no video; 0 if not submitted
  Comment for Student       what they did well, then where any points went
  TA Notes                  for the TA only: possible AI script, length, transcript glitches,
                            and where Claude differs from the grader
  Personal Comment          a warmer note to the student: praise first, then what to talk about
                            in the next reflection. If you edit one by hand, re-runs keep your
                            text; clear the cell to get Claude's version back.

Two more columns are for the TA to fill in and are never overwritten:

  TA Adjustment             points to add or remove after watching the video, e.g. -4 for a
                            confirmed AI-written script
  Adjustment Reason         why, in words for the student; it's listed with the deductions

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
    "Comment for Student": 80, "TA Notes (not for students)": 55, "Personal Comment for Student": 80,
    "Personal Comment (new style)": 80,
}
ADJUSTMENT, ADJUSTMENT_REASON = "TA Adjustment", "Adjustment Reason (for student)"
TA_INPUTS = {ADJUSTMENT: 12, ADJUSTMENT_REASON: 40}  # filled in by the TA; never cleared
PERSONAL, NEW_STYLE = "Personal Comment for Student", "Personal Comment (new style)"
# Comment columns a TA may edit by hand -> hidden column holding what we last wrote there, so edits can be kept
KEEP_EDITS = {PERSONAL: "Personal Comment as generated", NEW_STYLE: "New-style comment as generated"}
GENERATED = KEEP_EDITS[PERSONAL]
HIDDEN = {h: 10 for h in KEEP_EDITS.values()}
STUDENT_LABELS = {
    "Change in perception": "Change in perception",
    "Readings / assigned materials": "Readings",
    "In-class experiential learning": "In-class experience",
    "Next-phase priorities": "Next steps",
    "Personal & specific": "Personal reflection",
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

    First tries the full roster name as a prefix of the file name, then Canvas's newer
    'lastfirst_123_456_original' names, so 'doejane_...' finds 'Doe, Jane'. Last, falls back to
    first word of last name + first word of first name, so 'Ortega, Nina' finds 'Ortega Vidal,Nina'.
    """
    short, joined = {}, {}
    for k in roster_keys:
        short.setdefault(short_key(roster_names[k]), []).append(k)
        joined.setdefault(re.sub(r"[^\w]", "", k), []).append(k)
    matched, unmatched = {}, []
    for md in sorted(grades_dir.glob("*.md")):
        stem = key(md.stem)
        hits = ([k for k in roster_keys if stem.startswith(k)] or joined.get(stem.split("_")[0], [])
                or short.get(short_key(md.stem), []))
        if len(set(hits)) == 1 or (hits and stem.startswith(max(hits, key=len))):
            matched[max(hits, key=len)] = md
        else:
            unmatched.append(md.name)
    for name in unmatched:
        print(f"  !! no roster match for {name} (file name should start with 'Last, First' or 'lastfirst_')", file=sys.stderr)
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


def as_points(value) -> float:
    """-4, "-4", "−4" or "+2" -> a number; blank or anything else -> 0."""
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).strip().replace("\u2212", "-"))
    except ValueError:
        return 0


def personal_comment(fb: dict, late_off: float, adjustment: float = 0, reason: str | None = None) -> str | None:
    """The personal note from the grade file, plus any adjustment or late penalty in plain words."""
    lines = [fb["personal_comment"]] if fb["personal_comment"] else []
    if adjustment:
        lines.append(f"I {'removed' if adjustment < 0 else 'added'} {abs(adjustment):g} points after reviewing your "
                     f"video{': ' + reason if reason else '.'}")
    if late_off:
        lines.append(f"Because it came in after the Sep 24 grace period, the score is capped at "
                     f"{MAX_POINTS * LATE_CAP_PCT / 100:g}/{MAX_POINTS}.")
    return "\n\n".join(lines) or None


def student_comment(fb: dict, final: float, late_off: float, adjustment: float = 0, reason: str | None = None) -> str:
    """Praise first, then where any points went, in plain words."""
    if final == MAX_POINTS:
        return f"{final:g}/{MAX_POINTS}. {fb['comment']}"
    lines = [f"{final:g}/{MAX_POINTS}. {fb['comment']}", "", "Where the points went:"]
    lines += [f"\u2022 {STUDENT_LABELS.get(label, label)} (\u2212{off}): {why}" for label, off, why in fb["deductions"]]
    if adjustment:
        sign = "\u2212" if adjustment < 0 else "+"
        lines.append(f"\u2022 Adjustment ({sign}{abs(adjustment):g}): {reason or 'after reviewing your video.'}")
    if late_off:
        lines.append(f"\u2022 Late (\u2212{late_off:g}): submitted after the Sep 24 grace period, so it's capped at "
                     f"{MAX_POINTS * LATE_CAP_PCT / 100:g}/{MAX_POINTS}.")
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

    # Reuse our columns by name on a re-run. Add missing ones at the right edge (after a blank
    # divider the first time), so columns the sheet's formatting points at don't shift.
    c, next_col = {}, max(cols.values()) + (1 if "Claude Points" in cols else 2)
    for h in [*COLUMNS, *TA_INPUTS, *HIDDEN]:
        c[h] = cols.get(h, next_col)
        next_col += h not in cols
    for h, width in {**COLUMNS, **TA_INPUTS, **HIDDEN}.items():
        cell = ws.cell(header, c[h], h)
        cell.font, cell.fill, cell.alignment = Font(bold=True), HEADER_FILL, WRAP
        ws.column_dimensions[cell.column_letter].width = width
        ws.column_dimensions[cell.column_letter].hidden = h in HIDDEN

    rows = {key(ws.cell(r, name_col).value): r
            for r in range(header + 1, ws.max_row + 1) if ws.cell(r, name_col).value}
    names = {k: ws.cell(r, name_col).value for k, r in rows.items()}
    feedback = match_feedback(Path(args.grades), list(rows), names)

    finals, kept = [], []
    for k, r in rows.items():
        before = {h: (ws.cell(r, c[h]).value, ws.cell(r, c[g]).value) for h, g in KEEP_EDITS.items()}

        def set_kept(h: str, text: str | None) -> bool:
            """Write a comment column unless the TA edited the cell by hand; then keep their text."""
            cur, last = before[h]
            edited = bool(cur) and cur != (text if last is None else last)
            ws.cell(r, c[h], cur if edited else text)
            ws.cell(r, c[KEEP_EDITS[h]], text)
            if edited:
                kept.append(f"{names[k]} ({h})")
            return edited

        def set_personal(text: str | None, new_style: str | None = None) -> bool:
            set_kept(NEW_STYLE, new_style if text and new_style is not None else text)
            return set_kept(PERSONAL, text)

        for h in COLUMNS:
            if h not in KEEP_EDITS:  # set_kept() handles these, keeping hand edits
                ws.cell(r, c[h]).value = None
            ws.cell(r, c[h]).alignment = WRAP
        by, grader = ws.cell(r, by_col).value, ws.cell(r, grader_col).value
        grader = grader if isinstance(grader, (int, float)) else None
        if isinstance(by, str) and "not submitted" in by.lower():
            ws.cell(r, c["Final Points"], 0)
            ws.cell(r, c["Comment for Student"], "Not submitted.")
            set_personal("Not submitted.")
            continue

        submitted = as_date(ws.cell(r, date_col).value)
        late = submitted and days_late(datetime.combine(submitted.date(), time(23, 59))) > 0
        notes = []
        if k in feedback:
            fb = read_feedback(feedback[k])
            points = fb["total"]
            adjustment = as_points(ws.cell(r, c[ADJUSTMENT]).value)
            adjusted = max(0, min(MAX_POINTS, points + adjustment))
            final = min(adjusted, MAX_POINTS * LATE_CAP_PCT / 100) if late else adjusted
            late_off = adjusted - final
            ws.cell(r, c["Claude Points"], points)
            ws.cell(r, c["Late Policy"], -late_off if late_off else None)
            ws.cell(r, c["Comment for Student"], student_comment(
                fb, final, late_off, adjusted - points, ws.cell(r, c[ADJUSTMENT_REASON]).value))
            new_style = fb["new_style_comment"] or None
            if new_style and late_off:  # TA adjustments are left out: write their reason into the comment yourself
                new_style += f"\n\nBecause it came in after the Sep 24 grace period, the score is capped at {MAX_POINTS * LATE_CAP_PCT / 100:g}/{MAX_POINTS}."
            if set_personal(personal_comment(fb, late_off, adjusted - points, ws.cell(r, c[ADJUSTMENT_REASON]).value), new_style):
                notes.append("Personal Comment was edited by hand, so it was kept as is. Clear the cell to get Claude's version.")
            if grader is not None and grader != final:
                notes.append(f"Grader gave {grader:g}; Claude gives {final:g}.")
            if adjusted != points:
                notes.append(f"TA Adjustment of {adjusted - points:+g} applied.")
            notes += fb["flags"]
            if not submitted:
                notes.append("No submission date, so the late policy wasn't checked.")
        elif grader is not None:
            set_personal(None)
            final = grader
            notes.append("No video found here; Final Points uses the grader's points.")
            if as_points(ws.cell(r, c[ADJUSTMENT]).value):
                notes.append("TA Adjustment ignored: with no video, the grader's points are used as is.")
        else:
            set_personal(None)
            continue
        ws.cell(r, c["Final Points"], final)
        ws.cell(r, c["TA Notes (not for students)"], "\n".join(f"\u2022 {n}" for n in notes) or None)
        finals.append(final)

    wb.save(src)
    print(f"Updated '{args.sheet}' in {src} (original saved as {backup.name})")
    if kept:
        print(f"  kept {len(kept)} hand-edited comments: {', '.join(kept)}")
    if finals:
        avg = sum(finals) / len(finals)
        print(f"  {len(feedback)} graded by Claude; class average of {len(finals)} submissions: "
              f"{avg:.2f}/{MAX_POINTS} = {avg / MAX_POINTS:.1%}")


if __name__ == "__main__":
    main()
