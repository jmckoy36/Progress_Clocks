# Teach DangerClockFrame how to adapt the default fill
# Inside DangerClockFrame, add this method (anywhere in the class):

def _on_theme_changed(self):
    """
    When toggling Dark Mode:
    - If fill is still the default (black), switch to white for visibility.
    - When switching back to Light Mode:
      If fill is white (the dark-mode default), switch back to black.
    Custom colors are left untouched.
    """
    fill = (self.fill_color or "").lower()

    if self.inverted.get():
        # Dark Mode ON: background becomes black
        if fill in ("#000000", "black"):
            self.fill_color = "#FFFFFF"
            try:
                self.fill_preview.configure(bg=self.fill_color)
            except Exception:
                pass
    else:
        # Dark Mode OFF: background becomes white
        if fill in ("#ffffff", "white"):
            self.fill_color = "#000000"
            try:
                self.fill_preview.configure(bg=self.fill_color)
            except Exception:
                pass

    self.draw()

# This overrides the base hook so the Danger clock updates its default color only when it's still the default.
# If the user chose a custom color (e.g., red), we won't touch it.
# If you want this same behavior on future clocks, just copy that _on_theme_changed override into each clock class
# and adjust any color widgets (like fill_preview) they use.