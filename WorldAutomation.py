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


class WorldAutomation:
    def __init__(self, window_name="向僵尸开炮"):
        # 游戏窗口位置和大小
        self.X_POS = 0
        self.Y_POS = 0
        self.WIDTH = 400
        self.HEIGHT = 750

        # 游戏界面固定按钮坐标
        self.X_CHAT = 738
        self.Y_CHAT = 847
        self.X_ZHAOMU = 145
        self.Y_ZHAOMU = 429
        self.X_CONFIRM = 414
        self.Y_CONFIRM = 961

        # 运行状态开关
        self.IS_RUNNING = False

        # 初始化 OCR 读取器
        self.OCR_READER = easyocr.Reader(['ch_sim', 'en'], gpu=False)

        # 获取窗口句柄
        self.HWND = win32gui.FindWindow(None, window_name)  # 获取标题为“向僵尸开炮”的窗口的句柄
        self.TEMPLATE_IMGS = {}

        if self.HWND == 0:
            messagebox.showinfo("错误", "未找到标题为“向僵尸开炮”的窗口")
        else:
            win32gui.MoveWindow(self.HWND, self.X_POS, self.Y_POS, self.WIDTH, self.HEIGHT, True)

            if win32gui.IsIconic(self.HWND):
                win32gui.ShowWindow(self.HWND, win32con.SW_RESTORE)
                time.sleep(0.2)  # 给一点点时间让窗口重绘/恢复

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
        """
        直接点击，不先移动鼠标，适用于快速点击，但稳定性可能较差。
        """
        lParam = win32api.MAKELONG(x, y)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONUP, 0, lParam)

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

        # 拼接成一个完整的字符串
        text = "".join(results)
        return text, crop, bin_img

    def ocr_and_click(self, scene_bgr, roi, keyword, click_coords):
        """
        执行 OCR 识别，并在识别到关键字时执行点击操作。
        """
        # 获取 OCR 识别的文本
        text, crop, bin_img = self.ocr_text_in_roi(scene_bgr, roi)

        # 如果识别到目标文字，就执行点击
        if keyword in text:
            self.click_at_without_hover(click_coords[0], click_coords[1])

    def word_click(self):
        """
        执行自动化的点击操作和 OCR 识别。
        """
        # 每次进入新页面前，都需要先截下图
        scene_bgr = self.bkgnd_full_window_screenshot()
        # 执行点击前的操作
        self.click_at(self.X_CHAT, self.Y_CHAT)
        time.sleep(1)  # 等待界面稳定

        # 进入招募界面
        self.click_at(self.X_ZHAOMU, self.Y_ZHAOMU)
        time.sleep(0.8)  # 等待页面加载

        # 获取截图（此处假设 scene_bgr 是当前截图）
        scene_bgr = self.bkgnd_full_window_screenshot()

        # 设置 ROI 区域（这里是裁剪你框出的区域）
        ROI_TEXT = (300, 903, 474, 935)  # 假设此为你框出来的区域坐标

        # 进行 OCR 和点击
        keyword = "救援"  # 需要识别的关键字
        click_coords = (self.X_CONFIRM, self.Y_CONFIRM)  # 确认按钮位置

        while True:
            scene_bgr = self.bkgnd_full_window_screenshot()
            self.ocr_and_click(scene_bgr, ROI_TEXT, keyword, click_coords)

# 执行自动化操作
if __name__ == "__main__":
    automation = WorldAutomation()  # 创建自动化对象
    automation.word_click()  # 执行自动化点击操作