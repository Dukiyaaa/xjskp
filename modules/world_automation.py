#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 必要的库导入
import win32gui
import win32ui
import win32con
import win32api
import numpy as np
import cv2 as cv
import threading
import time
import os
import sys
from ctypes import windll
import random
import re
from template_matcher import *

from pathlib import Path
'''def resource_path(rel_path: str) -> str:
    """
    rel_path: 相对“项目根目录 my_code”的路径，如 r"images\\template\\main_start_game.png"
    - 开发环境：以 my_code 为根
    - PyInstaller：以 sys._MEIPASS 为根
    """
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        # 当前文件在 my_code/modules/world_automation.py
        # 所以项目根目录 = world_automation.py 的上一级（modules）的上一级 = my_code
        base = Path(__file__).resolve().parent.parent

    return str(base / rel_path)'''

def resource_path(rel_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)

# ---------------------- 环球抢票类，包含抢票、判断等级、退出队伍 ----------------------
class WorldAutomation:
    def __init__(self, window_name="向僵尸开炮"):
        # 用于记录每个“环球救援”任务的计数器
        self.world_counts = {f"world_{i + 1}": 0 for i in range(20)}
        self.world_counts["world_none"] = 0  # 初始化 21 个环球救援任务的计数器
        self.world_counts_cb = None
        # 模板路径字典，存储多个模板路径
        template_paths = {
            # 主页：开始游戏
            "start_game": resource_path(r"images\template\main_start_game.png"),
            # 主页：聊天框
            "main_chat": resource_path(r"images\template\main_chat.png"),
            # 主页，带红点的聊天框
            "main_chat_notice": resource_path(r"images\template\main_chat_notice.png"),
            # 主页，带军团公告的聊天框
            "main_chat_army": resource_path(r"images\template\main_chat_army.png"),
            # 聊天框：招募
            "chat_recruit": resource_path(r"images\template\chat_recruit.png"),
            # 组队界面：退出按钮
            "team_exit": resource_path(r"images\template\team_exit.png"),
            # 组队界面：环球救援难度
            "world_diff_1": resource_path(r"images\template\world_diff_1.png"),
            "world_diff_2": resource_path(r"images\template\world_diff_2.png"),
            "world_diff_3": resource_path(r"images\template\world_diff_3.png"),
            "world_diff_4": resource_path(r"images\template\world_diff_4.png"),
            "world_diff_5": resource_path(r"images\template\world_diff_5.png"),
            "world_diff_6": resource_path(r"images\template\world_diff_6.png"),
            "world_diff_7": resource_path(r"images\template\world_diff_7.png"),
            "world_diff_8": resource_path(r"images\template\world_diff_8.png"),
            "world_diff_9": resource_path(r"images\template\world_diff_9.png"),
            "world_diff_10": resource_path(r"images\template\world_diff_10.png"),
            "world_diff_11": resource_path(r"images\template\world_diff_11.png"),
            "world_diff_12": resource_path(r"images\template\world_diff_12.png"),
            "world_diff_13": resource_path(r"images\template\world_diff_13.png"),
            "world_diff_14": resource_path(r"images\template\world_diff_14.png"),
            "world_diff_15": resource_path(r"images\template\world_diff_15.png"),
            "world_diff_16": resource_path(r"images\template\world_diff_16.png"),
            "world_diff_17": resource_path(r"images\template\world_diff_17.png"),
            "world_diff_18": resource_path(r"images\template\world_diff_18.png"),
            "world_diff_19": resource_path(r"images\template\world_diff_19.png"),
            "world_diff_20": resource_path(r"images\template\world_diff_20.png"),
            # "recruit_button": resource_path(r"images\template\recruit_button.png"),
            "game_has_started": resource_path(r"images\template\game_has_started.png"),
            "master_left": resource_path(r"images\template\master_left.png"),
            "game_over_return": resource_path(r"images\template\game_over_return.png"),
            "invite": resource_path(r"images\template\invite.png"),
            "world_save_flag": resource_path(r"images\template\world_save_flag.png"),
            "fight": resource_path(r"images\template\fight.png"),
            "cancel": resource_path(r"images\template\cancel.png"),
            "cancel_time_act": resource_path(r"images\template\cancel_time_act.png"),
            "cross_server": resource_path(r"images\template\cross_server.png"),
            "upgrade_coin": resource_path(r"images\template\upgrade_coin.png"),
            "chart": resource_path(r"images\template\chart.png"),

            # 局内环球难度 目前只做到了12
            "world_diff_in_game_1": resource_path(r"images\template\world_diff_in_game_1.png"),
            "world_diff_in_game_2": resource_path(r"images\template\world_diff_in_game_2.png"),
            "world_diff_in_game_3": resource_path(r"images\template\world_diff_in_game_3.png"),
            "world_diff_in_game_4": resource_path(r"images\template\world_diff_in_game_4.png"),
            "world_diff_in_game_5": resource_path(r"images\template\world_diff_in_game_5.png"),
            "world_diff_in_game_6": resource_path(r"images\template\world_diff_in_game_6.png"),
            "world_diff_in_game_7": resource_path(r"images\template\world_diff_in_game_7.png"),
            "world_diff_in_game_8": resource_path(r"images\template\world_diff_in_game_8.png"),
            "world_diff_in_game_9": resource_path(r"images\template\world_diff_in_game_9.png"),
            "world_diff_in_game_10": resource_path(r"images\template\world_diff_in_game_10.png"),
            "world_diff_in_game_11": resource_path(r"images\template\world_diff_in_game_11.png"),
            "world_diff_in_game_12": resource_path(r"images\template\world_diff_in_game_12.png"),
            "world_diff_in_game_13": resource_path(r"images\template\world_diff_in_game_13.png"),
            "world_diff_in_game_14": resource_path(r"images\template\world_diff_in_game_14.png"),
            "world_diff_in_game_15": resource_path(r"images\template\world_diff_in_game_15.png"),
            "world_diff_in_game_16": resource_path(r"images\template\world_diff_in_game_16.png"),
            "world_diff_in_game_17": resource_path(r"images\template\world_diff_in_game_17.png"),
            "world_diff_in_game_18": resource_path(r"images\template\world_diff_in_game_18.png"),
            "world_diff_in_game_19": resource_path(r"images\template\world_diff_in_game_19.png"),
            "world_diff_in_game_20": resource_path(r"images\template\world_diff_in_game_20.png"),

            "resource": resource_path(r"images\template\resource.png"),
            "reconnect": resource_path(r"images\template\reconnect.png"),
            # 其他模板路径...
        }
        self.template_paths = template_paths
        # 初始化模板匹配类，传入多个模板路径
        self.template_matcher = TemplateMatcher(template_paths)

        # --- GUI/控制用：运行开关 + 工作线程占位 ---
        self._confirm_xy = None
        self.run_event = threading.Event()
        self.worker_thread = None

        # --- GUI 可选回调：日志/计数 ---
        self.log_cb = None
        self.counter_cb = None
        self.current_page_cb = None

        # 用于计数打了多少把环
        self.test_cnt = 0
        # 游戏窗口位置和大小
        self.X_POS = 0
        self.Y_POS = 0
        self.WIDTH = 400
        self.HEIGHT = 750

        # 游戏界面固定按钮坐标
        # ================= 标准画布尺寸 =================
        self.BASE_W, self.BASE_H = 774, 1487

        # ================= 标准画布点击坐标 =================
        self.PT = {
            # 主页
            "chat": (743, 846),
            "start_game": (384, 1239),

            # 聊天页
            "recruit": (140, 426),   # 这个建议你再实际截一张图确认一次

            # 招募页
            "confirm": (400, 952),

            # 资源页
            "resource_back": (404, 1400),

            # 组队页退队
            "leave_step1": (81, 1411),
            "leave_step2": (526, 928),

            # 战斗结算
            "game_over_return": (395, 1305),

            # 战斗中技能
            "skill_center": (379, 751),
            "skill_left": (95, 1184),
            "skill_right": (715, 1184),
            "mecha_skill": (711, 1028),
        }

        # ================= 标准画布 ROI =================
        self.ROI = {
            "team_world_text": (194, 188, 644, 260),
            "start_game_text": (288, 1186, 492, 1242),
            "team_leave_text": (645, 1188, 698, 1222),
            "in_game_diff_text": (400, 103, 516, 148),
            "game_over_return_text": (348, 1292, 442, 1337),
        }

        # 双线程,一个线程负责连点,一个线程负责截图判断是否停止点击
        self.stop_click_event = threading.Event()  # 用来让连点线程停下来
        self.click_thread = None
        # 抢环关键词
        self.keyword = "救援"
        # 运行状态开关
        self.IS_RUNNING = False
        # 重试次数,如果ocr持续识别不到文字,说明页面有问题,需返回首页
        self.RETRY = 0
        # 想打的最低级环
        self.EXPECT_DIFF = 7
        # 状态机管理 0:主页 1:聊天框 2:招募框 3:组队页面
        self.VIEW = 0
        # 鼠标点击间隔
        self._last_click_ts = 0.0
        self._min_click_interval = 0.025  # 25ms，建议 40~120ms 之间调
        # 初始化 OCR 读取器
        # self.OCR_READER = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        # 进入组队页面后，用于判断是否需要判断难度
        self.diff = None
        # 战斗日志记录
        # --- 单局统计 ---
        self._run_idx = 0  # 第几把（从 0 计起，开局时 +1）
        self._game_start_ts = None  # 本局开始时间戳
        self._game_diff = None  # 本局难度（进入战斗前记录）
        # 获取窗口句柄
        self.HWND = win32gui.FindWindow(None, window_name)  # 获取标题为“向僵尸开炮”的窗口的句柄
        self.TEMPLATE_IMGS = {}
        # 巡检
        self.SCAN_INTERVAL = 600  # 10分钟一次巡检
        self.SCAN_RETRY = 5  # 失败后最多重试次数
        self.SCAN_RETRY_GAP = 3  # 重试间隔（秒）
        self.VIEW_UNKNOWN = -1  # detect_view 识别失败时返回 -1

        if self.HWND == 0:
            raise RuntimeError(f"未找到窗口：{window_name}（FindWindow 失败）")
        else:
            win32gui.MoveWindow(self.HWND, self.X_POS, self.Y_POS, self.WIDTH, self.HEIGHT, True)
            if win32gui.IsIconic(self.HWND):
                win32gui.ShowWindow(self.HWND, win32con.SW_RESTORE)
                time.sleep(0.2)
    # GUI日志打印
    def _log(self, msg):
        msg = f"[WORLD] {msg}"
        if self.log_cb:
            self.log_cb(msg)
        else:
            print(msg)
    # 相对坐标计算
    def _abs_xy(self, scene_bgr: np.ndarray, x_c: float, y_c: float):
        """把相对坐标(0~1)转换为当前截图上的绝对像素坐标"""
        h, w = scene_bgr.shape[:2]
        return int(w * x_c), int(h * y_c)

    def _abs_roi(self, scene_bgr: np.ndarray, x1_c: float, y1_c: float, x2_c: float, y2_c: float):
        """把相对ROI转换为当前截图上的绝对像素ROI (x1,y1,x2,y2)"""
        h, w = scene_bgr.shape[:2]
        return (int(w * x1_c), int(h * y1_c), int(w * x2_c), int(h * y2_c))

    def _emit_counter(self):
        """把当前计数推给 GUI（如果有回调）"""
        if self.counter_cb:
            try:
                self.counter_cb(self.test_cnt)
            except Exception as e:
                self._log(f"[COUNTER_CB_ERROR] {e}")

    def _inc_counter(self, step=1):
        self.test_cnt += step
        self._log(f"[COUNTER] 已完成 {self.test_cnt} 局")
        self._emit_counter()

    def _inc_world_count(self, world_number: int | None):
        if world_number is None:
            world_key = "world_none"
            world_name = "None"
        else:
            world_key = f"world_{world_number}"
            world_name = f"环球救援{world_number}"

        if world_key in self.world_counts:
            self.world_counts[world_key] += 1
            self._log(f"[WORLD] {world_name} 已打 {self.world_counts[world_key]} 次")

            if self.world_counts_cb:
                self.world_counts_cb(self.world_counts)

    def _emit_view(self, v: int):
        if self.current_page_cb:
            try:
                # self._log("[DEBUG] automation触发page改变")
                self.current_page_cb(v)
            except Exception as e:
                self._log(f"[VIEW_CB_ERROR] {e}")
        else:
            self._log("[DEBUG] current_page_cb为None")

    def set_view(self, v: int):
        if v == self.VIEW:
            return
        self.VIEW = v
        self._emit_view(v)

    # 用于调试，保存截图
    def debug_dump_capture(self, scene_bgr: np.ndarray, name: str = "debug_capture"):
        h, w = scene_bgr.shape[:2]
        self._log(f"[CAP] screenshot size = {w}x{h}")
        try:
            import cv2 as cv
            fn = f"{name}_{w}x{h}.png"
            cv.imwrite(fn, scene_bgr)
            self._log(f"[CAP] saved => {fn}")
        except Exception as e:
            self._log(f"[CAP_ERROR] save failed: {e}")

    def debug_template_score(self, scene_bgr: np.ndarray, template_name: str, threshold: float = 0.90):
        try:
            found, score, top_left, tpl_hw = self.template_matcher.match_template(
                scene_bgr, template_name, threshold=threshold
            )
            self._log(
                f"[TPL] {template_name}: found={found} score={score:.3f} top_left={top_left} tpl_hw={tpl_hw} thr={threshold}"
            )
            return found, score, top_left, tpl_hw
        except Exception as e:
            self._log(f"[TPL_ERROR] {template_name}: {e}")
            return False, 0.0, None, None

    def debug_check_templates(self):
        # TemplateMatcher 里保存的 template_paths
        if not hasattr(self, "template_paths"):
            self._log("[TPL_PATH] self.template_paths not found (please store it in __init__)")
            return

        missing = []
        for k, p in self.template_paths.items():
            if not os.path.exists(p):
                missing.append((k, p))

        if not missing:
            self._log("[TPL_PATH] all templates exist")
        else:
            self._log(f"[TPL_PATH] missing {len(missing)} templates:")
            for k, p in missing[:10]:
                self._log(f"  - {k}: {p}")

    def _game_begin(self, diff: int | None):
        """记录开局信息，并打日志"""
        self._run_idx += 1
        self._game_start_ts = time.time()
        self._game_diff = diff
        self._log(f"[GAME] 第{self._run_idx}把开始 | 难度={diff} | 可在左侧按钮勾选是否自动选择中间词条")

    def _game_end(self):
        """记录结束信息，并打日志"""
        if self._game_start_ts is None:
            # 防御：如果没记录开局就结束了
            self._log("[GAME] 检测到结束，但未记录开局时间（可能是中途启动/异常跳转）")
            return

        cost = time.time() - self._game_start_ts
        diff = self._game_diff
        self._log(f"[GAME] 第{self._run_idx}把结束 | 难度={diff} | 耗时={cost:.1f}s")

        # 清空本局数据
        self._game_start_ts = None
        self._game_diff = None

    def reset_counter(self):
        self.test_cnt = 0
        self._emit_counter()
        self._log("[COUNTER] 已重置为 0")

    def reset_world_counts(self):
        for key in self.world_counts:
            self.world_counts[key] = 0

        if self.world_counts_cb:
            try:
                self.world_counts_cb(self.world_counts)
            except Exception as e:
                self._log(f"[WORLD_COUNTS_CB_ERROR] {e}")

        self._log("[WORLD] 环球统计已重置为 0")

    def find_button(self, scene_bgr, template_name):
        """
        使用模板匹配查找按钮
        :param scene_bgr: 截图图像
        :param template_name: 模板名称
        :return: 按钮位置 (x, y) 或 None
        """
        # 传递模板名称到模板匹配方法
        found, score, top_left, tpl_hw = self.template_matcher.match_template(scene_bgr, template_name, threshold=0.85)
        if found:
            center_x, center_y = self.template_matcher.get_center_position(top_left, tpl_hw)
            return center_x, center_y
        # else:
            # self._log(f"[DEBUG] 没有找到该标志,匹配得分为:{score}")
        return None
    # ===================== GUI友好：对外控制接口（第1步） =====================
    def set_callbacks(self, log_cb=None, counter_cb=None, current_page_cb=None, world_counts_cb=None):
        self.log_cb = log_cb
        self.counter_cb = counter_cb  # 完成局数 int
        self.current_page_cb = current_page_cb  # 当前所处页面的回调
        self.world_counts_cb = world_counts_cb  # 环球救援 dict

    def start(self, expect_diff: int = None, log_cb=None, counter_cb=None, current_page_cb=None, world_counts_cb=None):
        """
        启动抢环球（非阻塞）：内部开线程跑 word_click()
        - expect_diff: 设定最低难度
        - log_cb/counter_cb/world_counts_cb: GUI回调（可选）
        """
        # 已经在跑就不重复启动
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self._log("[WARN] WorldAutomation 已在运行中，忽略重复 start()")
            return

        if log_cb is not None or counter_cb is not None or current_page_cb is not None or world_counts_cb is not None:
            self.set_callbacks(log_cb=log_cb, counter_cb=counter_cb, current_page_cb=current_page_cb, world_counts_cb=world_counts_cb)

        if expect_diff is not None:
            try:
                self.EXPECT_DIFF = int(expect_diff)
            except Exception:
                self._log(f"[WARN] expect_diff={expect_diff} 非法，保持原值 EXPECT_DIFF={self.EXPECT_DIFF}")

        # 开关置为运行
        self.run_event.set()

        # 可选：每次开始前重置一些状态，避免上次停在半路
        self.VIEW = 0

        self.RETRY = 0
        # 计数是否要重置看你需求；这里先不动 test_cnt（你可以自己手动清零）
        # self.test_cnt = 0

        self._log(f"[INFO] 启动抢环球：最低难度 EXPECT_DIFF={self.EXPECT_DIFF}")

        def _worker():
            try:
                # 这里就是你原来的阻塞逻辑
                self.word_click()
            except Exception as e:
                self._log(f"[ERROR] worker 异常退出：{e}")
            finally:
                # 确保退出时连点线程被停掉
                try:
                    self.stop_clicking()
                except Exception:
                    pass
                self.run_event.clear()
                self._log("[INFO] 抢环球线程已停止")

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """停止抢环球（尽量立刻停）：清run_event + 停连点线程"""
        if not self.run_event.is_set():
            self._log("[INFO] 当前未运行，无需 stop()")
            return

        self._log("[INFO] 正在停止抢环球...")
        self.run_event.clear()
        # 如果正在战斗中被停止，输出本局已运行时间
        if self._game_start_ts is not None:
            cost = time.time() - self._game_start_ts
            self._log(f"[GAME] 手动停止 | 第{self._run_idx}把进行中 | 已耗时={cost:.1f}s | 难度={self._game_diff}")

        # 立刻停连点，避免还在狂点
        try:
            self.stop_clicking()
        except Exception:
            pass

        # GUI里一般不建议 join 卡住界面，所以这里不 join
        # 如果你想在命令行模式等待线程退出，可以手动在外部 join
