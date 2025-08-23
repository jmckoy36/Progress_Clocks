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
- **Linked Clocks timing behavior**: countdowns now fill segments proportionally across the total time (e.g., 4 segments over 4 minutes = 1 per minute).
- **Overlay display** now shows `HH:MM:SS` remaining instead of per-cycle resets.
- **Pause button removed**: Start now resumes if stopped; Stop halts all timers.
- **Overlay color selection** added; default adjusts to Light/Dark mode.
- **Serial clicks enforced**: only the current active dial can be clicked; right-click unfills in manual mode.
- **UI wording updated**: “Beep on dial complete” renamed to **“Enable Timer Alarms”** for clearer language.

### Fixed
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

