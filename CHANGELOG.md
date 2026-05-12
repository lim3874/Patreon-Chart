# Changelog

## 2.6.2 - 2026-05-12

### Fixed

- Increase sparse monthly chart label spacing so `YYYY-MM` labels do not overlap.

## 2.6.1 - 2026-05-12

### Fixed

- Center period chart bars when the selected group has only a few buckets, such as monthly charts with two months.

## 2.6.0 - 2026-05-12

### Changed

- Change the `재구독` period chart to show only rejoined-member counts instead of stacking first pledges with rejoins.
- Draw multi-series period charts as separate category bars instead of stacked total bars.

## 2.5.0 - 2026-05-12

### Added

- Add clickable sorting to Patreon API table headers.
- Toggle Patreon API table columns between ascending and descending order with repeated header clicks.
- Sort Patreon API amount and date columns using numeric/date values instead of plain text.

## 2.4.0 - 2026-05-12

### Added

- Add animated loading text to the `Gmail에서 불러오기` button while Gmail import is running.
- Add the same loading feedback to the Patreon current-member import button.

### Changed

- Restore import button labels and enabled state through one shared loading-state path after background work finishes.

## 2.3.0 - 2026-05-12

### Added

- Add `멤버순` and `티어순` sorting controls to the tier distribution chart.
- Persist the selected tier distribution sort mode in local app settings.

### Changed

- Show the actual selected date span on the `전체 회원` summary card instead of the generic `선택 기간` text.
- Move `티어 1`, `티어 2`, and `티어 3` summary cards to the second row.
- Remove the `확인 필요` summary card from the top summary area.

## 2.2.1 - 2026-05-12

### Fixed

- Widen the sidebar header area so the Korean `크리에이터 분석` title no longer clips on high-DPI displays.
- Use Malgun Gothic for the Korean sidebar title and subtitle.
- Reduce header padding around the sidebar logo to give the Korean title more usable width.

## 2.2.0 - 2026-05-12

### Added

- Localize the desktop dashboard UI into Korean.
- Add Korean labels for the sidebar, top action bar, summary cards, period chart controls, filters, date range dialog, and Patreon API workspace.
- Display Gmail member table values in Korean, including 신규 가입, 재구독, 티어, 청구 주기, 결제 상태, and 확인 필요.
- Display Patreon API member table statuses and common tier/payment values in Korean.

### Changed

- Keep legacy English setting values compatible while saving and showing the Korean UI labels going forward.

## 2.1.2 - 2026-05-12

### Fixed

- Replace the dark tile app icon with a cleaner transparent chart mark for the title bar and taskbar.
- Replace the sidebar `CA` placeholder with a small chart logo.
- Widen the sidebar and reduce the sidebar title size so `Creator Analytics` no longer clips on high-DPI displays.

## 2.1.1 - 2026-05-12

### Fixed

- Enable Windows per-monitor DPI awareness before Tk creates the app window so text is rendered sharply on 4K/high-DPI displays.
- Apply Tk font scaling from the active monitor DPI instead of relying on Windows bitmap scaling.
- Replace the taskbar icon with a high-contrast v3 chart icon that includes explicit 16, 24, 32, 48, 64, 128, and 256 px frames.
- Update the app icon references to use the new high-DPI icon asset.

## 2.1.0 - 2026-05-12

### Added

- Add rejoin detection for members who appear in Patreon new-member mail more than once.
- Add a `REJOINED` summary metric card.
- Add a `Rejoins` period chart dimension that compares first pledges and rejoined pledges over time.
- Mark repeated 가입 records as `Rejoin` in the List table.
- Add a `Status: Rejoined` filter to quickly inspect likely canceled-and-resubscribed members.

### Changed

- Rejoin detection uses the full Gmail history as context, then counts only rows inside the selected date range.

## 2.0.0 - 2026-05-12

### Changed

- Rebuild the desktop UI around the new Creator Analytics design:
  - left sidebar navigation
  - fixed top action bar
  - card-based summary metrics
  - modern dark table view
  - segmented period chart controls
  - redesigned Patreon API workspace
- Replace the old notebook-tab layout with sidebar page navigation for Summary, Period, List, and Patreon API.
- Convert the main dashboard labels and table headers to the Analytics Engine layout language.
- Use a dark-only interface so the app always matches the supplied dashboard design.

### Added

- Add member search, tier filtering, and status filtering to the List view toolbar.
- Add top-bar shortcuts for date range, Gmail import, settings, output folder, and Patreon API settings.

## 1.2.2 - 2026-05-12

### Fixed

- Replace the app icon with a small-size-optimized chart icon so it stays clear on the Windows taskbar.
- Package explicit 16, 24, 32, 48, 64, 128, and 256 px frames in the ICO file instead of relying on a single downscaled source image.
- Use the ICO directly on Windows so Tk does not downscale the large PNG for the taskbar icon.

## 1.2.1 - 2026-05-12

### Added

- Add a chart-style app icon in PNG and ICO formats.
- Apply the chart icon to the desktop window and Windows taskbar at runtime.

### Changed

- Update Windows app identity so the taskbar uses the app-specific icon instead of the default Python/Tk icon.

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
