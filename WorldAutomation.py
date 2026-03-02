#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

# 必要的库导入
import win32gui
import win32ui
import win32con
import win32api
import numpy as np
import cv2 as cv
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import threading
import time
import os
import sys
from ctypes import windll
import random
import easyocr
import re

# ---------------------- 环球抢票类，包含抢票、判断等级、退出队伍 ----------------------
class WorldAutomation:
    def __init__(self, window_name="向僵尸开炮"):
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
        # self.ROI_TEAM_X1_C = 0.258
        # self.ROI_TEAM_Y1_C = 0.221
        # self.ROI_TEAM_X2_C = 0.421
        # self.ROI_TEAM_Y2_C = 0.162
        # self.ROI_TEAM_X1_C = 0.2
        # self.ROI_TEAM_Y1_C = 0.2
        # self.ROI_TEAM_X2_C = 0.8
        # self.ROI_TEAM_Y2_C = 0.4
        # self.ROI_TEAM_TEXT = (int(self.WIDTH * 2 * self.ROI_TEAM_X1_C),
        #                  int(self.HEIGHT * 2 * self.ROI_TEAM_Y1_C),
        #                  int(self.WIDTH * 2 * self.ROI_TEAM_X2_C),
        #                  int(self.HEIGHT * 2 * self.ROI_TEAM_Y2_C))
        self.ROI_TEAM_TEXT = (202, 196, 610, 252)
        # 主界面 开始游戏按钮位置
        self.ROI_START_GAME_TEXT = (288, 1186, 492, 1242) # 主页开始游戏
        # self.ROI_START_GAME_TEXT = (269, 386, 349, 414) # 普通
        # self.ROI_START_GAME_TEXT = (360, 1435, 433, 1478) # 战斗
        # 组队界面的“离开”ROI，用于判断房主是否离开
        self.ROI_TEAM_LEAVE_TEXT = (645, 1188, 698, 1222)
        # 进入环球战斗页面后的ROI
        self.ROI_IN_GAME_TEXT = (284, 107, 517, 142)  # 战斗页面环球救援字样
        # 战斗结束后的返回ROI
        self.ROI_GAME_OVER_RETURN_TEXT = (348, 1292, 442, 1337)  # 战斗页面环球救援字样
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
        self.EXPECT_DIFF = 15
        # 状态机管理 0:主页 1:聊天框 2:招募框 3:组队页面
        self.VIEW = 3
        # 鼠标点击间隔
        self._last_click_ts = 0.0
        self._min_click_interval = 0.035  # 60ms，建议 40~120ms 之间调
        # 初始化 OCR 读取器
        self.OCR_READER = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        # 进入组队页面后，用于判断是否需要投票OCR
        self.check_flag = True
        # 存储难度值
        self.last_diff = None
        # 获取窗口句柄
        self.HWND = win32gui.FindWindow(None, window_name)  # 获取标题为“向僵尸开炮”的窗口的句柄
        self.TEMPLATE_IMGS = {}

        if self.HWND == 0:
            messagebox.showinfo("错误", "未找到标题为“向僵尸开炮”的窗口")
            raise SystemExit(1)
        else:
            win32gui.MoveWindow(self.HWND, self.X_POS, self.Y_POS, self.WIDTH, self.HEIGHT, True)

            if win32gui.IsIconic(self.HWND):
                win32gui.ShowWindow(self.HWND, win32con.SW_RESTORE)
                time.sleep(0.2)  # 给一点点时间让窗口重绘/恢复

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
            print("[WARNING] PrintWindow 截图可能失败")

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
            self.click_at_without_hover(self.X_CONFIRM, self.Y_CONFIRM)
            time.sleep(0.01)

    def start_clicking(self):
        if self.click_thread is not None and self.click_thread.is_alive():
            return
        print('[DEBUG] 开始连点')
        self.stop_click_event.clear()
        self.click_thread = threading.Thread(target=self.click_loop, daemon=True)
        self.click_thread.start()

    def stop_clicking(self):
        self.stop_click_event.set()
        if self.click_thread is not None:
            self.click_thread.join()  # 不用 timeout
            self.click_thread = None

