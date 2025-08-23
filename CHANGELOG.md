# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]
- Placeholder for upcoming changes.

---

## [v2.1.0] - 2025-08-23

### Added
- App now remembers last window size and which monitor it was on; on next launch it reopens centered on that monitor 
   instead of defaulting to the primary screen.
- **Settings dialogs** for:
  - Linked Clocks: manage Dark Mode, Show Countdown Overlay, Enable Timer Alarms.
  - Racing Clocks: Dark Mode toggle.
  - Danger Clocks: Dark Mode toggle.
- **"Clear All" button** in Edit Segment Labels dialog to reset all labels at once.
- **Prompt on Reset/Reset All** asking if labels should be cleared.
- **Option to reset timers** to `00:00:00` when performing Reset All on Linked Clocks.
- **Responsive dial layout**: adjusts to window size, preventing clocks from being cut off.
- **Inline note** under per-dial timer entries: “ⓘ fills segments evenly over total time.”

### Changed
- Danger Clocks: Settings button moved to the tab’s top bar for consistency.
- Racing Clocks: Removed per‑dial Settings buttons; use the tab‑level **Settings** dialog only.
- Linked Clocks: Removed per‑dial Settings; consolidated options into the tab‑level **Settings** dialog.  
- Linked Clocks: “Show Countdown Overlay” now defaults to **unchecked** on launch.
- Linked Clocks: “Enable Timer Alarms” checkbox now starts **unchecked** with no indeterminate state.
- Linked Clocks: Reverted the completion sound to the original single “ding”.
- Linked Clocks: Shifted **Start**/**Stop** controls left so they are not clipped on narrower windows.
- **Edit Segment Labels** now shows Segment numbers starting at **1** instead of 0 for clarity.
- **Edit Labels dialog** auto-sizes to fit all segment entries and centers over the app window.
- **Linked Clocks timing behavior**: countdowns now fill segments proportionally across the total time (e.g., 4 segments over 4 minutes = 1 per minute).
- **Overlay display** now shows `HH:MM:SS` remaining instead of per-cycle resets.
- **Pause button removed**: Start now resumes if stopped; Stop halts all timers.
- **Overlay color selection** added; default adjusts to Light/Dark mode.
- **Serial clicks enforced**: only the current active dial can be clicked; right-click unfills in manual mode.
- **UI wording updated**: “Beep on dial complete” renamed to **“Enable Timer Alarms”** for clearer language.

### Fixed
- **Racing Clocks**: Reset All now prompts the user whether to also clear segment labels.
- **Danger & Racing Clocks**: Double-clicking a segment now opens the label editor without also filling the segment.
- **UI clipping issues** when window not maximized:
  - Dark Mode label truncation.
  - Overlay/Beep checkboxes cut off.
  - Start button tooltip overlap.
- **Sequential clicks bug**: prevented filling later dials before the previous one is complete.
- **Overlay/Beep default states**: both now start unchecked (no black square artifacts).
- **Timer entry parsing**: supports `SS`, `MM:SS`, `HH:MM:SS`.
- **Timer entry focus bug**: clicking outside the entry commits the typed value.
- **Timed dial completion alarm**: now consistently triggers as expected.
- **Duplicate “Clock Name” field** in Danger Clock UI removed.

### Notes
- No data format changes; session files remain compatible with 2.1.0.
- 
---

## [v2.0.0] - 2025-08-21

### Added
- **Linked Clocks** tab introduced (up to 6 clocks, manual or timer-based).
- **Master Start/Stop controls** for linked series.
- **Reset All button**.
- **Per-dial editable names** and Notes button for tabs and clocks.
- **Overlay countdown** (digital format).
- **Fill color selector** per clock.
- **Session save/load** for all clocks.

