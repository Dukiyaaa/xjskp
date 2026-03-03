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
from template_matcher import TemplateMatcher

from pathlib import Path
def resource_path(rel_path: str) -> str:
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

    return str(base / rel_path)

# ---------------------- 环球抢票类，包含抢票、判断等级、退出队伍 ----------------------
class WorldAutomation:
    def __init__(self, window_name="向僵尸开炮"):
        # 模板路径字典，存储多个模板路径
        template_paths = {
            # 主页：开始游戏
            "start_game": resource_path(r"images\template\main_start_game.png"),
            # 主页：聊天框
            "main_chat": resource_path(r"images\template\main_chat.png"),
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
            # "world_diff_14": resource_path(r"images\template\world_diff_14.png"),
            # "world_diff_15": resource_path(r"images\template\world_diff_15.png"),
            # "recruit_button": resource_path(r"images\template\recruit_button.png"),
            "game_has_started": resource_path(r"images\template\game_has_started.png"),
            "master_left": resource_path(r"images\template\master_left.png"),
            "game_over_return": resource_path(r"images\template\game_over_return.png"),
            "invite": resource_path(r"images\template\invite.png"),
            "world_save_flag": resource_path(r"images\template\world_save_flag.png"),
            "fight": resource_path(r"images\template\fight.png")
            # 其他模板路径...
        }
        # 初始化模板匹配类，传入多个模板路径
        self.template_matcher = TemplateMatcher(template_paths)

        # --- GUI/控制用：运行开关 + 工作线程占位 ---
        self._confirm_xy = None
        self.run_event = threading.Event()
        self.worker_thread = None

        # --- GUI 可选回调：日志/计数 ---
        self.log_cb = None
        self.counter_cb = None

        # 用于计数打了多少把环
        self.test_cnt = 0
        # 游戏窗口位置和大小
        self.X_POS = 0
        self.Y_POS = 0
        self.WIDTH = 400
        self.HEIGHT = 750

        # 游戏界面固定按钮坐标
        # 聊天框全局相对坐标
        self.X_CHAT_C = 0.9225
        self.Y_CHAT_C = 0.5647
        self.X_CHAT = int(self.WIDTH * 2 * self.X_CHAT_C)
        self.Y_CHAT = int(self.HEIGHT * 2 * self.Y_CHAT_C)

        # 招募框全局相对坐标
        self.X_RECRUIT_C = 0.18125
        self.Y_RECRUIT_C = 0.2867
        self.X_RECRUIT = int(self.WIDTH * 2 * self.X_RECRUIT_C)
        self.Y_RECRUIT = int(self.HEIGHT * 2 * self.Y_RECRUIT_C)

        # 招募确定框全局相对坐标
        self.X_CONFIRM_C = 0.5175
        self.Y_CONFIRM_C = 0.641
        self.X_CONFIRM = int(self.WIDTH * 2 * self.X_CONFIRM_C)
        self.Y_CONFIRM = int(self.HEIGHT * 2 * self.Y_CONFIRM_C)
        self.click_coords = (self.X_CONFIRM, self.Y_CONFIRM)  # 确认按钮位置

        # OCR关键词ROI区域--招募框部分,不过目前暂时用不到了
        self.ROI_X1_C = 0.375
        self.ROI_Y1_C = 0.602
        self.ROI_X2_C = 0.5925
        self.ROI_Y2_C = 0.623
        self.ROI_TEXT = (int(self.WIDTH * 2 * self.ROI_X1_C),
                         int(self.HEIGHT * 2 * self.ROI_Y1_C),
                         int(self.WIDTH * 2 * self.ROI_X2_C),
                         int(self.HEIGHT * 2 * self.ROI_Y2_C))

        # 此处需要规范组队界面退出组队的按钮相对坐标比例
        self.ROI_TEAM_X1_C = 0.2525
        self.ROI_TEAM_Y1_C = 0.131
        self.ROI_TEAM_X2_C = 0.7625
        self.ROI_TEAM_Y2_C = 0.168
        self.ROI_TEAM_TEXT = (int(self.WIDTH * 2 * self.ROI_TEAM_X1_C),
                         int(self.HEIGHT * 2 * self.ROI_TEAM_Y1_C),
                         int(self.WIDTH * 2 * self.ROI_TEAM_X2_C),
                         int(self.HEIGHT * 2 * self.ROI_TEAM_Y2_C))
        # self.ROI_TEAM_TEXT = (202, 196, 610, 252)
        # 主界面 开始游戏按钮位置
        self.ROI_START_X1_C = 0.3858
        self.ROI_START_Y1_C = 0.8055
        self.ROI_START_X2_C = 0.6564
        self.ROI_START_Y2_C = 0.8428

        self.ROI_START_GAME_TEXT = (
            int(self.WIDTH * 2 * self.ROI_START_X1_C),
            int(self.HEIGHT * 2 * self.ROI_START_Y1_C),
            int(self.WIDTH * 2 * self.ROI_START_X2_C),
            int(self.HEIGHT * 2 * self.ROI_START_Y2_C),
        )
        # self.ROI_START_GAME_TEXT = (288, 1186, 492, 1242) # 主页开始游戏
        # 组队界面的“离开”ROI，用于判断房主是否离开
        self.ROI_TEAM_LEAVE_X1_C = 0.8334
        self.ROI_TEAM_LEAVE_Y1_C = 0.7994
        self.ROI_TEAM_LEAVE_X2_C = 0.9022
        self.ROI_TEAM_LEAVE_Y2_C = 0.8221

        self.ROI_TEAM_LEAVE_TEXT = (
            int(self.WIDTH * 2 * self.ROI_TEAM_LEAVE_X1_C),
            int(self.HEIGHT * 2 * self.ROI_TEAM_LEAVE_Y1_C),
            int(self.WIDTH * 2 * self.ROI_TEAM_LEAVE_X2_C),
            int(self.HEIGHT * 2 * self.ROI_TEAM_LEAVE_Y2_C),
        )
        # self.ROI_TEAM_LEAVE_TEXT = (645, 1188, 698, 1222)
        # 自己要离开队伍，需要点两次按钮
        self.LEAVE_STEP1_X_C = 0.10125
        self.LEAVE_STEP1_Y_C = 0.9407
        self.LEAVE_STEP2_X_C = 0.6575
        self.LEAVE_STEP2_Y_C = 0.6187
        self.LEAVE_STEP1_X = int(self.WIDTH * 2 * self.LEAVE_STEP1_X_C)
        self.LEAVE_STEP1_Y = int(self.HEIGHT * 2 * self.LEAVE_STEP1_Y_C)
        self.LEAVE_STEP2_X = int(self.WIDTH * 2 * self.LEAVE_STEP2_X_C)
        self.LEAVE_STEP2_Y = int(self.HEIGHT * 2 * self.LEAVE_STEP2_Y_C)
        # self.LEAVE_STEP1_X = 81
        # self.LEAVE_STEP1_Y = 1411
        # self.LEAVE_STEP2_X = 526
        # self.LEAVE_STEP2_Y = 928
        # 战斗页面顶部“环球救援”字样 ROI
        self.ROI_IN_GAME_X1_C = 0.355
        self.ROI_IN_GAME_Y1_C = 0.0713
        self.ROI_IN_GAME_X2_C = 0.64625
        self.ROI_IN_GAME_Y2_C = 0.0947

        self.ROI_IN_GAME_TEXT = (
            int(self.WIDTH * 2 * self.ROI_IN_GAME_X1_C),
            int(self.HEIGHT * 2 * self.ROI_IN_GAME_Y1_C),
            int(self.WIDTH * 2 * self.ROI_IN_GAME_X2_C),
            int(self.HEIGHT * 2 * self.ROI_IN_GAME_Y2_C),
        )
        # self.ROI_IN_GAME_TEXT = (284, 107, 517, 142)  # 战斗页面环球救援字样
        # 战斗结束后的“返回”按钮 ROI
        self.ROI_GAME_OVER_X1_C = 0.4505
        self.ROI_GAME_OVER_Y1_C = 0.8687
        self.ROI_GAME_OVER_X2_C = 0.5719
        self.ROI_GAME_OVER_Y2_C = 0.8987

        self.ROI_GAME_OVER_RETURN_TEXT = (
            int(self.WIDTH * 2 * self.ROI_GAME_OVER_X1_C),
            int(self.HEIGHT * 2 * self.ROI_GAME_OVER_Y1_C),
            int(self.WIDTH * 2 * self.ROI_GAME_OVER_X2_C),
            int(self.HEIGHT * 2 * self.ROI_GAME_OVER_Y2_C),
        )
        # self.ROI_GAME_OVER_RETURN_TEXT = (348, 1292, 442, 1337)

        # 返回点击按钮
        self.GAME_OVER_CLICK_X_C = 0.49375
        self.GAME_OVER_CLICK_Y_C = 0.8763
        self.GAME_OVER_CLICK_X = int(self.WIDTH * 2 * self.GAME_OVER_CLICK_X_C)
        self.GAME_OVER_CLICK_Y = int(self.HEIGHT * 2 * self.GAME_OVER_CLICK_Y_C)
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
        self._min_click_interval = 0.035  # 60ms，建议 40~120ms 之间调
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

        if self.HWND == 0:
            raise RuntimeError(f"未找到窗口：{window_name}（FindWindow 失败）")
        else:
            win32gui.MoveWindow(self.HWND, self.X_POS, self.Y_POS, self.WIDTH, self.HEIGHT, True)
            if win32gui.IsIconic(self.HWND):
                win32gui.ShowWindow(self.HWND, win32con.SW_RESTORE)
                time.sleep(0.2)
    # GUI日志打印
    def _log(self, msg: str):
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

    def _game_begin(self, diff: int | None):
        """记录开局信息，并打日志"""
        self._run_idx += 1
        self._game_start_ts = time.time()
        self._game_diff = diff
        self._log(f"[GAME] 第{self._run_idx}把开始 | 难度={diff}")

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

    def find_button(self, scene_bgr,template_name):
        """
        使用模板匹配查找按钮
        :param scene_bgr: 截图图像
        :param template_name: 模板名称
        :return: 按钮位置 (x, y) 或 None
        """
        # 传递模板名称到模板匹配方法
        found, score, top_left, tpl_hw = self.template_matcher.match_template(scene_bgr, template_name, threshold=0.90)
        if found:
            center_x, center_y = self.template_matcher.get_center_position(top_left, tpl_hw)
            return center_x, center_y
        return None
    # ===================== GUI友好：对外控制接口（第1步） =====================
    def set_callbacks(self, log_cb=None, counter_cb=None):
        """GUI可以传入回调；不传就走print。"""
        self.log_cb = log_cb
        self.counter_cb = counter_cb

    def start(self, expect_diff: int = None, log_cb=None, counter_cb=None):
        """
        启动抢环球（非阻塞）：内部开线程跑 word_click()
        - expect_diff: 设定最低难度
        - log_cb/counter_cb: GUI回调（可选）
        """
        # 已经在跑就不重复启动
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self._log("[WARN] WorldAutomation 已在运行中，忽略重复 start()")
            return

        if log_cb is not None or counter_cb is not None:
            self.set_callbacks(log_cb=log_cb, counter_cb=counter_cb)

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

        return capture

