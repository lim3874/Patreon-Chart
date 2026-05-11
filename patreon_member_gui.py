from __future__ import annotations

import csv
import datetime as dt
import json
import queue
import subprocess
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

TABLE_COLUMNS = [
    ("event_type", "항목", 110),
    ("received_at", "수신일", 170),
    ("member_name", "이름", 170),
    ("member_email", "이메일", 240),
    ("membership_tier", "멤버십 등급", 120),
    ("billing_cycle", "청구 주기", 100),
    ("payment_status", "결제 상태", 150),
    ("conversion_path", "유료 전환 경로", 140),
    ("original_amount", "원문 금액", 110),
    ("usd_estimate", "USD 추정", 100),
    ("confidence", "판정", 100),
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
    "bg": "#f5f6f8",
    "panel": "#ffffff",
    "panel_alt": "#f0f3f7",
    "ink": "#172033",
    "muted": "#667085",
    "line": "#d9dee8",
    "accent": "#0f766e",
    "accent_2": "#2563eb",
    "accent_3": "#7c3aed",
    "accent_4": "#dc2626",
    "review": "#a16207",
    "track": "#eef2f6",
    "table_review": "#fff7ed",
    "select_bg": "#cce7ff",
    "select_fg": "#172033",
}

DARK_THEME = {
    "bg": "#0f141d",
    "panel": "#171d29",
    "panel_alt": "#202938",
    "ink": "#e5e7eb",
    "muted": "#9ca3af",
    "line": "#2f3a4c",
    "accent": "#2dd4bf",
    "accent_2": "#60a5fa",
    "accent_3": "#a78bfa",
    "accent_4": "#f87171",
    "review": "#fbbf24",
    "track": "#263244",
    "table_review": "#3b2f14",
    "select_bg": "#164e63",
    "select_fg": "#f8fafc",
}

TIER_COLORS = {
    "1": "accent",
    "2": "accent_2",
    "3": "accent_3",
    "4": "accent_4",
    "needs_review": "review",
}

RANGE_PRESETS = ["지난 24시간", "지난 30일", "지난 6개월", "지난 12개월", "전체", "사용자 지정"]
GROUP_OPTIONS = ["매일", "매주", "매월"]
INSIGHT_DIMENSIONS = ["전체", "멤버십 등급", "청구 주기", "결제 상태", "유료로 전환하는 경로"]
SERIES_COLORS = ["#338ccf", "#ffb77c", "#88df3f", "#ffe047", "#a78bfa", "#2dd4bf"]


class PatreonMemberApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Patreon Gmail Member Exporter")
        self.geometry("1220x800")
        self.minsize(1040, 660)

        self.rows: list[dict[str, str]] = []
        self.visible_rows: list[dict[str, str]] = []
        self.patreon_rows: list[dict[str, str]] = []
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.is_running = False

        self.app_settings = load_app_settings(APP_SETTINGS_PATH)
        self.dark_mode_var = tk.BooleanVar(value=bool(self.app_settings.get("dark_mode", False)))
        self.range_var = tk.StringVar(value=str(self.app_settings.get("range_preset", "지난 30일")))
        if self.range_var.get() not in RANGE_PRESETS:
            self.range_var.set("지난 30일")
        self.group_var = tk.StringVar(value=str(self.app_settings.get("group_unit", "매일")))
        if self.group_var.get() not in GROUP_OPTIONS:
            self.group_var.set("매일")
        self.insight_dimension_var = tk.StringVar(value=str(self.app_settings.get("insight_dimension", "결제 상태")))
        if self.insight_dimension_var.get() not in INSIGHT_DIMENSIONS:
            self.insight_dimension_var.set("결제 상태")
        self.tier_filter_var = tk.StringVar(value="전체")
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
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=p["bg"])
        style.configure("Panel.TFrame", background=p["panel"], relief="solid", borderwidth=1)
        style.configure("Subtle.TFrame", background=p["panel_alt"])
        style.configure("TLabel", background=p["bg"], foreground=p["ink"])
        style.configure("Panel.TLabel", background=p["panel"], foreground=p["ink"])
        style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"])
        style.configure("PanelMuted.TLabel", background=p["panel"], foreground=p["muted"])
        style.configure("Title.TLabel", background=p["bg"], foreground=p["ink"], font=("Segoe UI", 18, "bold"))
        style.configure("MetricTitle.TLabel", background=p["panel"], foreground=p["muted"], font=("Segoe UI", 10))
        style.configure("MetricValue.TLabel", background=p["panel"], foreground=p["ink"], font=("Segoe UI", 22, "bold"))
        style.configure("TButton", padding=(12, 7), font=("Segoe UI", 10))
        style.configure("Accent.TButton", padding=(14, 8), font=("Segoe UI", 10, "bold"))
        style.configure("TCheckbutton", background=p["bg"], foreground=p["ink"])
        style.map("TCheckbutton", background=[("active", p["bg"])], foreground=[("active", p["ink"])])
        style.configure("TEntry", fieldbackground=p["panel"], foreground=p["ink"], insertcolor=p["ink"])
        style.configure("TCombobox", fieldbackground=p["panel"], background=p["panel"], foreground=p["ink"])
        style.configure("TNotebook", background=p["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=p["panel_alt"], foreground=p["ink"], padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", p["panel"])], foreground=[("selected", p["ink"])])
        style.configure(
            "Treeview",
            rowheight=30,
            font=("Segoe UI", 10),
            background=p["panel"],
            fieldbackground=p["panel"],
            foreground=p["ink"],
            bordercolor=p["line"],
        )
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background=p["panel_alt"], foreground=p["ink"])
        style.map("Treeview", background=[("selected", p["select_bg"])], foreground=[("selected", p["select_fg"])])

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill=tk.BOTH, expand=True)
        self.root_frame = root

        header = ttk.Frame(root)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Patreon 가입자 대시보드", style="Title.TLabel").pack(side=tk.LEFT)
        right_header = ttk.Frame(header)
        right_header.pack(side=tk.RIGHT)
        ttk.Checkbutton(
            right_header,
            text="다크 모드",
            variable=self.dark_mode_var,
            command=self.toggle_theme,
        ).pack(side=tk.RIGHT, padx=(14, 0))
        self.status_var = tk.StringVar(value="기존 결과를 불러오는 중입니다.")
        ttk.Label(right_header, textvariable=self.status_var, style="Muted.TLabel").pack(side=tk.RIGHT)

        controls = ttk.Frame(root, padding=(0, 14, 0, 10))
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="기간").pack(side=tk.LEFT)
        self.range_box = ttk.Combobox(
            controls,
            textvariable=self.range_var,
            values=RANGE_PRESETS,
            width=13,
            state="readonly",
        )
        self.range_box.pack(side=tk.LEFT, padx=(6, 14))
        self.range_box.bind("<<ComboboxSelected>>", lambda _event: self.on_range_changed())
        ttk.Label(controls, text="시작일").pack(side=tk.LEFT)
        self.after_entry = ttk.Entry(controls, textvariable=self.after_var, width=13)
        self.after_entry.pack(side=tk.LEFT, padx=(6, 14))
        ttk.Label(controls, text="종료일").pack(side=tk.LEFT)
        self.before_entry = ttk.Entry(controls, textvariable=self.before_var, width=13)
        self.before_entry.pack(side=tk.LEFT, padx=(6, 14))
        ttk.Button(controls, text="기간 적용", command=self.apply_filters).pack(side=tk.LEFT, padx=(0, 8))
        self.refresh_button = ttk.Button(
            controls,
            text="Gmail에서 새로 불러오기",
            style="Accent.TButton",
            command=self.refresh_from_gmail,
        )
        self.refresh_button.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(controls, text="결과 폴더", command=self.open_output_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="설정 파일", command=self.open_config).pack(side=tk.LEFT, padx=4)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.summary_tab = ttk.Frame(self.notebook, padding=12)
        self.period_tab = ttk.Frame(self.notebook, padding=12)
        self.table_tab = ttk.Frame(self.notebook, padding=12)
        self.patreon_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.summary_tab, text="요약")
        self.notebook.add(self.period_tab, text="기간별")
        self.notebook.add(self.table_tab, text="목록")
        self.notebook.add(self.patreon_tab, text="Patreon API")

        self._build_summary_tab()
        self._build_period_tab()
        self._build_table_tab()
        self._build_patreon_tab()

    def _build_summary_tab(self) -> None:
        self.metrics_frame = ttk.Frame(self.summary_tab)
        self.metrics_frame.pack(fill=tk.X, pady=(0, 12))
        self.metric_vars = {
            "total": tk.StringVar(value="0"),
            "tier1": tk.StringVar(value="0"),
            "tier2": tk.StringVar(value="0"),
            "tier3": tk.StringVar(value="0"),
            "tier4": tk.StringVar(value="0"),
            "review": tk.StringVar(value="0"),
        }
        for label, key in [
            ("전체", "total"),
            ("티어 1", "tier1"),
            ("티어 2", "tier2"),
            ("티어 3", "tier3"),
            ("티어 4", "tier4"),
            ("확인필요", "review"),
        ]:
            self._metric_card(self.metrics_frame, label, self.metric_vars[key]).pack(
                side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
            )

        chart_panel = ttk.Frame(self.summary_tab, style="Panel.TFrame", padding=16)
        chart_panel.pack(fill=tk.BOTH, expand=True)
        ttk.Label(chart_panel, text="티어 분포", style="Panel.TLabel", font=("Segoe UI", 13, "bold")).pack(anchor=tk.W)
        self.tier_chart = tk.Canvas(chart_panel, height=360, bg=self.palette["panel"], highlightthickness=0)
        self.tier_chart.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.tier_chart.bind("<Configure>", lambda _event: self._draw_tier_chart(self.visible_rows))

    def _build_period_tab(self) -> None:
        top = ttk.Frame(self.period_tab)
        top.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(top, text="신규 회원", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(top, text="집계 단위").pack(side=tk.RIGHT, padx=(12, 0))
        unit_box = ttk.Combobox(
            top,
            textvariable=self.group_var,
            values=GROUP_OPTIONS,
            width=8,
            state="readonly",
        )
        unit_box.pack(side=tk.RIGHT)
        unit_box.bind("<<ComboboxSelected>>", lambda _event: self.on_group_changed())

        panel = ttk.Frame(self.period_tab, style="Panel.TFrame", padding=16)
        panel.pack(fill=tk.BOTH, expand=True)
        self.dimension_frame = ttk.Frame(panel, style="Panel.TFrame")
        self.dimension_frame.pack(fill=tk.X, pady=(0, 12))
        self.dimension_buttons: dict[str, tk.Button] = {}
        for dimension in INSIGHT_DIMENSIONS:
            button = tk.Button(
                self.dimension_frame,
                text=dimension,
                command=lambda value=dimension: self.select_insight_dimension(value),
                bd=0,
                padx=18,
                pady=10,
                font=("Segoe UI", 11, "bold"),
                cursor="hand2",
            )
            button.pack(side=tk.LEFT, padx=(0, 8))
            self.dimension_buttons[dimension] = button
        self._refresh_dimension_buttons()
        self.period_chart = tk.Canvas(panel, height=520, bg=self.palette["panel"], highlightthickness=0)
        self.period_chart.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.period_chart.bind("<Configure>", lambda _event: self._draw_period_chart(self.visible_rows))

    def _build_table_tab(self) -> None:
        top = ttk.Frame(self.table_tab)
        top.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(top, text="티어 필터").pack(side=tk.LEFT)
        tier_box = ttk.Combobox(
            top,
            textvariable=self.tier_filter_var,
            values=["전체", "티어 1", "티어 2", "티어 3", "티어 4", "확인필요"],
            width=10,
            state="readonly",
        )
        tier_box.pack(side=tk.LEFT, padx=(6, 10))
        tier_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_table())
        self.count_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.count_var, style="Muted.TLabel").pack(side=tk.RIGHT)

        table_panel = ttk.Frame(self.table_tab, style="Panel.TFrame", padding=10)
        table_panel.pack(fill=tk.BOTH, expand=True)
        table_wrap = ttk.Frame(table_panel, style="Panel.TFrame")
        table_wrap.pack(fill=tk.BOTH, expand=True)
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
        top = ttk.Frame(self.patreon_tab)
        top.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(top, text="Patreon 키 설정", command=self.open_patreon_settings).pack(side=tk.LEFT, padx=(0, 8))
        self.patreon_refresh_button = ttk.Button(
            top,
            text="Patreon에서 현재 멤버 불러오기",
            style="Accent.TButton",
            command=self.refresh_from_patreon,
        )
        self.patreon_refresh_button.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top, text="Patreon CSV 열기", command=self.open_patreon_csv).pack(side=tk.LEFT, padx=4)
        self.patreon_status_var = tk.StringVar(value="Patreon API 설정 후 현재 멤버를 불러올 수 있습니다.")
        ttk.Label(top, textvariable=self.patreon_status_var, style="Muted.TLabel").pack(side=tk.RIGHT)

        metrics = ttk.Frame(self.patreon_tab)
        metrics.pack(fill=tk.X, pady=(0, 12))
        self.patreon_metric_vars = {
            "total": tk.StringVar(value="0"),
            "active": tk.StringVar(value="0"),
            "declined": tk.StringVar(value="0"),
            "former": tk.StringVar(value="0"),
        }
        for label, key in [
            ("전체 멤버", "total"),
            ("활성", "active"),
            ("결제 실패", "declined"),
            ("이전 멤버", "former"),
        ]:
            self._metric_card(metrics, label, self.patreon_metric_vars[key]).pack(
                side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
            )

        panel = ttk.Frame(self.patreon_tab, style="Panel.TFrame", padding=10)
        panel.pack(fill=tk.BOTH, expand=True)
        table_wrap = ttk.Frame(panel, style="Panel.TFrame")
        table_wrap.pack(fill=tk.BOTH, expand=True)
        self.patreon_tree = ttk.Treeview(
            table_wrap,
            columns=[column for column, _, _ in PATREON_TABLE_COLUMNS],
            show="headings",
            selectmode="browse",
        )
        for column, label, width in PATREON_TABLE_COLUMNS:
            self.patreon_tree.heading(column, text=label)
            self.patreon_tree.column(column, width=width, minwidth=70, anchor=tk.W)
        y_scroll = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.patreon_tree.yview)
        x_scroll = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.patreon_tree.xview)
        self.patreon_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.patreon_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)
        self._load_existing_patreon_csv()

    def _metric_card(self, parent: ttk.Frame, label: str, value_var: tk.StringVar) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        ttk.Label(frame, text=label, style="MetricTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(frame, textvariable=value_var, style="MetricValue.TLabel").pack(anchor=tk.W, pady=(6, 0))
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
        self._draw_period_chart(self.visible_rows)

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
            button.configure(
                bg="#3b3b3d" if selected and self.dark_mode_var.get() else (p["panel_alt"] if selected else p["panel"]),
                fg=p["ink"],
                activebackground=p["panel_alt"],
                activeforeground=p["ink"],
                relief=tk.FLAT,
                highlightthickness=0,
            )

    def _configure_tree_tags(self) -> None:
        if hasattr(self, "tree"):
            self.tree.tag_configure("needs_review", background=self.palette["table_review"], foreground=self.palette["ink"])
        if hasattr(self, "patreon_tree"):
            self.patreon_tree.tag_configure("declined", background=self.palette["table_review"], foreground=self.palette["ink"])

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
        self.current_start_date = start if isinstance(start, dt.date) else None
        self.current_end_date = end if isinstance(end, dt.date) else None
        self.visible_rows = [row for row in self.rows if self._row_in_period(row, start, end)]
        self._update_metrics(self.visible_rows)
        self._draw_tier_chart(self.visible_rows)
        self._draw_period_chart(self.visible_rows)
        self._refresh_table()
        self.status_var.set(f"표시 중: {len(self.visible_rows)}명 / 전체 {len(self.rows)}명")

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
        self.is_running = True
        self.refresh_button.configure(state=tk.DISABLED)
        self.status_var.set("Gmail에서 Patreon 가입 메일을 읽는 중입니다.")
        worker = threading.Thread(target=self._gmail_worker, args=(start_text, end_text), daemon=True)
        worker.start()

    def refresh_from_patreon(self) -> None:
        if self.is_running:
            return
        if not PATREON_CREDENTIALS_PATH.exists():
            messagebox.showwarning(
                "Patreon 키 설정 필요",
                "먼저 Patreon 키 설정을 열고 Client ID, Client Secret, Access Token, Refresh Token을 저장하세요.",
            )
            self.open_patreon_settings()
            return
        self.is_running = True
        self.patreon_refresh_button.configure(state=tk.DISABLED)
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
                self.is_running = False
                self.refresh_button.configure(state=tk.NORMAL)
                if hasattr(self, "patreon_refresh_button"):
                    self.patreon_refresh_button.configure(state=tk.NORMAL)
        except queue.Empty:
            pass
        self.after(200, self._poll_worker_queue)

    def _update_metrics(self, rows: list[dict[str, str]]) -> None:
        counts = self._tier_counts(rows)
        self.metric_vars["total"].set(str(len(rows)))
        self.metric_vars["tier1"].set(str(counts["1"]))
        self.metric_vars["tier2"].set(str(counts["2"]))
        self.metric_vars["tier3"].set(str(counts["3"]))
        self.metric_vars["tier4"].set(str(counts["4"]))
        self.metric_vars["review"].set(str(counts["needs_review"]))

    def _refresh_table(self) -> None:
        rows = self._filtered_table_rows()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            tags = ("needs_review",) if not row.get("tier") or row.get("confidence") == "needs_review" else ()
            self.tree.insert(
                "",
                tk.END,
                values=[self._table_value(row, column) for column, _, _ in TABLE_COLUMNS],
                tags=tags,
            )
        self.count_var.set(f"{len(rows)} rows")

    def _set_patreon_rows(self, rows: list[dict[str, str]]) -> None:
        for item in self.patreon_tree.get_children():
            self.patreon_tree.delete(item)
        for row in rows:
            tags = ("declined",) if row.get("patron_status") == "declined_patron" else ()
            self.patreon_tree.insert(
                "",
                tk.END,
                values=[row.get(column, "") for column, _, _ in PATREON_TABLE_COLUMNS],
                tags=tags,
            )
        counts = self._patreon_status_counts(rows)
        self.patreon_metric_vars["total"].set(str(len(rows)))
        self.patreon_metric_vars["active"].set(str(counts["active_patron"]))
        self.patreon_metric_vars["declined"].set(str(counts["declined_patron"]))
        self.patreon_metric_vars["former"].set(str(counts["former_patron"]))

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
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Client Secret, Access Token, Refresh Token은 비밀번호처럼 보관됩니다.",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 12))
        fields = [
            ("Client ID", "client_id", credentials.client_id, False),
            ("Client Secret", "client_secret", credentials.client_secret, True),
            ("Access Token", "access_token", credentials.access_token, True),
            ("Refresh Token", "refresh_token", credentials.refresh_token, True),
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
        selected = self.tier_filter_var.get()
        if selected == "전체":
            return self.visible_rows
        if selected == "확인필요":
            return [row for row in self.visible_rows if not row.get("tier")]
        tier = selected.replace("티어 ", "")
        return [row for row in self.visible_rows if row.get("tier") == tier]

    def _table_value(self, row: dict[str, str], column: str) -> str:
        if column == "event_type":
            return "신규 회원"
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
        return "확인필요"

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
            return "결제 완료 (재시도)"
        return "유료 (활성 상태)"

    def _conversion_path_label(self, row: dict[str, str]) -> str:
        sender = row.get("from", "").lower()
        if "patreon" in sender:
            return "메일"
        return "기타"

    def _draw_tier_chart(self, rows: list[dict[str, str]]) -> None:
        chart = self.tier_chart
        p = self.palette
        chart.configure(bg=p["panel"])
        chart.delete("all")
        counts = self._tier_counts(rows)
        data = [
            ("티어 1", counts["1"], p[TIER_COLORS["1"]]),
            ("티어 2", counts["2"], p[TIER_COLORS["2"]]),
            ("티어 3", counts["3"], p[TIER_COLORS["3"]]),
            ("티어 4", counts["4"], p[TIER_COLORS["4"]]),
            ("확인필요", counts["needs_review"], p[TIER_COLORS["needs_review"]]),
        ]
        width = max(chart.winfo_width(), 420)
        max_count = max([count for _, count, _ in data] + [1])
        left = 110
        right_pad = 70
        bar_w = max(160, width - left - right_pad)
        top = 34
        row_h = 56
        for index, (label, count, color) in enumerate(data):
            y = top + index * row_h
            fill_width = int(bar_w * (count / max_count)) if max_count else 0
            chart.create_text(18, y + 12, text=label, anchor=tk.W, fill=p["ink"], font=("Segoe UI", 10))
            chart.create_rectangle(left, y, left + bar_w, y + 24, fill=p["track"], outline="")
            if count:
                chart.create_rectangle(left, y, left + max(fill_width, 3), y + 24, fill=color, outline="")
            chart.create_text(left + bar_w + 14, y + 12, text=str(count), anchor=tk.W, fill=p["muted"], font=("Segoe UI", 10))
        if not rows:
            chart.create_text(
                width / 2,
                320,
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
        buckets = self._period_buckets(rows, self.group_var.get(), series)
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
                font=("Segoe UI", 10),
            )
        else:
            max_total = max(sum(values.values()) for _label, _date, values in buckets) or 1
            gap = 8
            bar_w = max(10, min(40, (plot_w - gap * (len(buckets) + 1)) / max(1, len(buckets))))
            step = (plot_w - bar_w) / max(1, len(buckets) - 1)
            for index, (label, _key_date, values) in enumerate(buckets):
                x = left + index * step
                y_base = y_bottom
                for key, _series_label, color in series:
                    value = values.get(key, 0)
                    if not value:
                        continue
                    segment_h = max(2, plot_h * (value / max_total))
                    chart.create_rectangle(
                        x,
                        y_base - segment_h,
                        x + bar_w,
                        y_base,
                        fill=color,
                        outline=p["panel"],
                    )
                    y_base -= segment_h
                if len(buckets) <= 18 or index % max(1, len(buckets) // 8) == 0:
                    chart.create_line(x + bar_w / 2, y_bottom, x + bar_w / 2, y_bottom + 8, fill=p["line"])
                    chart.create_text(
                        x + bar_w / 2,
                        y_bottom + 22,
                        text=label,
                        anchor=tk.N,
                        fill=p["muted"],
                        font=("Segoe UI", 9),
                    )

            for ratio in [0, 0.5, 1.0]:
                y = y_bottom - plot_h * ratio
                value = max_total * ratio
                label = f"{value:.1f}" if value and value != int(value) else str(int(value))
                chart.create_line(left - 4, y, left + plot_w, y, fill=p["line"])
                chart.create_text(left + plot_w + 12, y, text=label, anchor=tk.W, fill=p["muted"], font=("Segoe UI", 9))

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
            chart.create_text(x + 34, top + 28, text=label, anchor=tk.W, fill=p["muted"], font=("Segoe UI", 10))
            chart.create_text(x + 14, top + 58, text=str(counts.get(key, 0)), anchor=tk.W, fill=p["ink"], font=("Segoe UI", 16, "bold"))

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
        if dimension == "멤버십 등급":
            return [
                ("tier_1", "티어 1", SERIES_COLORS[0]),
                ("tier_2", "티어 2", SERIES_COLORS[1]),
                ("tier_3", "티어 3", SERIES_COLORS[2]),
                ("tier_4", "티어 4", SERIES_COLORS[3]),
                ("tier_review", "확인필요", SERIES_COLORS[4]),
            ]
        if dimension == "청구 주기":
            return [
                ("monthly", "월간", SERIES_COLORS[0]),
                ("annual", "연간", SERIES_COLORS[1]),
            ]
        if dimension == "결제 상태":
            return [
                ("paid_active", "유료 (활성 상태)", SERIES_COLORS[0]),
                ("retry_complete", "결제 완료 (재시도)", SERIES_COLORS[1]),
                ("gift_other", "선물 (타인)", SERIES_COLORS[2]),
                ("gift_self", "선물 (본인)", SERIES_COLORS[3]),
            ]
        if dimension == "유료로 전환하는 경로":
            return [
                ("email", "메일", SERIES_COLORS[0]),
                ("other_path", "기타", SERIES_COLORS[1]),
            ]
        return [("new_member", "신규 회원", SERIES_COLORS[0])]

    def _series_key_for_row(self, row: dict[str, str], dimension: str) -> str:
        if dimension == "멤버십 등급":
            tier = row.get("tier", "")
            return f"tier_{tier}" if tier in {"1", "2", "3", "4"} else "tier_review"
        if dimension == "청구 주기":
            return "annual" if self._billing_cycle_label(row) == "연간" else "monthly"
        if dimension == "결제 상태":
            status = self._payment_status_label(row)
            if status == "결제 완료 (재시도)":
                return "retry_complete"
            if status == "선물 (타인)":
                return "gift_other"
            if status == "선물 (본인)":
                return "gift_self"
            return "paid_active"
        if dimension == "유료로 전환하는 경로":
            return "email" if self._conversion_path_label(row) == "메일" else "other_path"
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
        if group == "매일":
            if (end - start).days > 400:
                start = end - dt.timedelta(days=400)
            current = start
            while current <= end:
                labels.append(self._bucket_label(current, group))
                current += dt.timedelta(days=1)
            return labels
        if group == "매주":
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
        if group == "매일":
            return row_date.strftime("%m. %d."), row_date
        if group == "매주":
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
        value = row.get("received_at", "")
        if not value:
            return None
        try:
            return dt.datetime.fromisoformat(value).date()
        except ValueError:
            return None

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
        state = tk.NORMAL if preset == "사용자 지정" else tk.DISABLED
        if hasattr(self, "after_entry"):
            self.after_entry.configure(state=state)
        if hasattr(self, "before_entry"):
            self.before_entry.configure(state=state)

    def _range_dates(self, preset: str) -> tuple[dt.date | None | str, dt.date | None | str]:
        today = dt.date.today()
        if preset == "지난 24시간":
            return today - dt.timedelta(days=1), today
        if preset == "지난 30일":
            return today - dt.timedelta(days=29), today
        if preset == "지난 6개월":
            return add_months(today, -6), today
        if preset == "지난 12개월":
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
    app = PatreonMemberApp()
    app.mainloop()
    return 0


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
                "Patreon Gmail Member Exporter",
                "프로그램을 시작하지 못했습니다.\n\noutput\\gui_error.log를 확인하세요.",
            )
        except tk.TclError:
            pass
        raise
