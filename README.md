# Reflection Video Grader

Turns student reflection videos into transcripts, then scores each one against
`rubric.md` (4 prompts, 40 points; each prompt is judged thoughtful / thin / missing and deductions come from `DEDUCTIONS` at the top of `grade.py`).

## Each batch

```bash
# 1. Put the new .mov files in a folder, then transcribe them (runs locally; audio never leaves the Mac)
.venv/bin/python transcribe.py path/to/videos

# 2. Score the transcripts with Claude (needs an API key from console.anthropic.com)
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/python grade.py
```

Output:
- `transcripts/<video>.txt`: full transcript with duration and word count
- `grades/<video>.md`: per-criterion score, quoted evidence, a comment you can give the student, and things to double-check
- `grades/grades.csv`: one row per student, for the gradebook

Both scripts skip files they've already processed, so re-running only handles
new uploads. Use `--force` to redo everything.

## Changing what counts

Edit `rubric.md`. `grade.py` sends it to Claude as the grading instructions.

## One-time setup (already done on this machine)

```bash
brew install ffmpeg
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
