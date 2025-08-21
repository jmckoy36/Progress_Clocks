# Git Quick Notes

## Initialize (only once per project)
git init

## Save changes (make a version)
Stage all files and save them with a message:

git add .
git commit -m "Describe change here"
### To add to GitHub
git push

## Check history
See a quick list of your commits:
git log --oneline


## Roll back to a previous version
*Careful with this — ask ChatGPT if unsure!*
git checkout <commit_id>

(Use the commit ID from `git log --oneline`)

## Tips
- Commit often, even small changes.  
- Use clear messages like `"Added Notes feature to Tug-of-War clock"`.  
- Each commit is a “restore point” you can go back to.  


# GitHub Workflow for Solo Projects (Progress_Clocks)

This is my quick guide for using Git + GitHub day to day.

---

## Daily Flow

1) Pull latest (in case I worked from another PC):
```bash
git pull
```

2) Work in PyCharm → save files.

3) Stage and commit changes:
```bash
git add .
git commit -m "Describe what changed (e.g., Add Race Clock tab with color pickers)"
```

4) Push to GitHub:
```bash
git push
```

---

## Feature Branches (safe experiments)

Create a new branch for a feature:
```bash
git checkout -b race-clocks
```

Work → commit → push:
```bash
git add .
git commit -m "Race Clocks: basic grid and controls"
git push -u origin race-clocks
```

Later, merge back to `main` using a Pull Request (good for reviewing diffs before merge):

- On GitHub, open the repo → switch to the branch → **Compare & pull request** → **Create pull request** → **Merge**.
- Update local `main`:
```bash
git checkout main
git pull
```

Delete the feature branch if done:
```bash
git branch -d race-clocks
git push origin --delete race-clocks
```

---

## Issues (my to-do list)

Create Issues on GitHub to track tasks/bugs (e.g., “Race Clock PNG export”, “Autosave indicator”).
Close them when done and reference the commit/PR if helpful.

---

## Tags & Releases (mark milestones)

Create a version tag:
```bash
git tag -a v1.0.0 -m "First stable: Danger + Tug-of-War + Notes + Autosave"
git push --tags
```

(Optional) On GitHub → **Releases** → **Draft a new release** and attach notes/files.

---

## Working on Multiple Computers

**First time on a new machine:**
```bash
git clone git@github.com:jmckoy36/Progress_Clocks.git   # SSH
# or: git clone https://github.com/jmckoy36/Progress_Clocks.git
cd Progress_Clocks
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows PowerShell
pip install -r requirements.txt   # if present; otherwise: pip install pillow
```

**Every session on any machine:**
```bash
git pull
# ...work...
git add .
git commit -m "Change description"
git push
```

---

## Useful One-Timers (already set or good to know)

Set upstream on first push to `main`:
```bash
git push --set-upstream origin main
```

Auto-set upstream for new branches:
```bash
git config --global push.autoSetupRemote true
```

Normalize line endings on Windows (optional, recommended):
```bash
git config --global core.autocrlf true
```

---

## Authentication Notes

**SSH (recommended across personal machines):**
- Generate once per machine:
  ```bash
  ssh-keygen -t ed25519 -C "label-or-email"
  ```
- Copy public key to GitHub → **Settings → SSH and GPG keys**.
- Use SSH remote:
  ```bash
  git remote set-url origin git@github.com:jmckoy36/Progress_Clocks.git
  ```

**HTTPS with token (PAT):**
- Create token with `repo` scope in GitHub settings.
- First push will ask for username + token (as password).

---

## Viewing History / Rolling Back (quick)

View condensed history:
```bash
git log --oneline --graph --decorate --all
```

Restore a single file from a previous commit:
```bash
git restore --source=<commit_id> path/to/file.py
```

Temporarily check out an old version (read-only “detached HEAD”):
```bash
git checkout <commit_id>
# return to main:
git checkout main
```

Safely undo a specific commit (creates a new revert commit):
```bash
git revert <commit_id>
```

---

## .gitignore (keep history clean)

Typical entries for this project:
```
__pycache__/
*.pyc
*.pyo
*.DS_Store
.env
.venv/
venv/
.idea/
.vscode/
session*.json
*.png
```
(If I want session files or PNG exports versioned, remove those lines.)

---

## README Checklist (optional)

- Project description + screenshot(s)
- How to run:
  ```
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  python app.py
  ```
- Features: Danger Clock, Tug-of-War, Notes, Autosave, PNG export
- Keyboard shortcuts (if any)
- Release notes / changelog link

---

## Quick Troubleshooting

- **“no upstream branch”** → run:
  ```bash
  git push --set-upstream origin <branch>
  ```
- **Auth failed** → verify SSH keys in GitHub or update token; check remote:
  ```bash
  git remote -v
  ```
- **Merge conflict** → in PyCharm: `VCS → Git → Resolve Conflicts…`

---

You said:
Yes, make it something I can add to my GIT_NOTES.md for future reference.
ChatGPT said:

Got it 👍 — here’s a clean, ready-to-drop section for your GIT_NOTES.md that covers switching between branches and keeping both main and feature branches updated across PCs.

## Working with Multiple Branches (main + feature branches)

### Switch Branches
- Switch to `main`:
  ```bash
  git switch main


Switch to a feature branch (example: feature/racing-clocks):

git switch feature/racing-clocks

Create Local Tracking Branch for a Remote Feature Branch

If the branch exists on GitHub but not locally:

git switch -c feature/racing-clocks --track origin/feature/racing-clocks

Keep Branches Updated

Always fetch updates from GitHub:

git fetch --all --prune


Fast-forward your branch to match GitHub:

git pull --ff-only

Verify Status

Check which branch you are on and sync status:

git status


See last few commits:

git log --oneline -5

Notes

main should always be stable and in sync with GitHub.

Do new development or experiments on feature branches.

Once work is ready, merge or create a Pull Request from the feature branch into main.

Use --ff-only to avoid accidental merge commits when updating from GitHub.


---

Would you like me to also expand this note with a short **“workflow example”** (like: *devel



