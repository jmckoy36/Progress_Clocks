# Progress_Clocks – TODOs

This file is for jotting down ideas, bugs, and enhancements before they are ready to be turned into GitHub Issues.

---

## 🐞 Bugs
- [ ] Danger Clock - Invert colors - shows black on black.
- [ ] 

---

## ✨ Features & Enhancements
### Main App
- [ ] Open the app in the same spot it was last closed
- [ ] In File Menu, add Add Danger Clock
- [ ] Auto-Save every 5 minutes silently
- [ ] Keyboard shortcuts

### Danger Clocks
- [ ] Add Save PNG button, save with current date and time
- [ ] 
- [ ] 
- [ ] 

---

## 💡 Future Ideas
- [ ] Tug-of-War Clock
- [ ] Save/load clock setups from a file
- [ ] Share/export clocks with others
- [ ] Add sound effects when a clock segment completes
- [ ] Add "Race Clock" type (multiple teams in tug-of-war style)
- [ ] Set All button: apply one time setting across all segments
- [ ] Smarter defaults for Mission Clock (start at 00:00)


## Workflow
Keep quick notes in TODO.md.
When something is ready to be “real”:
Copy it into a GitHub Issue.
Link your commits to it with Fixes #1 or Closes #1.
Keep TODO.md around for scratch ideas — no pressure to clean it up perfectly.

---

## 🔄 How to Promote TODOs to GitHub Issues

Sometimes a TODO grows into a real bug, feature, or enhancement.  
Here’s how to move it from this file into GitHub Issues:

1. **Open the repo on GitHub**  
   - Go to: https://github.com/jmckoy36/Progress_Clocks  
   - Click the **Issues** tab.

2. **Create a new issue**  
   - Click the green **New issue** button.  
   - Copy the TODO line (e.g., `- [ ] Add option to export clock data`).  
   - Paste it into the issue **title**. Add details in the **description**.

3. **Label it (optional)**  
   - On the right sidebar, add labels such as:  
     - 🐞 `bug`  
     - ✨ `enhancement`  
     - 💡 `idea`

4. **Link commits to the issue**  
   - When fixing it, reference the issue number in your commit message:  
     ```bash
     git commit -m "Fix objective labels only showing when custom names are used (Fixes #3)"
     ```
   - When pushed, GitHub automatically **closes Issue #3**.

✅ Use `TODO.md` for brainstorming & quick notes.  
✅ Use GitHub Issues for tracking progress, assigning, and closing tasks.
