from __future__ import annotations

import calendar
import csv
import datetime as dt
import json
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from export_patreon_members import (
    APP_DIR,
    RateProvider,
    build_query,
    load_config,
    parse_decimal_map,
    parse_member_record,
    read_gmail_messages,
    write_csv,
    write_html_report,
    write_xlsx,
)
from patreon_api import (
    PATREON_FIELDS,
    PatreonApiError,
    PatreonClient,
    PatreonCredentials,
    load_credentials as load_patreon_credentials,
    save_credentials as save_patreon_credentials,
    write_patreon_members_csv,
)

OUTPUT_DIR = APP_DIR / "output"
CSV_PATH = OUTPUT_DIR / "patreon_members.csv"
XLSX_PATH = OUTPUT_DIR / "patreon_members.xlsx"
HTML_PATH = OUTPUT_DIR / "patreon_members_report.html"
CONFIG_PATH = APP_DIR / "config.json"
CREDENTIALS_PATH = APP_DIR / "credentials.json"
TOKEN_PATH = APP_DIR / "token.json"
CACHE_PATH = APP_DIR / ".cache" / "rates.json"
PATREON_CREDENTIALS_PATH = APP_DIR / "patreon_credentials.json"
PATREON_MEMBERS_CSV_PATH = OUTPUT_DIR / "patreon_api_members.csv"
APP_SETTINGS_PATH = APP_DIR / "app_settings.json"
ASSETS_DIR = APP_DIR / "assets"
APP_ICON_PATH = ASSETS_DIR / "patreon_chart_icon_v4.ico"
APP_ICON_PNG_PATH = ASSETS_DIR / "patreon_chart_icon_v4.png"
_WINDOWS_PROCESS_CONFIGURED = False

TABLE_COLUMNS = [
    ("event_type", "구분", 130),
    ("received_at", "수신일", 165),
    ("member_name", "이름", 180),
    ("member_email", "이메일", 250),
    ("membership_tier", "티어", 135),
    ("billing_cycle", "청구 주기", 110),
    ("payment_status", "결제 상태", 150),
    ("conversion_path", "경로", 130),
    ("original_amount", "결제 금액", 115),
    ("usd_estimate", "USD 추정", 100),
    ("confidence", "확인", 100),
]

PATREON_TABLE_COLUMNS = [
    ("full_name", "이름", 170),
    ("email", "이메일", 240),
    ("patron_status", "상태", 120),
    ("tier_title", "Patreon 티어", 160),
    ("currently_entitled_amount_cents", "현재 금액", 100),
    ("last_charge_status", "최근 결제", 110),
    ("last_charge_date", "최근 결제일", 170),
    ("pledge_relationship_start", "가입 시작일", 170),
]

LIGHT_THEME = {
    "bg": "#eef2f6",
    "panel": "#ffffff",
    "panel_alt": "#e7edf5",
    "ink": "#172033",
    "muted": "#667085",
    "line": "#8d8a85",
    "accent": "#338ccf",
    "accent_2": "#ffb77c",
    "accent_3": "#88df3f",
    "accent_4": "#ffe047",
    "review": "#a78bfa",
    "track": "#dbe4ef",
    "table_review": "#fff7ed",
    "select_bg": "#cce7ff",
    "select_fg": "#172033",
    "tab_selected": "#ffffff",
    "control_bg": "#ffffff",
    "primary": "#2563eb",
    "primary_soft": "#bfdbfe",
    "success": "#059669",
    "danger": "#dc2626",
    "warning": "#d97706",
    "row_alt": "#f3f6fb",
    "table_header": "#e1e7f0",
    "sidebar": "#eef2f6",
    "content": "#f5f6f8",
    "topbar": "#ffffff",
}

DARK_THEME = {
    "bg": "#080e1d",
    "sidebar": "#090f20",
    "content": "#0b1120",
    "topbar": "#0d1324",
    "panel": "#151d30",
    "panel_alt": "#222b40",
    "ink": "#e9efff",
    "muted": "#9aa6bd",
    "line": "#253149",
    "accent": "#9db8ef",
    "accent_2": "#d79b76",
    "accent_3": "#55e0aa",
    "accent_4": "#f18a1b",
    "review": "#8f98aa",
    "track": "#26304a",
    "table_review": "#251d2d",
    "select_bg": "#24385f",
    "select_fg": "#f8fbff",
    "tab_selected": "#202a40",
    "control_bg": "#0d1528",
    "primary": "#4d8dff",
    "primary_soft": "#a9c2ff",
    "success": "#5be7ad",
    "danger": "#ff8f9a",
    "warning": "#ffb779",
    "row_alt": "#121a2c",
    "table_header": "#252e43",
}

TIER_COLORS = {
    "1": "accent",
    "2": "accent_2",
    "3": "accent_3",
    "4": "accent_4",
    "needs_review": "review",
}

RANGE_PRESETS = ["지난 30일", "반년", "1년", "전체", "사용자 지정"]
RANGE_PRESET_ALIASES = {
    "지난 24시간": "지난 30일",
    "지난 6개월": "반년",
    "지난 12개월": "1년",
    "지난 1년": "1년",
}
GROUP_OPTIONS = ["매일", "매주", "매월"]
INSIGHT_DIMENSIONS = ["전체", "재구독", "멤버십 등급", "청구 주기", "결제 상태", "유료 전환 경로"]
SERIES_COLORS = ["#9db8ef", "#55e0aa", "#ffb779", "#8f98aa", "#d79b76", "#a78bfa"]
GMAIL_REFRESH_TEXT = "▭  Gmail에서 불러오기"
PATREON_REFRESH_TEXT = "현재 멤버 불러오기"
LOADING_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


