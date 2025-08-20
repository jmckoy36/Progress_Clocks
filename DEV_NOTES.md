# Developer Notes for Progress Clocks

## Reusable Patterns

### Dark Mode Toggle Hook
- Checkbox label: "Dark Mode"
- Base hook method `_on_theme_changed(self)` in `ClockBase`
- Override in child clocks to auto-adjust fill color

**Base Implementation (ClockBase)**
```python
def _on_theme_changed(self):
    """Hook for subclasses when theme flips; default just redraws."""
    self.draw()


# DangerClockFrame Override
def _on_theme_changed(self):
    fill = (self.fill_color or "").lower()
    if self.inverted.get():
        if fill in ("#000000", "black"):
            self.fill_color = "#FFFFFF"
            self.fill_preview.configure(bg=self.fill_color)
    else:
        if fill in ("#ffffff", "white"):
            self.fill_color = "#000000"
            self.fill_preview.configure(bg=self.fill_color)
    self.draw()

---

## 2. Create a `snippets/` folder
- Inside, keep small `.py` files for copy/paste code.  
- For example:  
  - `snippets/dark_mode_hook.py`  
  - `snippets/timer_pattern.py`  
  - `snippets/notes_modal.py`  

---

## 3. GitHub Labels / Issues
Since you mentioned GitHub earlier:  
- You can also file this as an **enhancement** issue:  
  - Title: *Add reusable Dark Mode hook for clocks*  
  - Description: Paste the snippet.  
- That way, it’s searchable in your repo history and easy to copy later.  

---