# ---------------------- 后台截图函数（优化后：消除冗余操作） ----------------------
    # 我自己电脑的截图尺寸(宽,高)，别人电脑上要想跑起来必须统一尺寸
    def normalize_scene(self, scene_bgr):
        h, w = scene_bgr.shape[:2]
        if (w, h) == (self.BASE_W, self.BASE_H):
            return scene_bgr
        return cv.resize(scene_bgr, (self.BASE_W, self.BASE_H), interpolation=cv.INTER_LINEAR)

    def bkgnd_full_window_screenshot(self) -> np.ndarray:
        """
        截取指定窗口的图像，返回截图的 numpy 数组。
        """
        # 如果窗口最小化，先恢复
        # if win32gui.IsIconic(self.HWND):
        #     win32gui.ShowWindow(self.HWND, win32con.SW_RESTORE)
        #     time.sleep(0.2)  # 给一点点时间让窗口重绘/恢复
        windll.user32.SetProcessDPIAware()  # 抑制系统缩放
        rect = win32gui.GetClientRect(self.HWND)  # 获取窗口客户区坐标
        width, height = rect[2] - rect[0], rect[3] - rect[1]

        hwnd_dc = win32gui.GetWindowDC(self.HWND)  # 获取设备上下文
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        # 创建位图对象
        save_bit_map = win32ui.CreateBitmap()
        save_bit_map.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bit_map)

        # 使用 PrintWindow 截图
        result = windll.user32.PrintWindow(self.HWND, save_dc.GetSafeHdc(), 3)
        if result != 1:
            self._log("[WARNING] PrintWindow 截图可能失败")

        # 获取位图数据并转换为 numpy 数组
        bmpinfo = save_bit_map.GetInfo()
        bmpstr = save_bit_map.GetBitmapBits(True)
        capture = np.frombuffer(bmpstr, dtype=np.uint8).reshape((bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4))
        capture = np.ascontiguousarray(capture)[..., :-1]

        # 临时保存截图，用于调试
        # cv.imwrite("debug_screenshot.png", capture)

        # 释放资源
        win32gui.DeleteObject(save_bit_map.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(self.HWND, hwnd_dc)

        capture = self.normalize_scene(capture)
        return capture

# ---------------------- 点击相关函数，包括指定坐标点击(先移鼠标再点，更稳定)、直接点(速度更快)---------------------
    def _map_norm_to_client(self, x, y):
        # 当前真实客户区尺寸（用于 PostMessage）
        rect = win32gui.GetClientRect(self.HWND)
        cw, ch = rect[2] - rect[0], rect[3] - rect[1]

        # x,y 是基准尺寸(774x1487)上的坐标
        nx = int(x * cw / self.BASE_W)
        ny = int(y * ch / self.BASE_H)
        return nx, ny

    def click_at(self, x, y, delay=0.03):
        """
        模拟鼠标点击，先移动到目标位置，再按下和抬起鼠标。
        """
        x, y = self._map_norm_to_client(x, y)
        lParam = win32api.MAKELONG(x, y)
        # 让窗口先收到“鼠标移动到此处”
        win32api.PostMessage(self.HWND, win32con.WM_MOUSEMOVE, 0, lParam)
        time.sleep(0.01)  # 等待鼠标移动完成
        # 按下与抬起鼠标
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        time.sleep(delay)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONUP, 0, lParam)

    def click_at_without_hover(self, x, y):
        now = time.time()
        if now - self._last_click_ts < self._min_click_interval:
            return
        self._last_click_ts = now

        x, y = self._map_norm_to_client(x, y)
        lParam = win32api.MAKELONG(x, y)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONUP, 0, lParam)