class PatreonMemberApp(tk.Tk):
    def __init__(self) -> None:
        configure_windows_process()
        super().__init__()
        self._configure_dpi_scaling()
        self.title("Patreon 가입자 대시보드")
        self._icon_image: tk.PhotoImage | None = None
        self._apply_window_icon()
        self.geometry("1280x820")
        self.minsize(1120, 720)

        self.rows: list[dict[str, str]] = []
        self.visible_rows: list[dict[str, str]] = []
        self.patreon_rows: list[dict[str, str]] = []
        self.rejoin_row_keys: set[tuple[str, str, str, str]] = set()
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.is_running = False
        self.loading_after_id: str | None = None
        self.loading_frame_index = 0
        self.loading_context: str | None = None
        self.patreon_sort_column: str | None = None
        self.patreon_sort_descending = False

        self.app_settings = load_app_settings(APP_SETTINGS_PATH)
        self.app_settings["dark_mode"] = True
        self.dark_mode_var = tk.BooleanVar(value=True)
        self.range_var = tk.StringVar(value=str(self.app_settings.get("range_preset", "지난 30일")))
        if self.range_var.get() in RANGE_PRESET_ALIASES:
            self.range_var.set(RANGE_PRESET_ALIASES[self.range_var.get()])
            self.app_settings["range_preset"] = self.range_var.get()
        if self.range_var.get() not in RANGE_PRESETS:
            self.range_var.set("지난 30일")
        self.group_var = tk.StringVar(value=str(self.app_settings.get("group_unit", "매일")))
        legacy_groups = {
            "Daily": "매일",
            "Weekly": "매주",
            "Monthly": "매월",
        }
        if self.group_var.get() in legacy_groups:
            self.group_var.set(legacy_groups[self.group_var.get()])
        if self.group_var.get() not in GROUP_OPTIONS:
            self.group_var.set("매일")
        self.insight_dimension_var = tk.StringVar(value=str(self.app_settings.get("insight_dimension", "결제 상태")))
        legacy_dimensions = {
            "All": "전체",
            "Rejoins": "재구독",
            "Membership Tier": "멤버십 등급",
            "Billing Cycle": "청구 주기",
            "Payment Status": "결제 상태",
            "Paid Path": "유료 전환 경로",
            "유료로 전환하는 경로": "유료 전환 경로",
        }
        if self.insight_dimension_var.get() in legacy_dimensions:
            self.insight_dimension_var.set(legacy_dimensions[self.insight_dimension_var.get()])
        if self.insight_dimension_var.get() not in INSIGHT_DIMENSIONS:
            self.insight_dimension_var.set("결제 상태")
        self.search_var = tk.StringVar(value="")
        self.status_filter_var = tk.StringVar(value="상태: 전체")
        self.tier_filter_var = tk.StringVar(value="전체 티어")
        self.tier_sort_var = tk.StringVar(value=str(self.app_settings.get("tier_sort", "멤버순")))
        if self.tier_sort_var.get() in {"member_count", "members"}:
            self.tier_sort_var.set("멤버순")
        elif self.tier_sort_var.get() == "tier":
            self.tier_sort_var.set("티어순")
        if self.tier_sort_var.get() not in {"멤버순", "티어순"}:
            self.tier_sort_var.set("멤버순")
        self.after_var = tk.StringVar(value="")
        self.before_var = tk.StringVar(value="")
        self.current_start_date: dt.date | None = None
        self.current_end_date: dt.date | None = None
        self.palette = LIGHT_THEME

        self._configure_style()
        self._build_ui()
        self._apply_range_preset_to_entries()
        self._load_existing_csv()
        self._poll_worker_queue()

    def _configure_style(self) -> None:
        self.palette = DARK_THEME if self.dark_mode_var.get() else LIGHT_THEME
        p = self.palette
        self.configure(bg=p["bg"])
        self.option_add("*TCombobox*Listbox.background", p["panel"])
        self.option_add("*TCombobox*Listbox.foreground", p["ink"])
        self.option_add("*TCombobox*Listbox.selectBackground", p["select_bg"])
        self.option_add("*TCombobox*Listbox.selectForeground", p["select_fg"])
        self.option_add("*TCombobox*Listbox.font", ("Malgun Gothic", 10))
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        base_font = ("Malgun Gothic", 10)
        style.configure(".", font=base_font)
        style.configure("TFrame", background=p["bg"])
        style.configure(
            "Panel.TFrame",
            background=p["panel"],
            relief="solid",
            borderwidth=2,
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
        )
        style.configure(
            "Subtle.TFrame",
            background=p["panel_alt"],
            relief="solid",
            borderwidth=1,
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
        )
        style.configure("TLabel", background=p["bg"], foreground=p["ink"], font=base_font)
        style.configure("Panel.TLabel", background=p["panel"], foreground=p["ink"], font=base_font)
        style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"], font=base_font)
        style.configure("PanelMuted.TLabel", background=p["panel"], foreground=p["muted"], font=base_font)
        style.configure("Title.TLabel", background=p["bg"], foreground=p["ink"], font=("Malgun Gothic", 22, "bold"))
        style.configure("MetricTitle.TLabel", background=p["panel"], foreground=p["muted"], font=("Malgun Gothic", 11))
        style.configure("MetricValue.TLabel", background=p["panel"], foreground=p["ink"], font=("Malgun Gothic", 24, "bold"))
        style.configure(
            "TButton",
            padding=(16, 9),
            font=("Malgun Gothic", 11, "bold"),
            background=p["control_bg"],
            foreground=p["ink"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
            relief="solid",
            borderwidth=2,
            focusthickness=1,
            focuscolor=p["line"],
        )
        style.map(
            "TButton",
            background=[("active", p["track"]), ("disabled", p["panel_alt"])],
            foreground=[("active", p["ink"]), ("disabled", p["muted"])],
        )
        style.configure(
            "Accent.TButton",
            padding=(16, 9),
            font=("Malgun Gothic", 11, "bold"),
            background=p["control_bg"],
            foreground=p["ink"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
            relief="solid",
            borderwidth=2,
        )
        style.map(
            "Accent.TButton",
            background=[("active", p["track"]), ("disabled", p["panel_alt"])],
            foreground=[("active", p["ink"]), ("disabled", p["muted"])],
        )
        style.configure("TCheckbutton", background=p["bg"], foreground=p["ink"], font=("Malgun Gothic", 10, "bold"))
        style.map("TCheckbutton", background=[("active", p["bg"])], foreground=[("active", p["ink"])])
        style.configure(
            "TEntry",
            padding=4,
            fieldbackground=p["control_bg"],
            foreground=p["ink"],
            insertcolor=p["ink"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
            relief="solid",
            borderwidth=2,
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", p["panel_alt"]), ("readonly", p["panel_alt"])],
            foreground=[("disabled", p["ink"]), ("readonly", p["ink"])],
        )
        style.configure(
            "TCombobox",
            padding=3,
            fieldbackground=p["control_bg"],
            background=p["control_bg"],
            foreground=p["ink"],
            arrowcolor=p["ink"],
            selectbackground=p["control_bg"],
            selectforeground=p["ink"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
            relief="solid",
            borderwidth=2,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", p["control_bg"]), ("disabled", p["panel_alt"])],
            foreground=[("readonly", p["ink"]), ("disabled", p["ink"])],
            selectbackground=[("readonly", p["control_bg"])],
            selectforeground=[("readonly", p["ink"])],
            arrowcolor=[("readonly", p["ink"]), ("disabled", p["muted"])],
        )
        style.configure(
            "TNotebook",
            background=p["bg"],
            borderwidth=2,
            bordercolor=p["line"],
            tabmargins=(0, 8, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background=p["panel_alt"],
            foreground=p["ink"],
            padding=(20, 9),
            font=("Malgun Gothic", 10, "bold"),
            borderwidth=2,
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
        )
        style.map("TNotebook.Tab", background=[("selected", p["tab_selected"])], foreground=[("selected", p["ink"])])
        style.configure(
            "Treeview",
            rowheight=48,
            font=("Segoe UI", 11),
            background=p["panel"],
            fieldbackground=p["panel"],
            foreground=p["ink"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
            relief="solid",
            borderwidth=2,
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=p.get("table_header", p["panel_alt"]),
            foreground=p["ink"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
            relief="solid",
            borderwidth=2,
        )
        style.map("Treeview", background=[("selected", p["select_bg"])], foreground=[("selected", p["select_fg"])])
        for scrollbar_style in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(
                scrollbar_style,
                background=p["panel_alt"],
                troughcolor=p["panel"],
                bordercolor=p["line"],
                arrowcolor=p["ink"],
                lightcolor=p["line"],
                darkcolor=p["line"],
            )
        self._apply_window_chrome()

    def _apply_window_chrome(self, window: tk.Tk | tk.Toplevel | None = None) -> None:
        target = window or self
        palette = dict(self.palette)
        dark_mode = bool(self.dark_mode_var.get())
        def apply_theme() -> None:
            try:
                if target.winfo_exists():
                    set_windows_window_theme(target, dark_mode, palette)
            except tk.TclError:
                pass

        target.after_idle(apply_theme)
        target.after(250, apply_theme)

    def _build_ui(self) -> None:
        p = self.palette
        self.configure(bg=p["content"])
        self.status_var = tk.StringVar(value="기존 결과를 불러오는 중입니다.")
        self.patreon_status_var = tk.StringVar(value="Patreon API 설정 후 현재 멤버를 불러올 수 있습니다.")
        self.metric_vars = {
            "total": tk.StringVar(value="0"),
            "rejoin": tk.StringVar(value="0"),
            "tier1": tk.StringVar(value="0"),
            "tier2": tk.StringVar(value="0"),
            "tier3": tk.StringVar(value="0"),
            "tier4": tk.StringVar(value="0"),
            "review": tk.StringVar(value="0"),
        }
        self.metric_detail_vars = {
            "total": tk.StringVar(value="전체 기간"),
        }
        self.patreon_metric_vars = {
            "total": tk.StringVar(value="0"),
            "active": tk.StringVar(value="0"),
            "declined": tk.StringVar(value="0"),
            "former": tk.StringVar(value="0"),
        }

        shell = tk.Frame(self, bg=p["content"])
        shell.pack(fill=tk.BOTH, expand=True)
        self.root_frame = shell

        self.sidebar = tk.Frame(shell, bg=p["sidebar"], width=380)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.main_area = tk.Frame(shell, bg=p["content"])
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_sidebar()
        self._build_topbar()

        self.page_host = tk.Frame(self.main_area, bg=p["content"])
        self.page_host.pack(fill=tk.BOTH, expand=True, padx=32, pady=32)
        self.page_host.columnconfigure(0, weight=1)
        self.page_host.rowconfigure(0, weight=1)

        self.pages: dict[str, tk.Frame] = {}
        self.summary_tab = tk.Frame(self.page_host, bg=p["content"])
        self.period_tab = tk.Frame(self.page_host, bg=p["content"])
        self.table_tab = tk.Frame(self.page_host, bg=p["content"])
        self.patreon_tab = tk.Frame(self.page_host, bg=p["content"])
        self.pages = {
            "summary": self.summary_tab,
            "period": self.period_tab,
            "list": self.table_tab,
            "patreon": self.patreon_tab,
        }

        self._build_summary_tab()
        self._build_period_tab()
        self._build_table_tab()
        self._build_patreon_tab()
        self._show_page("summary")

    def _build_sidebar(self) -> None:
        p = self.palette
        top = tk.Frame(self.sidebar, bg=p["sidebar"])
        top.pack(fill=tk.X, padx=24, pady=(28, 36))

        avatar = tk.Canvas(top, width=56, height=56, bg=p["sidebar"], highlightthickness=0)
        avatar.pack(side=tk.LEFT, padx=(0, 14), anchor=tk.N)
        self._draw_sidebar_logo(avatar)

        title_box = tk.Frame(top, bg=p["sidebar"])
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.sidebar_title_label = tk.Label(
            title_box,
            text="크리에이터\n분석",
            bg=p["sidebar"],
            fg=p["primary_soft"],
            justify=tk.LEFT,
            wraplength=260,
            font=("Malgun Gothic", 16, "bold"),
        )
        self.sidebar_title_label.pack(anchor=tk.W)
        self.sidebar_subtitle_label = tk.Label(
            title_box,
            text="멤버십 현황",
            bg=p["sidebar"],
            fg=p["muted"],
            font=("Malgun Gothic", 10),
        )
        self.sidebar_subtitle_label.pack(anchor=tk.W, pady=(2, 0))

        self.nav_buttons: dict[str, tk.Button] = {}
        nav = tk.Frame(self.sidebar, bg=p["sidebar"])
        nav.pack(fill=tk.X, padx=16)
        for key, icon, label in [
            ("summary", "[]", "요약"),
            ("period", "##", "기간별"),
            ("list", "==", "목록"),
            ("patreon", "<>", "Patreon API"),
        ]:
            self.nav_buttons[key] = self._nav_button(nav, key, icon, label)

        bottom = tk.Frame(self.sidebar, bg=p["sidebar"])
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=24, pady=(0, 24))
        tk.Frame(bottom, bg=p["line"], height=1).pack(fill=tk.X, pady=(0, 24))
        tk.Button(
            bottom,
            text="결과 폴더  ->",
            command=self.open_output_folder,
            bd=0,
            bg=p["primary_soft"],
            fg="#082454",
            activebackground="#c1d4ff",
            activeforeground="#082454",
            padx=18,
            pady=12,
            cursor="hand2",
            font=("Segoe UI", 12, "bold"),
        ).pack(fill=tk.X)

    def _draw_sidebar_logo(self, canvas: tk.Canvas) -> None:
        p = self.palette
        canvas.create_oval(3, 3, 53, 53, fill=p["panel_alt"], outline=p["line"], width=1)
        canvas.create_line(17, 16, 17, 41, 42, 41, fill=p["primary_soft"], width=3)
        for x0, y0, x1, color in [
            (21, 30, 26, p["primary"]),
            (29, 24, 34, p["accent_3"]),
            (37, 18, 42, p["accent_4"]),
        ]:
            canvas.create_rectangle(x0, y0, x1, 40, fill=color, outline="")
        canvas.create_line(20, 31, 29, 25, 36, 29, 43, 18, fill=p["ink"], width=2)

    def _nav_button(self, parent: tk.Frame, key: str, icon: str, label: str) -> tk.Button:
        p = self.palette
        button = tk.Button(
            parent,
            text=f"{icon}   {label}",
            command=lambda: self._show_page(key),
            anchor=tk.W,
            bd=0,
            bg=p["sidebar"],
            fg=p["ink"],
            activebackground=p["panel"],
            activeforeground=p["ink"],
            padx=18,
            pady=13,
            cursor="hand2",
            font=("Segoe UI", 12, "bold" if key == "summary" else "normal"),
        )
        button.pack(fill=tk.X, pady=5)
        return button

    def _build_topbar(self) -> None:
        p = self.palette
        bar = tk.Frame(self.main_area, bg=p["topbar"], height=78, highlightbackground=p["line"], highlightthickness=0)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        tk.Frame(bar, bg=p["line"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        title = tk.Label(
            bar,
            text="가입자 분석 대시보드",
            bg=p["topbar"],
            fg=p["ink"],
            font=("Segoe UI", 20, "bold"),
        )
        title.pack(side=tk.LEFT, padx=(32, 0))

        actions = tk.Frame(bar, bg=p["topbar"])
        actions.pack(side=tk.RIGHT, padx=24)
        self.date_button = self._pill_button(actions, "▣  기간 설정", self._open_date_range_dialog, primary=False)
        self.date_button.pack(side=tk.LEFT, padx=(0, 12))
        self.refresh_button = self._pill_button(actions, GMAIL_REFRESH_TEXT, self.refresh_from_gmail, primary=True)
        self.refresh_button.pack(side=tk.LEFT, padx=(0, 22))
        tk.Frame(actions, bg=p["line"], width=1, height=42).pack(side=tk.LEFT, padx=(0, 18))
        self._icon_button(actions, "⚙", self.open_config).pack(side=tk.LEFT, padx=7)
        self._icon_button(actions, "⎋", self.open_output_folder).pack(side=tk.LEFT, padx=7)
        self._icon_button(actions, "◎", self.open_patreon_settings).pack(side=tk.LEFT, padx=7)

    def _pill_button(self, parent: tk.Frame, text: str, command, primary: bool = False) -> tk.Button:
        p = self.palette
        return tk.Button(
            parent,
            text=text,
            command=command,
            bd=1,
            relief=tk.SOLID,
            bg=p["panel_alt"] if primary else p["control_bg"],
            fg=p["ink"],
            activebackground=p["select_bg"],
            activeforeground=p["ink"],
            disabledforeground=p["muted"],
            highlightbackground=p["line"],
            highlightcolor=p["line"],
            padx=18,
            pady=10,
            cursor="hand2",
            font=("Segoe UI", 12, "bold" if primary else "normal"),
        )

    def _icon_button(self, parent: tk.Frame, text: str, command) -> tk.Button:
        p = self.palette
        return tk.Button(
            parent,
            text=text,
            command=command,
            bd=0,
            bg=p["topbar"],
            fg=p["ink"],
            activebackground=p["panel"],
            activeforeground=p["primary_soft"],
            width=2,
            cursor="hand2",
            font=("Segoe UI Symbol", 18),
        )

    def _show_page(self, page: str) -> None:
        for frame in self.pages.values():
            frame.grid_forget()
        self.pages[page].grid(row=0, column=0, sticky="nsew")
        self.current_page = page
        p = self.palette
        for key, button in self.nav_buttons.items():
            selected = key == page
            button.configure(
                bg=p["panel"] if selected else p["sidebar"],
                fg=p["primary_soft"] if selected else p["ink"],
                font=("Segoe UI", 12, "bold" if selected else "normal"),
            )
        self.after(50, self._redraw_visible_charts)

    def _redraw_visible_charts(self) -> None:
        if hasattr(self, "tier_chart"):
            self._draw_tier_chart(self.visible_rows)
        if hasattr(self, "period_chart"):
            self._draw_period_chart(self.visible_rows)

    def _apply_window_icon(self) -> None:
        if APP_ICON_PATH.exists():
            try:
                self.iconbitmap(default=str(APP_ICON_PATH))
            except tk.TclError:
                pass
        if sys.platform == "win32":
            return
        if APP_ICON_PNG_PATH.exists():
            try:
                self._icon_image = tk.PhotoImage(file=str(APP_ICON_PNG_PATH))
                self.iconphoto(True, self._icon_image)
            except tk.TclError:
                self._icon_image = None

    def _configure_dpi_scaling(self) -> None:
        if sys.platform != "win32":
            return
        try:
            pixels_per_inch = float(self.winfo_fpixels("1i"))
            if pixels_per_inch > 0:
                self.tk.call("tk", "scaling", pixels_per_inch / 72.0)
        except tk.TclError:
            pass

    def _build_summary_tab(self) -> None:
        for column in range(3):
            self.summary_tab.columnconfigure(column, weight=1, uniform="summary_cards")
        self.summary_tab.rowconfigure(2, weight=1)
        summary_cards = [
            (0, 0, 2, "전체 회원", "total", self.metric_detail_vars["total"], "success"),
            (0, 2, 1, "재구독", "rejoin", "반복 가입", "success"),
            (1, 0, 1, "티어 1", "tier1", "회원", "accent_2"),
            (1, 1, 1, "티어 2", "tier2", "회원", "accent"),
            (1, 2, 1, "티어 3", "tier3", "회원", "accent_4"),
        ]
        for row, column, columnspan, label, key, detail, color_key in summary_cards:
            card = self._metric_card(self.summary_tab, label, self.metric_vars[key], detail, color_key)
            card.grid(
                row=row,
                column=column,
                columnspan=columnspan,
                sticky="nsew",
                padx=(0 if column == 0 else 10, 0),
                pady=(0, 18),
            )

        chart_panel = self._card_frame(self.summary_tab)
        chart_panel.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(22, 0))
        chart_panel.rowconfigure(1, weight=1)
        chart_panel.columnconfigure(0, weight=1)
        header = tk.Frame(chart_panel, bg=self.palette["panel"])
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 10))
        tk.Label(
            header,
            text="티어 분포",
            bg=self.palette["panel"],
            fg=self.palette["ink"],
            font=("Segoe UI", 16, "bold"),
        ).pack(side=tk.LEFT)
        sort_group = tk.Frame(header, bg=self.palette["panel_alt"])
        sort_group.pack(side=tk.RIGHT)
        self.tier_sort_buttons: dict[str, tk.Button] = {}
        for option in ["멤버순", "티어순"]:
            button = tk.Button(
                sort_group,
                text=option,
                command=lambda value=option: self._select_tier_sort(value),
                bd=0,
                padx=15,
                pady=8,
                cursor="hand2",
                font=("Segoe UI", 10, "bold" if option == self.tier_sort_var.get() else "normal"),
            )
            button.pack(side=tk.LEFT, padx=2, pady=2)
            self.tier_sort_buttons[option] = button
        self._refresh_tier_sort_buttons()
        self.tier_chart = tk.Canvas(chart_panel, height=310, bg=self.palette["panel"], highlightthickness=0)
        self.tier_chart.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 22))
        self.tier_chart.bind("<Configure>", lambda _event: self._draw_tier_chart(self.visible_rows))

    def _build_period_tab(self) -> None:
        self.period_tab.rowconfigure(0, weight=1)
        self.period_tab.columnconfigure(0, weight=1)
        panel = self._card_frame(self.period_tab)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.rowconfigure(2, weight=1)
        panel.columnconfigure(0, weight=1)

        header = tk.Frame(panel, bg=self.palette["panel"])
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 8))
        tk.Label(header, text="회원 활동", bg=self.palette["panel"], fg=self.palette["ink"], font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)
        group = tk.Frame(header, bg=self.palette["panel_alt"])
        group.pack(side=tk.RIGHT)
        self.group_buttons: dict[str, tk.Button] = {}
        for option in GROUP_OPTIONS:
            button = tk.Button(
                group,
                text=option,
                command=lambda value=option: self._select_group(value),
                bd=0,
                padx=15,
                pady=8,
                cursor="hand2",
                font=("Segoe UI", 10, "bold" if option == self.group_var.get() else "normal"),
            )
            button.pack(side=tk.LEFT, padx=2, pady=2)
            self.group_buttons[option] = button
        self._refresh_group_buttons()

        self.dimension_frame = tk.Frame(panel, bg=self.palette["panel"])
        self.dimension_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 12))
        self.dimension_buttons: dict[str, tk.Button] = {}
        for dimension in INSIGHT_DIMENSIONS:
            button = tk.Button(
                self.dimension_frame,
                text=dimension,
                command=lambda value=dimension: self.select_insight_dimension(value),
                bd=0,
                padx=14,
                pady=8,
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
            )
            button.pack(side=tk.LEFT, padx=(0, 6))
            self.dimension_buttons[dimension] = button
        self._refresh_dimension_buttons()
        self.period_chart = tk.Canvas(panel, height=520, bg=self.palette["panel"], highlightthickness=0)
        self.period_chart.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self.period_chart.bind("<Configure>", lambda _event: self._draw_period_chart(self.visible_rows))

    def _build_table_tab(self) -> None:
        self.table_tab.rowconfigure(1, weight=1)
        self.table_tab.columnconfigure(0, weight=1)
        toolbar = self._card_frame(self.table_tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        inner = tk.Frame(toolbar, bg=self.palette["panel"])
        inner.pack(fill=tk.X, padx=22, pady=22)
        search = ttk.Entry(inner, textvariable=self.search_var, width=38)
        search.pack(side=tk.LEFT, ipady=6, padx=(0, 18))
        search.insert(0, "")
        search.bind("<KeyRelease>", lambda _event: self._refresh_table())
        search.configure()
        tier_box = ttk.Combobox(
            inner,
            textvariable=self.tier_filter_var,
            values=["전체 티어", "티어 1", "티어 2", "티어 3", "티어 4", "확인 필요"],
            width=14,
            state="readonly",
        )
        tier_box.pack(side=tk.LEFT, padx=(0, 18), ipady=5)
        tier_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_table())
        status_box = ttk.Combobox(
            inner,
            textvariable=self.status_filter_var,
            values=["상태: 전체", "재구독", "유료 활성", "결제 완료", "선물 (타인)", "선물 (본인)", "확인 필요"],
            width=16,
            state="readonly",
        )
        status_box.pack(side=tk.LEFT, padx=(0, 18), ipady=5)
        status_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_table())
        self.count_var = tk.StringVar(value="")
        count = tk.Label(
            inner,
            textvariable=self.count_var,
            bg=self.palette["control_bg"],
            fg=self.palette["ink"],
            padx=16,
            pady=8,
            font=("Segoe UI", 10),
        )
        count.pack(side=tk.RIGHT)

        table_panel = self._card_frame(self.table_tab)
        table_panel.grid(row=1, column=0, sticky="nsew")
        table_panel.rowconfigure(0, weight=1)
        table_panel.columnconfigure(0, weight=1)
        table_wrap = tk.Frame(table_panel, bg=self.palette["panel"])
        table_wrap.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.tree = ttk.Treeview(
            table_wrap,
            columns=[column for column, _, _ in TABLE_COLUMNS],
            show="headings",
            selectmode="browse",
        )
        for column, label, width in TABLE_COLUMNS:
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=60, anchor=tk.W)
        y_scroll = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)
        self._configure_tree_tags()

    def _build_patreon_tab(self) -> None:
        self.patreon_tab.rowconfigure(2, weight=1)
        for column in range(4):
            self.patreon_tab.columnconfigure(column, weight=1, uniform="patreon_cards")
        toolbar = tk.Frame(self.patreon_tab, bg=self.palette["content"])
        toolbar.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 18))
        tk.Button(
            toolbar,
            text="Patreon 키 설정",
            command=self.open_patreon_settings,
            bd=0,
            bg=self.palette["panel_alt"],
            fg=self.palette["ink"],
            padx=18,
            pady=10,
            cursor="hand2",
            font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 12))
        self.patreon_refresh_button = tk.Button(
            toolbar,
            text=PATREON_REFRESH_TEXT,
            command=self.refresh_from_patreon,
            bd=0,
            bg=self.palette["primary_soft"],
            fg="#082454",
            disabledforeground=self.palette["muted"],
            padx=18,
            pady=10,
            cursor="hand2",
            font=("Segoe UI", 11, "bold"),
        )
        self.patreon_refresh_button.pack(side=tk.LEFT, padx=(0, 12))
        tk.Button(
            toolbar,
            text="Patreon CSV 열기",
            command=self.open_patreon_csv,
            bd=0,
            bg=self.palette["panel_alt"],
            fg=self.palette["ink"],
            padx=18,
            pady=10,
            cursor="hand2",
            font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            toolbar,
            textvariable=self.patreon_status_var,
            bg=self.palette["content"],
            fg=self.palette["muted"],
            font=("Segoe UI", 10),
        ).pack(side=tk.RIGHT)

        for index, (label, key) in enumerate([
            ("전체 회원", "total"),
            ("활성", "active"),
            ("결제 실패", "declined"),
            ("이전 회원", "former"),
        ]):
            card = self._metric_card(self.patreon_tab, label, self.patreon_metric_vars[key], "", "accent")
            card.grid(row=1, column=index, sticky="nsew", padx=(0, 12 if index < 3 else 0), pady=(0, 18))

        panel = self._card_frame(self.patreon_tab)
        panel.grid(row=2, column=0, columnspan=4, sticky="nsew")
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)
        table_wrap = tk.Frame(panel, bg=self.palette["panel"])
        table_wrap.grid(row=0, column=0, sticky="nsew")
        self.patreon_tree = ttk.Treeview(
            table_wrap,
            columns=[column for column, _, _ in PATREON_TABLE_COLUMNS],
            show="headings",
            selectmode="browse",
        )
        for column, label, width in PATREON_TABLE_COLUMNS:
            self.patreon_tree.heading(
                column,
                text=label,
                command=lambda selected=column: self._sort_patreon_by_column(selected),
            )
            self.patreon_tree.column(column, width=width, minwidth=70, anchor=tk.W)
        y_scroll = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.patreon_tree.yview)
        x_scroll = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.patreon_tree.xview)
        self.patreon_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.patreon_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)
        self._configure_tree_tags()
        self._load_existing_patreon_csv()

    def _card_frame(self, parent: tk.Frame) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=self.palette["panel"],
            highlightbackground=self.palette["line"],
            highlightthickness=1,
        )

    def _metric_card(
        self,
        parent: tk.Frame,
        label: str,
        value_var: tk.StringVar,
        detail: str | tk.StringVar = "",
        color_key: str = "accent",
    ) -> tk.Frame:
        frame = self._card_frame(parent)
        frame.configure(height=128)
        frame.pack_propagate(False)
        tk.Label(
            frame,
            text=label,
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, padx=22, pady=(20, 4))
        row = tk.Frame(frame, bg=self.palette["panel"])
        row.pack(fill=tk.X, padx=22)
        tk.Label(
            row,
            textvariable=value_var,
            bg=self.palette["panel"],
            fg=self.palette["ink"],
            font=("Segoe UI", 24, "bold"),
        ).pack(side=tk.LEFT)
        if detail:
            label_kwargs = {
                "bg": self.palette["panel"],
                "fg": self.palette["success"] if isinstance(detail, str) and detail.startswith("↑") else self.palette["ink"],
                "font": ("Segoe UI", 11),
            }
            if isinstance(detail, tk.StringVar):
                detail_label = tk.Label(row, textvariable=detail, **label_kwargs)
            else:
                detail_label = tk.Label(row, text=f"  {detail}", **label_kwargs)
            detail_label.pack(side=tk.LEFT, pady=(8, 0), padx=(8 if isinstance(detail, tk.StringVar) else 0, 0))
        bar = tk.Frame(frame, bg=self.palette["track"], height=5)
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=22, pady=(0, 22))
        fill = tk.Frame(bar, bg=self.palette.get(color_key, self.palette["accent"]), height=5)
        fill.place(relx=0, rely=0, relwidth=0.08 if label.endswith("1") else 0.75 if label.endswith("2") else 0.02, relheight=1)
        return frame

    def toggle_theme(self) -> None:
        self.app_settings["dark_mode"] = bool(self.dark_mode_var.get())
        save_app_settings(APP_SETTINGS_PATH, self.app_settings)
        self._configure_style()
        self._configure_tree_tags()
        self._refresh_dimension_buttons()
        self._draw_tier_chart(self.visible_rows)
        self._draw_period_chart(self.visible_rows)

    def on_range_changed(self) -> None:
        self.app_settings["range_preset"] = self.range_var.get()
        save_app_settings(APP_SETTINGS_PATH, self.app_settings)
        self._apply_range_preset_to_entries()
        self.apply_filters()

    def on_group_changed(self) -> None:
        self.app_settings["group_unit"] = self.group_var.get()
        save_app_settings(APP_SETTINGS_PATH, self.app_settings)
        self._refresh_group_buttons()
        self._draw_period_chart(self.visible_rows)

    def _select_group(self, group: str) -> None:
        self.group_var.set(group)
        self.on_group_changed()

    def _refresh_group_buttons(self) -> None:
        if not hasattr(self, "group_buttons"):
            return
        for group, button in self.group_buttons.items():
            selected = group == self.group_var.get()
            button.configure(
                bg=self.palette["control_bg"] if selected else self.palette["panel_alt"],
                fg=self.palette["ink"] if selected else self.palette["muted"],
                activebackground=self.palette["select_bg"],
                activeforeground=self.palette["ink"],
                font=("Segoe UI", 10, "bold" if selected else "normal"),
            )

    def _select_tier_sort(self, sort_mode: str) -> None:
        self.tier_sort_var.set(sort_mode)
        self.app_settings["tier_sort"] = sort_mode
        save_app_settings(APP_SETTINGS_PATH, self.app_settings)
        self._refresh_tier_sort_buttons()
        self._draw_tier_chart(self.visible_rows)

    def _refresh_tier_sort_buttons(self) -> None:
        if not hasattr(self, "tier_sort_buttons"):
            return
        for sort_mode, button in self.tier_sort_buttons.items():
            selected = sort_mode == self.tier_sort_var.get()
            button.configure(
                bg=self.palette["control_bg"] if selected else self.palette["panel_alt"],
                fg=self.palette["ink"] if selected else self.palette["muted"],
                activebackground=self.palette["select_bg"],
                activeforeground=self.palette["ink"],
                font=("Segoe UI", 10, "bold" if selected else "normal"),
            )

    def select_insight_dimension(self, dimension: str) -> None:
        self.insight_dimension_var.set(dimension)
        self.app_settings["insight_dimension"] = dimension
        save_app_settings(APP_SETTINGS_PATH, self.app_settings)
        self._refresh_dimension_buttons()
        self._draw_period_chart(self.visible_rows)

    def _refresh_dimension_buttons(self) -> None:
        if not hasattr(self, "dimension_buttons"):
            return
        p = self.palette
        for dimension, button in self.dimension_buttons.items():
            selected = dimension == self.insight_dimension_var.get()
            selected_bg = p["control_bg"] if selected else p["panel_alt"]
            normal_bg = p["panel"]
            button.configure(
                bg=selected_bg if selected else normal_bg,
                fg=p["ink"] if selected else p["muted"],
                activebackground=selected_bg if selected else p["track"],
                activeforeground=p["ink"],
                relief=tk.FLAT,
                borderwidth=0,
                highlightthickness=0,
            )

    def _open_date_range_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("기간 설정")
        dialog.geometry("460x340")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=self.palette["content"])
        self._apply_window_chrome(dialog)
        frame = tk.Frame(dialog, bg=self.palette["panel"], highlightbackground=self.palette["line"], highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        tk.Label(frame, text="기간 설정", bg=self.palette["panel"], fg=self.palette["ink"], font=("Segoe UI", 18, "bold")).pack(anchor=tk.W, padx=22, pady=(20, 14))

        form = tk.Frame(frame, bg=self.palette["panel"])
        form.pack(fill=tk.X, padx=22)
        tk.Label(form, text="기간", bg=self.palette["panel"], fg=self.palette["muted"], font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=6)
        range_box = ttk.Combobox(form, textvariable=self.range_var, values=RANGE_PRESETS, width=24, state="readonly")
        range_box.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=6)
        range_box.bind("<<ComboboxSelected>>", lambda _event: self.on_range_changed())
        tk.Label(form, text="시작일", bg=self.palette["panel"], fg=self.palette["muted"], font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=6)
        after_row = tk.Frame(form, bg=self.palette["panel"])
        after_row.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=6)
        after_row.columnconfigure(0, weight=1)
        self.after_entry = ttk.Entry(after_row, textvariable=self.after_var, width=22)
        self.after_entry.grid(row=0, column=0, sticky="ew")
        self._calendar_button(after_row, lambda: self._open_calendar_popup(self.after_var, "시작일 선택")).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )
        tk.Label(form, text="종료일", bg=self.palette["panel"], fg=self.palette["muted"], font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=6)
        before_row = tk.Frame(form, bg=self.palette["panel"])
        before_row.grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=6)
        before_row.columnconfigure(0, weight=1)
        self.before_entry = ttk.Entry(before_row, textvariable=self.before_var, width=22)
        self.before_entry.grid(row=0, column=0, sticky="ew")
        self._calendar_button(before_row, lambda: self._open_calendar_popup(self.before_var, "종료일 선택")).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )
        form.columnconfigure(1, weight=1)
        self._apply_range_preset_to_entries()

        buttons = tk.Frame(frame, bg=self.palette["panel"])
        buttons.pack(fill=tk.X, padx=22, pady=(20, 0))
        tk.Button(
            buttons,
            text="적용",
            command=lambda: (self.apply_filters(), dialog.destroy()),
            bd=0,
            bg=self.palette["primary_soft"],
            fg="#082454",
            padx=18,
            pady=9,
            cursor="hand2",
            font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.RIGHT)
        tk.Button(
            buttons,
            text="취소",
            command=dialog.destroy,
            bd=0,
            bg=self.palette["panel_alt"],
            fg=self.palette["ink"],
            padx=18,
            pady=9,
            cursor="hand2",
            font=("Segoe UI", 11),
        ).pack(side=tk.RIGHT, padx=(0, 10))

    def _calendar_button(self, parent: tk.Widget, command) -> tk.Button:
        return tk.Button(
            parent,
            text="달력",
            command=command,
            bd=0,
            bg=self.palette["panel_alt"],
            fg=self.palette["ink"],
            activebackground=self.palette["select_bg"],
            activeforeground=self.palette["ink"],
            padx=10,
            pady=5,
            cursor="hand2",
            font=("Malgun Gothic", 9, "bold"),
        )

    def _open_calendar_popup(self, variable: tk.StringVar, title: str) -> None:
        parsed = self._parse_date_text(variable.get().strip())
        selected = parsed if isinstance(parsed, dt.date) else dt.date.today()
        state = {"year": selected.year, "month": selected.month}
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.geometry("330x360")
        popup.transient(self)
        popup.grab_set()
        popup.configure(bg=self.palette["panel"])
        self._apply_window_chrome(popup)

        header = tk.Frame(popup, bg=self.palette["panel"])
        header.pack(fill=tk.X, padx=16, pady=(16, 8))
        month_label = tk.Label(
            header,
            bg=self.palette["panel"],
            fg=self.palette["ink"],
            font=("Malgun Gothic", 13, "bold"),
        )
        month_label.pack(side=tk.LEFT, expand=True)
        days = tk.Frame(popup, bg=self.palette["panel"])
        days.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        def move_month(delta: int) -> None:
            month = state["month"] + delta
            year = state["year"]
            if month < 1:
                year -= 1
                month = 12
            elif month > 12:
                year += 1
                month = 1
            state["year"] = year
            state["month"] = month
            render()

        tk.Button(
            header,
            text="<",
            command=lambda: move_month(-1),
            bd=0,
            bg=self.palette["panel_alt"],
            fg=self.palette["ink"],
            width=3,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 8))
        month_label.pack_forget()
        month_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(
            header,
            text=">",
            command=lambda: move_month(1),
            bd=0,
            bg=self.palette["panel_alt"],
            fg=self.palette["ink"],
            width=3,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.RIGHT, padx=(8, 0))

        def choose(day: dt.date) -> None:
            self._set_custom_range_date(variable, day)
            popup.destroy()

        def render() -> None:
            for child in days.winfo_children():
                child.destroy()
            year = state["year"]
            month = state["month"]
            month_label.configure(text=f"{year}년 {month}월")
            for column, text in enumerate(["월", "화", "수", "목", "금", "토", "일"]):
                tk.Label(
                    days,
                    text=text,
                    bg=self.palette["panel"],
                    fg=self.palette["muted"],
                    font=("Malgun Gothic", 9, "bold"),
                ).grid(row=0, column=column, sticky="nsew", padx=1, pady=(0, 5))
                days.columnconfigure(column, weight=1)
            month_days = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
            for row_index, week in enumerate(month_days, start=1):
                for column, day in enumerate(week):
                    in_month = day.month == month
                    is_selected = day == selected
                    button = tk.Button(
                        days,
                        text=str(day.day),
                        command=lambda value=day: choose(value),
                        bd=0,
                        bg=self.palette["select_bg"] if is_selected else self.palette["control_bg"],
                        fg=self.palette["ink"] if in_month else self.palette["muted"],
                        activebackground=self.palette["select_bg"],
                        activeforeground=self.palette["ink"],
                        cursor="hand2",
                        font=("Segoe UI", 10, "bold" if is_selected else "normal"),
                    )
                    button.grid(row=row_index, column=column, sticky="nsew", padx=1, pady=1, ipady=6)
                    days.rowconfigure(row_index, weight=1)

        render()

    def _set_custom_range_date(self, variable: tk.StringVar, selected_date: dt.date) -> None:
        variable.set(selected_date.strftime("%Y/%m/%d"))
        self.range_var.set("사용자 지정")
        self.app_settings["range_preset"] = "사용자 지정"
        save_app_settings(APP_SETTINGS_PATH, self.app_settings)
        self._apply_range_preset_to_entries()

    def _configure_tree_tags(self) -> None:
        if hasattr(self, "tree"):
            self.tree.tag_configure("needs_review", background=self.palette["table_review"], foreground=self.palette["ink"])
            self.tree.tag_configure("rejoin", background="#14283a", foreground=self.palette["ink"])
            self.tree.tag_configure("alt", background=self.palette["row_alt"], foreground=self.palette["ink"])
        if hasattr(self, "patreon_tree"):
            self.patreon_tree.tag_configure("declined", background=self.palette["table_review"], foreground=self.palette["ink"])
            self.patreon_tree.tag_configure("alt", background=self.palette["row_alt"], foreground=self.palette["ink"])

    def _load_existing_csv(self) -> None:
        if not CSV_PATH.exists():
            self.status_var.set("아직 결과가 없습니다. Gmail에서 새로 불러오기를 누르세요.")
            self.rows = []
            self.apply_filters()
            return
        try:
            with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
                self.rows = list(csv.DictReader(handle))
        except OSError as exc:
            messagebox.showerror("불러오기 실패", str(exc))
            self.rows = []
        self.apply_filters()
        self.status_var.set(f"기존 결과를 불러왔습니다: {CSV_PATH.name}")

    def _load_existing_patreon_csv(self) -> None:
        if not PATREON_MEMBERS_CSV_PATH.exists():
            self._set_patreon_rows([])
            return
        try:
            with PATREON_MEMBERS_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
                self.patreon_rows = list(csv.DictReader(handle))
        except OSError as exc:
            messagebox.showerror("Patreon CSV 불러오기 실패", str(exc))
            self.patreon_rows = []
        self._set_patreon_rows(self.patreon_rows)
        self.patreon_status_var.set(f"기존 Patreon API 결과를 불러왔습니다: {len(self.patreon_rows)}명")

    def apply_filters(self) -> None:
        if self.range_var.get() != "사용자 지정":
            self._apply_range_preset_to_entries()
        start = self._parse_date_text(self.after_var.get().strip())
        end = self._parse_date_text(self.before_var.get().strip())
        if start == "invalid" or end == "invalid":
            messagebox.showwarning("날짜 형식", "날짜는 YYYY/MM/DD 또는 YYYY-MM-DD 형식으로 입력하세요.")
            return
        self._set_rejoin_cache(self.rows)
        self.current_start_date = start if isinstance(start, dt.date) else None
        self.current_end_date = end if isinstance(end, dt.date) else None
        self.visible_rows = [row for row in self.rows if self._row_in_period(row, start, end)]
        self._update_metrics(self.visible_rows)
        self._update_period_summary_label()
        self._draw_tier_chart(self.visible_rows)
        self._draw_period_chart(self.visible_rows)
        self._refresh_table()
        self.status_var.set(f"표시 중: {len(self.visible_rows)}명 / 전체 {len(self.rows)}명")

    def _update_period_summary_label(self) -> None:
        self.metric_detail_vars["total"].set(self._period_summary_label())

    def _period_summary_label(self) -> str:
        start = self.current_start_date
        end = self.current_end_date
        if start and end:
            return f"{start:%Y/%m/%d} - {end:%Y/%m/%d}"
        if start:
            return f"{start:%Y/%m/%d} 이후"
        if end:
            return f"{end:%Y/%m/%d}까지"
        return "전체 기간"

    def _start_loading(self, context: str) -> None:
        self.is_running = True
        self.loading_context = context
        self.loading_frame_index = 0
        if hasattr(self, "refresh_button"):
            self.refresh_button.configure(state=tk.DISABLED)
        if hasattr(self, "patreon_refresh_button"):
            self.patreon_refresh_button.configure(state=tk.DISABLED)
        self._animate_loading_button()

    def _animate_loading_button(self) -> None:
        if not self.loading_context:
            return
        frame = LOADING_FRAMES[self.loading_frame_index % len(LOADING_FRAMES)]
        self.loading_frame_index += 1
        if self.loading_context == "gmail" and hasattr(self, "refresh_button"):
            self.refresh_button.configure(text=f"{frame}  Gmail 불러오는 중...")
        elif self.loading_context == "patreon" and hasattr(self, "patreon_refresh_button"):
            self.patreon_refresh_button.configure(text=f"{frame}  Patreon 불러오는 중...")
        self.loading_after_id = self.after(160, self._animate_loading_button)

    def _stop_loading(self) -> None:
        if self.loading_after_id is not None:
            try:
                self.after_cancel(self.loading_after_id)
            except tk.TclError:
                pass
            self.loading_after_id = None
        self.loading_context = None
        self.loading_frame_index = 0
        self.is_running = False
        if hasattr(self, "refresh_button"):
            self.refresh_button.configure(text=GMAIL_REFRESH_TEXT, state=tk.NORMAL)
        if hasattr(self, "patreon_refresh_button"):
            self.patreon_refresh_button.configure(text=PATREON_REFRESH_TEXT, state=tk.NORMAL)

    def refresh_from_gmail(self) -> None:
        if self.is_running:
            return
        if not CREDENTIALS_PATH.exists():
            messagebox.showwarning(
                "credentials.json 필요",
                f"Gmail API JSON 파일을 여기에 넣어야 합니다.\n\n{CREDENTIALS_PATH}",
            )
            return
        start_text, end_text = self._gmail_query_date_texts()
        if start_text == "invalid" or end_text == "invalid":
            messagebox.showwarning("날짜 형식", "날짜는 YYYY/MM/DD 또는 YYYY-MM-DD 형식으로 입력하세요.")
            return
        self._start_loading("gmail")
        self.status_var.set("Gmail에서 Patreon 가입 메일을 읽는 중입니다.")
        worker = threading.Thread(target=self._gmail_worker, args=(start_text, end_text), daemon=True)
        worker.start()

    def refresh_from_patreon(self) -> None:
        if self.is_running:
            return
        if not PATREON_CREDENTIALS_PATH.exists():
            messagebox.showwarning(
                "Patreon 키 설정 필요",
                "먼저 Patreon 키 설정을 열고 클라이언트 ID, 클라이언트 암호, 액세스 토큰, 새로고침 토큰을 저장하세요.",
            )
            self.open_patreon_settings()
            return
        self._start_loading("patreon")
        self.patreon_status_var.set("Patreon API에서 현재 멤버를 읽는 중입니다.")
        worker = threading.Thread(target=self._patreon_worker, daemon=True)
        worker.start()

    def _gmail_worker(self, start_text: str, end_text: str) -> None:
        try:
            config = load_config(CONFIG_PATH)
            query = build_query(config["gmail_query"], start_text, end_text)
            rate_provider = RateProvider(
                cache_path=CACHE_PATH,
                fallback_rates=parse_decimal_map(config.get("fallback_rates_to_usd", {})),
                exchange_mode="email-date",
            )
            excluded_emails = {email.lower() for email in config.get("excluded_emails", [])}
            records = []
            seen = set()
            for message in read_gmail_messages(
                credentials_path=CREDENTIALS_PATH,
                token_path=TOKEN_PATH,
                query=query,
                limit=0,
                include_spam_trash=False,
            ):
                dedupe_key = message.message_id or message.gmail_id or f"{message.subject}:{message.received_at}"
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                record = parse_member_record(message, config, rate_provider, excluded_emails)
                if record is not None:
                    records.append(record)
            records.sort(key=lambda item: item.received_at, reverse=True)
            write_csv(CSV_PATH, records)
            write_xlsx(XLSX_PATH, records)
            write_html_report(HTML_PATH, records)
            rows = [record.as_row() for record in records]
            self.worker_queue.put(("success", rows))
        except Exception:
            error_text = traceback.format_exc()
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUTPUT_DIR / "gui_error.log").write_text(error_text, encoding="utf-8")
            self.worker_queue.put(("error", error_text))

    def _patreon_worker(self) -> None:
        try:
            client = PatreonClient(PATREON_CREDENTIALS_PATH)
            campaigns = client.get_campaigns()
            if not campaigns:
                raise PatreonApiError("No Patreon campaigns were returned for this token.")
            campaign = campaigns[0]
            rows = client.get_members(campaign["id"])
            write_patreon_members_csv(PATREON_MEMBERS_CSV_PATH, rows)
            self.worker_queue.put(("patreon_success", {"campaign": campaign, "rows": rows}))
        except Exception:
            error_text = traceback.format_exc()
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUTPUT_DIR / "patreon_api_error.log").write_text(error_text, encoding="utf-8")
            self.worker_queue.put(("patreon_error", error_text))

    def _poll_worker_queue(self) -> None:
        try:
            while True:
                event, payload = self.worker_queue.get_nowait()
                self._stop_loading()
                if event == "success":
                    self.rows = list(payload)  # type: ignore[arg-type]
                    self.apply_filters()
                    self.status_var.set("Gmail 동기화 완료")
                    messagebox.showinfo("완료", f"{len(self.rows)}명의 Patreon 가입자를 불러왔습니다.")
                elif event == "error":
                    self.status_var.set("오류가 발생했습니다.")
                    messagebox.showerror(
                        "오류",
                        "작업 중 오류가 발생했습니다.\n\n자세한 내용은 output\\gui_error.log를 확인하세요.",
                    )
                elif event == "patreon_success":
                    payload_dict = dict(payload)  # type: ignore[arg-type]
                    self.patreon_rows = list(payload_dict["rows"])
                    self._set_patreon_rows(self.patreon_rows)
                    campaign = payload_dict["campaign"]
                    self.patreon_status_var.set(
                        f"Patreon 동기화 완료: {campaign.get('creation_name') or campaign.get('id')} / {len(self.patreon_rows)}명"
                    )
                    messagebox.showinfo("완료", f"Patreon 현재 멤버 {len(self.patreon_rows)}명을 불러왔습니다.")
                elif event == "patreon_error":
                    self.patreon_status_var.set("Patreon API 오류가 발생했습니다.")
                    messagebox.showerror(
                        "Patreon API 오류",
                        "Patreon API 작업 중 오류가 발생했습니다.\n\n자세한 내용은 output\\patreon_api_error.log를 확인하세요.",
                    )
        except queue.Empty:
            pass
        self.after(200, self._poll_worker_queue)

    def _update_metrics(self, rows: list[dict[str, str]]) -> None:
        counts = self._tier_counts(rows)
        self.metric_vars["total"].set(str(len(rows)))
        self.metric_vars["rejoin"].set(str(sum(1 for row in rows if self._is_rejoin_row(row))))
        self.metric_vars["tier1"].set(str(counts["1"]))
        self.metric_vars["tier2"].set(str(counts["2"]))
        self.metric_vars["tier3"].set(str(counts["3"]))
        self.metric_vars["tier4"].set(str(counts["4"]))
        self.metric_vars["review"].set(str(counts["needs_review"]))

    def _set_rejoin_cache(self, rows: list[dict[str, str]]) -> None:
        entries: list[tuple[dt.datetime, str, dict[str, str]]] = []
        for row in rows:
            identity = self._member_identity(row)
            if not identity:
                continue
            entries.append((self._row_datetime(row) or dt.datetime.min, identity, row))
        seen: set[str] = set()
        rejoin_keys: set[tuple[str, str, str, str]] = set()
        for _received_at, identity, row in sorted(entries, key=lambda item: item[0]):
            if identity in seen:
                rejoin_keys.add(self._row_identity_key(row))
            else:
                seen.add(identity)
        self.rejoin_row_keys = rejoin_keys

    def _member_identity(self, row: dict[str, str]) -> str:
        email = row.get("member_email", "").strip().lower()
        if email:
            return f"email:{email}"
        name = row.get("member_name", "").strip().lower()
        return f"name:{name}" if name else ""

    def _row_identity_key(self, row: dict[str, str]) -> tuple[str, str, str, str]:
        return (
            self._member_identity(row),
            row.get("received_at", ""),
            row.get("member_email", "").strip().lower(),
            row.get("member_name", "").strip().lower(),
        )

    def _is_rejoin_row(self, row: dict[str, str]) -> bool:
        return self._row_identity_key(row) in self.rejoin_row_keys

    def _refresh_table(self) -> None:
        rows = self._filtered_table_rows()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, row in enumerate(rows):
            tags = []
            if index % 2:
                tags.append("alt")
            if self._is_rejoin_row(row):
                tags.append("rejoin")
            if not row.get("tier") or row.get("confidence") == "needs_review":
                tags.append("needs_review")
            self.tree.insert(
                "",
                tk.END,
                values=[self._table_value(row, column) for column, _, _ in TABLE_COLUMNS],
                tags=tuple(tags),
            )
        self.count_var.set(f"{len(rows)}명")

    def _set_patreon_rows(self, rows: list[dict[str, str]]) -> None:
        self._refresh_patreon_headings()
        display_rows = self._sorted_patreon_rows(rows)
        for item in self.patreon_tree.get_children():
            self.patreon_tree.delete(item)
        for index, row in enumerate(display_rows):
            tags = []
            if index % 2:
                tags.append("alt")
            if row.get("patron_status") == "declined_patron":
                tags.append("declined")
            self.patreon_tree.insert(
                "",
                tk.END,
                values=[self._patreon_table_value(row, column) for column, _, _ in PATREON_TABLE_COLUMNS],
                tags=tuple(tags),
            )
        counts = self._patreon_status_counts(rows)
        self.patreon_metric_vars["total"].set(str(len(rows)))
        self.patreon_metric_vars["active"].set(str(counts["active_patron"]))
        self.patreon_metric_vars["declined"].set(str(counts["declined_patron"]))
        self.patreon_metric_vars["former"].set(str(counts["former_patron"]))

    def _sort_patreon_by_column(self, column: str) -> None:
        if self.patreon_sort_column == column:
            self.patreon_sort_descending = not self.patreon_sort_descending
        else:
            self.patreon_sort_column = column
            self.patreon_sort_descending = False
        self._set_patreon_rows(self.patreon_rows)

    def _refresh_patreon_headings(self) -> None:
        if not hasattr(self, "patreon_tree"):
            return
        marker = " ▼" if self.patreon_sort_descending else " ▲"
        for column, label, _width in PATREON_TABLE_COLUMNS:
            text = f"{label}{marker}" if column == self.patreon_sort_column else label
            self.patreon_tree.heading(
                column,
                text=text,
                command=lambda selected=column: self._sort_patreon_by_column(selected),
            )

    def _sorted_patreon_rows(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        column = self.patreon_sort_column
        if not column:
            return list(rows)
        filled: list[dict[str, str]] = []
        empty: list[dict[str, str]] = []
        for row in rows:
            if row.get(column, "").strip():
                filled.append(row)
            else:
                empty.append(row)
        filled.sort(key=lambda row: self._patreon_sort_value(row, column), reverse=self.patreon_sort_descending)
        return filled + empty

    def _patreon_sort_value(self, row: dict[str, str], column: str) -> object:
        value = row.get(column, "").strip()
        if column == "currently_entitled_amount_cents":
            try:
                return float(value.replace(",", ""))
            except ValueError:
                return 0.0
        if column in {"last_charge_date", "pledge_relationship_start"}:
            return self._parse_patreon_datetime(value) or dt.datetime.min
        if column == "tier_title":
            return self._patreon_tier_sort_value(value)
        return self._patreon_table_value(row, column).casefold()

    def _parse_patreon_datetime(self, value: str) -> dt.datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = dt.datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    def _patreon_tier_sort_value(self, value: str) -> tuple[int, str]:
        normalized = value.strip().casefold()
        if normalized == "free":
            return (0, normalized)
        if normalized.startswith("tier "):
            suffix = normalized.removeprefix("tier ").strip()
            if suffix.isdigit():
                return (int(suffix), normalized)
        return (999, normalized)

    def _patreon_table_value(self, row: dict[str, str], column: str) -> str:
        value = row.get(column, "")
        if column == "patron_status":
            return {
                "active_patron": "활성",
                "declined_patron": "결제 실패",
                "former_patron": "이전 회원",
            }.get(value, value)
        if column == "tier_title":
            if value == "Free":
                return "무료"
            if value.startswith("Tier "):
                return value.replace("Tier ", "티어 ")
            return value
        if column == "last_charge_status":
            return {
                "Paid": "결제 완료",
                "Declined": "결제 실패",
                "Pending": "대기 중",
                "Refunded": "환불",
            }.get(value, value)
        return value

    def _patreon_status_counts(self, rows: list[dict[str, str]]) -> dict[str, int]:
        counts = {"active_patron": 0, "declined_patron": 0, "former_patron": 0}
        for row in rows:
            status = row.get("patron_status", "")
            if status in counts:
                counts[status] += 1
        return counts

    def open_patreon_settings(self) -> None:
        credentials = load_patreon_credentials(PATREON_CREDENTIALS_PATH)
        dialog = tk.Toplevel(self)
        dialog.title("Patreon API 키 설정")
        dialog.geometry("760x460")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=self.palette["bg"])
        self._apply_window_chrome(dialog)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="클라이언트 암호, 액세스 토큰, 새로고침 토큰은 비밀번호처럼 보관됩니다.",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 12))
        fields = [
            ("클라이언트 ID", "client_id", credentials.client_id, False),
            ("클라이언트 암호", "client_secret", credentials.client_secret, True),
            ("액세스 토큰", "access_token", credentials.access_token, True),
            ("새로고침 토큰", "refresh_token", credentials.refresh_token, True),
        ]
        variables: dict[str, tk.StringVar] = {}
        for label, key, value, secret in fields:
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=6)
            ttk.Label(row, text=label, width=16).pack(side=tk.LEFT)
            var = tk.StringVar(value=value)
            variables[key] = var
            entry = ttk.Entry(row, textvariable=var, show="*" if secret else "", width=82)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def save() -> None:
            new_credentials = PatreonCredentials(
                client_id=variables["client_id"].get().strip(),
                client_secret=variables["client_secret"].get().strip(),
                access_token=variables["access_token"].get().strip(),
                refresh_token=variables["refresh_token"].get().strip(),
            )
            if not new_credentials.is_complete():
                messagebox.showwarning("입력 필요", "네 가지 값을 모두 입력해야 합니다.")
                return
            save_patreon_credentials(PATREON_CREDENTIALS_PATH, new_credentials)
            self.patreon_status_var.set("Patreon API 키를 저장했습니다.")
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(buttons, text="저장", style="Accent.TButton", command=save).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="취소", command=dialog.destroy).pack(side=tk.RIGHT, padx=(0, 8))

    def _filtered_table_rows(self) -> list[dict[str, str]]:
        rows = self.visible_rows
        search = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        if search:
            rows = [
                row
                for row in rows
                if search in row.get("member_name", "").lower()
                or search in row.get("member_email", "").lower()
                or search in row.get("subject", "").lower()
            ]
        selected = self.tier_filter_var.get()
        if selected not in {"전체", "전체 티어", "All Tiers"}:
            if selected in {"확인필요", "확인 필요", "Needs Check"}:
                rows = [row for row in rows if not row.get("tier")]
            else:
                tier = selected.replace("티어 ", "").replace("Tier ", "")
                rows = [row for row in rows if row.get("tier") == tier]
        status = self.status_filter_var.get() if hasattr(self, "status_filter_var") else "상태: 전체"
        if status not in {"Status: All", "상태: 전체", "전체"}:
            if status in {"재구독", "Rejoined"}:
                rows = [row for row in rows if self._is_rejoin_row(row)]
            elif status in {"확인 필요", "Needs Check"}:
                rows = [row for row in rows if not row.get("tier") or row.get("confidence") == "needs_review"]
            else:
                status = {
                    "Active Paid": "유료 활성",
                    "Payment Completed": "결제 완료",
                    "Gift (Other)": "선물 (타인)",
                    "Gift (Self)": "선물 (본인)",
                }.get(status, status)
                rows = [row for row in rows if self._payment_status_label(row) == status]
        return rows

    def _table_value(self, row: dict[str, str], column: str) -> str:
        if column == "event_type":
            return "재구독" if self._is_rejoin_row(row) else "신규 가입"
        if column == "membership_tier":
            return self._membership_tier_label(row)
        if column == "billing_cycle":
            return self._billing_cycle_label(row)
        if column == "payment_status":
            return self._payment_status_label(row)
        if column == "conversion_path":
            return self._conversion_path_label(row)
        return row.get(column, "")

    def _membership_tier_label(self, row: dict[str, str]) -> str:
        tier = row.get("tier", "")
        if tier in {"1", "2", "3", "4"}:
            return f"티어 {tier}"
        return "확인 필요"

    def _billing_cycle_label(self, row: dict[str, str]) -> str:
        subject = row.get("subject", "").lower()
        if "annual" in subject or "yearly" in subject or "연간" in subject:
            return "연간"
        return "월간"

    def _payment_status_label(self, row: dict[str, str]) -> str:
        text = f"{row.get('subject', '')} {row.get('match_method', '')} {row.get('confidence', '')}".lower()
        if "gift" in text or "선물" in text:
            if "self" in text or "본인" in text:
                return "선물 (본인)"
            return "선물 (타인)"
        if row.get("confidence") == "needs_review":
            return "결제 완료"
        return "유료 활성"

    def _conversion_path_label(self, row: dict[str, str]) -> str:
        sender = row.get("from", "").lower()
        if "patreon" in sender:
            return "Gmail"
        return "기타"

    def _draw_tier_chart(self, rows: list[dict[str, str]]) -> None:
        chart = self.tier_chart
        p = self.palette
        chart.configure(bg=p["panel"])
        chart.delete("all")
        counts = self._tier_counts(rows)
        data = [
            (1, "티어 1", counts["1"], p[TIER_COLORS["1"]]),
            (2, "티어 2", counts["2"], p[TIER_COLORS["2"]]),
            (3, "티어 3", counts["3"], p[TIER_COLORS["3"]]),
            (4, "티어 4", counts["4"], p[TIER_COLORS["4"]]),
        ]
        if self.tier_sort_var.get() == "멤버순":
            data.sort(key=lambda item: (-item[2], item[0]))
        else:
            data.sort(key=lambda item: item[0])
        width = max(chart.winfo_width(), 420)
        height = max(chart.winfo_height(), 300)
        max_count = max([count for _tier, _label, count, _color in data] + [1])
        left = 140
        right_pad = 70
        bar_w = max(160, width - left - right_pad)
        top = 28
        row_h = max(52, min(70, (height - 44) // max(1, len(data))))
        chart.create_line(0, 0, width, 0, fill=p["line"])
        for index, (_tier, label, count, color) in enumerate(data):
            y = top + index * row_h
            fill_width = int(bar_w * (count / max_count)) if max_count else 0
            chart.create_text(0, y + 17, text=label, anchor=tk.W, fill=p["ink"], font=("Segoe UI", 11))
            chart.create_rectangle(left, y, left + bar_w, y + 34, fill=p["track"], outline="")
            if count:
                chart.create_rectangle(left, y, left + max(fill_width, 5), y + 34, fill=color, outline="")
            chart.create_text(left + bar_w + 18, y + 17, text=str(count), anchor=tk.W, fill=p["ink"], font=("Segoe UI", 13, "bold"))
        if not rows:
            chart.create_text(
                width / 2,
                height / 2,
                text="표시할 데이터가 없습니다.",
                anchor=tk.CENTER,
                fill=p["muted"],
                font=("Segoe UI", 10),
            )

    def _draw_period_chart(self, rows: list[dict[str, str]]) -> None:
        chart = self.period_chart
        p = self.palette
        chart.configure(bg=p["panel"])
        chart.delete("all")
        series = self._insight_series()
        group = self.group_var.get()
        buckets = self._period_buckets(rows, group, series)
        width = max(chart.winfo_width(), 840)
        height = max(chart.winfo_height(), 500)
        left = 58
        right = 50
        top = 34
        card_h = 98
        bottom = 126 + card_h
        plot_w = width - left - right
        plot_h = height - top - bottom
        if plot_h < 160:
            plot_h = 160
        y_bottom = top + plot_h
        chart.create_line(left, y_bottom, left + plot_w, y_bottom, fill=p["line"])
        chart.create_line(left, top, left, y_bottom, fill=p["line"])

        if not buckets:
            chart.create_text(
                width / 2,
                top + plot_h / 2,
                text="선택한 기간에 표시할 데이터가 없습니다.",
                anchor=tk.CENTER,
                fill=p["muted"],
                font=("Malgun Gothic", 10),
            )
        else:
            max_total = max(
                [value for _label, _date, values in buckets for value in values.values()] + [1]
            )
            series_count = max(1, len(series))
            series_gap = 3 if series_count > 1 else 0
            if len(buckets) <= 8:
                bar_w = 30 if series_count == 1 else max(8, min(22, 54 / series_count))
                actual_group_w = bar_w * series_count + series_gap * (series_count - 1)
                label_slot_min = 126 if group in {"매월", "Monthly"} else 88
                natural_slot_w = max(label_slot_min, actual_group_w + 46)
                if natural_slot_w * len(buckets) > plot_w:
                    slot_w = max(actual_group_w + 24, plot_w / max(1, len(buckets)))
                else:
                    slot_w = natural_slot_w
                plot_start = left + max(0, (plot_w - slot_w * len(buckets)) / 2)
            else:
                slot_w = plot_w / max(1, len(buckets))
                group_gap = 8
                group_w = max(8, slot_w - group_gap)
                bar_w = max(3, min(40, (group_w - series_gap * (series_count - 1)) / series_count))
                actual_group_w = bar_w * series_count + series_gap * (series_count - 1)
                plot_start = left
            for index, (label, _key_date, values) in enumerate(buckets):
                slot_x = plot_start + index * slot_w
                group_x = slot_x + (slot_w - actual_group_w) / 2
                for series_index, (key, _series_label, color) in enumerate(series):
                    value = values.get(key, 0)
                    if not value:
                        continue
                    x = group_x + series_index * (bar_w + series_gap)
                    segment_h = max(2, plot_h * (value / max_total))
                    chart.create_rectangle(
                        x,
                        y_bottom - segment_h,
                        x + bar_w,
                        y_bottom,
                        fill=color,
                        outline=p["panel"],
                    )
                if len(buckets) <= 18 or index % max(1, len(buckets) // 8) == 0:
                    label_x = slot_x + slot_w / 2
                    chart.create_line(label_x, y_bottom, label_x, y_bottom + 8, fill=p["line"])
                    chart.create_text(
                        label_x,
                        y_bottom + 22,
                        text=label,
                        anchor=tk.N,
                        fill=p["muted"],
                        font=("Malgun Gothic", 9),
                    )

            for ratio in [0, 0.5, 1.0]:
                y = y_bottom - plot_h * ratio
                value = max_total * ratio
                label = f"{value:.1f}" if value and value != int(value) else str(int(value))
                chart.create_line(left - 4, y, left + plot_w, y, fill=p["line"])
                chart.create_text(left + plot_w + 12, y, text=label, anchor=tk.W, fill=p["muted"], font=("Malgun Gothic", 9))

        self._draw_insight_cards(chart, rows, series, left, y_bottom + 76, width - left - right)

    def _draw_insight_cards(
        self,
        chart: tk.Canvas,
        rows: list[dict[str, str]],
        series: list[tuple[str, str, str]],
        left: int,
        top: float,
        available_w: int,
    ) -> None:
        p = self.palette
        counts = {key: 0 for key, _label, _color in series}
        for row in rows:
            key = self._series_key_for_row(row, self.insight_dimension_var.get())
            if key in counts:
                counts[key] += 1
        card_gap = 12
        card_w = min(220, max(150, (available_w - card_gap * (len(series) - 1)) / max(1, len(series))))
        for index, (key, label, color) in enumerate(series):
            x = left + index * (card_w + card_gap)
            if x + card_w > left + available_w + 1:
                break
            chart.create_rectangle(x, top, x + card_w, top + 88, fill=p["panel_alt"], outline=p["muted"], width=1)
            chart.create_rectangle(x + 14, top + 22, x + 26, top + 34, fill=color, outline=color)
            chart.create_text(x + 34, top + 28, text=label, anchor=tk.W, fill=p["muted"], font=("Malgun Gothic", 10))
            chart.create_text(x + 14, top + 58, text=str(counts.get(key, 0)), anchor=tk.W, fill=p["ink"], font=("Malgun Gothic", 16, "bold"))

    def _period_buckets(
        self,
        rows: list[dict[str, str]],
        group: str,
        series: list[tuple[str, str, str]],
    ) -> list[tuple[str, dt.date, dict[str, int]]]:
        buckets: dict[str, dict[str, int]] = {}
        order: dict[str, dt.date] = {}
        series_keys = [key for key, _label, _color in series]
        start, end = self._bucket_bounds(rows)
        if start and end:
            for label, key_date in self._bucket_labels_between(start, end, group):
                buckets[label] = {key: 0 for key in series_keys}
                order[label] = key_date
        for row in rows:
            row_date = self._row_date(row)
            if not row_date:
                continue
            label, key_date = self._bucket_label(row_date, group)
            if label not in buckets:
                buckets[label] = {key: 0 for key in series_keys}
                order[label] = key_date
            bucket_key = self._series_key_for_row(row, self.insight_dimension_var.get())
            if bucket_key in buckets[label]:
                buckets[label][bucket_key] += 1
        return [(label, order[label], buckets[label]) for label in sorted(buckets, key=lambda item: order[item])]

    def _insight_series(self) -> list[tuple[str, str, str]]:
        dimension = self.insight_dimension_var.get()
        if dimension in {"재구독", "Rejoins"}:
            return [
                ("rejoin", "재구독", SERIES_COLORS[1]),
            ]
        if dimension in {"멤버십 등급", "Membership Tier"}:
            return [
                ("tier_1", "티어 1", SERIES_COLORS[1]),
                ("tier_2", "티어 2", SERIES_COLORS[0]),
                ("tier_3", "티어 3", SERIES_COLORS[2]),
                ("tier_4", "티어 4", SERIES_COLORS[3]),
                ("tier_review", "확인 필요", SERIES_COLORS[4]),
            ]
        if dimension in {"청구 주기", "Billing Cycle"}:
            return [
                ("monthly", "월간", SERIES_COLORS[0]),
                ("annual", "연간", SERIES_COLORS[1]),
            ]
        if dimension in {"결제 상태", "Payment Status"}:
            return [
                ("paid_active", "유료 활성", SERIES_COLORS[0]),
                ("retry_complete", "결제 완료", SERIES_COLORS[1]),
                ("gift_other", "선물 (타인)", SERIES_COLORS[2]),
                ("gift_self", "선물 (본인)", SERIES_COLORS[3]),
            ]
        if dimension in {"유료 전환 경로", "유료로 전환하는 경로", "Paid Path"}:
            return [
                ("email", "Gmail", SERIES_COLORS[0]),
                ("other_path", "기타", SERIES_COLORS[1]),
            ]
        return [("new_member", "신규 회원", SERIES_COLORS[0])]

    def _series_key_for_row(self, row: dict[str, str], dimension: str) -> str:
        if dimension in {"재구독", "Rejoins"}:
            return "rejoin" if self._is_rejoin_row(row) else "first_pledge"
        if dimension in {"멤버십 등급", "Membership Tier"}:
            tier = row.get("tier", "")
            return f"tier_{tier}" if tier in {"1", "2", "3", "4"} else "tier_review"
        if dimension in {"청구 주기", "Billing Cycle"}:
            return "annual" if self._billing_cycle_label(row) in {"연간", "Annual"} else "monthly"
        if dimension in {"결제 상태", "Payment Status"}:
            status = self._payment_status_label(row)
            if status in {"결제 완료", "Payment Completed"}:
                return "retry_complete"
            if status in {"선물 (타인)", "Gift (Other)"}:
                return "gift_other"
            if status in {"선물 (본인)", "Gift (Self)"}:
                return "gift_self"
            return "paid_active"
        if dimension in {"유료 전환 경로", "유료로 전환하는 경로", "Paid Path"}:
            return "email" if self._conversion_path_label(row) == "Gmail" else "other_path"
        return "new_member"

    def _bucket_bounds(self, rows: list[dict[str, str]]) -> tuple[dt.date | None, dt.date | None]:
        row_dates = [row_date for row in rows if (row_date := self._row_date(row))]
        start = self.current_start_date or (min(row_dates) if row_dates else None)
        end = self.current_end_date or (max(row_dates) if row_dates else None)
        if start and end and start > end:
            return end, start
        return start, end

    def _bucket_labels_between(self, start: dt.date, end: dt.date, group: str) -> list[tuple[str, dt.date]]:
        labels: list[tuple[str, dt.date]] = []
        if group in {"매일", "Daily"}:
            if (end - start).days > 400:
                start = end - dt.timedelta(days=400)
            current = start
            while current <= end:
                labels.append(self._bucket_label(current, group))
                current += dt.timedelta(days=1)
            return labels
        if group in {"매주", "Weekly"}:
            year, week, _weekday = start.isocalendar()
            current = dt.date.fromisocalendar(year, week, 1)
            while current <= end:
                labels.append(self._bucket_label(current, group))
                current += dt.timedelta(days=7)
            return labels
        current = dt.date(start.year, start.month, 1)
        while current <= end:
            labels.append(self._bucket_label(current, group))
            if current.month == 12:
                current = dt.date(current.year + 1, 1, 1)
            else:
                current = dt.date(current.year, current.month + 1, 1)
        return labels

    def _bucket_label(self, row_date: dt.date, group: str) -> tuple[str, dt.date]:
        if group in {"매일", "Daily"}:
            return row_date.strftime("%m. %d."), row_date
        if group in {"매주", "Weekly"}:
            year, week, _weekday = row_date.isocalendar()
            key_date = dt.date.fromisocalendar(year, week, 1)
            return key_date.strftime("%m. %d."), key_date
        key_date = dt.date(row_date.year, row_date.month, 1)
        return key_date.strftime("%Y-%m"), key_date

    def _tier_counts(self, rows: list[dict[str, str]]) -> dict[str, int]:
        counts = {"1": 0, "2": 0, "3": 0, "4": 0, "needs_review": 0}
        for row in rows:
            tier = row.get("tier", "")
            if tier in {"1", "2", "3", "4"}:
                counts[tier] += 1
            else:
                counts["needs_review"] += 1
        return counts

    def _row_in_period(self, row: dict[str, str], start: dt.date | None | str, end: dt.date | None | str) -> bool:
        row_date = self._row_date(row)
        if row_date is None:
            return True
        if isinstance(start, dt.date) and row_date < start:
            return False
        if isinstance(end, dt.date) and row_date > end:
            return False
        return True

    def _row_date(self, row: dict[str, str]) -> dt.date | None:
        row_datetime = self._row_datetime(row)
        return row_datetime.date() if row_datetime else None

    def _row_datetime(self, row: dict[str, str]) -> dt.datetime | None:
        value = row.get("received_at", "")
        if not value:
            return None
        try:
            parsed = dt.datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    def _parse_date_text(self, value: str) -> dt.date | None | str:
        if not value:
            return None
        normalized = value.replace("-", "/")
        try:
            return dt.datetime.strptime(normalized, "%Y/%m/%d").date()
        except ValueError:
            return "invalid"

    def _apply_range_preset_to_entries(self) -> None:
        preset = self.range_var.get()
        start, end = self._range_dates(preset)
        if preset != "사용자 지정":
            self.after_var.set("" if start is None else start.strftime("%Y/%m/%d"))
            self.before_var.set("" if end is None else end.strftime("%Y/%m/%d"))
        state = tk.NORMAL if preset == "사용자 지정" else "readonly"
        if hasattr(self, "after_entry"):
            try:
                if self.after_entry.winfo_exists():
                    self.after_entry.configure(state=state)
            except tk.TclError:
                pass
        if hasattr(self, "before_entry"):
            try:
                if self.before_entry.winfo_exists():
                    self.before_entry.configure(state=state)
            except tk.TclError:
                pass

    def _range_dates(self, preset: str) -> tuple[dt.date | None | str, dt.date | None | str]:
        today = dt.date.today()
        if preset == "지난 30일":
            return today - dt.timedelta(days=29), today
        if preset in {"반년", "지난 6개월"}:
            return add_months(today, -6), today
        if preset in {"1년", "지난 1년", "지난 12개월"}:
            return add_months(today, -12), today
        if preset == "전체":
            return None, None
        return self._parse_custom_range_dates()

    def _parse_custom_range_dates(self) -> tuple[dt.date | None | str, dt.date | None | str]:
        start = self._parse_date_text(self.after_var.get().strip())
        end = self._parse_date_text(self.before_var.get().strip())
        return start, end

    def _gmail_query_date_texts(self) -> tuple[str, str]:
        if self.range_var.get() != "사용자 지정":
            self._apply_range_preset_to_entries()
        start = self._parse_date_text(self.after_var.get().strip())
        end = self._parse_date_text(self.before_var.get().strip())
        if start == "invalid" or end == "invalid":
            return "invalid", "invalid"
        after_text = start.strftime("%Y/%m/%d") if isinstance(start, dt.date) else ""
        if isinstance(end, dt.date):
            before_text = (end + dt.timedelta(days=1)).strftime("%Y/%m/%d")
        else:
            before_text = ""
        return after_text, before_text

    def open_output_folder(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(OUTPUT_DIR)])

    def open_patreon_csv(self) -> None:
        if PATREON_MEMBERS_CSV_PATH.exists():
            subprocess.Popen(["explorer", str(PATREON_MEMBERS_CSV_PATH)])
        else:
            messagebox.showinfo("파일 없음", "아직 Patreon API CSV가 없습니다.")

    def open_config(self) -> None:
        if not CONFIG_PATH.exists():
            load_config(CONFIG_PATH)
        subprocess.Popen(["notepad", str(CONFIG_PATH)])


def main() -> int:
    configure_windows_process()
    app = PatreonMemberApp()
    app.mainloop()
    return 0


def configure_windows_process() -> None:
    global _WINDOWS_PROCESS_CONFIGURED
    if _WINDOWS_PROCESS_CONFIGURED:
        return
    set_windows_dpi_awareness()
    set_windows_app_id()
    _WINDOWS_PROCESS_CONFIGURED = True


def set_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except Exception:
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            pass
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    except Exception:
        pass


def set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("lim3874.PatreonChart.MemberExporter")
    except Exception:
        pass


def set_windows_window_theme(window: tk.Tk | tk.Toplevel, dark_mode: bool, palette: dict[str, str]) -> int:
    if sys.platform != "win32":
        return 0
    try:
        import ctypes

        handles = get_windows_toplevel_handles(window, ctypes)
        enabled = ctypes.c_int(1 if dark_mode else 0)
        caption_color = ctypes.c_int(hex_to_colorref(palette.get("topbar", palette.get("bg", "#ffffff"))))
        text_color = ctypes.c_int(hex_to_colorref(palette.get("ink", "#000000")))
        border_color = ctypes.c_int(hex_to_colorref(palette.get("line", "#000000")))
        applied = 0
        for hwnd in handles:
            hwnd_arg = ctypes.c_void_p(hwnd)
            for attribute in (20, 19):
                result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd_arg,
                    ctypes.c_int(attribute),
                    ctypes.byref(enabled),
                    ctypes.sizeof(enabled),
                )
                if result == 0:
                    applied += 1
            for attribute, value in ((35, caption_color), (36, text_color), (34, border_color)):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd_arg,
                    ctypes.c_int(attribute),
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            redraw_windows_frame(hwnd, ctypes)
        return applied
    except Exception:
        return 0


def get_windows_toplevel_handles(window: tk.Tk | tk.Toplevel, ctypes_module: object) -> list[int]:
    handles: list[int] = []

    def add_handle(value: object) -> None:
        try:
            hwnd = int(value)
        except (TypeError, ValueError):
            try:
                hwnd = int(str(value), 0)
            except (TypeError, ValueError):
                return
        if hwnd and hwnd not in handles:
            handles.append(hwnd)

    add_handle(window.winfo_id())
    try:
        add_handle(window.tk.call("wm", "frame", window._w))
    except tk.TclError:
        pass

    user32 = ctypes_module.windll.user32
    for hwnd in tuple(handles):
        add_handle(user32.GetParent(hwnd))
        add_handle(user32.GetAncestor(hwnd, 2))

    return handles


def redraw_windows_frame(hwnd: int, ctypes_module: object) -> None:
    user32 = ctypes_module.windll.user32
    hwnd_arg = ctypes_module.c_void_p(hwnd)
    swp_nomove = 0x0002
    swp_nosize = 0x0001
    swp_nozorder = 0x0004
    swp_framechanged = 0x0020
    rdw_invalidate = 0x0001
    rdw_updatenow = 0x0100
    rdw_frame = 0x0400
    user32.SetWindowPos(hwnd_arg, None, 0, 0, 0, 0, swp_nomove | swp_nosize | swp_nozorder | swp_framechanged)
    user32.RedrawWindow(hwnd_arg, None, None, rdw_invalidate | rdw_updatenow | rdw_frame)


def hex_to_colorref(value: str) -> int:
    color = value.strip().lstrip("#")
    if len(color) != 6:
        return 0
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    return red | (green << 8) | (blue << 16)


def add_months(value: dt.date, months: int) -> dt.date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, days_in_month(year, month))
    return dt.date(year, month, day)


def days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (dt.date(year, month + 1, 1) - dt.timedelta(days=1)).day


def load_app_settings(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_app_settings(path: Path, settings: dict[str, object]) -> None:
    path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        error_text = traceback.format_exc()
        (OUTPUT_DIR / "gui_error.log").write_text(error_text, encoding="utf-8")
        try:
            messagebox.showerror(
                "Patreon 가입자 대시보드",
                "프로그램을 시작하지 못했습니다.\n\noutput\\gui_error.log를 확인하세요.",
            )
        except tk.TclError:
            pass
        raise