# ---------------------- 点击相关函数，包括指定坐标点击(先移鼠标再点，更稳定)、直接点(速度更快)---------------------
    def click_at(self, x, y, delay=0.03):
        """
        模拟鼠标点击，先移动到目标位置，再按下和抬起鼠标。
        """
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

        lParam = win32api.MAKELONG(x, y)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONUP, 0, lParam)

# ---------------------- 连点线程 ---------------------
    # 连点线程
    def click_loop(self):
        while not self.stop_click_event.is_set():
            if self._confirm_xy is None:
                self._log("[ERROR] _confirm_xy 为空，跳过连点")
                time.sleep(0.1)  # 等待一段时间再检查
                continue
            x, y = self._confirm_xy
            self.click_at_without_hover(x, y)
            time.sleep(0.01)

    def start_clicking(self):
        if self.click_thread is not None and self.click_thread.is_alive():
            return
        self._log('[DEBUG] 开始连点')
        # 确保确认按钮坐标已经计算出来
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
        :param scene_bgr: 当前截图
        :param roi_team: ROI区域用于裁剪匹配区域
        :return: 难度等级
        """
        max_score = 0
        ret = None

        for i in range(12):  # 假设有20个难度模板
            template_name = f'world_diff_{i + 1}'  # world_diff_1.png, world_diff_2.png...

            # 调用模板匹配方法
            found, score, top_left, tpl_hw = self.template_matcher.match_template(
                scene_bgr, template_name, threshold=0.95
            )

            # print(f'template_name: {template_name}, found={found}, score: {score:.3f}')

            # 如果找到了匹配的模板，并且分数高于当前最大分数
            if found and score > max_score:
                max_score = score
                ret = i + 1  # 返回当前匹配的难度等级

        return ret  # 返回匹配到的难度等级，如果没有匹配到则返回 None
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
            while self.run_event.is_set():
                # self._log(f'[DEBUG] 当前view: {self.VIEW}')
                if self.VIEW == 0:
                    # 为了稳定，在这个页面也要做判断，看看是不是真的回到了这个页面
                    # 每次进入新页面前，都需要先截下图
                    scene_bgr = self.bkgnd_full_window_screenshot()
                    # 使用模板匹配找“开始游戏”按钮

                    start_button_position = self.find_button(scene_bgr, "start_game")
                    main_chat_button_position = self.find_button(scene_bgr, "main_chat")
                    chat_recruit_button_position = self.find_button(scene_bgr, "chat_recruit")
                    fight_button_position = self.find_button(scene_bgr, "fight")
                    game_has_started_position = self.find_button(scene_bgr, "game_has_started")
                    if start_button_position and fight_button_position:
                        self._log("[STATE] 处于主页中,即将进入聊天框")
                        # 通过模板匹配找到聊天框按钮
                        self.click_at(main_chat_button_position[0], main_chat_button_position[1])
                        time.sleep(0.5)
                        self.VIEW = 1
                    elif chat_recruit_button_position:
                        self._log("[STATE] 实际处于聊天框中")
                        self.VIEW = 1
                    elif game_has_started_position:
                        self._log("[STATE] 实际已在战斗中")
                        self._game_begin(self.diff)
                        self.VIEW = 4

                elif self.VIEW == 1:
                    # 每次进入新页面前，都需要先截下图
                    scene_bgr = self.bkgnd_full_window_screenshot()
                    chat_recruit_button_position = self.find_button(scene_bgr, "chat_recruit")
                    if chat_recruit_button_position:
                        # 通过模板匹配找到招募按钮
                        self._log("[STATE] 处于聊天框中,即将进入招募页")
                        self.click_at(chat_recruit_button_position[0], chat_recruit_button_position[1])
                        time.sleep(0.5)
                        self.VIEW = 2
                elif self.VIEW == 2:
                    # 主线程负责监控：截图 + 判断是否进入“组队界面”
                    scene_bgr = self.bkgnd_full_window_screenshot()
                    if self._confirm_xy is None:
                        self._confirm_xy = self._abs_xy(scene_bgr, self.X_CONFIRM_C, self.Y_CONFIRM_C)
                    # 进入VIEW2：启动连点线程（只启动一次）
                    self.start_clicking()
                    #不从返回键来判断是不是在队内了，而是通过顶部环球字样
                    team_exit_button_position = self.find_button(scene_bgr, "team_exit")
                    # 有个bug，组队界面如果刚进去别人就退了的话，也会有个开始游戏的按钮
                    start_button_position = self.find_button(scene_bgr, "start_game")
                    game_has_started_position = self.find_button(scene_bgr, "game_has_started")
                    fight_button_position = self.find_button(scene_bgr, "fight")
                    if team_exit_button_position:
                        self._log("[STATE] 已进入组队界面，停止连点")
                        self.stop_clicking()
                        time.sleep(0.5)
                        self.diff = None
                        self.VIEW = 3
                    elif start_button_position and fight_button_position:
                        self._log("[STATE] 回到了主页面，停止连点")
                        self.stop_clicking()
                        time.sleep(0.5)
                        self.diff = None
                        self.VIEW = 0
                    elif game_has_started_position:
                        self._log(f'[STATE] 没来的及进入下一view，游戏开始了')
                        self._game_begin(self.diff)
                        self.stop_clicking()
                        self.VIEW = 4
                    time.sleep(0.05)  # 监控节流
                    if not self.run_event.is_set():
                        break
                elif self.VIEW == 3:
                    # 每轮先截图一次，后面都用这张图来算坐标（保证一致）
                    scene_bgr = self.bkgnd_full_window_screenshot()
                    self.diff = self.get_world_diff(scene_bgr)
                    if self.diff is None:
                        self.RETRY += 1
                        self._log(f"[WARN] 未识别到难度diff，RETRY={self.RETRY}")
                        if self.RETRY >= 50:
                            self.RETRY = 0
                            self._log("[WARN] 连续识别失败，可能是正在进入游戏中")
                            self.stop_clicking()
                            # self.VIEW = 2
                        time.sleep(0.2)
                        continue
                    else:
                        self.RETRY = 0
                    # 动态点击坐标（退队两步）
                    leave1_x, leave1_y = self._abs_xy(scene_bgr, self.LEAVE_STEP1_X_C, self.LEAVE_STEP1_Y_C)
                    leave2_x, leave2_y = self._abs_xy(scene_bgr, self.LEAVE_STEP2_X_C, self.LEAVE_STEP2_Y_C)
                    if self.diff < int(self.EXPECT_DIFF):
                        self._log(f"检测环球难度:{self.diff},低于要求难度{self.EXPECT_DIFF}，即将退出")
                        # 先尝试退出队伍
                        self.click_at_without_hover(leave1_x, leave1_y)
                        time.sleep(0.2)
                        self.click_at_without_hover(leave2_x, leave2_y)
                        time.sleep(2)
                        # 判断：退回主界面 / 游戏开始 / 仍在组队
                        scene_bgr = self.bkgnd_full_window_screenshot()
                        start_button_position = self.find_button(scene_bgr, "start_game")
                        game_has_started_position = self.find_button(scene_bgr, "game_has_started")
                        if game_has_started_position:
                            self._log(f'[STATE] 没来的及退出，游戏开始了')
                            self._game_begin(self.diff)
                            self.stop_clicking()
                            self.VIEW = 4
                        elif start_button_position:
                            self._log("[STATE] 成功退回到主页面")
                            self.diff = None
                            self.VIEW = 0
                    else:
                        # 否则等待房主开启游戏
                        scene_bgr = self.bkgnd_full_window_screenshot()
                        game_has_started_position = self.find_button(scene_bgr, "game_has_started")
                        master_left_position = self.find_button(scene_bgr, "master_left")
                        if game_has_started_position:
                            self._log(f'[STATE] 房主已开启游戏，祝你胜利')
                            self._game_begin(self.diff)
                            self.stop_clicking()
                            self.VIEW = 4
                        elif master_left_position:
                            self._log(f'[STATE] 队长不想打，自己退了')
                            self.click_at_without_hover(leave1_x, leave1_y)
                            time.sleep(0.2)
                            self.click_at_without_hover(leave2_x, leave2_y)
                            time.sleep(2)
                            # 有时会退出到了主界面但游戏还是开始了
                            scene_bgr = self.bkgnd_full_window_screenshot()
                            start_button_position = self.find_button(scene_bgr, "start_game")

                            if start_button_position:
                                self._log("[STATE] 成功退回到主页面")
                                self.diff = None
                                self.VIEW = 0
                        else:
                            self._log('[STATE] 等待房主开启游戏中')

                        time.sleep(1)
                        if not self.run_event.is_set():
                            break
                elif self.VIEW == 4:
                    time.sleep(1.0)
                    scene_bgr = self.bkgnd_full_window_screenshot()
                    game_over_return_position = self.find_button(scene_bgr, "game_over_return")
                    if game_over_return_position:
                        self._log("[STATE] 战斗结束，回到主页面，继续循环")
                        self._game_end()
                        # 增加计数
                        self._inc_counter(1)
                        self.click_at_without_hover(game_over_return_position[0], game_over_return_position[1])
                        time.sleep(2)

                        # 重新截图，判断是回到主页面还是组队页面
                        scene_bgr = self.bkgnd_full_window_screenshot()
                        start_button_position = self.find_button(scene_bgr, "start_game")
                        team_exit_position  = self.find_button(scene_bgr, "team_exit")
                        fight_button_position = self.find_button(scene_bgr, "fight")
                        if start_button_position and fight_button_position:
                            self._log("[STATE] 成功退回到主页面")
                            self.diff = None
                            self.VIEW = 0
                        elif team_exit_position :
                            self._log("[STATE] 已自动退回到组队页面")
                            # 动态计算“离开”按钮的坐标
                            leave1_x, leave1_y = self._abs_xy(scene_bgr, self.LEAVE_STEP1_X_C, self.LEAVE_STEP1_Y_C)
                            leave2_x, leave2_y = self._abs_xy(scene_bgr, self.LEAVE_STEP2_X_C, self.LEAVE_STEP2_Y_C)

                            # 执行离开操作
                            self.click_at_without_hover(leave1_x, leave1_y)
                            time.sleep(0.2)
                            self.click_at_without_hover(leave2_x, leave2_y)
                            time.sleep(0.8)

                            # 确保返回到主页面
                            self.diff = None
                            self.VIEW = 0
                    # else:
                    #     self._log("[STATE] 战斗进行中...")
        finally:
            self.stop_clicking()  # 确保退出必停连点

# 执行自动化操作
if __name__ == "__main__":
    automation = WorldAutomation()
    # 启动
    automation.start(expect_diff=7)
    # 让它跑一会儿（你也可以改成 while True）
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        automation.stop()
        time.sleep(0.5)  # 给线程一点点收尾时间