# ---------------------- 连点线程 ---------------------
    # 连点线程 模拟真人
    def click_loop(self):
        next_click = time.perf_counter()
        while not self.stop_click_event.is_set():
            if self._confirm_xy is None:
                time.sleep(0.05)
                continue
            now = time.perf_counter()
            if now >= next_click:
                x, y = self._confirm_xy
                self.click_at_without_hover(x, y)

                next_click = now + self._min_click_interval + random.uniform(0.001, 0.003)
            else:
                time.sleep(0.001)

    def start_clicking(self):
        if self.click_thread is not None and self.click_thread.is_alive():
            return
        # 确保确认按钮坐标已经计算出来
        self._log(f'[STATE]已进入招募页,即将开始连点抢票,连点期间鼠标无法手动控制')
        if not self._confirm_xy:
            self._log("[ERROR] _confirm_xy 未计算，等待初始化")
            return  # 跳过连点操作，直到确认按钮坐标计算完成

        self.stop_click_event.clear()
        self.click_thread = threading.Thread(target=self.click_loop, daemon=True)
        self.click_thread.start()

    def stop_clicking(self):
        self.stop_click_event.set()
        if self.click_thread is not None:
            self.click_thread.join()  # 不用 timeout
            self.click_thread = None

    def get_world_diff(self, scene_bgr):
        """
        快速检测当前队伍的环球难度
        """
        max_score = 0.0
        ret = None

        roi = self.ROI["team_world_text"]

        for i in range(20):  
            template_name = f"world_diff_{i + 1}"

            found, score, top_left, tpl_hw = self.template_matcher.match_template_in_roi(
                scene_bgr,
                template_name,
                roi,
                threshold=0.85
            )

            if found and score > max_score:
                max_score = score
                ret = i + 1

        return ret

    def get_world_diff_in_game(self, scene_bgr):
        """
        战斗页面内再次识别当前环球难度
        """
        max_score = 0.0
        ret = None

        roi = self.ROI["in_game_diff_text"]

        for i in range(20):
            template_name = f"world_diff_in_game_{i + 1}"

            found, score, top_left, tpl_hw = self.template_matcher.match_template_in_roi(
                scene_bgr,
                template_name,
                roi,
                threshold=0.98
            )

            if found and score > max_score:
                max_score = score
                ret = i + 1

        return ret
    def detect_ad_popup(self, scene_bgr):
        """
        检测广告/活动弹窗
        返回:
            {
                "is_ad": bool,
                "close_name": str | None,
                "close_pos": tuple[int, int] | None
            }
        """
        ad_templates = [
            "cancel",
            "cancel_time_act",
        ]

        for name in ad_templates:
            pos = self.find_button(scene_bgr, name)
            if pos is not None:
                return {
                    "is_ad": True,
                    "close_name": name,
                    "close_pos": pos,
                }

        return {
            "is_ad": False,
            "close_name": None,
            "close_pos": None,
        }

    def handle_ad_popup(self, scene_bgr, sleep_after=1.0) -> bool:
        """
        如果当前是广告/活动弹窗，则自动关闭
        返回:
            True  -> 已检测到并处理
            False -> 当前不是广告页
        """
        ad_info = self.detect_ad_popup(scene_bgr)
        if not ad_info["is_ad"]:
            return False

        self._log(f"[STATE]检测到广告/活动弹窗: {ad_info['close_name']}，准备关闭")
        x, y = ad_info["close_pos"]
        self.click_at(x, y)
        time.sleep(sleep_after)
        return True

    def detect_upgrade_popup(self, scene_bgr):
        """
        检测升级弹窗
        返回:
            {
                "is_upgrade": bool,
                "close_name": str | None,
                "close_pos": tuple[int, int] | None
            }
        """
        upgrade_templates = [
            "upgrade_coin",
        ]

        for name in upgrade_templates:
            pos = self.find_button(scene_bgr, name)
            if pos is not None:
                return {
                    "is_upgrade": True,
                    "close_name": name,
                    "close_pos": pos,
                }

        return {
            "is_upgrade": False,
            "close_name": None,
            "close_pos": None,
        }

    def handle_upgrade_popup(self, scene_bgr, sleep_after=1.0) -> bool:
        """
        如果当前是升级弹窗，则自动关闭
        返回:
            True  -> 已检测到并处理
            False -> 当前不是升级弹窗
        """
        upgrade_info = self.detect_upgrade_popup(scene_bgr)
        if not upgrade_info["is_upgrade"]:
            return False

        self._log(f"[STATE]检测到升级弹窗: {upgrade_info['close_name']}，准备关闭")
        x, y = upgrade_info["close_pos"]
        self.click_at(x, y + 100)
        time.sleep(sleep_after)
        return True
    
    def detect_reconnect_popup(self, scene_bgr):
        """
        检测重连弹窗
        返回:
            {
                "is_reconnect": bool,
                "close_name": str | None,
                "close_pos": tuple[int, int] | None
            }
        """
        reconnect_templates = [
            "reconnect",
        ]

        for name in reconnect_templates:
            pos = self.find_button(scene_bgr, name)
            if pos is not None:
                return {
                    "is_reconnect": True,
                    "close_name": name,
                    "close_pos": pos,
                }

        return {
            "is_reconnect": False,
            "close_name": None,
            "close_pos": None,
        }
    
    def handle_reconnect_popup(self, scene_bgr, sleep_after=1.0) -> bool:
        """
        如果当前是重连弹窗，则自动关闭
        返回:
            True  -> 已检测到并处理
            False -> 当前不是重连弹窗
        """
        reconnect_info = self.detect_reconnect_popup(scene_bgr)
        if not reconnect_info["is_reconnect"]:
            return False

        self._log(f"[STATE]检测到重连弹窗: {reconnect_info['close_name']}，准备重连")
        x, y = reconnect_info["close_pos"]
        self.click_at(x, y)
        time.sleep(sleep_after)
        return True

    # 只做页面判断，不做点击行为
    def is_home_page(self, scene_bgr):
        # 通过主页的开始游戏和底部的战斗按钮来判断是否为主页
        start_btn = self.find_button(scene_bgr, "start_game")
        fight_btn = self.find_button(scene_bgr, "fight")
        return start_btn is not None and fight_btn is not None

    def is_chat_page(self, scene_bgr):
        # 通过招募按钮来判断是否在跨服聊天
        return self.find_button(scene_bgr, "chat_recruit") is not None

    def is_recruit_page(self, scene_bgr):
        # 通过跨服聊天来判断是否在招募页面
        return self.find_button(scene_bgr, "cross_server") is not None

    def is_team_page(self, scene_bgr):
        # 通过底部的返回键来判断是否进入了组队页面
        return self.find_button(scene_bgr, "team_exit") is not None

    def is_battle_page(self, scene_bgr):
        # 通过暂停按钮和伤害统计表来判断是否在战斗界面
        return (
                self.find_button(scene_bgr, "game_has_started") is not None
                or self.find_button(scene_bgr, "chart") is not None
        )

    def detect_view(self, scene_bgr: np.ndarray) -> int:
        self._log('[STATE]触发定时检查当前页面归属')

        if self.detect_ad_popup(scene_bgr)["is_ad"]:
            self._log('[STATE]当前存在广告遮挡，暂不判页')
            return self.VIEW_UNKNOWN

        if self.detect_upgrade_popup(scene_bgr)["is_upgrade"]:
            self._log('[STATE]当前存在升级页面遮挡，暂不判页')
            return self.VIEW_UNKNOWN

        if self.detect_reconnect_popup(scene_bgr)["is_reconnect"]:
            self._log('[STATE]当前存在重连页面遮挡，暂不判页')
            return self.VIEW_UNKNOWN
        
        if self.is_battle_page(scene_bgr):
            self._log('[STATE]当前页面为战斗页面')
            return 4

        if self.is_team_page(scene_bgr):
            self._log('[STATE]当前页面为组队页面')
            return 3

        if self.is_recruit_page(scene_bgr):
            self._log('[STATE]当前页面为招募页面')
            return 2

        if self.is_chat_page(scene_bgr):
            self._log('[STATE]当前页面为聊天页面')
            return 1

        if self.is_home_page(scene_bgr):
            self._log('[STATE]当前页面为主页面')
            return 0

        self._log('[STATE]未能判断出页面归属')
        return self.VIEW_UNKNOWN

    def scan_view_with_retry(self) -> int:
        """
        多次尝试识别页面：
        - 成功：返回 0/1/2/3/4
        - 全失败：返回 VIEW_UNKNOWN
        """
        for i in range(1, self.SCAN_RETRY + 1):
            if not self.run_event.is_set():
                return self.VIEW_UNKNOWN

            try:
                scene_bgr = self.bkgnd_full_window_screenshot()
                # 若有广告，先关闭广告
                if self.handle_ad_popup(scene_bgr, sleep_after=1.0):
                    continue
                # 若有升级，先关闭升级
                if self.handle_upgrade_popup(scene_bgr, sleep_after=1.0):
                    continue
                # 若有掉线重连，先重连
                if self.handle_reconnect_popup(scene_bgr, sleep_after=1.0):
                    continue
                v = self.detect_view(scene_bgr)
                self._log(f"[SCAN] try {i}/{self.SCAN_RETRY} => {v}")

                if v != self.VIEW_UNKNOWN:
                    return v
            except Exception as e:
                self._log(f"[SCAN_ERROR] try {i}/{self.SCAN_RETRY}: {e}")

            self._log(f"[SCAN] 未能检测出当前页面归属,将在2s后重试")
            time.sleep(self.SCAN_RETRY_GAP)

        return self.VIEW_UNKNOWN

    # 采集特征，返回按钮位置
    def collect_view0_features(self, scene_bgr):
        return {
            "main_chat": self.find_button(scene_bgr, "main_chat"),
            "main_chat_army": self.find_button(scene_bgr, "main_chat_army"),
            "resource": self.find_button(scene_bgr, "resource"),
            "master_left": self.find_button(scene_bgr, "master_left"),
            "game_over_return": self.find_button(scene_bgr, "game_over_return"),

            "start_game": self.find_button(scene_bgr, "start_game"),
            "fight": self.find_button(scene_bgr, "fight"),
            "chat_recruit": self.find_button(scene_bgr, "chat_recruit"),
            "cross_server": self.find_button(scene_bgr, "cross_server"),
            "game_has_started": self.find_button(scene_bgr, "game_has_started"),
            "chart": self.find_button(scene_bgr, "chart"),
        }

    def collect_view1_features(self, scene_bgr):
        return {
            "chat_recruit": self.find_button(scene_bgr, "chat_recruit"),
            "cross_server": self.find_button(scene_bgr, "cross_server"),
            "start_game": self.find_button(scene_bgr, "start_game"),
            "fight": self.find_button(scene_bgr, "fight"),
            "game_has_started": self.find_button(scene_bgr, "game_has_started"),
            "game_over_return": self.find_button(scene_bgr, "game_over_return"),
            "chart": self.find_button(scene_bgr, "chart"),
            "master_left": self.find_button(scene_bgr, "master_left"),
        }

    def collect_view2_features(self, scene_bgr):
        return {
            "team_exit": self.find_button(scene_bgr, "team_exit"),
            "start_game": self.find_button(scene_bgr, "start_game"),
            "fight": self.find_button(scene_bgr, "fight"),
            "game_has_started": self.find_button(scene_bgr, "game_has_started"),
            "game_over_return": self.find_button(scene_bgr, "game_over_return"),
            "chart": self.find_button(scene_bgr, "chart"),
            "cross_server": self.find_button(scene_bgr, "cross_server"),
            "chat_recruit": self.find_button(scene_bgr, "chat_recruit"),
        }

    def collect_view3_features(self, scene_bgr):
        return {
            "start_game": self.find_button(scene_bgr, "start_game"),
            "resource": self.find_button(scene_bgr, "resource"),
            "fight": self.find_button(scene_bgr, "fight"),
            "game_has_started": self.find_button(scene_bgr, "game_has_started"),
            "game_over_return": self.find_button(scene_bgr, "game_over_return"),
            "chart": self.find_button(scene_bgr, "chart"),
            "master_left": self.find_button(scene_bgr, "master_left"),
            "team_exit": self.find_button(scene_bgr, "team_exit"),
        }

    def collect_view4_features(self, scene_bgr):
        return {
            "start_game": self.find_button(scene_bgr, "start_game"),
            "fight": self.find_button(scene_bgr, "fight"),
            "team_exit": self.find_button(scene_bgr, "team_exit"),
            "game_has_started": self.find_button(scene_bgr, "game_has_started"),
            "game_over_return": self.find_button(scene_bgr, "game_over_return"),
            "chart": self.find_button(scene_bgr, "chart"),
        }

    def is_home_page_by_feats(self, feats):
        return feats["start_game"] is not None and feats["fight"] is not None

    def is_resource_page_by_feats(self, feats):
        return feats["resource"] is not None
    
    def is_chat_page_by_feats(self, feats):
        return feats["chat_recruit"] is not None

    def is_recruit_page_by_feats(self, feats):
        return feats["cross_server"] is not None

    def is_team_page_by_feats(self, feats):
        return feats["master_left"] is not None

    def is_battle_page_by_feats(self, feats):
        return feats["game_has_started"] is not None or feats["chart"] is not None

    def handle_view0(self):
        # 主页
        scene_bgr = self.bkgnd_full_window_screenshot()

        feats = self.collect_view0_features(scene_bgr)

        if self.handle_ad_popup(scene_bgr, sleep_after=1.0):
            return

        if self.is_home_page_by_feats(feats):
            self._log("[STATE]处于主页中,即将进入聊天框")
            pos = feats["main_chat"] or feats["main_chat_army"]
            if pos:
                self.click_at(pos[0], pos[1])
            else:
                self._log("[ERROR]检测不到聊天框位置,尝试采用固定坐标点击进入聊天框页面！！！")
                self.click_at(*self.PT["chat"])
            time.sleep(0.5)
            self.set_view(1)
            return

        # 因为bug跳到了资源页
        if self.is_resource_page_by_feats(feats):
            self._log("[STATE]当前处于资源页,即将返回招募页")
            self.click_at(*self.PT["resource_back"])
            self.set_view(0)
            time.sleep(0.5)
            return
        
        if self.is_chat_page_by_feats(feats):
            self._log("[STATE]当前实际处于聊天框中")
            self.set_view(1)
            return

        if self.is_recruit_page_by_feats(feats):
            self._log("[STATE]当前实际处于招募页面中")
            self.set_view(2)
            return

        if self.is_team_page_by_feats(feats):
            self._log("[STATE]当前实际处于组队页面中")
            self.set_view(3)
            return

        if self.is_battle_page_by_feats(feats):
            self._log("[STATE]当前实际已在战斗中")
            self._game_begin(self.diff)
            self.set_view(4)
            return

        # if feats["master_left"]:
        #     self._log("[STATE]当前处于单人组队界面,即将点击左下角返回键退回到首页")
        #     leave1_x, leave1_y = self.PT["leave_step1"]
        #     self.click_at_without_hover(leave1_x, leave1_y)
        #     time.sleep(1)
        #     self.diff = None
        #     self.set_view(0)
        #     return

        if feats["game_over_return"]:
            self._log("[STATE]当前处于战斗结算界面,即将返回")
            self._game_end()
            # 增加计数
            self._inc_counter(1)
            pos = feats["game_over_return"]
            self.click_at_without_hover(pos[0], pos[1])
            return

        if self.handle_upgrade_popup(scene_bgr, sleep_after=1.0):
            return
        
        if self.handle_reconnect_popup(scene_bgr, sleep_after=1.0):
            return

    def handle_view1(self):
        # 跨服聊天
        scene_bgr = self.bkgnd_full_window_screenshot()

        feats = self.collect_view1_features(scene_bgr)

        # 正常聊天页：点击“招募”进入招募页
        if self.is_chat_page_by_feats(feats):
            self._log("[STATE]处于聊天框中,即将进入招募页,自动连点开始抢票")
            pos = feats["chat_recruit"]
            self.click_at(pos[0], pos[1])
            self.set_view(2)
            time.sleep(0.5)
            return
        
        # 实际已经在招募页
        if self.is_recruit_page_by_feats(feats):
            self._log("[STATE]当前实际已处于招募页面中")
            self.set_view(2)
            return

        # 实际回到了主页
        if self.is_home_page_by_feats(feats):
            self._log("[STATE]当前实际已回到主页")
            self.set_view(0)
            return

        if self.is_team_page_by_feats(feats):
            self._log("[STATE]当前实际处于组队主页")
            self.set_view(3)
            return

        # 实际已经进入战斗
        if self.is_battle_page_by_feats(feats):
            self._log("[STATE]当前实际已在战斗中")
            self._game_begin(self.diff)
            self.set_view(4)
            return

        self._log("[STATE]VIEW=1 下未识别出明确页面特征，保持当前状态")

    def handle_view2(self):
        # 招募页
        scene_bgr = self.bkgnd_full_window_screenshot()

        # 初始化招募确认按钮坐标（只算一次）
        if self._confirm_xy is None:
            self._confirm_xy = self.PT["confirm"]

        # 招募页里开始连点（只会启动一次）
        self.start_clicking()

        feats = self.collect_view2_features(scene_bgr)

        # 已进入组队界面
        if feats["team_exit"]:
            self._log("[STATE]已进入组队界面，停止连点")
            self.stop_clicking()
            self.diff = None
            self.set_view(3)
            time.sleep(0.5)
            return

        # 还没来得及判断难度就直接开打了
        if self.is_battle_page_by_feats(feats):
            self._log("[STATE]还没来得及进行环球难度判断，游戏便开始了")
            self._game_begin(self.diff)
            self.stop_clicking()
            self.set_view(4)
            return

        # 由于 bug 或其他原因回到了主页面
        if self.is_home_page_by_feats(feats):
            self.stop_clicking()
            time.sleep(0.5)
            scene_bgr = self.bkgnd_full_window_screenshot()
            feats = self.collect_view2_features(scene_bgr)
            if self.is_home_page_by_feats(feats):
                self._log("[STATE]由于游戏bug回到了主页面，停止连点")
                self.diff = None
                self.set_view(0)
                time.sleep(0.5)
            return

        # 仍在招募页，保持连点
        if feats["cross_server"]:
            time.sleep(0.05)
            return

        if self.is_chat_page_by_feats(feats):
            self._log("[STATE]处于聊天框中,即将进入招募页,自动连点开始抢票")
            pos = feats["chat_recruit"]
            self.click_at(pos[0], pos[1])
            self.set_view(2)
            time.sleep(0.5)
            return

        self._log("[STATE]VIEW=2 下未识别出明确页面特征，保持当前状态")
        time.sleep(0.05)

    def handle_view3(self):
        # 组队页
        # 每轮先截图一次，后面统一用这张图算
        scene_bgr = self.bkgnd_full_window_screenshot()

        # 识别当前环球难度
        self.diff = self.get_world_diff(scene_bgr)

        # 退出点击坐标（退队两步）
        leave1_x, leave1_y = self.PT["leave_step1"]
        leave2_x, leave2_y = self.PT["leave_step2"]

        # -------- 情况1：难度低于预期，尝试退出 --------
        if self.diff is not None and self.diff < int(self.EXPECT_DIFF):
            # self._log("[STATE]当队里有两人时,退出分为两步,先点左下角退出键,再点弹窗确认")
            self.click_at_without_hover(leave1_x, leave1_y)
            time.sleep(0.2)
            self.click_at_without_hover(leave2_x, leave2_y)
            time.sleep(2)
            self._log(f"[STATE]检测环球难度:{self.diff},低于要求难度{self.EXPECT_DIFF}，已尝试退出")
            # 退出后重新判断页面
            scene_bgr = self.bkgnd_full_window_screenshot()
            feats = self.collect_view3_features(scene_bgr)

            self._log("[STATE]正在判断是否成功退出")

            if self.is_battle_page_by_feats(feats):
                self._log("[STATE]没来的及退出，游戏开始了")
                self._game_begin(self.diff)
                self.stop_clicking()
                self.set_view(4)
                return

            if self.is_home_page_by_feats(feats):
                self._log("[STATE]成功退回到主页面")
                self.diff = None
                self.set_view(0)
                return
            # 因为bug跳到了资源页
            elif self.is_resource_page_by_feats(feats):
                self._log("[STATE]当前处于资源页,即将返回招募页")
                self.click_at(*self.PT["resource_back"])
                self.set_view(0)
                time.sleep(0.5)
                return

            self._log("[STATE]很可能没来的及退出，游戏开始了")
            return

        # -------- 情况2：难度未知 / 难度符合预期，等待房主开打 --------
        if self.diff is None:
            self._log("[STATE]未能检测出环球难度等级")
        else:
            self._log(f"[STATE]检测出环球难度等级={self.diff}")

        scene_bgr = self.bkgnd_full_window_screenshot()
        feats = self.collect_view3_features(scene_bgr)

        if self.is_battle_page_by_feats(feats):
            self._log("[STATE]房主已开启游戏，祝你胜利")
            self._game_begin(self.diff)
            self.stop_clicking()
            self.set_view(4)
            return

        if feats["master_left"]:
            self._log("[STATE]队长不想打，自己退了,即将退出队伍到主页面")
            self._log("[STATE]当队里只有一人时,退出只有一步,直接点击左下角退出键")

            self.click_at_without_hover(leave1_x, leave1_y)
            time.sleep(2)

            # 有时会退出到了主界面但游戏还是开始了，再检查一次
            scene_bgr = self.bkgnd_full_window_screenshot()
            feats = self.collect_view3_features(scene_bgr)

            if self.is_home_page_by_feats(feats):
                self._log("[STATE]成功退回到主页面")
                self.diff = None
                self.set_view(0)
                return

        self._log("[STATE]等待房主开启游戏中")
        time.sleep(1)

    def handle_view4(self):
        time.sleep(1.0)
        scene_bgr = self.bkgnd_full_window_screenshot()

        final_diff = self.get_world_diff_in_game(scene_bgr)
        if final_diff is not None and final_diff != self._game_diff:
            self._game_diff = final_diff
            self._log(f"[STATE] 战斗页最终识别难度 = {final_diff}")

        feats = self.collect_view4_features(scene_bgr)

        # -------- 情况1：战斗结束，出现返回按钮 --------
        if feats["game_over_return"]:
            time.sleep(3)
            self._log("[STATE]战斗结束，回到主页面，继续循环")

            final_diff = self._game_diff
            self._inc_world_count(final_diff)   # 先记难度统计
            self._game_end()                    # 再清空本局数据

            # 增加总局数
            self._inc_counter(1)

            pos = feats["game_over_return"]
            self.click_at_without_hover(pos[0], pos[1])
            time.sleep(2)

            # 重新截图，判断是回到主页面还是组队页面
            scene_bgr = self.bkgnd_full_window_screenshot()
            feats = self.collect_view4_features(scene_bgr)

            if self.is_home_page_by_feats(feats):
                self._log("[STATE]成功退回到主页面")
                self.diff = None
                self.set_view(0)
                return

            if feats["team_exit"]:
                self._log("[STATE]已自动退回到组队页面,准备退回到主页面")
                self._log("[STATE]当队里只有一人时,退出只有一步,直接点击左下角退出键")

                leave1_x, leave1_y = self.PT["leave_step1"]
                self.click_at_without_hover(leave1_x, leave1_y)
                time.sleep(2)

                self.diff = None
                self.set_view(0)
                return

            self._log("[STATE]战斗结束后未识别出明确页面特征，保持当前状态")
            return

        # -------- 情况2：战斗仍在进行中 --------
        if getattr(self, "mid_entry_click_enabled", True):
            # 循环点中间词条、先锋技能、机甲技能
            # 点中间的词条
            self.click_at_without_hover(*self.PT["skill_center"])
            time.sleep(0.5)
            # 先锋技能1
            self.click_at_without_hover(*self.PT["skill_left"])
            time.sleep(0.5)
            # 先锋技能2
            self.click_at_without_hover(*self.PT["skill_right"])
            time.sleep(0.5)
            # 机甲技能
            self.click_at_without_hover(*self.PT["mecha_skill"])
            time.sleep(0.5)

        time.sleep(2)