# ---------------------- OCR部分接口 ---------------------
    def ocr_text_in_roi(self, scene_bgr: np.ndarray, roi):
        """
        从指定的区域进行 OCR 识别，返回识别到的文本。
        """
        x1, y1, x2, y2 = roi
        crop = scene_bgr[y1:y2, x1:x2]

        # 预处理：增强文字
        gray = cv.cvtColor(crop, cv.COLOR_BGR2GRAY)
        gray = cv.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv.INTER_CUBIC)  # 放大提高精度
        _, bin_img = cv.threshold(gray, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)

        # OCR 识别
        results = self.OCR_READER.readtext(bin_img, detail=0)  # 获取识别到的文字列表

        # cv.imwrite("debug_roi_crop.png", crop)
        # cv.imwrite("debug_roi_bin.png", bin_img)
        # 拼接成一个完整的字符串
        text = "".join(results)
        return text, crop, bin_img
    # 这个函数目前用不到了
    def ocr_and_click(self, scene_bgr, roi, keyword, click_coords):
        """
        执行 OCR 识别，并在识别到关键字时执行点击操作。
        """
        # 获取 OCR 识别的文本
        text, crop, bin_img = self.ocr_text_in_roi(scene_bgr, roi)
        if text == "":
            self.RETRY += 1
            if self.RETRY > 10:
                self.VIEW = 0
                self.RETRY = 0
                print(f'页面可能不处于招募界面,即将返回主页')
                return
        print(f'[OCR]: 识别出的文本为 {text}')
        cv.imwrite("debug_roi_crop.png", crop)
        cv.imwrite("debug_roi_bin.png", bin_img)
        # 如果识别到目标文字，就执行点击
        if keyword in text:
            self.click_at_without_hover(self.X_CONFIRM,self.Y_CONFIRM)
    # OCR字符串解析
    def parse_difficulty(self, text: str):
        if not text:
            return None
        t = re.sub(r"\s+", "", text)  # 去空白

        # 1) 优先找 “难度X”
        m = re.search(r"难度\D*(\d+)", t)
        if m:
            return int(m.group(1))

        # 2) 退化：抓所有数字，取最后一个
        nums = re.findall(r"\d+", t)
        if nums:
            return int(nums[-1])
        return None

