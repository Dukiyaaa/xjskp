#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
app_gui.py
- Tkinter GUI for automation modules
- Thread-safe log display (Queue + root.after polling)
- Integrates WorldAutomation module via callbacks: log_cb / counter_cb
"""

import sys
import time
import os
import json
import queue
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# from sympy.codegen.ast import String

try:
    from world_automation import *
    _world_import_err = None
except Exception:
    WorldAutomation = None
    _world_import_err = traceback.format_exc()

try:
    from tower_automation import *
    _tower_import_err = None
except Exception:
    TowerAutomation = None
    _tower_import_err = traceback.format_exc()

try:
    from expedition_automation import *
    _expedition_import_err = None
except Exception:
    ExpeditionAutomation = None
    _expedition_import_err = traceback.format_exc()

try:
    from mutual_world_automation import MutualWorldAutomation
    _mutual_world_import_err = None
except Exception:
    MutualWorldAutomation = None
    _mutual_world_import_err = traceback.format_exc()

try:
    from in_game_option_selector import InGameOptionSelector
    _skill_selector_import_err = None
except Exception:
    InGameOptionSelector = None
    _skill_selector_import_err = traceback.format_exc()

class AppGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("向僵尸开炮脚本")
        self.root.geometry("980x720")
        self.root.minsize(900, 650)

        # Thread-safe message queue: worker threads -> GUI thread
        self.msg_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()

        # Module instance
        self.automation = None
        self.ad_watcher = None
        self.txt_ads_log = None

        self.tower_automation = None
        self.txt_tower_log = None
        self.expedition_automation = None
        self.txt_expedition_log = None
        self.mutual_world_automation = None
        self.txt_mutual_world_log = None
        self.mutual_world_friend_templates = {}
        self.cmb_mutual_world_friend = None

        # 任务队列模块
        self.task_queue = []              # 队列数据
        self.queue_running = False        # 队列是否在运行
        self.queue_current_index = -1     # 当前跑到哪个任务
        self.queue_after_id = None        # after轮询句柄
        self.txt_queue_log = None         # 队列日志框

        # 本次程序运行中，是否已经执行过一次缩窗
        self.skill_priority_config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "skill_priority.json"
        )
        self.skill_priority = self._load_skill_priority()
        self.lst_skill_priority = None

        self.window_resized_once = False
        # ---- Style ----
        self._build_style()

        # ---- Layout ----
        self._build_layout()

        # Poll queue for UI updates
        self.root.after(60, self._poll_queue)

        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # If import failed, show warning (but keep GUI running)
        if WorldAutomation is None:
            self._push_log("ERROR", f"无法导入 WorldAutomation：\n{_world_import_err}\n"
                                    f"请确认：\n"
                                    f"1) modules/world_automation.py 存在并包含 WorldAutomation\n"
                                    f"或\n"
                                    f"2) world_automation.py 与 app_gui.py 同级\n")

    # ---------------- UI build ----------------
    def _build_style(self):
        style = ttk.Style(self.root)
        # Use default theme if available
        try:
            style.theme_use("vista")
        except Exception:
            pass

        style.configure("TButton", padding=6)
        style.configure("Header.TLabel", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Hint.TLabel", foreground="#666666")

    def _build_layout(self):
        # Top header
        header = ttk.Frame(self.root, padding=(12, 10))
        header.pack(fill="x")

        ttk.Label(header, text="向僵尸开炮脚本-季季如春", style="Header.TLabel").pack(side="left")
        ttk.Label(header, text="日志/计数回调已做线程安全队列转发", style="Hint.TLabel").pack(side="left", padx=12)

        # Notebook (Tabs)
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Tab: 环球抢环
        self.tab_world = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_world, text="环球抢环")

        self.tab_tower = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_tower, text="自动爬塔")

        self.tab_expedition = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_expedition, text="自动远征")

        # 新增：看广告
        self.tab_mutual_world = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_mutual_world, text="\u4e92\u73af\u6a21\u5f0f")

        self.tab_ads = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_ads, text="自动看广告")

        # 任务队列
        self.tab_queue = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_queue, text="任务队列")

        self.tab_skill_priority = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_skill_priority, text="技能优先级")

        self.tab_about = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_about, text="设置/关于")

        self._build_world_tab(self.tab_world)
        self._build_tower_tab(self.tab_tower)
        self._build_expedition_tab(self.tab_expedition)
        self._build_mutual_world_tab(self.tab_mutual_world)
        self._build_ads_tab(self.tab_ads)
        self._build_queue_tab(self.tab_queue)
        self._build_skill_priority_tab(self.tab_skill_priority)
        self._build_about_tab(self.tab_about)

    def _build_world_tab(self, parent: ttk.Frame):
        # Left control panel
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=(0, 12))

        # Right log panel
        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True)

        # ---- Controls group ----
        grp = ttk.LabelFrame(left, text="参数与控制", padding=10)
        grp.pack(fill="x")
        # grp.columnconfigure(3, weight=1)

        # Window name
        ttk.Label(grp, text="窗口名（FindWindow）").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.var_window_name = tk.StringVar(value="向僵尸开炮")
        ent_win = ttk.Entry(grp, textvariable=self.var_window_name, width=22)
        ent_win.grid(row=0, column=1, sticky="w", pady=(0, 6))

        # Expect diff
        param_row = ttk.Frame(grp)
        param_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Label(param_row, text="最低难度").grid(row=0, column=0, sticky="w")

        self.var_expect_diff = tk.StringVar(value="7")
        ent_diff = ttk.Entry(param_row, textvariable=self.var_expect_diff, width=8)
        ent_diff.grid(row=0, column=1, sticky="w", padx=(8, 24))

        ttk.Label(param_row, text="连点间隔(秒)").grid(row=0, column=2, sticky="w")

        self.var_click_interval = tk.StringVar(value="0.025")
        ent_click_interval = ttk.Entry(param_row, textvariable=self.var_click_interval, width=8)
        ent_click_interval.grid(row=0, column=3, sticky="w", padx=(8, 0))

        ttk.Label(param_row, text="\u96be\u5ea6\u8bc6\u522b\u9608\u503c").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_world_diff_threshold = tk.StringVar(value="0.90")
        ent_world_diff_threshold = ttk.Entry(param_row, textvariable=self.var_world_diff_threshold, width=8)
        ent_world_diff_threshold.grid(row=1, column=1, sticky="w", padx=(8, 24), pady=(6, 0))

        ttk.Label(param_row, text="\u6218\u6597\u81ea\u52a8\u9000\u51fa(\u5206\u949f)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.var_world_battle_auto_exit_minutes = tk.StringVar(value="0")
        ttk.Entry(param_row, textvariable=self.var_world_battle_auto_exit_minutes, width=8).grid(
            row=2, column=1, sticky="w", padx=(8, 24), pady=(6, 0)
        )

        # Buttons row
        btn_row = ttk.Frame(grp)
        btn_row.grid(row=2, column=0, columnspan=2, sticky="we", pady=(6, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.btn_start = ttk.Button(btn_row, text="启动", command=self.on_start)
        self.btn_start.grid(row=0, column=0, sticky="we", padx=(0, 6))

        self.btn_stop = ttk.Button(btn_row, text="停止", command=self.on_stop, state="disabled")
        self.btn_stop.grid(row=0, column=1, sticky="we")

        # Reset counter
        self.btn_reset = ttk.Button(grp, text="重置计数", command=self.on_reset_counter, state="disabled")
        self.btn_reset.grid(row=3, column=0, columnspan=2, sticky="we", pady=(10, 0))

        # 局内自动点击中间词条开关
        self.var_mid_entry_click = tk.BooleanVar(value=True)
        self.chk_mid_entry = ttk.Checkbutton(
            grp,
            text="\u6218\u6597\u4e2d\u667a\u80fd\u9009\u8bcd\u6761",
            variable=self.var_mid_entry_click,
            command=self.on_toggle_mid_entry_click
        )
        self.chk_mid_entry.grid(row=4, column=0, columnspan=2, sticky="we", pady=(10, 0))

        # 仅接受邀请模式开关
        self.var_invite_only = tk.BooleanVar(value=False)
        self.chk_invite_only = ttk.Checkbutton(
            grp,
            text="仅接受邀请（勾选后不主动抢环，只接收并判断邀请）",
            variable=self.var_invite_only
        )
        self.chk_invite_only.grid(row=5, column=0, columnspan=2, sticky="we", pady=(8, 0))

        # Counter display
        grp2 = ttk.LabelFrame(left, text="状态", padding=10)
        grp2.pack(fill="x", pady=(12, 0))

        # 0) 完成局数
        ttk.Label(grp2, text="完成局数：").grid(row=0, column=0, sticky="w")
        self.var_counter = tk.StringVar(value="0")
        ttk.Label(grp2, textvariable=self.var_counter, font=("Consolas", 14, "bold")).grid(row=0, column=1, sticky="w")

        # 1) 运行状态
        self.var_running = tk.StringVar(value="未运行")
        ttk.Label(grp2, text="运行状态：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(grp2, textvariable=self.var_running).grid(row=1, column=1, sticky="w", pady=(8, 0))

        # 2) 所处页面
        self.var_current_page = tk.StringVar(value="主页")  # 初始值为 "主页"
        ttk.Label(grp2, text="当前所处页面：").grid(row=2, column=0, sticky="w")
        ttk.Label(grp2, textvariable=self.var_current_page, font=("Consolas", 14, "bold")).grid(row=2, column=1,
                                                                                                sticky="w")
        # 环球救援统计表（3x7）
        grp3 = ttk.LabelFrame(left, text="环球统计", padding=10)
        grp3.pack(fill="x", pady=(12, 0))

        self.var_world_counts = {}

        cols = 7
        total = 21   # 20 + None

        for i in range(total):
            row = i // cols
            col = i % cols

            if i < 20:
                name = f"环球{i+1}"
                key = f"world_{i+1}"
            else:
                name = "None"
                key = "world_none"

            # 标题
            ttk.Label(grp3, text=name).grid(row=row*2, column=col, padx=6, pady=(2,0))

            # 计数器
            var = tk.StringVar(value="0")
            self.var_world_counts[key] = var

            ttk.Label(
                grp3,
                textvariable=var,
                font=("Consolas", 12, "bold")
            ).grid(row=row*2+1, column=col, padx=6, pady=(0,6))

        for c in range(7):
            grp3.columnconfigure(c, weight=1)

        self.btn_reset_world_counts = ttk.Button(
            grp3,
            text="重置环球统计",
            command=self.on_reset_world_counts,
            state="disabled"
        )
        self.btn_reset_world_counts.grid(
            row=6, column=0, columnspan=7, sticky="we", pady=(8, 0)
        )

        # ---- Log box ----
        log_grp = ttk.LabelFrame(right, text="日志输出", padding=10)
        log_grp.pack(fill="both", expand=True)

        self.txt_log = tk.Text(log_grp, wrap="word", height=24)
        self.txt_log.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(log_grp, orient="vertical", command=self.txt_log.yview)
        sb.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=sb.set)

        # Log tags
        self.txt_log.tag_configure("INFO", foreground="#1f6feb")
        self.txt_log.tag_configure("WARN", foreground="#b58900")
        self.txt_log.tag_configure("ERROR", foreground="#d73a49")
        self.txt_log.tag_configure("DEBUG", foreground="#6a737d")

        # Bottom quick tools
        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="清空日志", command=self.on_clear_log).pack(side="left")
        ttk.Button(bottom, text="复制日志", command=self.on_copy_log).pack(side="left", padx=8)

    def _build_tower_tab(self, parent: ttk.Frame):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True)

        grp = ttk.LabelFrame(left, text="爬塔控制", padding=10)
        grp.pack(fill="x")

        ttk.Label(grp, text="窗口名（FindWindow）").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.var_tower_window_name = tk.StringVar(value="向僵尸开炮")
        ttk.Entry(grp, textvariable=self.var_tower_window_name, width=22).grid(
            row=0, column=1, sticky="w", pady=(0, 6)
        )

        btn_row = ttk.Frame(grp)
        btn_row.grid(row=1, column=0, columnspan=2, sticky="we", pady=(6, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.btn_tower_start = ttk.Button(btn_row, text="启动", command=self.on_tower_start)
        self.btn_tower_start.grid(row=0, column=0, sticky="we", padx=(0, 6))

        self.btn_tower_stop = ttk.Button(btn_row, text="停止", command=self.on_tower_stop, state="disabled")
        self.btn_tower_stop.grid(row=0, column=1, sticky="we")

        grp2 = ttk.LabelFrame(left, text="状态", padding=10)
        grp2.pack(fill="x", pady=(12, 0))

        self.var_tower_running = tk.StringVar(value="未运行")
        ttk.Label(grp2, text="运行状态：").grid(row=0, column=0, sticky="w")
        ttk.Label(grp2, textvariable=self.var_tower_running).grid(row=0, column=1, sticky="w")

        log_grp = ttk.LabelFrame(right, text="爬塔日志输出", padding=10)
        log_grp.pack(fill="both", expand=True)

        self.txt_tower_log = tk.Text(log_grp, wrap="word", height=24)
        self.txt_tower_log.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(log_grp, orient="vertical", command=self.txt_tower_log.yview)
        sb.pack(side="right", fill="y")
        self.txt_tower_log.configure(yscrollcommand=sb.set)

        self.txt_tower_log.tag_configure("INFO", foreground="#1f6feb")
        self.txt_tower_log.tag_configure("WARN", foreground="#b58900")
        self.txt_tower_log.tag_configure("ERROR", foreground="#d73a49")
        self.txt_tower_log.tag_configure("DEBUG", foreground="#6a737d")

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="清空日志", command=self.on_clear_tower_log).pack(side="left")
        ttk.Button(bottom, text="复制日志", command=self.on_copy_tower_log).pack(side="left", padx=8)
    
    def _build_expedition_tab(self, parent: ttk.Frame):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True)

        grp = ttk.LabelFrame(left, text="远征控制", padding=10)
        grp.pack(fill="x")

        ttk.Label(grp, text="窗口名（FindWindow）").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.var_expedition_window_name = tk.StringVar(value="向僵尸开炮")
        ttk.Entry(grp, textvariable=self.var_expedition_window_name, width=22).grid(
            row=0, column=1, sticky="w", pady=(0, 6)
        )

        ttk.Label(grp, text="远征身份").grid(row=1, column=0, sticky="w", pady=(0, 6))
        self.var_expedition_role = tk.StringVar(value="出票位")
        cmb_role = ttk.Combobox(
            grp,
            textvariable=self.var_expedition_role,
            values=["出票位", "打手位"],
            state="readonly",
            width=19
        )
        cmb_role.grid(row=1, column=1, sticky="w", pady=(0, 6))

        self.var_expedition_smart_option = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            grp,
            text="\u6218\u6597\u4e2d\u667a\u80fd\u9009\u8bcd\u6761",
            variable=self.var_expedition_smart_option
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Label(grp, text="超时换房(秒)").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.var_expedition_cancel_ready_timeout = tk.StringVar(value="40")
        ttk.Entry(
            grp,
            textvariable=self.var_expedition_cancel_ready_timeout,
            width=8
        ).grid(row=3, column=1, sticky="w", pady=(6, 0))

        btn_row = ttk.Frame(grp)
        btn_row.grid(row=4, column=0, columnspan=2, sticky="we", pady=(6, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.btn_expedition_start = ttk.Button(
            btn_row,
            text="启动",
            command=self.on_expedition_start
        )
        self.btn_expedition_start.grid(row=0, column=0, sticky="we", padx=(0, 6))

        self.btn_expedition_stop = ttk.Button(
            btn_row,
            text="停止",
            command=self.on_expedition_stop,
            state="disabled"
        )
        self.btn_expedition_stop.grid(row=0, column=1, sticky="we")

        grp2 = ttk.LabelFrame(left, text="状态", padding=10)
        grp2.pack(fill="x", pady=(12, 0))

        self.var_expedition_running = tk.StringVar(value="未运行")
        ttk.Label(grp2, text="运行状态：").grid(row=0, column=0, sticky="w")
        ttk.Label(grp2, textvariable=self.var_expedition_running).grid(row=0, column=1, sticky="w")

        self.var_expedition_role_show = tk.StringVar(value="出票位")
        ttk.Label(grp2, text="当前身份：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(grp2, textvariable=self.var_expedition_role_show).grid(row=1, column=1, sticky="w", pady=(8, 0))

        log_grp = ttk.LabelFrame(right, text="远征日志输出", padding=10)
        log_grp.pack(fill="both", expand=True)

        self.txt_expedition_log = tk.Text(log_grp, wrap="word", height=24)
        self.txt_expedition_log.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(log_grp, orient="vertical", command=self.txt_expedition_log.yview)
        sb.pack(side="right", fill="y")
        self.txt_expedition_log.configure(yscrollcommand=sb.set)

        self.txt_expedition_log.tag_configure("INFO", foreground="#1f6feb")
        self.txt_expedition_log.tag_configure("WARN", foreground="#b58900")
        self.txt_expedition_log.tag_configure("ERROR", foreground="#d73a49")
        self.txt_expedition_log.tag_configure("DEBUG", foreground="#6a737d")

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="清空日志", command=self.on_clear_expedition_log).pack(side="left")
        ttk.Button(bottom, text="复制日志", command=self.on_copy_expedition_log).pack(side="left", padx=8)

    def _build_mutual_world_tab(self, parent: ttk.Frame):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True)

        grp = ttk.LabelFrame(left, text="\u4e92\u73af\u8bbe\u7f6e", padding=10)
        grp.pack(fill="x")

        ttk.Label(grp, text="\u7a97\u53e3\u540d(FindWindow)").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.var_mutual_world_window_name = tk.StringVar(value="\u5411\u50f5\u5c38\u5f00\u70ae")
        ttk.Entry(grp, textvariable=self.var_mutual_world_window_name, width=24).grid(
            row=0, column=1, sticky="w", pady=(0, 6)
        )

        ttk.Label(grp, text="\u8eab\u4efd").grid(row=1, column=0, sticky="w", pady=(0, 6))
        self.var_mutual_world_role = tk.StringVar(value="\u51fa\u7968\u4f4d")
        cmb_role = ttk.Combobox(
            grp,
            textvariable=self.var_mutual_world_role,
            values=["\u51fa\u7968\u4f4d", "\u975e\u51fa\u7968\u4f4d"],
            state="readonly",
            width=21
        )
        cmb_role.grid(row=1, column=1, sticky="w", pady=(0, 6))
        cmb_role.bind("<<ComboboxSelected>>", self.on_mutual_world_friend_changed)

        ttk.Label(grp, text="\u6a21\u677f\u6587\u4ef6").grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.var_mutual_world_friend_template = tk.StringVar(value="")
        ttk.Entry(grp, textvariable=self.var_mutual_world_friend_template, width=24).grid(
            row=2, column=1, sticky="w", pady=(0, 6)
        )
        ttk.Button(grp, text="\u9009\u62e9", command=self.on_mutual_world_choose_template).grid(
            row=2, column=2, sticky="w", padx=(6, 0), pady=(0, 6)
        )

        ttk.Label(grp, text="\u5339\u914d\u9608\u503c").grid(row=3, column=0, sticky="w", pady=(0, 6))
        self.var_mutual_world_threshold = tk.StringVar(value="0.95")
        ttk.Entry(grp, textvariable=self.var_mutual_world_threshold, width=8).grid(
            row=3, column=1, sticky="w", pady=(0, 6)
        )

        self.var_mutual_world_smart_option = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            grp,
            text="\u6218\u6597\u4e2d\u667a\u80fd\u9009\u6280\u80fd",
            variable=self.var_mutual_world_smart_option
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        ttk.Label(grp, text="\u6218\u6597\u81ea\u52a8\u9000\u51fa(\u5206\u949f)").grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.var_mutual_world_battle_auto_exit_minutes = tk.StringVar(value="0")
        ttk.Entry(grp, textvariable=self.var_mutual_world_battle_auto_exit_minutes, width=8).grid(
            row=5, column=1, sticky="w", pady=(8, 0)
        )

        btn_row = ttk.Frame(grp)
        btn_row.grid(row=6, column=0, columnspan=3, sticky="we", pady=(6, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.btn_mutual_world_start = ttk.Button(btn_row, text="\u542f\u52a8", command=self.on_mutual_world_start)
        self.btn_mutual_world_start.grid(row=0, column=0, sticky="we", padx=(0, 6))

        self.btn_mutual_world_stop = ttk.Button(
            btn_row,
            text="\u505c\u6b62",
            command=self.on_mutual_world_stop,
            state="disabled"
        )
        self.btn_mutual_world_stop.grid(row=0, column=1, sticky="we")

        grp_state = ttk.LabelFrame(left, text="\u72b6\u6001", padding=10)
        grp_state.pack(fill="x", pady=(12, 0))

        self.var_mutual_world_running = tk.StringVar(value="\u672a\u8fd0\u884c")
        ttk.Label(grp_state, text="\u8fd0\u884c\u72b6\u6001").grid(row=0, column=0, sticky="w")
        ttk.Label(grp_state, textvariable=self.var_mutual_world_running).grid(row=0, column=1, sticky="w")

        self.var_mutual_world_page = tk.StringVar(value="\u672a\u77e5")
        ttk.Label(grp_state, text="\u5f53\u524d\u9875\u9762").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(grp_state, textvariable=self.var_mutual_world_page).grid(row=1, column=1, sticky="w", pady=(8, 0))

        self.var_mutual_world_friend_name = tk.StringVar(value="\u4f46\u6b32\u5b63\u5b63\u5982\u6625")
        ttk.Label(grp_state, text="\u961f\u53cb").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.cmb_mutual_world_friend = ttk.Combobox(
            grp_state,
            textvariable=self.var_mutual_world_friend_name,
            values=["\u4f46\u6b32\u5b63\u5b63\u5982\u6625", "\u5929\u5929\u5f00\u5fc3", "\u6625\u98ce\u5341\u91cc"],
            state="readonly",
            width=21
        )
        self.cmb_mutual_world_friend.grid(row=2, column=1, sticky="w", pady=(8, 0))
        self.cmb_mutual_world_friend.bind("<<ComboboxSelected>>", self.on_mutual_world_friend_changed)

        log_grp = ttk.LabelFrame(right, text="\u4e92\u73af\u65e5\u5fd7", padding=10)
        log_grp.pack(fill="both", expand=True)

        self.txt_mutual_world_log = tk.Text(log_grp, wrap="word", height=24)
        self.txt_mutual_world_log.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(log_grp, orient="vertical", command=self.txt_mutual_world_log.yview)
        sb.pack(side="right", fill="y")
        self.txt_mutual_world_log.configure(yscrollcommand=sb.set)

        self.txt_mutual_world_log.tag_configure("INFO", foreground="#1f6feb")
        self.txt_mutual_world_log.tag_configure("WARN", foreground="#b58900")
        self.txt_mutual_world_log.tag_configure("ERROR", foreground="#d73a49")
        self.txt_mutual_world_log.tag_configure("DEBUG", foreground="#6a737d")

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="\u6e05\u7a7a\u65e5\u5fd7", command=self.on_clear_mutual_world_log).pack(side="left")
        ttk.Button(bottom, text="\u590d\u5236\u65e5\u5fd7", command=self.on_copy_mutual_world_log).pack(side="left", padx=8)
        self.on_mutual_world_friend_changed()

    def _build_ads_tab(self, parent: ttk.Frame):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True)

        grp = ttk.LabelFrame(left, text="广告模块控制", padding=10)
        grp.pack(fill="x")

        # 体力广告：轮数/冷却
        ttk.Label(grp, text="体力广告轮数 max_rounds").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.var_ads_power_rounds = tk.StringVar(value="30")
        ttk.Entry(grp, textvariable=self.var_ads_power_rounds, width=18).grid(row=0, column=1, sticky="w", pady=(0, 6))

        ttk.Label(grp, text="冷却 cooldown(秒)").grid(row=1, column=0, sticky="w", pady=(0, 6))
        self.var_ads_power_cooldown = tk.StringVar(value="300")
        ttk.Entry(grp, textvariable=self.var_ads_power_cooldown, width=18).grid(row=1, column=1, sticky="w",
                                                                                pady=(0, 6))

        btn_row = ttk.Frame(grp)
        btn_row.grid(row=2, column=0, columnspan=2, sticky="we", pady=(10, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.btn_ads_power_start = ttk.Button(btn_row, text="启动体力广告", command=self.on_ads_power_start,
                                              state="disabled")
        self.btn_ads_power_start.grid(row=0, column=0, sticky="we", padx=(0, 6))

        self.btn_ads_power_stop = ttk.Button(btn_row, text="停止体力广告", command=self.on_ads_power_stop,
                                             state="disabled")
        self.btn_ads_power_stop.grid(row=0, column=1, sticky="we")

        # 右侧：提示/说明（你也可以放独立日志框，但复用主日志最省事）
        # 右侧：说明
        ttk.Label(
            right,
            text="说明：要想使用自动看体力广告，需要先启动抢环，随后停止，回到主页面，再点击看广告按钮\n",
            style="Hint.TLabel"
        ).pack(anchor="nw", pady=(0, 10))

        # 右侧：广告日志框
        ads_log_grp = ttk.LabelFrame(right, text="广告日志输出", padding=10)
        ads_log_grp.pack(fill="both", expand=True)

        self.txt_ads_log = tk.Text(ads_log_grp, wrap="word", height=18)
        self.txt_ads_log.pack(side="left", fill="both", expand=True)

        sb_ads = ttk.Scrollbar(ads_log_grp, orient="vertical", command=self.txt_ads_log.yview)
        sb_ads.pack(side="right", fill="y")
        self.txt_ads_log.configure(yscrollcommand=sb_ads.set)

        # 广告日志 tags（沿用同一套颜色）
        self.txt_ads_log.tag_configure("INFO", foreground="#1f6feb")
        self.txt_ads_log.tag_configure("WARN", foreground="#b58900")
        self.txt_ads_log.tag_configure("ERROR", foreground="#d73a49")
        self.txt_ads_log.tag_configure("DEBUG", foreground="#6a737d")

        # 广告日志底部快捷按钮（可选）
        ads_bottom = ttk.Frame(right)
        ads_bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(ads_bottom, text="清空广告日志", command=self.on_clear_ads_log).pack(side="left")
        ttk.Button(ads_bottom, text="复制广告日志", command=self.on_copy_ads_log).pack(side="left", padx=8)

    def _build_queue_tab(self, parent: ttk.Frame):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=(0, 12))

        middle = ttk.Frame(parent)
        middle.pack(side="left", fill="both", expand=False, padx=(0, 12))

        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True)

        # ---- 左侧：添加任务 ----
        grp_add = ttk.LabelFrame(left, text="添加任务", padding=10)
        grp_add.pack(fill="x")

        ttk.Label(grp_add, text="任务类型").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.var_queue_task_type = tk.StringVar(value="抢环球")
        cmb_task = ttk.Combobox(
            grp_add,
            textvariable=self.var_queue_task_type,
            values=["抢环球", "爬塔", "自动远征", "体力广告"],
            state="readonly",
            width=18
        )
        cmb_task.grid(row=0, column=1, sticky="w", pady=(0, 6))

        ttk.Label(grp_add, text="最低难度").grid(row=1, column=0, sticky="w", pady=(0, 6))
        self.var_queue_expect_diff = tk.StringVar(value="7")
        ttk.Entry(grp_add, textvariable=self.var_queue_expect_diff, width=20).grid(
            row=1, column=1, sticky="w", pady=(0, 6)
        )

        self.var_queue_invite_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            grp_add,
            text="仅接受邀请",
            variable=self.var_queue_invite_only
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Button(grp_add, text="加入队列", command=self.on_queue_add).grid(
            row=3, column=0, columnspan=2, sticky="we", pady=(8, 0)
        )

        # ---- 中间：队列列表 ----
        grp_list = ttk.LabelFrame(middle, text="任务列表", padding=10)
        grp_list.pack(fill="both", expand=True)

        self.lst_queue = tk.Listbox(grp_list, height=18, width=40)
        self.lst_queue.pack(fill="both", expand=True)

        btns = ttk.Frame(grp_list)
        btns.pack(fill="x", pady=(10, 0))

        ttk.Button(btns, text="上移", command=self.on_queue_move_up).pack(side="left")
        ttk.Button(btns, text="下移", command=self.on_queue_move_down).pack(side="left", padx=6)
        ttk.Button(btns, text="删除", command=self.on_queue_delete).pack(side="left", padx=6)
        ttk.Button(btns, text="清空", command=self.on_queue_clear).pack(side="left", padx=6)

        # ---- 右侧：运行控制 + 日志 ----
        grp_ctrl = ttk.LabelFrame(right, text="队列控制", padding=10)
        grp_ctrl.pack(fill="x")

        self.var_queue_status = tk.StringVar(value="未运行")
        ttk.Label(grp_ctrl, text="状态：").grid(row=0, column=0, sticky="w")
        ttk.Label(grp_ctrl, textvariable=self.var_queue_status).grid(row=0, column=1, sticky="w")

        ctrl_btns = ttk.Frame(grp_ctrl)
        ctrl_btns.grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 0))

        self.btn_queue_start = ttk.Button(ctrl_btns, text="启动队列", command=self.on_queue_start)
        self.btn_queue_start.pack(side="left")

        self.btn_queue_stop = ttk.Button(ctrl_btns, text="停止队列", command=self.on_queue_stop, state="disabled")
        self.btn_queue_stop.pack(side="left", padx=8)

        log_grp = ttk.LabelFrame(right, text="队列日志", padding=10)
        log_grp.pack(fill="both", expand=True, pady=(12, 0))

        self.txt_queue_log = tk.Text(log_grp, wrap="word", height=18)
        self.txt_queue_log.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(log_grp, orient="vertical", command=self.txt_queue_log.yview)
        sb.pack(side="right", fill="y")
        self.txt_queue_log.configure(yscrollcommand=sb.set)

    def on_queue_add(self):
        task_type = self.var_queue_task_type.get()

        if task_type == "抢环球":
            try:
                expect_diff = int(self.var_queue_expect_diff.get().strip())
            except Exception:
                messagebox.showwarning("提示", "最低难度必须是整数。")
                return

            task = {
                "task_type": "world",
                "name": f"抢环球(难度≥{expect_diff}, {'仅邀请' if self.var_queue_invite_only.get() else '主动'})",
                "params": {
                    "expect_diff": expect_diff,
                    "invite_only": self.var_queue_invite_only.get()
                }
            }

        elif task_type == "爬塔":
            task = {
                "task_type": "tower",
                "name": "爬塔",
                "params": {}
            }

        elif task_type == "自动远征":
            role_text = self.var_expedition_role.get()
            cancel_ready_timeout = self._get_expedition_cancel_ready_timeout()
            if cancel_ready_timeout is None:
                return
            task = {
                "task_type": "expedition",
                "name": f"自动远征({role_text})",
                "params": {
                    "role_text": role_text,
                    "smart_option_enabled": self.var_expedition_smart_option.get(),
                    "cancel_ready_timeout": cancel_ready_timeout
                }
            }

        elif task_type == "体力广告":
            try:
                max_rounds = int(self.var_ads_power_rounds.get().strip())
                cooldown = int(self.var_ads_power_cooldown.get().strip())
            except Exception:
                messagebox.showwarning("提示", "广告轮数和冷却时间必须是整数。")
                return

            task = {
                "task_type": "ads_power",
                "name": f"体力广告(轮数={max_rounds}, 冷却={cooldown}s)",
                "params": {
                    "max_rounds": max_rounds,
                    "cooldown": cooldown
                }
            }

        else:
            messagebox.showwarning("提示", f"未知任务类型：{task_type}")
            return

        self.task_queue.append(task)
        self.lst_queue.insert("end", task["name"])
        self._append_queue_log(f"[QUEUE] 已添加任务：{task['name']}")

    def on_queue_move_up(self):
        sel = self.lst_queue.curselection()
        if not sel:
            return
        i = sel[0]
        if i == 0:
            return

        self.task_queue[i - 1], self.task_queue[i] = self.task_queue[i], self.task_queue[i - 1]

        self._refresh_queue_listbox()
        self.lst_queue.selection_set(i - 1)

    def on_queue_move_down(self):
        sel = self.lst_queue.curselection()
        if not sel:
            return
        i = sel[0]
        if i >= len(self.task_queue) - 1:
            return

        self.task_queue[i + 1], self.task_queue[i] = self.task_queue[i], self.task_queue[i + 1]

        self._refresh_queue_listbox()
        self.lst_queue.selection_set(i + 1)

    def on_queue_delete(self):
        sel = self.lst_queue.curselection()
        if not sel:
            return
        i = sel[0]
        task = self.task_queue.pop(i)
        self._refresh_queue_listbox()
        self._append_queue_log(f"[QUEUE] 已删除任务：{task['name']}")

    def on_queue_clear(self):
        self.task_queue.clear()
        self._refresh_queue_listbox()
        self._append_queue_log("[QUEUE] 已清空任务列表")

    def _refresh_queue_listbox(self):
        self.lst_queue.delete(0, "end")
        for task in self.task_queue:
            self.lst_queue.insert("end", task["name"])

    def _append_queue_log(self, msg: str):
        if self.txt_queue_log is None:
            return
        ts = time.strftime("%H:%M:%S")
        self.txt_queue_log.insert("end", f"{ts} {msg}\n")
        self.txt_queue_log.see("end")

    def _default_skill_priority(self):
        if InGameOptionSelector is not None:
            return list(InGameOptionSelector.DEFAULT_SKILL_PRIORITY)
        return [
            "hail",
            "ice",
            "thermobaric_bomb",
            "electromagnetic",
            "gun",
            "matrix",
            "airdrop",
            "electrode_pillar",
            "vehicle",
            "ray",
            "laser",
            "drone",
            "tornado",
            "fuel",
            "bouncing_projectile",
            "transition_electron",
            "air_blade",
            "spacetime",
        ]

    def _skill_label_map(self):
        if InGameOptionSelector is not None:
            return dict(InGameOptionSelector.SKILL_CATEGORY_LABELS)
        return {
            "hail": "冰雹",
            "ice": "干冰弹",
            "thermobaric_bomb": "温压弹",
            "electromagnetic": "电磁",
            "gun": "枪",
            "matrix": "矩阵",
            "airdrop": "空投",
            "electrode_pillar": "电极柱",
            "vehicle": "车",
            "ray": "射线",
            "laser": "激光",
            "drone": "无人机",
            "tornado": "龙卷风",
            "fuel": "燃油",
            "bouncing_projectile": "弹球",
            "transition_electron": "跃迁电子",
            "air_blade": "气刃",
            "spacetime": "时空",
        }

    def _load_skill_priority(self):
        default_priority = self._default_skill_priority()
        try:
            if not os.path.exists(self.skill_priority_config_path):
                return default_priority
            with open(self.skill_priority_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            priority = data.get("priority", data if isinstance(data, list) else [])
            priority = [item for item in priority if item in default_priority]
            for item in default_priority:
                if item not in priority:
                    priority.append(item)
            return priority
        except Exception:
            return default_priority

    def _save_skill_priority(self):
        try:
            with open(self.skill_priority_config_path, "w", encoding="utf-8") as f:
                json.dump({"priority": self.skill_priority}, f, ensure_ascii=False, indent=2)
            self._push_log("INFO", "[GUI] 技能优先级已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存技能优先级失败：{e}")

    def get_skill_priority_config(self):
        return list(self.skill_priority)

    def _get_expedition_cancel_ready_timeout(self):
        try:
            value = float(self.var_expedition_cancel_ready_timeout.get().strip())
            if value <= 0:
                raise ValueError
            return value
        except Exception:
            messagebox.showwarning("提示", "取消准备超时需要是大于 0 的数字，例如 40。")
            return None

    def _apply_skill_priority_to_module(self, module):
        if module is None:
            return
        priority = self.get_skill_priority_config()
        try:
            if hasattr(module, "set_skill_priority"):
                module.set_skill_priority(priority)
            else:
                setattr(module, "skill_priority", priority)
        except Exception as e:
            self._push_log("WARN", f"[GUI] 应用技能优先级失败：{e}")

    def _refresh_skill_priority_listbox(self):
        if self.lst_skill_priority is None:
            return
        label_map = self._skill_label_map()
        self.lst_skill_priority.delete(0, "end")
        for index, skill in enumerate(self.skill_priority, start=1):
            label = label_map.get(skill, skill)
            self.lst_skill_priority.insert("end", f"{index:02d}. {label} ({skill})")

    def _build_skill_priority_tab(self, parent: ttk.Frame):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="both", expand=False, padx=(0, 12))

        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True)

        grp = ttk.LabelFrame(left, text="技能优先级", padding=10)
        grp.pack(fill="both", expand=True)

        ttk.Label(grp, text="从上到下优先级由高到低").pack(anchor="w", pady=(0, 6))

        self.lst_skill_priority = tk.Listbox(grp, height=22, width=42, exportselection=False)
        self.lst_skill_priority.pack(fill="both", expand=True)

        btns = ttk.Frame(grp)
        btns.pack(fill="x", pady=(10, 0))

        ttk.Button(btns, text="上移", command=self.on_skill_priority_move_up).pack(side="left")
        ttk.Button(btns, text="下移", command=self.on_skill_priority_move_down).pack(side="left", padx=6)
        ttk.Button(btns, text="恢复默认", command=self.on_skill_priority_reset).pack(side="left", padx=6)

        btns2 = ttk.Frame(grp)
        btns2.pack(fill="x", pady=(8, 0))
        ttk.Button(btns2, text="保存配置", command=self.on_skill_priority_save).pack(side="left")
        ttk.Button(btns2, text="重新加载", command=self.on_skill_priority_reload).pack(side="left", padx=6)

        info = ttk.LabelFrame(right, text="说明", padding=10)
        info.pack(fill="both", expand=True)
        msg = (
            "这里配置的是自动选技能的全局优先级。\n\n"
            "后续抢环、爬塔模块接入 InGameOptionSelector 时，"
            "会读取这份顺序作为选择依据。\n\n"
            "如果三张卡里有同优先级/同技能，选择最左边。"
        )
        ttk.Label(info, text=msg, justify="left", wraplength=440).pack(anchor="nw")

        self._refresh_skill_priority_listbox()

    def on_skill_priority_move_up(self):
        sel = self.lst_skill_priority.curselection() if self.lst_skill_priority is not None else ()
        if not sel:
            return
        i = sel[0]
        if i <= 0:
            return
        self.skill_priority[i - 1], self.skill_priority[i] = self.skill_priority[i], self.skill_priority[i - 1]
        self._refresh_skill_priority_listbox()
        self.lst_skill_priority.selection_set(i - 1)

    def on_skill_priority_move_down(self):
        sel = self.lst_skill_priority.curselection() if self.lst_skill_priority is not None else ()
        if not sel:
            return
        i = sel[0]
        if i >= len(self.skill_priority) - 1:
            return
        self.skill_priority[i + 1], self.skill_priority[i] = self.skill_priority[i], self.skill_priority[i + 1]
        self._refresh_skill_priority_listbox()
        self.lst_skill_priority.selection_set(i + 1)

    def on_skill_priority_reset(self):
        self.skill_priority = self._default_skill_priority()
        self._refresh_skill_priority_listbox()

    def on_skill_priority_save(self):
        self._save_skill_priority()

    def on_skill_priority_reload(self):
        self.skill_priority = self._load_skill_priority()
        self._refresh_skill_priority_listbox()
    
    def on_queue_start(self):
        if self.queue_running:
            self._append_queue_log("[QUEUE] 队列已在运行中")
            return

        if not self.task_queue:
            messagebox.showwarning("提示", "任务队列为空，请先添加任务。")
            return

        self.queue_running = True
        self.queue_current_index = -1
        self.var_queue_status.set("运行中")
        self.btn_queue_start.configure(state="disabled")
        self.btn_queue_stop.configure(state="normal")

        self.btn_start.configure(state="disabled")
        self.btn_tower_start.configure(state="disabled")
        self.btn_expedition_start.configure(state="disabled")
        self.btn_ads_power_start.configure(state="disabled")

        self._append_queue_log("[QUEUE] 开始执行任务队列")
        self._queue_start_next_task()

    def on_queue_stop(self):
        if not self.queue_running:
            return

        self.queue_running = False

        try:
            if self.automation is not None and self.automation.run_event.is_set():
                self.automation.stop()
        except Exception as e:
            self._append_queue_log(f"[QUEUE] 停止 WorldAutomation 时异常: {e}")

        try:
            if self.tower_automation is not None and self.tower_automation.run_event.is_set():
                self.tower_automation.stop()
        except Exception as e:
            self._append_queue_log(f"[QUEUE] 停止 TowerAutomation 时异常: {e}")

        try:
            if self.expedition_automation is not None and self.expedition_automation.run_event.is_set():
                self.expedition_automation.stop()
        except Exception as e:
            self._append_queue_log(f"[QUEUE] 停止 ExpeditionAutomation 时异常: {e}")

        try:
            if self.ad_watcher is not None and self.ad_watcher.power_running:
                self.ad_watcher.stop_power_ads()
        except Exception as e:
            self._append_queue_log(f"[QUEUE] 停止 AdWatcher 时异常: {e}")

        if self.queue_after_id is not None:
            try:
                self.root.after_cancel(self.queue_after_id)
            except Exception:
                pass
            self.queue_after_id = None

        self.var_queue_status.set("已停止")
        self.btn_queue_start.configure(state="normal")
        self.btn_queue_stop.configure(state="disabled")

        self.btn_start.configure(state="normal")
        self.btn_tower_start.configure(state="normal")
        self.btn_expedition_start.configure(state="normal")
        self.btn_ads_power_start.configure(state="normal")

        self._append_queue_log("[QUEUE] 已手动停止任务队列")

    def _queue_start_next_task(self):
        if not self.queue_running:
            return

        self.queue_current_index += 1

        if self.queue_current_index >= len(self.task_queue):
            self._queue_finish("[QUEUE] 所有任务执行完成")
            return

        task = self.task_queue[self.queue_current_index]
        task_type = task["task_type"]
        task_name = task["name"]

        self._append_queue_log(f"[QUEUE] 开始执行第 {self.queue_current_index + 1} 个任务: {task_name}")

        try:
            if task_type == "world":
                params = task.get("params", {})
                expect_diff = params.get("expect_diff", 7)
                invite_only = params.get("invite_only", False)

                window_name = self.var_window_name.get().strip()
                click_interval = float(self.var_click_interval.get().strip())
                battle_auto_exit_minutes = float(self.var_world_battle_auto_exit_minutes.get().strip() or "0")

                if self.automation is None:
                    self.automation = WorldAutomation(
                        window_name=window_name,
                        battle_auto_exit_minutes=battle_auto_exit_minutes,
                        auto_resize_window=self._consume_resize_once_flag()
                    )
                    self.automation.set_callbacks(
                        log_cb=self.log_cb,
                        current_page_cb=self.current_page_cb,
                        counter_cb=self.counter_cb,
                        world_counts_cb=self.world_counts_cb
                    )
                    self._apply_skill_priority_to_module(self.automation)
                    self.btn_ads_power_start.configure(state="normal")
                    self._push_log("INFO", f"[GUI] 已初始化 WorldAutomation(window_name='{window_name}')")

                self.automation.mid_entry_click_enabled = self.var_mid_entry_click.get()
                self.automation._min_click_interval = click_interval
                self.automation.set_battle_auto_exit_minutes(battle_auto_exit_minutes)
                self.automation.start(
                    expect_diff=expect_diff,
                    invite_only=invite_only,
                    log_cb=self.log_cb,
                    current_page_cb=self.current_page_cb,
                    counter_cb=self.counter_cb,
                    world_counts_cb=self.world_counts_cb
                )

                self.var_running.set("运行中")
                self.btn_start.configure(state="disabled")
                self.btn_stop.configure(state="normal")
                self.btn_reset.configure(state="normal")
                self.btn_reset_world_counts.configure(state="normal")

            elif task_type == "tower":
                window_name = self.var_tower_window_name.get().strip()

                if self.tower_automation is None:
                    self.tower_automation = TowerAutomation(
                        window_name=window_name,
                        auto_resize_window=self._consume_resize_once_flag()
                    )
                    self.tower_automation.set_callbacks(
                        log_cb=self.log_cb,
                        current_page_cb=self.current_page_cb
                    )
                    self._apply_skill_priority_to_module(self.tower_automation)
                    self._push_log("INFO", f"[GUI] 已初始化 TowerAutomation(window_name='{window_name}')")

                self.tower_automation.start(
                    log_cb=self.log_cb,
                    current_page_cb=self.current_page_cb
                )

                self.var_tower_running.set("运行中")
                self.btn_tower_start.configure(state="disabled")
                self.btn_tower_stop.configure(state="normal")

            elif task_type == "expedition":
                params = task.get("params", {})
                role_text = params.get("role_text", self.var_expedition_role.get())
                smart_option_enabled = params.get(
                    "smart_option_enabled",
                    self.var_expedition_smart_option.get()
                )
                cancel_ready_timeout = params.get("cancel_ready_timeout")
                if cancel_ready_timeout is None:
                    cancel_ready_timeout = self._get_expedition_cancel_ready_timeout()
                    if cancel_ready_timeout is None:
                        self._queue_start_next_task()
                        return
                role = "ticket" if role_text == "出票位" else "fighter"
                window_name = self.var_expedition_window_name.get().strip()

                if self.expedition_automation is None:
                    self.expedition_automation = ExpeditionAutomation(
                        window_name=window_name,
                        role=role,
                        auto_resize_window=self._consume_resize_once_flag()
                    )
                    self.expedition_automation.set_callbacks(log_cb=self.log_cb)
                    self._apply_skill_priority_to_module(self.expedition_automation)
                    self._push_log("INFO", f"[GUI] 已初始化 ExpeditionAutomation(window_name='{window_name}', role='{role}')")
                else:
                    self.expedition_automation.role = role
                    self._apply_skill_priority_to_module(self.expedition_automation)

                self.expedition_automation.smart_option_enabled = smart_option_enabled
                self.expedition_automation._cancel_ready_timeout = float(cancel_ready_timeout)
                self.expedition_automation.start(log_cb=self.log_cb)

                self.var_expedition_running.set("运行中")
                self.var_expedition_role_show.set(role_text)
                self.btn_expedition_start.configure(state="disabled")
                self.btn_expedition_stop.configure(state="normal")

            elif task_type == "ads_power":
                params = task.get("params", {})
                max_rounds = params.get("max_rounds", 30)
                cooldown = params.get("cooldown", 300)

                if not self._ensure_ad_watcher():
                    self._append_queue_log("[QUEUE] AdWatcher 初始化失败，跳过该任务")
                    self._queue_start_next_task()
                    return

                self.ad_watcher.start_power_ads(max_rounds=max_rounds, cooldown=cooldown)

                self.btn_ads_power_start.configure(state="disabled")
                self.btn_ads_power_stop.configure(state="normal")
                self._append_queue_log(f"[QUEUE] 已启动体力广告任务: max_rounds={max_rounds}, cooldown={cooldown}s")

            else:
                self._append_queue_log(f"[QUEUE] 未知任务类型: {task_type}")
                self._queue_start_next_task()
                return

            if task_type in ("world", "tower", "expedition"):
                self.queue_after_id = self.root.after(500, self._queue_check_current_task)

        except Exception as e:
            tb = traceback.format_exc()
            self._append_queue_log(f"[QUEUE] 启动任务失败: {task_name} | {e}")
            self._push_log("ERROR", f"[QUEUE] 启动任务失败：{e}\n{tb}")
            self._queue_start_next_task()

    def _queue_check_current_task(self):
        if not self.queue_running:
            return

        if self.queue_current_index < 0 or self.queue_current_index >= len(self.task_queue):
            self._queue_finish("[QUEUE] 当前任务索引异常，队列结束")
            return

        task = self.task_queue[self.queue_current_index]
        task_type = task["task_type"]

        alive = False

        try:
            if task_type == "world":
                alive = (
                    self.automation is not None and
                    self.automation.worker_thread is not None and
                    self.automation.worker_thread.is_alive()
                )
                if not alive:
                    self.var_running.set("未运行")
                    self.btn_start.configure(state="normal")
                    self.btn_stop.configure(state="disabled")

            elif task_type == "tower":
                alive = (
                    self.tower_automation is not None and
                    self.tower_automation.worker_thread is not None and
                    self.tower_automation.worker_thread.is_alive()
                )
                if not alive:
                    self.var_tower_running.set("未运行")
                    self.btn_tower_start.configure(state="normal")
                    self.btn_tower_stop.configure(state="disabled")

            elif task_type == "expedition":
                alive = (
                    self.expedition_automation is not None and
                    self.expedition_automation.worker_thread is not None and
                    self.expedition_automation.worker_thread.is_alive()
                )
                if not alive:
                    self.var_expedition_running.set("未运行")
                    self.btn_expedition_start.configure(state="normal")
                    self.btn_expedition_stop.configure(state="disabled")

        except Exception as e:
            self._append_queue_log(f"[QUEUE] 检查任务状态异常: {e}")
            alive = False

        if alive:
            self.queue_after_id = self.root.after(500, self._queue_check_current_task)
        else:
            self._append_queue_log(f"[QUEUE] 第 {self.queue_current_index + 1} 个任务已结束，准备下一个")
            self._queue_start_next_task()

    def _queue_finish(self, msg: str):
        self.queue_running = False
        self.queue_current_index = -1

        if self.queue_after_id is not None:
            try:
                self.root.after_cancel(self.queue_after_id)
            except Exception:
                pass
            self.queue_after_id = None

        self.var_queue_status.set("未运行")
        self.btn_queue_start.configure(state="normal")
        self.btn_queue_stop.configure(state="disabled")

        self.btn_start.configure(state="normal")
        self.btn_tower_start.configure(state="normal")
        self.btn_expedition_start.configure(state="normal")
        self.btn_ads_power_start.configure(state="normal")

        self._append_queue_log(msg)

    def _build_about_tab(self, parent: ttk.Frame):
        ttk.Label(parent, text="这里预留做全局设置/模块管理器/调试工具。", style="Hint.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text=
            "v3.0:加入自动爬塔模块,目前在窗口初始化上与抢环模块有一点冲突\n"
            "v2.0:优化了环球难度判断逻辑,现在判断比之前准确一些;加入环球统计功能\n"
            "v1.6:加入自动看广告模块,目前仅支持自动看体力广告,但测试还不够多\n"
            "v1.5:加入中间词条选择开关;优化遇到广告时的处理方法;战斗界面判定条件优化,",
            style="Hint.TLabel"
        ).pack(anchor="w", pady=(6, 0))

    # ---------------- Callbacks (from module threads) ----------------
    def log_cb(self, msg: str):
        """Worker thread safe: push to queue."""
        # Try to infer level from prefix like [INFO]/[WARN]...
        level = "INFO"
        s = msg.strip()
        if s.startswith("[ERROR]") or "ERROR" in s[:10]:
            level = "ERROR"
        elif s.startswith("[WARN]") or s.startswith("[WARNING]"):
            level = "WARN"
        elif s.startswith("[DEBUG]") or s.startswith("[STATE]") or s.startswith("[OCR]") or s.startswith("[TEAM OCR]"):
            level = "DEBUG"
        self.msg_queue.put((level, msg))

    def counter_cb(self, cnt: int):
        """完成局数（int）"""
        self.msg_queue.put(("COUNTER", str(cnt)))

    def current_page_cb(self, page_num):
        """当前页面"""
        # 直接传递数字
        self.msg_queue.put(("VIEW", page_num))

    def world_counts_cb(self, world_counts: dict):
        """ 环球救援统计（dict） """
        self.msg_queue.put(("WORLD_COUNTS", world_counts))
        self._push_log("DEBUG", f"[GUI] 接收到 WORLD_COUNTS 更新: {world_counts}")  # 调试信息
    def mutual_world_log_cb(self, msg: str):
        level = "INFO"
        s = msg.strip()
        if s.startswith("[ERROR]") or "ERROR" in s[:20]:
            level = "ERROR"
        elif s.startswith("[WARN]") or s.startswith("[WARNING]") or "WARN" in s[:20]:
            level = "WARN"
        elif s.startswith("[DEBUG]") or s.startswith("[STATE]"):
            level = "DEBUG"
        self.msg_queue.put((level, msg))

    def mutual_world_page_cb(self, page: str):
        self.msg_queue.put(("MUTUAL_WORLD_PAGE", page))

    # ---------------- Queue polling (GUI thread) ----------------
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "COUNTER":
                    self.var_counter.set(payload)
                elif kind == "VIEW":
                    # print(f'[DEBUG] 页面发生变化，: {payload}')  # 这里输出页面更新的值
                    view_map = {
                        0: "主页",
                        1: "聊天框",
                        2: "招募页",
                        3: "组队页",
                        4: "战斗中",
                    }
                    page_name = view_map.get(payload, "未知页面")
                    self.var_current_page.set(page_name)  # 将更新后的页面名称设置到 GUI
                elif kind == "WORLD_COUNTS":
                    wc = payload
                    for key, val in wc.items():
                        if key in self.var_world_counts:
                            self.var_world_counts[key].set(str(val))
                elif kind == "MUTUAL_WORLD_PAGE":
                    page_map = {
                        "team": "\u7ec4\u961f\u9875",
                        "battle": "\u6218\u6597\u4e2d",
                        "result": "\u7ed3\u7b97\u9875",
                        "invitation": "\u9080\u8bf7\u5f39\u7a97",
                        "waiting_invite": "\u7b49\u5f85\u9080\u8bf7",
                        "unknown": "\u672a\u77e5",
                    }
                    self.var_mutual_world_page.set(page_map.get(payload, str(payload)))
                elif kind == "AD_POWER_DONE":
                    ok = payload["ok"]
                    reason = payload["reason"]

                    self.btn_ads_power_start.configure(state="normal")
                    self.btn_ads_power_stop.configure(state="disabled")

                    self._push_log(
                        "INFO" if ok else "WARN",
                        f"[GUI][AD] 体力广告结束 ok={ok} reason={reason}"
                    )

                    if self.queue_running:
                        self._append_queue_log(f"[QUEUE] 广告任务结束 ok={ok} reason={reason}，准备下一个任务")
                        self._queue_start_next_task()
                else:
                    self._append_log(kind, payload)
        except queue.Empty:
            pass
        finally:
            self.root.after(60, self._poll_queue)

    def _append_log(self, level: str, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"{ts} {msg}\n"
        tag = level if level in ("INFO", "WARN", "ERROR", "DEBUG") else "INFO"

        s = msg.lstrip()

        if s.startswith("[WORLD]") or s.startswith("[GUI]"):
            self.txt_log.insert("end", line, tag)
            self.txt_log.see("end")

        elif s.startswith("[TOWER]"):
            if self.txt_tower_log is not None:
                self.txt_tower_log.insert("end", line, tag)
                self.txt_tower_log.see("end")

        elif s.startswith("[AD]"):
            if self.txt_ads_log is not None:
                self.txt_ads_log.insert("end", line, tag)
                self.txt_ads_log.see("end")
        elif s.startswith("[EXPEDITION]"):
            if self.txt_expedition_log is not None:
                self.txt_expedition_log.insert("end", line, tag)
                self.txt_expedition_log.see("end")
        elif s.startswith("[MUTUAL_WORLD]"):
            if self.txt_mutual_world_log is not None:
                self.txt_mutual_world_log.insert("end", line, tag)
                self.txt_mutual_world_log.see("end")

    def _push_log(self, level: str, msg: str):
        """Direct push from GUI thread."""
        self._append_log(level, msg)

    # ---------------- Button handlers ----------------
    def on_start(self):
        if WorldAutomation is None:
            messagebox.showerror("错误", "WorldAutomation 未导入成功，无法启动。请检查文件位置与导入路径。")
            return

        # Parse params
        window_name = self.var_window_name.get().strip()
        if not window_name:
            messagebox.showwarning("提示", "窗口名不能为空。")
            return

        try:
            expect_diff = int(self.var_expect_diff.get().strip())
        except Exception:
            messagebox.showwarning("提示", "最低难度必须是整数。")
            return
        try:
            click_interval = float(self.var_click_interval.get().strip())
            if click_interval <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("提示", "连点间隔必须是大于0的小数，例如 0.03")
            return

        try:
            world_diff_threshold = float(self.var_world_diff_threshold.get().strip())
            if world_diff_threshold <= 0 or world_diff_threshold > 1:
                raise ValueError
        except Exception:
            messagebox.showwarning("\u63d0\u793a", "\u96be\u5ea6\u8bc6\u522b\u9608\u503c\u9700\u8981\u662f 0~1 \u4e4b\u95f4\u7684\u5c0f\u6570\uff0c\u4f8b\u5982 0.90")
            return

        try:
            battle_auto_exit_minutes = float(self.var_world_battle_auto_exit_minutes.get().strip() or "0")
            if battle_auto_exit_minutes < 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("\u63d0\u793a", "\u6218\u6597\u81ea\u52a8\u9000\u51fa\u65f6\u95f4\u9700\u8981\u662f\u5927\u4e8e\u7b49\u4e8e 0 \u7684\u6570\u5b57\uff0c0 \u8868\u793a\u5173\u95ed")
            return

        invite_only = self.var_invite_only.get()

        # Create module instance if needed
        if self.automation is None:
            try:
                self.automation = WorldAutomation(
                    window_name=window_name,
                    battle_auto_exit_minutes=battle_auto_exit_minutes,
                    auto_resize_window=self._consume_resize_once_flag()
                )
                # set callbacks once
                self.automation.set_callbacks(
                    log_cb=self.log_cb,
                    current_page_cb=self.current_page_cb,
                    counter_cb=self.counter_cb,
                    world_counts_cb=self.world_counts_cb
                )
                self._apply_skill_priority_to_module(self.automation)
                self.btn_ads_power_start.configure(state="normal")
                self._push_log("INFO", f"[GUI] 已初始化 WorldAutomation(window_name='{window_name}')")
            except Exception as e:
                tb = traceback.format_exc()
                self._push_log("ERROR", f"[GUI] 初始化失败：{e}\n{tb}")
                messagebox.showerror("初始化失败", f"{e}")
                self.automation = None
                return
        else:
            # If already exists, you may want to rebind window by recreating instance.
            # For now, just warn if user changed window name.
            if window_name != getattr(self.automation, "window_name", window_name):
                self._push_log("WARN", "[GUI] 已存在 automation 实例；若窗口名改变，建议停止后重启程序或改造模块支持切换窗口。")

        # Start
        try:
            # 同步 GUI 开关状态
            self.automation.mid_entry_click_enabled = self.var_mid_entry_click.get()
            self.automation._min_click_interval = click_interval
            self.automation.world_diff_match_threshold = world_diff_threshold
            self.automation.set_battle_auto_exit_minutes(battle_auto_exit_minutes)
            self.automation.start(
                expect_diff=expect_diff,
                invite_only=invite_only,
                log_cb=self.log_cb,
                current_page_cb=self.current_page_cb,
                counter_cb=self.counter_cb,
                world_counts_cb=self.world_counts_cb
            )
            self.var_running.set("运行中")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.btn_reset.configure(state="normal")
            self.btn_reset_world_counts.configure(state="normal")
            # self.btn_ads_power_start.configure(state="normal")
            self._push_log("INFO", f"[GUI] 启动：EXPECT_DIFF={expect_diff}")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] 启动失败：{e}\n{tb}")
            messagebox.showerror("启动失败", f"{e}")

    def on_stop(self):
        if self.automation is None:
            return
        try:
            self.automation.stop()
            self.var_running.set("未运行")
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self._push_log("INFO", "[GUI] 已请求停止")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] stop() 异常：{e}\n{tb}")

    def on_reset_counter(self):
        if self.automation is None:
            return
        try:
            # Your class has reset_counter()
            if hasattr(self.automation, "reset_counter"):
                self.automation.reset_counter()
            else:
                # fallback: UI reset only
                self.var_counter.set("0")
            self._push_log("INFO", "[GUI] 已重置计数")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] reset_counter() 异常：{e}\n{tb}")

    def on_clear_log(self):
        self.txt_log.delete("1.0", "end")

    def on_copy_log(self):
        try:
            content = self.txt_log.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._push_log("INFO", "[GUI] 日志已复制到剪贴板")
        except Exception as e:
            self._push_log("ERROR", f"[GUI] 复制失败：{e}")

    def on_clear_ads_log(self):
        if self.txt_ads_log is not None:
            self.txt_ads_log.delete("1.0", "end")

    def on_copy_ads_log(self):
        if self.txt_ads_log is None:
            return
        try:
            content = self.txt_ads_log.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._push_log("INFO", "[GUI] 广告日志已复制到剪贴板")
        except Exception as e:
            self._push_log("ERROR", f"[GUI] 复制广告日志失败：{e}")

    def on_close(self):
        try:
            self.on_queue_stop()
        except Exception:
            pass

        try:
            if self.automation is not None:
                self.automation.stop()
                time.sleep(0.05)
        except Exception:
            pass

        try:
            if self.tower_automation is not None:
                self.tower_automation.stop()
                time.sleep(0.05)
        except Exception:
            pass
        
        try:
            if self.expedition_automation is not None:
                self.expedition_automation.stop()
                time.sleep(0.05)
        except Exception:
            pass
        try:
            if self.mutual_world_automation is not None:
                self.mutual_world_automation.stop()
                time.sleep(0.05)
        except Exception:
            pass
        self.root.destroy()

    def on_toggle_mid_entry_click(self):
        enabled = self.var_mid_entry_click.get()
        self._push_log(
            "INFO",
            f"[GUI] 局内自动点击中间词条：{'开启' if enabled else '关闭'}"
        )
        if self.automation is not None:
            setattr(self.automation, "mid_entry_click_enabled", enabled)

    def on_ads_power_done(self, ok: bool, reason: str):
        # worker线程 -> queue
        self.msg_queue.put(("AD_POWER_DONE", {"ok": ok, "reason": reason}))

    def on_reset_world_counts(self):
        if self.automation is None:
            for var in self.var_world_counts.values():
                var.set("0")
            self._push_log("INFO", "[GUI] 已重置环球统计（仅界面）")
            return

        try:
            if hasattr(self.automation, "reset_world_counts"):
                self.automation.reset_world_counts()
            else:
                for var in self.var_world_counts.values():
                    var.set("0")

            self._push_log("INFO", "[GUI] 已重置环球统计")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] reset_world_counts() 异常：{e}\n{tb}")

    def _ensure_ad_watcher(self) -> bool:
        """确保 AdWatcher 已创建且绑定到当前 automation。"""
        if self.automation is None:
            messagebox.showwarning("提示", "请先在“环球抢环”页点击【启动】，初始化窗口后再使用广告模块。")
            return False

        if self.ad_watcher is None:
            try:
                # 按你的文件名改：比如 ad_watcher.py
                from ad_watcher import AdWatcher
                self.ad_watcher = AdWatcher(world=self.automation, scan_interval=300)
                self.ad_watcher.set_callbacks(log_cb=self.log_cb, on_power_done=self.on_ads_power_done)
                self._push_log("INFO", "[GUI] 已初始化 AdWatcher（复用当前 WorldAutomation）")
            except Exception as e:
                tb = traceback.format_exc()
                self._push_log("ERROR", f"[GUI] 初始化 AdWatcher 失败：{e}\n{tb}")
                messagebox.showerror("错误", f"初始化 AdWatcher 失败：{e}")
                self.ad_watcher = None
                return False
        return True

    def on_ads_power_start(self):
        if not self._ensure_ad_watcher():
            return

        try:
            max_rounds = int(self.var_ads_power_rounds.get().strip())
            cooldown = int(self.var_ads_power_cooldown.get().strip())
        except Exception:
            messagebox.showwarning("提示", "max_rounds / cooldown 必须是整数。")
            return

        self.ad_watcher.start_power_ads(max_rounds=max_rounds, cooldown=cooldown)
        self._push_log("INFO", f"[GUI][AD] 启动体力广告：max_rounds={max_rounds}, cooldown={cooldown}s")
        self.btn_ads_power_start.configure(state="disabled")
        self.btn_ads_power_stop.configure(state="normal")

    def on_ads_power_stop(self):
        if self.ad_watcher is None:
            return
        self.ad_watcher.stop_power_ads()
        self._push_log("INFO", "[GUI][AD] 已请求停止体力广告")
        self.btn_ads_power_start.configure(state="normal")
        self.btn_ads_power_stop.configure(state="disabled")

    def on_tower_start(self):
        if TowerAutomation is None:
            messagebox.showerror("错误", "TowerAutomation 未导入成功，无法启动。请检查 tower_automation.py。")
            return

        window_name = self.var_tower_window_name.get().strip()
        if not window_name:
            messagebox.showwarning("提示", "窗口名不能为空。")
            return

        if self.tower_automation is None:
            try:
                self.tower_automation = TowerAutomation(
                    window_name=window_name,
                    auto_resize_window=self._consume_resize_once_flag()
                )
                self.tower_automation.set_callbacks(
                    log_cb=self.log_cb,
                    current_page_cb=self.current_page_cb
                )
                self._apply_skill_priority_to_module(self.tower_automation)
                self._push_log("INFO", f"[GUI] 已初始化 TowerAutomation(window_name='{window_name}')")
            except Exception as e:
                tb = traceback.format_exc()
                self._push_log("ERROR", f"[GUI] 初始化 TowerAutomation 失败：{e}\n{tb}")
                messagebox.showerror("初始化失败", f"{e}")
                self.tower_automation = None
                return

        try:
            self.tower_automation.start(
                log_cb=self.log_cb,
                current_page_cb=self.current_page_cb
            )
            self.var_tower_running.set("运行中")
            self.btn_tower_start.configure(state="disabled")
            self.btn_tower_stop.configure(state="normal")
            self._push_log("INFO", "[GUI] 爬塔模块已启动")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] 启动 TowerAutomation 失败：{e}\n{tb}")
            messagebox.showerror("启动失败", f"{e}")


    def on_tower_stop(self):
        if self.tower_automation is None:
            return
        try:
            self.tower_automation.stop()
            self.var_tower_running.set("未运行")
            self.btn_tower_start.configure(state="normal")
            self.btn_tower_stop.configure(state="disabled")
            self._push_log("INFO", "[GUI] 已请求停止爬塔模块")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] tower stop() 异常：{e}\n{tb}")

    def on_expedition_start(self):
        if ExpeditionAutomation is None:
            messagebox.showerror(
                "错误",
                f"ExpeditionAutomation 未导入成功，无法启动。请检查 expedition_automation.py。\n\n{_expedition_import_err}"
            )
            return

        window_name = self.var_expedition_window_name.get().strip()
        if not window_name:
            messagebox.showwarning("提示", "窗口名不能为空。")
            return

        role_text = self.var_expedition_role.get()
        if role_text == "出票位":
            role = "ticket"
        else:
            role = "fighter"

        smart_option_enabled = self.var_expedition_smart_option.get()
        cancel_ready_timeout = self._get_expedition_cancel_ready_timeout()
        if cancel_ready_timeout is None:
            return

        if self.expedition_automation is None:
            try:
                self.expedition_automation = ExpeditionAutomation(
                    window_name=window_name,
                    role=role,
                    auto_resize_window=self._consume_resize_once_flag()
                )
                self.expedition_automation.set_callbacks(
                    log_cb=self.log_cb
                )
                self._apply_skill_priority_to_module(self.expedition_automation)
                self._push_log(
                    "INFO",
                    f"[GUI] 已初始化 ExpeditionAutomation(window_name='{window_name}', role='{role}')"
                )
            except Exception as e:
                tb = traceback.format_exc()
                self._push_log("ERROR", f"[GUI] 初始化 ExpeditionAutomation 失败：{e}\n{tb}")
                messagebox.showerror("初始化失败", f"{e}")
                self.expedition_automation = None
                return
        else:
            # 允许不重建实例，直接切换出票位/打手位
            self.expedition_automation.role = role
            self._apply_skill_priority_to_module(self.expedition_automation)

        self.expedition_automation.smart_option_enabled = smart_option_enabled
        self.expedition_automation._cancel_ready_timeout = cancel_ready_timeout

        try:
            self.expedition_automation.start(
                log_cb=self.log_cb
            )

            self.var_expedition_running.set("运行中")
            self.var_expedition_role_show.set(role_text)
            self.btn_expedition_start.configure(state="disabled")
            self.btn_expedition_stop.configure(state="normal")

            self._push_log("INFO", f"[GUI] 远征模块已启动，当前身份：{role_text}")

        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] 启动 ExpeditionAutomation 失败：{e}\n{tb}")
            messagebox.showerror("启动失败", f"{e}")


    def on_expedition_stop(self):
        if self.expedition_automation is None:
            return

        try:
            self.expedition_automation.stop()
            self.var_expedition_running.set("未运行")
            self.btn_expedition_start.configure(state="normal")
            self.btn_expedition_stop.configure(state="disabled")
            self._push_log("INFO", "[GUI] 已请求停止远征模块")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] expedition stop() 异常：{e}\n{tb}")


    def _mutual_world_friend_template_candidates(self, friend_name: str, role: str = "ticket"):
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "template")
        role_prefix = "no_ticket" if role == "non_ticket" else "ticket"
        alias_map = {
            "\u5929\u5929\u5f00\u5fc3": [
                f"{role_prefix}_friend_tiantiankaixin.png",
                "friend_tiantiankaixin.png",
            ],
            "\u4f46\u6b32\u5b63\u5b63\u5982\u6625": [
                f"{role_prefix}_friend_danyujijiruchun.png",
                "friend_danyujijiruchun.png",
            ],
            "\u6625\u98ce\u5341\u91cc": [
                f"{role_prefix}_friend_chunfengshili.png",
                "friend_chunfengshili.png",
            ],
        }
        names = [
            *alias_map.get(friend_name, []),
            f"{friend_name}.png",
            f"friend_{friend_name}.png",
            f"teammate_{friend_name}.png",
        ]
        return [os.path.join(template_dir, name) for name in names]

    def _resolve_mutual_world_friend_template(self, friend_name: str, role: str = "ticket"):
        manual_key = (role, friend_name)
        if manual_key in self.mutual_world_friend_templates:
            return self.mutual_world_friend_templates[manual_key]
        if friend_name in self.mutual_world_friend_templates:
            return self.mutual_world_friend_templates[friend_name]
        for path in self._mutual_world_friend_template_candidates(friend_name, role=role):
            if os.path.exists(path):
                return path
        return ""

    def _get_mutual_world_role(self):
        role_text = self.var_mutual_world_role.get().strip()
        return "non_ticket" if role_text == "\u975e\u51fa\u7968\u4f4d" else "ticket"

    def _refresh_mutual_world_friend_combo(self):
        if self.cmb_mutual_world_friend is None:
            return
        names = ["\u4f46\u6b32\u5b63\u5b63\u5982\u6625", "\u5929\u5929\u5f00\u5fc3", "\u6625\u98ce\u5341\u91cc"]
        for key in self.mutual_world_friend_templates:
            name = key[1] if isinstance(key, tuple) else key
            if name not in names:
                names.append(name)
        self.cmb_mutual_world_friend.configure(values=names)

    def on_mutual_world_friend_changed(self, event=None):
        friend_name = self.var_mutual_world_friend_name.get().strip()
        role = self._get_mutual_world_role()
        self.var_mutual_world_friend_template.set(
            self._resolve_mutual_world_friend_template(friend_name, role=role)
        )

    def on_mutual_world_choose_template(self):
        path = filedialog.askopenfilename(
            title="\u9009\u62e9\u961f\u53cb\u6a21\u677f",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp"),
                ("All files", "*.*"),
            ]
        )
        if path:
            friend_name = os.path.splitext(os.path.basename(path))[0]
            role = self._get_mutual_world_role()
            self.mutual_world_friend_templates[(role, friend_name)] = path
            self.var_mutual_world_friend_name.set(friend_name)
            self._refresh_mutual_world_friend_combo()
            self.var_mutual_world_friend_template.set(path)

    def on_mutual_world_start(self):
        if MutualWorldAutomation is None:
            messagebox.showerror(
                "\u9519\u8bef",
                f"MutualWorldAutomation \u672a\u5bfc\u5165\u6210\u529f\uff0c\u65e0\u6cd5\u542f\u52a8\u3002\n\n{_mutual_world_import_err}"
            )
            return

        window_name = self.var_mutual_world_window_name.get().strip()
        if not window_name:
            messagebox.showwarning("\u63d0\u793a", "\u7a97\u53e3\u540d\u4e0d\u80fd\u4e3a\u7a7a")
            return

        role_text = self.var_mutual_world_role.get().strip()
        role = "non_ticket" if role_text == "\u975e\u51fa\u7968\u4f4d" else "ticket"
        friend_name = self.var_mutual_world_friend_name.get().strip()
        friend_template = self.var_mutual_world_friend_template.get().strip()
        template_basename = os.path.basename(friend_template)
        auto_template_names = {
            "friend_tiantiankaixin.png",
            "ticket_friend_tiantiankaixin.png",
            "no_ticket_friend_tiantiankaixin.png",
            "friend_danyujijiruchun.png",
            "ticket_friend_danyujijiruchun.png",
            "no_ticket_friend_danyujijiruchun.png",
            "friend_chunfengshili.png",
            "ticket_friend_chunfengshili.png",
            "no_ticket_friend_chunfengshili.png",
        }
        if not friend_template or template_basename in auto_template_names:
            friend_template = self._resolve_mutual_world_friend_template(friend_name, role=role)
            self.var_mutual_world_friend_template.set(friend_template)

        try:
            threshold = float(self.var_mutual_world_threshold.get().strip())
            if threshold <= 0 or threshold > 1:
                raise ValueError
        except Exception:
            messagebox.showwarning("\u63d0\u793a", "\u5339\u914d\u9608\u503c\u9700\u8981\u662f 0~1 \u4e4b\u95f4\u7684\u5c0f\u6570\uff0c\u4f8b\u5982 0.85")
            return

        smart_option_enabled = self.var_mutual_world_smart_option.get()
        try:
            battle_auto_exit_minutes = float(self.var_mutual_world_battle_auto_exit_minutes.get().strip() or "0")
            if battle_auto_exit_minutes < 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("\u63d0\u793a", "\u6218\u6597\u81ea\u52a8\u9000\u51fa\u65f6\u95f4\u9700\u8981\u662f\u5927\u4e8e\u7b49\u4e8e 0 \u7684\u6570\u5b57\uff0c0 \u8868\u793a\u5173\u95ed")
            return

        if self.mutual_world_automation is None:
            try:
                self.mutual_world_automation = MutualWorldAutomation(
                    window_name=window_name,
                    role=role,
                    friend_name=friend_name,
                    friend_template_path=friend_template,
                    friend_match_threshold=threshold,
                    smart_option_enabled=smart_option_enabled,
                    battle_auto_exit_minutes=battle_auto_exit_minutes,
                    auto_resize_window=self._consume_resize_once_flag()
                )
                self.mutual_world_automation.set_callbacks(
                    log_cb=self.mutual_world_log_cb,
                    current_page_cb=self.mutual_world_page_cb
                )
                self._apply_skill_priority_to_module(self.mutual_world_automation)
                self._push_log("INFO", f"[GUI] MutualWorldAutomation initialized role={role_text}")
            except Exception as e:
                tb = traceback.format_exc()
                self._push_log("ERROR", f"[GUI] MutualWorldAutomation init failed: {e}\n{tb}")
                messagebox.showerror("\u521d\u59cb\u5316\u5931\u8d25", f"{e}")
                self.mutual_world_automation = None
                return
        else:
            self.mutual_world_automation.role = role
            self.mutual_world_automation.friend_name = friend_name
            self.mutual_world_automation.friend_match_threshold = threshold
            self.mutual_world_automation.smart_option_enabled = smart_option_enabled
            self.mutual_world_automation.set_battle_auto_exit_minutes(battle_auto_exit_minutes)
            self.mutual_world_automation.set_friend_template_path(friend_template)
            self._apply_skill_priority_to_module(self.mutual_world_automation)

        try:
            self.mutual_world_automation.start(
                role=role,
                log_cb=self.mutual_world_log_cb,
                current_page_cb=self.mutual_world_page_cb
            )
            self.var_mutual_world_running.set("\u8fd0\u884c\u4e2d")
            self.var_mutual_world_page.set("\u672a\u77e5")
            self.btn_mutual_world_start.configure(state="disabled")
            self.btn_mutual_world_stop.configure(state="normal")
            self._push_log("INFO", f"[GUI] \u4e92\u73af\u6a21\u5f0f\u5df2\u542f\u52a8\uff0c\u8eab\u4efd={role_text}")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] MutualWorldAutomation start failed: {e}\n{tb}")
            messagebox.showerror("\u542f\u52a8\u5931\u8d25", f"{e}")

    def on_mutual_world_stop(self):
        if self.mutual_world_automation is None:
            return
        try:
            self.mutual_world_automation.stop()
            self.var_mutual_world_running.set("\u672a\u8fd0\u884c")
            self.btn_mutual_world_start.configure(state="normal")
            self.btn_mutual_world_stop.configure(state="disabled")
            self._push_log("INFO", "[GUI] \u4e92\u73af\u6a21\u5f0f\u5df2\u505c\u6b62")
        except Exception as e:
            tb = traceback.format_exc()
            self._push_log("ERROR", f"[GUI] mutual world stop failed: {e}\n{tb}")

    def on_clear_mutual_world_log(self):
        if self.txt_mutual_world_log is not None:
            self.txt_mutual_world_log.delete("1.0", "end")

    def on_copy_mutual_world_log(self):
        if self.txt_mutual_world_log is None:
            return
        try:
            content = self.txt_mutual_world_log.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._push_log("INFO", "[GUI] \u4e92\u73af\u65e5\u5fd7\u5df2\u590d\u5236")
        except Exception as e:
            self._push_log("ERROR", f"[GUI] \u590d\u5236\u4e92\u73af\u65e5\u5fd7\u5931\u8d25: {e}")

    def on_clear_expedition_log(self):
        if self.txt_expedition_log is not None:
            self.txt_expedition_log.delete("1.0", "end")


    def on_copy_expedition_log(self):
        if self.txt_expedition_log is None:
            return

        try:
            content = self.txt_expedition_log.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._push_log("INFO", "[GUI] 远征日志已复制到剪贴板")
        except Exception as e:
            self._push_log("ERROR", f"[GUI] 复制远征日志失败：{e}")
            
    def on_clear_tower_log(self):
        if self.txt_tower_log is not None:
            self.txt_tower_log.delete("1.0", "end")


    def on_copy_tower_log(self):
        if self.txt_tower_log is None:
            return
        try:
            content = self.txt_tower_log.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._push_log("INFO", "[GUI] 爬塔日志已复制到剪贴板")
        except Exception as e:
            self._push_log("ERROR", f"[GUI] 复制爬塔日志失败：{e}")
    
    def _consume_resize_once_flag(self) -> bool:
        """
        本次程序运行中只允许第一次返回 True。
        后续再调用都返回 False。
        """
        if self.window_resized_once:
            return False
        self.window_resized_once = True
        return True
def main():
    root = tk.Tk()
    # 强行固定缩放系数
    # root.tk.call('tk', 'scaling', 1.0)
    app = AppGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