# ---------------------- 主程序 ---------------------
    def word_click(self):
        """
        执行自动化的点击操作和 OCR 识别。
        """
        # 获取截图（此处假设 scene_bgr 是当前截图）
        # scene_bgr = self.bkgnd_full_window_screenshot()
        text = ''
        main_text = ''
        # 先判断初始界面，可能不在主页，后续加这个？
        try:
            # SCAN_INTERVAL = 600  # 每SCAN_INTERVAL秒进行一次巡检
            next_scan_ts = time.monotonic() + self.SCAN_INTERVAL  # SCAN_INTERVAL秒后第一次巡检
            while self.run_event.is_set():
                # 定时检查页面
                now = time.monotonic()
                if now >= next_scan_ts:
                    try:
                        v = self.scan_view_with_retry()
                        if v != self.VIEW_UNKNOWN:
                            self._log(f"[SCAN] success => set_view({v})")
                            self.set_view(v)
                        else:
                            self._log("[SCAN] all retries failed, keep current VIEW")
                    except Exception as e:
                        self._log(f"[SCAN_ERROR] {e}")
                    next_scan_ts = now + self.SCAN_INTERVAL
                # 每个页面下的处理逻辑
                if self.VIEW == 0:
                    self.handle_view0()
                    if not self.run_event.is_set():
                        break
                elif self.VIEW == 1:
                    self.handle_view1()
                    if not self.run_event.is_set():
                        break
                elif self.VIEW == 2:
                    self.handle_view2()
                    if not self.run_event.is_set():
                        break
                elif self.VIEW == 3:
                    self.handle_view3()
                    if not self.run_event.is_set():
                        break
                elif self.VIEW == 4:
                    self.handle_view4()
                    if not self.run_event.is_set():
                        break
        finally:
            self.stop_clicking()  # 确保退出必停连点

# 执行自动化操作
if __name__ == "__main__":
    automation = WorldAutomation()
    scene_bgr = automation.bkgnd_full_window_screenshot()
    v = automation.detect_view(scene_bgr)
    automation._log(f"[SCAN] 10min detect_view => {v}")
