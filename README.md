# Reflection Video Grader

Helps TAs grade student video reflections for an entrepreneurship course. It
transcribes each video locally, has Claude judge the reflection against a
rubric, and merges the results and the late policy into a copy of the TA
gradebook. Students answer four prompts in a 3–5 minute video:

1. How their perception of entrepreneurship has changed
2. Takeaways from readings / assigned materials
3. What they got out of in-class experiential learning
4. What they'll prioritize in the next phase of their venture

The output is a first pass for the TA to review. The TA's spreadsheet stays
the official record.

## How grading works

Every reflection starts at **40 points**. Each of the four prompts gets one label:

| Label | Meaning | Points off | In the spreadsheet |
|---|---|---|---|
| **Thoughtful** | Engages with it in their own words | 0 | 3 |
| **Thin** | Touched on, but vague or only implied | −1 | 2 |
| **Missing** | Not answered | −2 | 1 |

So Points = 40 minus what the four prompt columns fall short of 3. The bar is
deliberately generous: most honest reflections earn full marks. Delivery
(filler words, volume) goes into the comment as coaching, not into the score.
Length outside 3–5 minutes is flagged but not penalized.

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

# 3. Merge AI grades + late policy into a copy of the gradebook
#    (close the review copy in Excel first; this overwrites it)
.venv/bin/python gradebook.py "Reflection 1 Grades_claude.xlsx"
```

Each step skips work it has already done, so re-running only handles new
uploads. Use `--force` with steps 1 and 2 to redo everything.

### What you get

- `transcripts/<video>.txt`: full transcript with duration and word count
- `grades/<video>.md`: the label for each prompt with a quote as evidence, a
  comment for the student (praise first, then one or two things to improve),
  and anything the TA should double-check
- `grades/grades.csv`: one row per student
- `<gradebook> - AI review.xlsx`: a copy of the TA's spreadsheet with extra
  columns to the right: AI score per prompt (same 3 / 2 / 1 scale), AI points,
  days late, late deduction, final points, what the final is based on, where
  the TA and the AI disagree, and AI notes. Blank Length cells are filled in
  from the video. Nothing else in the TA's columns is changed.

**Final points** use the TA's Points when they're filled in, otherwise the
AI's. Students marked "NOT Submitted" get 0.

### Matching videos to students

Videos are matched to the roster by the name at the start of the file name.
Shortened names work: "Ortega, Nina" matches "Ortega Vidal, Nina", and
"Doe, Jane" matches "Doe, Jane Marie". A video that can't be matched is
reported as a warning, not skipped silently.

## What lives where

| Thing | Where | In git? |
|---|---|---|
| **Gradebook spreadsheet** (`.xlsx`): student roster, submission dates, length, the TA's grade for each prompt (3 / 2 / 1), Points out of 40, and comments | Project folder, kept by the TA | **No**: all spreadsheets are git-ignored because they contain student names and grades |
| **Grading rubric**: what counts as thoughtful / thin / missing, with anonymized calibration examples | `rubric.md` | Yes |
| **Student videos, transcripts, AI feedback** | `Videos/`, `transcripts/`, `grades/` | No |

| Script | What it does |
|---|---|
| `transcribe.py` | Video → text with Whisper (mlx-whisper, on-device) |
| `grade.py` | Transcript + `rubric.md` → labels, evidence, and comment, from Claude |
| `gradebook.py` | AI grades + late policy → review copy of the gradebook |
| `late.py` | The late policy |

## Keeping the AI in line with the TAs

When a TA disagrees with a grade, add that case to the calibration examples in
`rubric.md`. Say which prompts were thoughtful, thin, or missing and why, and
use "Student E", "Student F", and so on instead of names. Worked examples
change the AI's judgment far more reliably than rewording the rules. Then run
`grade.py --force` and check the "TA vs AI" column.

## Known quirks

- **Whisper sometimes invents text when a video ends in silence**, such as a
  phrase repeated over and over, or "you. you." The rubric tells the grader to
  ignore it, and the grade file flags it. Check the end of the video if it
  looks like real speech was lost.
- **The AI only sees the transcript.** It can't judge tone, volume, or
  confidence, and Whisper drops many "ums".

## One-time setup (already done on this machine)

```bash
brew install ffmpeg
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
