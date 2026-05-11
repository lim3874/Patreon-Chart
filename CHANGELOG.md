# Changelog

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
