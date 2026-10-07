# Setting up the grader on your own computer

A step-by-step guide for a TA running this for the first time. It takes about
15 minutes, plus a one-time download of about 1.5 GB for the speech-to-text
model.

## What you need

- **A Mac with Apple Silicon** (M1, M2, M3, or newer). To check: Apple menu →
  About This Mac → "Chip" should say Apple M-something. The transcription step
  uses a version of Whisper that only runs on these Macs. On Windows or an
  Intel Mac, ask the repo owner first.
- **Access to this GitHub repo.** It's private, so the owner has to add you as
  a collaborator (Settings → Collaborators). Accept the email invite.
- **An Anthropic API key** for the grading step. Ask the repo owner for one or
  create your own at https://console.anthropic.com (API Keys → Create Key).
  Grading costs a few cents per video. Transcription is free and runs on your Mac.
- **The student files, sent to you separately.** The videos and the gradebook
  spreadsheet are deliberately *not* in GitHub because they contain student
  names and grades. Get them from Canvas or from the other TA.

## 1. Install the tools (one time)

Open **Terminal** (press ⌘-Space, type "Terminal", press Enter) and run these
one at a time.

Install Homebrew, the Mac package manager, if you don't have it. It asks for
your Mac password; nothing appears as you type, which is normal.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

When it finishes, it prints two or three "Next steps" commands that start with
`echo` and `eval`. Copy and run those too, then close and reopen Terminal.

Then install ffmpeg (reads the audio out of videos), Python, and git:

```bash
brew install ffmpeg python@3.12 git gh
```

## 2. Download the code

```bash
gh auth login        # choose GitHub.com → HTTPS → "Login with a web browser"
cd ~/Documents
gh repo clone fmbarrera/Video-Transcript-Generator
cd Video-Transcript-Generator
```

## 3. Set up Python (one time)

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 4. Add your API key (one time)

So you don't have to paste it every time, save it in your shell profile:

```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-PASTE-YOUR-KEY-HERE' >> ~/.zshrc
source ~/.zshrc
```

Keep the key private. Don't put it in any file inside this folder, and don't
share it in chat.

## 5. Add the student files

Inside the `Video-Transcript-Generator` folder:

- Create a folder named **`Videos`** and put the student videos in it. Each file
  name must start with the student's name as **"Last, First"** (Canvas
  downloads already do this), e.g. `Doe, Jane Movie on 9-19-26.mov`.
- Put the **gradebook spreadsheet** (`.xlsx`) directly in the folder.

Git ignores both, so they can't be uploaded by accident.

## 6. Grade a batch

Close the spreadsheet in Excel first, then run the three steps from the
`Video-Transcript-Generator` folder in Terminal:

```bash
cd ~/Documents/Video-Transcript-Generator

# 1. Videos → transcripts (local; the first run downloads the speech model)
.venv/bin/python transcribe.py Videos

# 2. Transcripts → grades (uses the API key)
.venv/bin/python grade.py

# 3. Grades → points and student comments in the spreadsheet
.venv/bin/python gradebook.py "Reflection 1 Grades_claude new template.xlsx" --sheet "Reflections 1"
```

Use your spreadsheet's actual file name and tab name in step 3. Each step
skips videos it has already done, so you can add new videos and run all three
again. Then open the spreadsheet and review the new columns. See the README for
what each column means and how grading works.

## 7. Getting updates

When the other TA changes the rubric or the code:

```bash
cd ~/Documents/Video-Transcript-Generator
git pull
.venv/bin/pip install -r requirements.txt
```

To regrade everything with the updated rubric, run `grade.py --force`, then
step 3 again.

## If something goes wrong

| Message | Fix |
|---|---|
| `command not found: brew` | Run the "Next steps" lines Homebrew printed in step 1, then reopen Terminal |
| `No such file or directory: ffmpeg` | `brew install ffmpeg` |
| `authentication_error` / `API key is invalid` | Check the key in `~/.zshrc`, then `source ~/.zshrc` |
| `no roster match for …` | Rename the video so it starts with the student's "Last, First" as it appears in the spreadsheet |
| `Couldn't find a header row` | The tab needs a header row with `Student` in column A. Check the `--sheet` name |
| `PermissionError` when saving the spreadsheet | Close it in Excel and run step 3 again |
| `mlx` / `Metal` errors in step 1 | This Mac isn't Apple Silicon (see "What you need") |
