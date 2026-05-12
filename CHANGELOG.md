# Changelog

## 1.2.0 - 2026-05-12

### Changed

- Redesign the desktop dashboard with a Patreon-style dark layout:
  - stronger dark background
  - beige panel borders
  - square tab styling
  - dark rectangular action buttons
  - denser Patreon API member table view
- Make dark mode the default for new local settings so the first launch matches the dashboard design.
- Use Korean-friendly UI fonts across labels, buttons, charts, and tables.

### Fixed

- Improve dark-mode readability for combobox dropdowns, readonly date fields, tree headings, and chart labels.
- Keep chart category buttons readable in both selected and unselected dark-mode states.

## 1.1.1 - 2026-05-12

### Fixed

- Improve dark-mode contrast for buttons, comboboxes, and readonly date fields.
- Keep preset date fields readable in dark mode by using readonly state instead of disabled state.

## 1.1.0 - 2026-05-12

### Added

- Add Patreon-style date range preset dropdown:
  - last 24 hours
  - last 30 days
  - last 6 months
  - last 12 months
  - all time
  - custom
- Add Patreon-style insight controls for the period chart:
  - all
  - membership tier
  - billing cycle
  - payment status
  - paid conversion path
- Add daily/weekly/monthly chart granularity controls with persistent settings.
- Add card-style chart summaries for each selected insight category.
- Add member table columns for event type, membership tier, billing cycle, payment status, and paid conversion path.

## 1.0.1 - 2026-05-12

### Fixed

- Persist the dark mode toggle in `app_settings.json` so the GUI keeps the selected theme after restart.

## 1.0.0 - 2026-05-11

Initial release.

### Added

- Gmail API integration for collecting Patreon new-member notification emails.
- Currency and amount parser for Patreon membership emails.
- Tier classification for USD 2.99, 4.99, 9.99, and 29.99 memberships.
- Local price mapping with exchange-rate fallback for non-USD payments.
- CSV, Excel, and HTML report export.
- Windows desktop launcher script.
- Tkinter desktop dashboard with light/dark mode.
- Summary, period chart, and member list tabs.
- Date range filters and daily/weekly/monthly period charts.
- Patreon API integration tab for current member state, tiers, and payment status.
- Local Patreon API credential storage through the app settings dialog.
- Unit tests for core Patreon email parsing cases.

### Security

- Ignored local OAuth/token/config/output files by default.
- Added example credential/config files without secrets.
