# Changelog

## 2.13.5 - 2026-05-15

### Fixed

- Reduce restore flicker for the custom Windows title bar by re-enabling borderless chrome while the app is still minimized instead of after the window becomes visible again.
- Hide any active Patreon column drag preview before minimizing the app.

## 2.13.4 - 2026-05-15

### Fixed

- Reduce Patreon API column drag lag by moving the preview back to a reused lightweight popup instead of repainting it inside the table window.
- Prevent the drag preview from flashing at its default position before it is placed under the cursor.

## 2.13.3 - 2026-05-15

### Fixed

- Smooth Patreon API column drag previews by reusing the preview widget instead of recreating it for every drag.
- Coalesce preview movement with Tk idle frames so rapid mouse events update to the latest position without extra repaint work.

## 2.13.2 - 2026-05-15

### Fixed

- Make Patreon API column drag previews smoother by using a lightweight in-app overlay instead of moving a separate popup window on every mouse event.

## 2.13.1 - 2026-05-15

### Fixed

- Center the Patreon API column drag preview directly under the mouse cursor instead of offsetting it to the lower right.

## 2.13.0 - 2026-05-15

### Added

- Add an Excel-like floating preview while dragging Patreon API table column headers.

### Changed

- Patreon API column header clicks now sort on release, so a held click can still become a drag without triggering an early sort.
- Column drag cleanup now clears the floating preview on drop or cancel.

## 2.12.1 - 2026-05-15

### Changed

- Remove the duplicate `Discord 봇 설정` button from the Patreon API toolbar now that Discord bot credentials are managed from the main settings dialog.
- Keep `Discord 정보 채우기` in the Patreon API toolbar as the action for enriching already-loaded Patreon rows.

## 2.12.0 - 2026-05-15

### Added

- Add persistent Patreon API table column ordering.
- Add header drag-and-drop reordering for Patreon API table columns.
- Add a Patreon table column settings dialog for choosing which columns are visible and changing their order with controls.
- Add a Patreon table column settings shortcut in the Patreon API workspace and main settings dialog.

### Changed

- Patreon API table row rendering now keeps the full internal column set while using Treeview display columns for user-controlled visibility and order.

## 2.11.0 - 2026-05-15

### Added

- Replace the top-bar settings icon behavior with an in-app settings dialog instead of opening `config.json` in Notepad.
- Add settings tabs for Gmail search query, tier USD prices, local currency price maps, fallback exchange rates, excluded emails, Patreon settings shortcuts, Discord bot token, and Discord server ID.
- Keep an advanced `config.json` editor shortcut inside the settings dialog for manual troubleshooting.

### Changed

- Discord bot token and server ID can now be saved from the main settings dialog as well as the Discord-specific dialog.

## 2.10.0 - 2026-05-15

### Added

- Add optional Discord bot integration for resolving Patreon-provided Discord user IDs into Discord usernames, display names, server nicknames, roles, and server join dates.
- Add a Discord bot settings dialog that stores the bot token and target server ID in ignored local `discord_credentials.json`.
- Add a `Discord 정보 채우기` action to enrich existing Patreon API CSV rows without reloading Patreon.
- Add Discord lookup status and server/member fields to the Patreon API CSV and table.
- Add tests for flattening Discord guild member responses.

### Changed

- Patreon current-member imports automatically attempt Discord enrichment when Discord credentials are configured, while preserving the Patreon import if Discord lookup fails.

## 2.9.0 - 2026-05-15

### Added

- Request every documented Patreon member field available from the campaign members endpoint, including deprecated `is_follower`.
- Export expanded related data for users, tiers, campaigns, pledge history, and optional address fields.
- Add tier Discord role IDs, campaign Discord server ID, pledge history summaries, social connection JSON, Patreon profile metadata, and campaign metadata to the Patreon API CSV.
- Add more Patreon API table columns for the expanded export fields.
- Add tests for expanded Patreon member row parsing.

### Changed

- Patreon member import now keeps syncing if optional address data is unavailable for the current OAuth token.
- Patreon API table sorting now handles expanded amount, count, date, and boolean fields.

## 2.8.0 - 2026-05-14

### Added

- Replace the native Windows title bar with an app-rendered dark title bar so dark mode does not depend on OS title-bar support.
- Add Discord ID and Discord name columns to Patreon API imports via `user.social_connections`.
- Add more Patreon API member fields: next charge date, next pay amount, pledge cadence, gift/free-trial flags, member note, profile URL, and lifetime support amount.
- Add a unit test for Discord social connection parsing.

### Changed

- Patreon API table sorting now handles the new amount, date, and boolean fields using typed sort keys.

## 2.7.2 - 2026-05-14

### Fixed

- Apply Windows dark title bar styling to the actual decorated window frame instead of the Tk client area.
- Reapply title bar styling shortly after window creation so the main window and dialogs keep dark chrome after they are realized.

## 2.7.1 - 2026-05-14

### Fixed

- Apply Windows dark title bar styling to the main window when dark mode is enabled.
- Apply the same title bar styling to app-owned dialogs such as date range, calendar, and Patreon API settings.

## 2.7.0 - 2026-05-12

### Added

- Add calendar pickers for the start and end date fields in the date range dialog.
- Add a custom range mode automatically when a calendar date is selected.

### Changed

- Simplify date range presets to `지난 30일`, `반년`, `1년`, `전체`, and `사용자 지정`.
- Map older saved range presets such as `지난 6개월` and `지난 12개월` to the new labels.

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
