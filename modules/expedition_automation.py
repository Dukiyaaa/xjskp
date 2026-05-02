#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
from ctypes import windll

import cv2 as cv
import numpy as np
import win32api
import win32con
import win32gui
import win32ui

from template_matcher import TemplateMatcher


def resource_path(rel_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)


class ExpeditionAutomation:
    """
    远征自动化

    当前版本只做一个小功能：
    1. 出票位 ticket：检测并点击“开始游戏”
    2. 打手位 fighter：检测并点击“准备”

    页面状态：
    VIEW = 0：远征房间页
    """

    def __init__(self, window_name="向僵尸开炮", role="ticket", auto_resize_window=False):
        """
        :param window_name: 小程序窗口标题
        :param role:
            - "ticket"  出票位，点击开始游戏
            - "fighter" 打手位，点击准备
        :param auto_resize_window: 是否自动调整窗口大小
        """

        if role not in ("ticket", "fighter"):
            raise ValueError("role 只能是 'ticket' 或 'fighter'")

        self.role = role

        template_paths = {
            "expedition_start_game": resource_path(r"images\template\expedition_start_game.png"),
            "expedition_ready": resource_path(r"images\template\expedition_ready.png"),
        }

        self.template_paths = template_paths
        self.template_matcher = TemplateMatcher(template_paths)

        self.run_event = threading.Event()
        self.worker_thread = None

        self.log_cb = None
        self.current_page_cb = None

        self.X_POS = 0
        self.Y_POS = 0
        self.WIDTH = 400
        self.HEIGHT = 750

        self.BASE_W, self.BASE_H = 774, 1487

        # 当前远征自动化只有一个页面
        self.VIEW = 0

        # 底部按钮区域：包含“开始游戏”和“准备”
        self.ROI = {
            "roi_bottom_button": (205, 1305, 609, 1470),
        }

        # 底部按钮兜底点击点，当前主要使用模板匹配返回的位置点击
        self.PT = {
            "bottom_button": (396, 1381),
        }

        self._last_click_ts = 0.0
        self._min_click_interval = 0.05

        self.HWND = win32gui.FindWindow(None, window_name)
        if self.HWND == 0:
            raise RuntimeError(f"未找到窗口：{window_name}（FindWindow 失败）")

        if auto_resize_window:
            win32gui.MoveWindow(
                self.HWND,
                self.X_POS,
                self.Y_POS,
                self.WIDTH,
                self.HEIGHT,
                True
            )

        if win32gui.IsIconic(self.HWND):
            win32gui.ShowWindow(self.HWND, win32con.SW_RESTORE)
            time.sleep(0.2)

    def _log(self, msg: str):
        msg = f"[EXPEDITION] {msg}"
        if self.log_cb:
            self.log_cb(msg)
        else:
            print(msg)

    def _emit_view(self, v: int):
        if self.current_page_cb:
            try:
                self.current_page_cb(v)
            except Exception as e:
                self._log(f"[VIEW_CB_ERROR] {e}")

    def set_view(self, v: int):
        if v == self.VIEW:
            return
        self.VIEW = v
        self._emit_view(v)

    def set_callbacks(self, log_cb=None, current_page_cb=None):
        self.log_cb = log_cb
        self.current_page_cb = current_page_cb

    def start(self, log_cb=None, current_page_cb=None):
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self._log("[WARN] ExpeditionAutomation 已在运行中，忽略重复 start()")
            return

        if log_cb is not None or current_page_cb is not None:
            self.set_callbacks(log_cb=log_cb, current_page_cb=current_page_cb)

        self.run_event.set()
        self.VIEW = 0

        if self.role == "ticket":
            self._log("[INFO] 启动远征自动化，当前身份：出票位")
        else:
            self._log("[INFO] 启动远征自动化，当前身份：打手位")

        def _worker():
            try:
                self.word_click()
            except Exception as e:
                self._log(f"[ERROR] worker 异常退出：{e}")
            finally:
                self.run_event.clear()
                self._log("[INFO] 远征线程已停止")

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def stop(self):
        if not self.run_event.is_set():
            self._log("[INFO] 当前未运行，无需 stop()")
            return

        self._log("[INFO] 正在停止远征自动化...")
        self.run_event.clear()

    def normalize_scene(self, scene_bgr):
        h, w = scene_bgr.shape[:2]
        if (w, h) == (self.BASE_W, self.BASE_H):
            return scene_bgr
        return cv.resize(scene_bgr, (self.BASE_W, self.BASE_H), interpolation=cv.INTER_LINEAR)

    def bkgnd_full_window_screenshot(self) -> np.ndarray:
        windll.user32.SetProcessDPIAware()

        rect = win32gui.GetClientRect(self.HWND)
        width, height = rect[2] - rect[0], rect[3] - rect[1]

        hwnd_dc = win32gui.GetWindowDC(self.HWND)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        save_bit_map = win32ui.CreateBitmap()
        save_bit_map.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bit_map)

        result = windll.user32.PrintWindow(self.HWND, save_dc.GetSafeHdc(), 3)
        if result != 1:
            self._log("[WARNING] PrintWindow 截图可能失败")

        bmpinfo = save_bit_map.GetInfo()
        bmpstr = save_bit_map.GetBitmapBits(True)

        capture = np.frombuffer(bmpstr, dtype=np.uint8).reshape(
            (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)
        )

        capture = np.ascontiguousarray(capture)[..., :-1]

        win32gui.DeleteObject(save_bit_map.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(self.HWND, hwnd_dc)

        return self.normalize_scene(capture)

    def _map_norm_to_client(self, x, y):
        rect = win32gui.GetClientRect(self.HWND)
        cw, ch = rect[2] - rect[0], rect[3] - rect[1]

        nx = int(x * cw / self.BASE_W)
        ny = int(y * ch / self.BASE_H)

        return nx, ny

    def click_at_without_hover(self, x, y):
        now = time.time()
        if now - self._last_click_ts < self._min_click_interval:
            return

        self._last_click_ts = now

        x, y = self._map_norm_to_client(x, y)
        lParam = win32api.MAKELONG(x, y)

        win32api.PostMessage(
            self.HWND,
            win32con.WM_LBUTTONDOWN,
            win32con.MK_LBUTTON,
            lParam
        )
        win32api.PostMessage(
            self.HWND,
            win32con.WM_LBUTTONUP,
            0,
            lParam
        )

    def find_button(self, scene_bgr, template_name, roi=None, threshold=0.85):
        if roi is None:
            found, score, top_left, tpl_hw = self.template_matcher.match_template(
                scene_bgr,
                template_name,
                threshold=threshold
            )
        else:
            roi_rect = self.ROI[roi] if isinstance(roi, str) else roi
            found, score, top_left, tpl_hw = self.template_matcher.match_template_in_roi(
                scene_bgr,
                template_name,
                roi_rect,
                threshold=threshold
            )

        if found:
            center_x, center_y = self.template_matcher.get_center_position(top_left, tpl_hw)
            return center_x, center_y

        return None

    def debug_dump_roi(self, roi_name: str, scene_bgr=None, save_full_with_box: bool = True):
        if roi_name not in self.ROI:
            self._log(f"[ROI_DEBUG] 未找到 ROI: {roi_name}")
            return None

        if scene_bgr is None:
            scene_bgr = self.bkgnd_full_window_screenshot()

        x1, y1, x2, y2 = self.ROI[roi_name]

        h, w = scene_bgr.shape[:2]
        x1 = max(0, min(x1, w))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            self._log(f"[ROI_DEBUG] ROI 非法: {roi_name} -> {(x1, y1, x2, y2)}")
            return None

        roi_img = scene_bgr[y1:y2, x1:x2].copy()

        ts = time.strftime("%Y%m%d_%H%M%S")
        roi_path = f"debug_{roi_name}_{ts}.png"
        cv.imwrite(roi_path, roi_img)

        self._log(
            f"[ROI_DEBUG] 已保存 ROI 图像: {roi_path}, "
            f"size={roi_img.shape[1]}x{roi_img.shape[0]}"
        )

        if save_full_with_box:
            full_img = scene_bgr.copy()
            cv.rectangle(full_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv.putText(
                full_img,
                roi_name,
                (x1, max(30, y1 - 10)),
                cv.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

            full_path = f"debug_full_{roi_name}_{ts}.png"
            cv.imwrite(full_path, full_img)
            self._log(f"[ROI_DEBUG] 已保存带框整图: {full_path}")

        return roi_img

    def collect_view0_features(self, scene_bgr):
        return {
            "start_game": self.find_button(
                scene_bgr,
                "expedition_start_game",
                roi="roi_bottom_button",
                threshold=0.85
            ),
            "ready": self.find_button(
                scene_bgr,
                "expedition_ready",
                roi="roi_bottom_button",
                threshold=0.85
            ),
        }

    def handle_view0(self):
        scene_bgr = self.bkgnd_full_window_screenshot()
        feats = self.collect_view0_features(scene_bgr)

        if self.role == "ticket":
            if feats["start_game"]:
                self._log("[STATE] VIEW=0 出票位：检测到开始游戏，准备点击")
                x, y = feats["start_game"]
                self.click_at_without_hover(x, y)
                time.sleep(1.0)
                return

            self._log("[STATE] VIEW=0 出票位：未检测到开始游戏按钮")
            time.sleep(0.5)
            return

        if self.role == "fighter":
            if feats["ready"]:
                self._log("[STATE] VIEW=0 打手位：检测到准备，准备点击")
                x, y = feats["ready"]
                self.click_at_without_hover(x, y)
                time.sleep(1.0)
                return

            self._log("[STATE] VIEW=0 打手位：未检测到准备按钮")
            time.sleep(0.5)
            return

    def word_click(self):
        while self.run_event.is_set():
            if self.VIEW == 0:
                self.handle_view0()
            else:
                self._log(f"[WARN] 未定义的 VIEW={self.VIEW}，重置为 0")
                self.set_view(0)

            if not self.run_event.is_set():
                break

            time.sleep(0.2)


if __name__ == "__main__":
    # 出票位：点击“开始游戏”
    # automation = ExpeditionAutomation(role="ticket")

    # 打手位：点击“准备”
    automation = ExpeditionAutomation(role="fighter")

    automation.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        automation.stop()