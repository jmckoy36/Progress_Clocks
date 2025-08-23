# Git Workflow Cheat Sheet (Progress Clocks)

## 0) Naming
- Feature branches: `feature/<short-name>` (e.g., `feature/linked-clocks`)
- Tags: semantic versioning `vMAJOR.MINOR.PATCH` (e.g., `v2.0.0`)

---

## 1) Start a New Feature
```powershell
git switch main
git pull origin main
git switch -c feature/<short-name>
```

Work… commit as you go:
```powershell
git add .
git commit -m "Message"
git push --set-upstream origin feature/<short-name>   # (first push only)
```

---

## 2) Merge Feature into Main (command-line workflow)
Make sure feature branch has latest main (optional but recommended):
```powershell
git switch feature/<short-name>
git pull
git fetch origin
git merge origin/main      # resolve conflicts if any, then: git add <files> && git commit
git push
```

Merge into `main`:
```powershell
git switch main
git pull origin main
git merge --no-ff feature/<short-name>   # save history that this was a feature branch
git push origin main
```

(Optional) Clean up:
```powershell
git branch -d feature/<short-name>
git push origin --delete feature/<short-name>
```

---

## 3) Version Bump & Tag a Release
In `progress_clocks.py` (top-level, not in docstring):
```python
__version__ = "X.Y.Z"
```

Update notes (`GIT_NOTES.md` / `CHANGELOG.md`), then:
```powershell
git add progress_clocks.py GIT_NOTES.md CHANGELOG.md
git commit -m "Bump version to vX.Y.Z; update changelog"
git push origin main
```

Create & push tag:
```powershell
git tag -a vX.Y.Z -m "Release vX.Y.Z: <short description>"
git push origin vX.Y.Z
```

---

## 4) Start the Next Feature After a Release
```powershell
git switch main
git pull
git switch -c feature/<next-short-name>
```

---

## 5) Publish a New Branch (first time only)
```powershell
git push --set-upstream origin feature/<short-name>
```
(After this, just `git push` / `git pull`.)

---

## 6) Sync Another Machine (bring laptop/PC up to date)
```powershell
git fetch origin
git branch -a
git switch -c feature/<short-name> origin/feature/<short-name>   # if branch is new on this machine
git pull
```

---

## 7) Quick Vim-in-Merge Reminder
- Save & exit: `ESC` → `:wq` → `Enter`
- Abort merge message (don’t usually do this): `ESC` → `:q!`

---

## 8) Undo a Merge (advanced, safe on shared branches)
Find the merge commit hash:
```powershell
git log --oneline
```
Revert the merge:
```powershell
git revert -m 1 <merge_commit_hash>
git push
```


---

## 9) Updating Another PC with Work from Laptop (or vice versa)

### If the branch already exists locally:
```powershell
git switch <branch-name>
git pull
```

### If the branch is new (created on the other machine):
```powershell
git fetch origin
git switch -c <branch-name> origin/<branch-name>
git pull
```

**Summary:**  
- If branch exists → just `git pull`.  
- If branch is new → `git fetch` + `git switch -c ... origin/...` first, then `git pull`.


---

## 10) Git Dashboard Commands (Checking Your State)

### Check local branches:
```powershell
git branch
```
- Shows branches you have locally.  
- `*` marks the branch you are currently on.  

### Check all branches (local + remote):
```powershell
git branch -a
```
- Lists both your local branches and those on GitHub (`remotes/origin/...`).  
- If a branch only appears under `remotes/origin/...`, it exists on GitHub but not locally yet.  

### Check your current state:
```powershell
git status
```
- Shows which branch you are on.  
- Whether you are ahead/behind GitHub.  
- Which files are modified, staged, or ready to commit.  

**Rule of thumb:**  
- Use `git branch` to confirm what branches you have locally.  
- Use `git branch -a` to see remote ones as well.  
- Use `git status` constantly while working as your "dashboard."  


---

## 11) Save Changes (Make a Version) & Push to GitHub

### Stage files you changed
```powershell
git add .
```
- Stages **all** modified/new files in the repo.  
- To stage specific files only: `git add progress_clocks.py TEST_CHECKLIST.md`

### Commit with a clear message
```powershell
git commit -m "Short, imperative message summarizing what changed"
```
- Good examples:
  - `Fix: prevent label truncation on Danger Clock`
  - `Feat: add Linked Clocks skeleton with sync hooks`
  - `Docs: add Git workflow cheat sheet`

### Push your commits to GitHub
```powershell
git push
```
- If this is a **new branch's first push**, you may need:
```powershell
git push --set-upstream origin <branch-name>
```

**Tip:** Run `git status` before/after to confirm what’s staged, committed, and whether you’re ahead/behind the remote.

---

## 12) Check History (Commits on Current Branch)

### View a concise one-line history
```powershell
git log --oneline
```
- Shows each commit as a single line: `<short-hash> <message>`  
- Useful for quickly finding a recent commit to revert or tag.

### Show last N commits
```powershell
git log --oneline -n 10
```

### See graph of branches/merges
```powershell
git log --oneline --graph --decorate --all
```
- Adds ASCII graph, shows branch names/tags, and includes all branches.

**Note:** The flag is `--oneline` (with an **e**), not `--online`.
