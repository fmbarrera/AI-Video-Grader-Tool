# Setting up the grader on your own computer

A step-by-step guide for a TA running this for the first time, on **Windows**
(e.g. a Dell) or a **Mac**. Setup takes about 15 minutes, plus a one-time
download of about 1.5 GB for the speech-to-text model.

- [What you need](#what-you-need)
- [Choosing how to grade](#choosing-how-to-grade)
- [Windows setup](#windows-setup)
- [Mac setup](#mac-setup)
- [Grading a batch](#grading-a-batch)
- [Getting updates](#getting-updates)
- [If something goes wrong](#if-something-goes-wrong)

## What you need

- **A Windows 10/11 PC or a Mac.** Both work. Transcription is fastest on
  Apple Silicon Macs (about 15 seconds per video). On a Windows laptop expect
  roughly 1–3 minutes per video.
- **Access to this GitHub repo.** It's private, so the owner has to add you as
  a collaborator (Settings → Collaborators). Accept the email invite.
- **One way to run the grading step**, either a Claude subscription or an
  Anthropic API key. See [Choosing how to grade](#choosing-how-to-grade) below.
  Transcription and the spreadsheet step need neither: they're free and run on
  your own computer, so student audio is never uploaded.
- **The student files, sent to you separately.** The videos and the gradebook
  spreadsheet are deliberately *not* in GitHub because they contain student
  names and grades. Get them from Canvas or from the other TA.

### Choosing how to grade

Grading (step 2) is the only part that needs AI. It sends each **transcript
text** (never the video or audio) to Claude, together with `rubric.md`. Pick
one option:

| | **Option A: Claude Code** | **Option B: API key** |
|---|---|---|
| What you need | A paid Claude plan (Pro, Max, Team, or Enterprise) and Claude Code installed | An Anthropic API key with credits |
| Extra cost | None beyond your plan (counts toward its usage limits) | About 5 cents per video (~$3–4 per class) |
| How it runs | You paste one prompt into Claude Code and approve its steps | Fully automatic: `grade.py` |

Both use the same `rubric.md` and write the same files, so the results look
the same either way.

**Option A: Claude Code.** Install it by following the official guide at
https://code.claude.com/docs/en/setup and sign in with your Claude account.
Nothing else is needed. Skip "Save your API key" in the setup below.

**Option B: API key.** You need:

- **An Anthropic API key**: a long string starting with `sk-ant-api03-`.
  Create one at **https://console.anthropic.com** → sign in → **API Keys** →
  **Create Key**. It's shown only once, so copy it right away.
- **Billing on that Console account.** API usage is prepaid: go to
  **Settings → Billing** and add credits ($5 is plenty to start).

A Claude.ai subscription is **not** an API key and doesn't include API
credits. No OpenAI, Google, or Hugging Face key is needed for anything.
`grade.py` uses Claude Opus 5.5 (`claude-opus-5-5`). You can see exact
spending under **Usage** in the Console. The simplest setup is for each TA
to create their own key. Never send a key by email or chat, and never put it
in a file inside this folder.

## Windows setup

Open **PowerShell**: press the Windows key, type "PowerShell", press Enter.
Run each command below, one at a time.

**1. Install the tools.** `winget` comes with Windows 10/11. Accept any
prompts.

```powershell
winget install --id Gyan.FFmpeg -e
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
winget install --id GitHub.cli -e
```

**Close PowerShell and open a new one** so it picks up the new programs.

**2. Download the code.**

```powershell
gh auth login        # choose GitHub.com → HTTPS → "Login with a web browser"
cd $HOME\Documents
gh repo clone fmbarrera/Video-Transcript-Generator
cd Video-Transcript-Generator
```

**3. Set up Python.**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

**4. Save your API key (Option B only).** Keep it private. Don't put it in
any file in this folder, and don't share it in chat.

```powershell
setx ANTHROPIC_API_KEY "sk-ant-PASTE-YOUR-KEY-HERE"
```

Close PowerShell and open a new one so the key takes effect. Then go to
[Grading a batch](#grading-a-batch). On Windows, the commands there start with
`.venv\Scripts\python` instead of `.venv/bin/python`.

## Mac setup

Open **Terminal** (press ⌘-Space, type "Terminal", press Enter) and run these
one at a time.

**1. Install the tools.** Install Homebrew if you don't have it. It asks for
your Mac password; nothing appears as you type, which is normal.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

When it finishes, it prints two or three "Next steps" commands that start with
`echo` and `eval`. Run those too, then close and reopen Terminal. Then:

```bash
brew install ffmpeg python@3.12 git gh
```

**2. Download the code.**

```bash
gh auth login        # choose GitHub.com → HTTPS → "Login with a web browser"
cd ~/Documents
gh repo clone fmbarrera/Video-Transcript-Generator
cd Video-Transcript-Generator
```

**3. Set up Python.**

```bash
"$(brew --prefix)/bin/python3.12" -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**4. Save your API key (Option B only).** Keep it private, as above.

```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-PASTE-YOUR-KEY-HERE' >> ~/.zshrc
source ~/.zshrc
```

## Grading a batch

**Add the student files** inside the `Video-Transcript-Generator` folder:

- Create a folder named **`Videos`** and put the student videos in it. Each file
  name must start with the student's name as **"Last, First"** (Canvas
  downloads already do this), e.g. `Doe, Jane Movie on 9-19-26.mov`.
- Put the **gradebook spreadsheet** (`.xlsx`) directly in the folder.

Git ignores both, so they can't be uploaded by accident.

**Close the spreadsheet in Excel**, then run the three steps from the
`Video-Transcript-Generator` folder:

Windows (PowerShell):

```powershell
cd $HOME\Documents\Video-Transcript-Generator
.venv\Scripts\python transcribe.py Videos          # 1. videos -> transcripts (local)
.venv\Scripts\python grade.py                      # 2. transcripts -> grades (Option B; see below for Option A)
.venv\Scripts\python gradebook.py "Reflection 1 Grades_claude new template.xlsx" --sheet "Reflections 1"   # 3. -> spreadsheet
```

Mac (Terminal):

```bash
cd ~/Documents/Video-Transcript-Generator
.venv/bin/python transcribe.py Videos
.venv/bin/python grade.py
.venv/bin/python gradebook.py "Reflection 1 Grades_claude new template.xlsx" --sheet "Reflections 1"
```

Use your spreadsheet's actual file name and tab name in step 3.

**Step 2 with Option A (Claude Code):** skip the `grade.py` line. After step 1,
open Claude Code in the `Video-Transcript-Generator` folder (`cd` into it and
type `claude`), paste the prompt below, and approve the steps it asks to run.
Then run step 3 as usual.

```text
Grade the student reflection transcripts in this folder. Read rubric.md and
follow it exactly; don't change rubric.md or any code. For every transcript in
transcripts/ that has no matching file in grades/, judge the five checks, and
decide whether there are strong signs of an AI-written script. Save each grade
in this project's own format: build a grade.Grade object and write it with
grade.write_feedback(Path("grades") / f"{stem}.md", stem, minutes, g), getting
minutes from grade.read_transcript. Write each rationale to the student, saying
exactly what was missing for any thin or missing check. When you're done, run
grade.rebuild_csv(Path("grades")) and show me a table of each student, their
points, and why points came off.
``` The first run
of step 1 downloads the speech model, so it takes longer. Each step skips
videos it has already done, so you can add new videos and run all three again.
Then open the spreadsheet and review the new columns. See the README for what
each column means and how grading works.

If transcription is too slow on your computer, add `--model small` to step 1.
It's several times faster and a little less accurate.

## Getting updates

When the other TA changes the rubric or the code, run this from the
`Video-Transcript-Generator` folder (on Windows, use
`.venv\Scripts\python -m pip` in place of `.venv/bin/pip`):

```bash
git pull
.venv/bin/pip install -r requirements.txt
```

To regrade everything with the updated rubric, run `grade.py --force` (Option B)
or delete the files in `grades/` and paste the prompt again (Option A), then
run step 3 again.

## If something goes wrong

| Message | Fix |
|---|---|
| `'ffmpeg' is not recognized` (Windows) / `No such file or directory: ffmpeg` | Install ffmpeg (step 1), then open a **new** PowerShell / Terminal window |
| `'py' is not recognized` (Windows) | Install Python (step 1), then open a new PowerShell window |
| `command not found: brew` (Mac) | Run the "Next steps" lines Homebrew printed, then reopen Terminal |
| `authentication_error` / `API key is invalid` | Option B: re-save the key (step 4), then open a new window. Or use Option A |
| `no roster match for …` | Rename the video so it starts with the student's "Last, First" as it appears in the spreadsheet |
| `Couldn't find a header row` | The tab needs a header row with `Student` in column A. Check the `--sheet` name |
| `PermissionError` when saving the spreadsheet | Close it in Excel and run step 3 again |
