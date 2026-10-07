# Reflection Video Grader

Helps TAs grade student video reflections for an entrepreneurship course. It
transcribes each video locally, has Claude judge the reflection against a
rubric, and merges the results and the late policy into a copy of the TA
gradebook. Students answer four prompts in a 3–5 minute video:

1. How their perception of entrepreneurship has changed
2. Takeaways from readings / assigned materials
3. What they got out of in-class experiential learning
4. What they'll prioritize in the next phase of their venture

**Setting it up on another computer?** Follow [SETUP.md](SETUP.md).

The output is a first pass for the TA to review. The TA's spreadsheet stays
the official record.

## How grading works

Every reflection starts at **40 points**. The professor's target is a class
average of about 88% among students who submitted. Each reflection gets five
checks, the four prompts plus one for authenticity:

1. **Change in perception**: what they used to think vs. now
2. **Specific takeaway**: from a reading, case, framework, or class session that
   can be identified (course ideas with no source don't count)
3. **Experiential learning**: an in-class activity, interview, or speaker, and what it taught them
4. **Next-phase priority for their venture**: a general mindset doesn't count
5. **Personal & specific**: their own interviews, venture, or background come through,
   rather than a polished generic summary

| Label | Meaning | Points off | In the spreadsheet |
|---|---|---|---|
| **Thoughtful** | Clearly meets the check | 0 | 3 |
| **Thin** | Vague, generic, or only implied | −2 | 1 |
| **Missing** | Not addressed | −2 | 1 |

**Possible AI script** is flagged for the TA to confirm by watching the video
(eyes reading a screen, flat delivery). It is never deducted automatically.
Delivery (filler words, volume) goes into the comment as coaching, not into
the score. Length outside 3–5 minutes is flagged but not penalized.

The point values live in `DEDUCTIONS` at the top of `grade.py`. What counts as
thoughtful / thin / missing lives in `rubric.md`, along with anonymized
examples graded by the TAs, which keep the AI consistent with how they grade.

## Late policy

Defined in `late.py` (times are Eastern):

- **Due** 11:59 pm Sep 23, 2026, with a one-day grace period: anything in by
  **11:59 pm Sep 24** gets full marks.
- **Anything later** is capped at **80% (32/40)**, however many days late. A late
  reflection that earned 30/40 stays at 30. One that earned 40/40 becomes 32.

Run `.venv/bin/python late.py` to see examples. Change `LATE_CAP_PCT` or
`GRACE_DEADLINE` in `late.py` to adjust it.

## Each batch

```bash
# 1. Download the videos into Videos/. File names must start with "Last, First"
#    (as Canvas does). Transcribe them; this runs locally, audio never leaves the Mac.
.venv/bin/python transcribe.py Videos

# 2. Judge the transcripts with Claude (needs an API key from console.anthropic.com)
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/python grade.py

# 3. Write Claude's points and student comments into the gradebook
#    (close it in Excel first)
.venv/bin/python gradebook.py "Reflection 1 Grades_claude new template.xlsx" --sheet "Reflections 1"
```

Each step skips work it has already done, so re-running only handles new
uploads. Use `--force` with steps 1 and 2 to redo everything.

### What you get

- `transcripts/<video>.txt`: full transcript with duration and word count
- `grades/<video>.md`: the label for each prompt with a quote as evidence, a
  comment for the student (praise first, then one or two things to improve),
  and anything the TA should double-check
- `grades/grades.csv`: one row per student
- **The gradebook itself** (the sheet named with `--sheet`): five columns are
  added to the right of the TA's columns. Re-running updates them in place.
  - **Claude Points**: 40 minus 2 for each thin or missing check
  - **Late Policy**: points removed by the 80% cap, if late
  - **Final Points**: Claude's points after the late policy; the grader's
    points when there's no video; 0 if not submitted
  - **Comment for Student**: written so students understand why they didn't
    get full marks: each deduction with its reason, then what they did well
  - **TA Notes (not for students)**: possible AI script, length, transcript
    glitches, and where Claude differs from the grader's points

  The TA's own columns are never changed. Before the first run, a copy is
  saved as `<name> (before Claude).xlsx`. The sheet needs a header row with
  `Student` in column A and columns named `Graded by`, `Grader's Assigned
  Points` and `Date Submitted`.

### Matching videos to students

Videos are matched to the roster by the name at the start of the file name.
Shortened names work: "Ortega, Nina" matches "Ortega Vidal, Nina", and
"Doe, Jane" matches "Doe, Jane Marie". A video that can't be matched is
reported as a warning, not skipped silently.

## What lives where

| Thing | Where | In git? |
|---|---|---|
| **Gradebook spreadsheet** (`.xlsx`): student roster, submission dates, length, the TA's grade for each prompt (3 = full credit), Points out of 40, and comments | Project folder, kept by the TA | **No**: all spreadsheets are git-ignored because they contain student names and grades |
| **Grading rubric**: what counts as thoughtful / thin / missing, with anonymized calibration examples | `rubric.md` | Yes |
| **Student videos, transcripts, AI feedback** | `Videos/`, `transcripts/`, `grades/` | No |

| Script | What it does |
|---|---|
| `transcribe.py` | Video → text with Whisper (mlx-whisper, on-device) |
| `grade.py` | Transcript + `rubric.md` → labels, evidence, AI-script flag, and comment, from Claude |
| `gradebook.py` | Grades + late policy → points and student comments in the gradebook |
| `late.py` | The late policy |

## Keeping the AI in line with the TAs

When a TA disagrees with a grade, add that case to the calibration examples in
`rubric.md`. Say which prompts were thoughtful, thin, or missing and why, and
use "Student E", "Student F", and so on instead of names. Worked examples
change the AI's judgment far more reliably than rewording the rules. Then run
`grade.py --force` and check the TA Notes column.

## Known quirks

- **Whisper sometimes invents text when a video ends in silence**, such as a
  phrase repeated over and over, or "you. you." The rubric tells the grader to
  ignore it, and the grade file flags it. Check the end of the video if it
  looks like real speech was lost.
- **The AI only sees the transcript.** It can't judge tone, volume, or
  confidence, and Whisper drops many "ums".

## One-time setup

Full walkthrough for a new computer: [SETUP.md](SETUP.md). Short version:

```bash
brew install ffmpeg
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