# ---------------------- 主程序 ---------------------
    def word_click(self):
        """
        执行自动化的点击操作和 OCR 识别。
        """
        # 获取截图（此处假设 scene_bgr 是当前截图）
        # scene_bgr = self.bkgnd_full_window_screenshot()
        text = ''
        main_text = ''
        while True:
            print(f'[DEBUG] 当前view: {self.VIEW}')
            if self.VIEW == 0:
                # 每次进入新页面前，都需要先截下图
                scene_bgr = self.bkgnd_full_window_screenshot()
                # 执行点击前的操作
                time.sleep(1)
                self.click_at(self.X_CHAT, self.Y_CHAT)
                time.sleep(1)  # 等待界面稳定
                self.VIEW = 1
            elif self.VIEW == 1:
                # 每次进入新页面前，都需要先截下图
                scene_bgr = self.bkgnd_full_window_screenshot()
                # 进入招募界面
                time.sleep(1)
                self.click_at(self.X_RECRUIT, self.Y_RECRUIT)
                time.sleep(1)   # 等待页面加载
                self.VIEW = 2
            elif self.VIEW == 2:
                # 进入VIEW2：启动连点线程（只启动一次）
                self.start_clicking()
                # 主线程负责监控：截图 + 判断是否进入“组队界面”
                scene = self.bkgnd_full_window_screenshot()
                # 触发条件：识别到“寰球救援-难度”
                # 组队内，最上方难度字样
                text, _, _ = self.ocr_text_in_roi(scene, self.ROI_TEAM_TEXT)
                # 主页面 开始游戏字样
                main_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_START_GAME_TEXT)
                # 游戏内，顶部环球字样
                game_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_IN_GAME_TEXT)
                if "救援" in text:
                    print("[STATE] 已进入组队界面，停止连点")
                    self.stop_clicking()
                    time.sleep(0.5)
                    self.check_flag = True
                    self.last_diff = None
                    self.VIEW = 3
                elif "开始" in main_text or "游戏" in main_text:
                    print("[STATE] 回到了主页面，停止连点")
                    self.stop_clicking()
                    time.sleep(0.5)
                    self.VIEW = 0
                elif "救援" in game_text:
                    print(f'[STATE] 没来的及进入下一view，游戏开始了')
                    self.stop_clicking()
                    self.VIEW = 4
                time.sleep(0.05)  # 监控节流
            # 组队页面
            elif self.VIEW == 3:
                # 解析难度 有时候diff会为none 待解决
                # 只在刚进组队页面时识别一次难度，并缓存
                if self.check_flag or self.last_diff is None:
                    self.check_flag = False
                    diff = None
                    for _ in range(3):
                        scene = self.bkgnd_full_window_screenshot()
                        text, _, _ = self.ocr_text_in_roi(scene, self.ROI_TEAM_TEXT)
                        diff = self.parse_difficulty(text)
                        print(f'[TEAM OCR] text:{text}, diff:{diff}')
                        if diff is not None:
                            break
                        time.sleep(0.15)
                    if diff is None:
                        print('[STATE] diff仍为None，回到主页重来')
                        self.click_at_without_hover(81, 1411)
                        time.sleep(0.2)
                        self.click_at_without_hover(526, 928)
                        time.sleep(0.8)
                        self.VIEW = 0
                        continue
                    self.last_diff = diff
                diff = self.last_diff  # 后续循环都用缓存值
                # text = ''
                # 低于期望等级直接退出队伍
                if diff < int(self.EXPECT_DIFF):
                    print(f"检测环球难度:{diff},低于要求难度{self.EXPECT_DIFF}，即将退出")
                    # 此处有可能没来得及退出别人就开启了
                    self.click_at_without_hover(81, 1411)
                    time.sleep(0.2)
                    self.click_at_without_hover(526, 928)
                    time.sleep(0.5)
                    '''在这里判断:
                    1.低于期望等级，自己退了出去
                    2.队长不想打，自己退了
                    3.没来得及退出队长就开了'''
                    # 1.低于期望等级，自己退了出去
                    scene = self.bkgnd_full_window_screenshot()
                    main_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_START_GAME_TEXT)
                    game_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_IN_GAME_TEXT)
                    team_leave_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_TEAM_LEAVE_TEXT)
                    # print(f'[DEBUG] main_text: {main_text},game_text: {game_text},team_leave_text: {team_leave_text}')
                    # 3.没来得及退出队长就开了
                    if "救援" in game_text:
                        print(f'[STATE] 没来的及退出，游戏开始了')
                        self.stop_clicking()
                        self.VIEW = 4
                    elif "开始" in main_text or "游戏" in main_text:
                        print("[STATE] 成功退回到主页面")
                        self.VIEW = 0
                else:
                    # 否则等待房主开启游戏
                    scene = self.bkgnd_full_window_screenshot()
                    main_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_START_GAME_TEXT)
                    # 游戏内，顶部环球字样
                    game_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_IN_GAME_TEXT)
                    team_leave_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_TEAM_LEAVE_TEXT)
                    # print(f'[DEBUG]main_text: {main_text},game_text: {game_text},team_leave_text: {team_leave_text}')
                    if "救援" in game_text:
                        print(f'[STATE] 房主已开启游戏，祝你胜利')
                        self.stop_clicking()
                        self.VIEW = 4
                    elif "开" not in team_leave_text:
                        print(f'[STATE] 队长不想打，自己退了')
                        self.click_at_without_hover(81, 1411)
                        time.sleep(0.5)
                        self.click_at_without_hover(526, 928)
                        time.sleep(0.5)
                        # 有时会退出到了主界面但游戏还是开始了
                        scene = self.bkgnd_full_window_screenshot()
                        main_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_START_GAME_TEXT)
                        if "开始" in main_text or "游戏" in main_text:
                            print("[STATE] 已自动退回到主页面")
                            self.VIEW = 0
                    else:
                        print('[STATE] 等待房主开启游戏中')
                    time.sleep(1)
            elif self.VIEW == 4:
                time.sleep(1.0)
                scene = self.bkgnd_full_window_screenshot()
                return_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_GAME_OVER_RETURN_TEXT)
                print(f'[DEBUG] return_text:{return_text}')
                if "返" in return_text:
                    print("[STATE] 战斗结束，回到主页面，继续循环")
                    self.click_at_without_hover(394, 1307)
                    time.sleep(2)
                    scene = self.bkgnd_full_window_screenshot()
                    # 组队内，最上方难度字样
                    text, _, _ = self.ocr_text_in_roi(scene, self.ROI_TEAM_TEXT)
                    # 主页
                    main_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_START_GAME_TEXT)
                    if "开始" in main_text or "游戏" in main_text:
                        print("[STATE] 已自动退回到主页面")
                        self.VIEW = 0
                    elif "救援" in text:
                        print("[STATE] 已自动退回到组队页面")
                        self.click_at_without_hover(81, 1411)
                        time.sleep(0.2)
                        self.click_at_without_hover(526, 928)
                        time.sleep(0.8)
                        self.VIEW = 0
                else:
                    print("[STATE] 战斗进行中...")

            # 测试分支
            elif self.VIEW == 5:
                '''在这里判断:
                1.低于期望等级，自己退了出去
                2.队长不想打，自己退了
                3.没来得及退出队长就开了'''
                # 1.低于期望等级，自己退了出去
                scene = self.bkgnd_full_window_screenshot()
                main_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_START_GAME_TEXT)
                game_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_IN_GAME_TEXT)
                team_leave_text, _, _ = self.ocr_text_in_roi(scene, self.ROI_TEAM_LEAVE_TEXT)
                print(f'main_text: {main_text},game_text: {game_text},team_leave_text: {team_leave_text}')
                if "开始" in main_text or "游戏" in main_text:
                    print("[STATE] 已自动退回到主页面")
                    self.VIEW = 0
                # 2.队长不想打，自己退了，则需要自己退队返回主界面
                elif "开" not in team_leave_text:
                    print(f'队长不想打，自己退了')
                    self.click_at_without_hover(81, 1411)
                    time.sleep(0.5)
                    self.click_at_without_hover(526, 928)
                    time.sleep(0.5)
                    self.VIEW = 0
                # 3.没来得及退出队长就开了
                elif "难度" in game_text:
                    break

# 执行自动化操作
if __name__ == "__main__":
    automation = WorldAutomation()  # 创建自动化对象
    automation.word_click()  # 执行自动化点击操作