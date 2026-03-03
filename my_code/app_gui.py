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
import queue
import traceback
import tkinter as tk
from tkinter import ttk, messagebox
from modules.world_automation import WorldAutomation

class AppGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("向僵尸开炮 - 自动化控制台")
        self.root.geometry("980x720")
        self.root.minsize(900, 650)

        # Thread-safe message queue: worker threads -> GUI thread
        self.msg_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()

        # Module instance
        self.automation = None

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
            self._push_log("ERROR", f"无法导入 WorldAutomation：\n{_import_err}\n"
                                    f"请确认：\n"
                                    f"1) modules/world_automation.py 存在并包含 WorldAutomation\n"
                                    f"或\n"
                                    f"2) world_automation.py 与 app_gui.py 同级\n")

    # ---------------- UI build ----------------
    def _build_style(self):
        style = ttk.Style(self.root)
        # Use default theme if available
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TButton", padding=6)
        style.configure("Header.TLabel", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Hint.TLabel", foreground="#666666")

    def _build_layout(self):
        # Top header
        header = ttk.Frame(self.root, padding=(12, 10))
        header.pack(fill="x")

        ttk.Label(header, text="环球抢票模块-季季如春", style="Header.TLabel").pack(side="left")
        ttk.Label(header, text="日志/计数回调已做线程安全队列转发", style="Hint.TLabel").pack(side="left", padx=12)

        # Notebook (Tabs)
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Tab: 环球抢环
        self.tab_world = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_world, text="环球抢环")

        # Tab: 设置/关于（占位）
        self.tab_about = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_about, text="设置/关于")

        self._build_world_tab(self.tab_world)
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

        # Window name
        ttk.Label(grp, text="窗口名（FindWindow）").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.var_window_name = tk.StringVar(value="向僵尸开炮")
        ent_win = ttk.Entry(grp, textvariable=self.var_window_name, width=22)
        ent_win.grid(row=0, column=1, sticky="w", pady=(0, 6))

        # Expect diff
        ttk.Label(grp, text="最低难度 EXPECT_DIFF").grid(row=1, column=0, sticky="w", pady=(0, 6))
        self.var_expect_diff = tk.StringVar(value="7")
        ent_diff = ttk.Entry(grp, textvariable=self.var_expect_diff, width=22)
        ent_diff.grid(row=1, column=1, sticky="w", pady=(0, 6))

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

        # Counter display
        grp2 = ttk.LabelFrame(left, text="状态", padding=10)
        grp2.pack(fill="x", pady=(12, 0))

        ttk.Label(grp2, text="完成局数：").grid(row=0, column=0, sticky="w")
        self.var_counter = tk.StringVar(value="0")
        self.lbl_counter = ttk.Label(grp2, textvariable=self.var_counter, font=("Consolas", 14, "bold"))
        self.lbl_counter.grid(row=0, column=1, sticky="w")

        self.var_running = tk.StringVar(value="未运行")
        ttk.Label(grp2, text="运行状态：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(grp2, textvariable=self.var_running).grid(row=1, column=1, sticky="w", pady=(8, 0))

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

    def _build_about_tab(self, parent: ttk.Frame):
        ttk.Label(parent, text="这里预留做全局设置/模块管理器/调试工具。", style="Hint.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text="建议后续做一个 ModuleManager：统一“只能有一个模块控制窗口”，避免冲突。",
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
        """Worker thread safe: push counter update."""
        self.msg_queue.put(("COUNTER", str(cnt)))

    # ---------------- Queue polling (GUI thread) ----------------
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "COUNTER":
                    self.var_counter.set(payload)
                else:
                    self._append_log(kind, payload)
        except queue.Empty:
            pass
        finally:
            self.root.after(60, self._poll_queue)

    def _append_log(self, level: str, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"{ts} {msg}\n"
        self.txt_log.insert("end", line, level if level in ("INFO", "WARN", "ERROR", "DEBUG") else "INFO")
        self.txt_log.see("end")

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

        # Create module instance if needed
        if self.automation is None:
            try:
                self.automation = WorldAutomation(window_name=window_name)
                # set callbacks once
                self.automation.set_callbacks(log_cb=self.log_cb, counter_cb=self.counter_cb)
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
            self.automation.start(expect_diff=expect_diff, log_cb=self.log_cb, counter_cb=self.counter_cb)
            self.var_running.set("运行中")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.btn_reset.configure(state="normal")
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

    def on_close(self):
        # Graceful stop
        try:
            if self.automation is not None:
                self.automation.stop()
                # Give a tiny time slice to let threads settle (non-blocking)
                time.sleep(0.05)
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    # 强行固定缩放系数
    # root.tk.call('tk', 'scaling', 1.0)
    app = AppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()