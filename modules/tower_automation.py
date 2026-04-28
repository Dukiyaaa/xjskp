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


class TowerAutomation:
    def __init__(self, window_name="向僵尸开炮", auto_resize_window=False):
        template_paths = {
            "challenge": resource_path(r"images\template\challenge.png"),
            "already_auto_selected": resource_path(r"images\template\already_auto_selected.png"),
            "tower_start_game": resource_path(r"images\template\tower_start_game.png"),
            "eye": resource_path(r"images\template\eye.png"),
            "tower_game_over_return": resource_path(r"images\template\tower_game_over_return.png"),
            "next_level": resource_path(r"images\template\next_level.png"),
            "tower_reach_limited": resource_path(r"images\template\tower_reach_limited.png"),
            "main_tower": resource_path(r"images\template\main_tower.png"),
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

        self.PT = {
            "base": (508, 1421),
            "hall": (171, 696),
            "hall_challenge": (519, 1264),
            "enter_main_tower": (411, 511),
            "auto_select": (318, 1124),
            "back_home_step_1": (673, 341),
            "back_home_step_2": (111, 1412),
            "back_home_step_3": (111, 1412),
            "back_home_step_4": (111, 1412),
            "back_home_step_5": (398, 1404),
        }

        self.ROI = {
            "roi_challenge": (309, 666, 489, 729),
            "roi_already_auto_selected": (249, 1084, 358, 1166),
            "roi_tower_start_game": (241, 1161, 565, 1243),
            "roi_eye": (659, 1321, 754, 1422),
            "roi_tower_game_over_return": (259, 1278, 513, 1349),
            "roi_next_level": (400, 100, 647, 1300),
            "roi_tower_reach_limited": (234, 745, 560, 830),
            "roi_main_tower": (255, 207, 538, 313),
        }

        self.VIEW = 0
        self._last_click_ts = 0.0
        self._min_click_interval = 0.025

        self.skill_select_init = False

        self.HWND = win32gui.FindWindow(None, window_name)
        if self.HWND == 0:
            raise RuntimeError(f"未找到窗口：{window_name}（FindWindow 失败）")

        if auto_resize_window:
            win32gui.MoveWindow(
                self.HWND, self.X_POS, self.Y_POS, self.WIDTH, self.HEIGHT, True
            )

        if win32gui.IsIconic(self.HWND):
            win32gui.ShowWindow(self.HWND, win32con.SW_RESTORE)
            time.sleep(0.2)

    def _log(self, msg: str):
        msg = f"[TOWER] {msg}"
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
            self._log("[WARN] TowerAutomation 已在运行中，忽略重复 start()")
            return

        if log_cb is not None or current_page_cb is not None:
            self.set_callbacks(log_cb=log_cb, current_page_cb=current_page_cb)

        self.run_event.set()
        self.VIEW = 0
        self._log("[INFO] 启动爬塔自动化")

        def _worker():
            try:
                self.word_click()
            except Exception as e:
                self._log(f"[ERROR] worker 异常退出：{e}")
            finally:
                self.run_event.clear()
                self._log("[INFO] 爬塔线程已停止")

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def stop(self):
        if not self.run_event.is_set():
            self._log("[INFO] 当前未运行，无需 stop()")
            return
        self._log("[INFO] 正在停止爬塔自动化...")
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

    def debug_dump_roi(self, roi_name: str, scene_bgr=None, save_full_with_box: bool = True):
        """
        调试用：截取并保存某个 ROI 的实际图像，同时可选保存一张带 ROI 框的整图。
        :param roi_name: self.ROI 里的键名
        :param scene_bgr: 可传已有截图；不传则函数内部自动截图
        :param save_full_with_box: 是否额外保存带红框的整图
        :return: roi_img 或 None
        """
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
        self._log(f"[ROI_DEBUG] 已保存 ROI 图像: {roi_path}, size={roi_img.shape[1]}x{roi_img.shape[0]}")

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

    def click_at_without_hover(self, x, y):
        now = time.time()
        if now - self._last_click_ts < self._min_click_interval:
            return
        self._last_click_ts = now

        x, y = self._map_norm_to_client(x, y)
        lParam = win32api.MAKELONG(x, y)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONUP, 0, lParam)

    def find_button(self, scene_bgr, template_name, roi=None, threshold=0.85):
        if roi is None:
            found, score, top_left, tpl_hw = self.template_matcher.match_template(
                scene_bgr, template_name, threshold=threshold
            )
        else:
            roi_rect = self.ROI[roi] if isinstance(roi, str) else roi
            found, score, top_left, tpl_hw = self.template_matcher.match_template_in_roi(
                scene_bgr, template_name, roi_rect, threshold=threshold
            )

        if found:
            center_x, center_y = self.template_matcher.get_center_position(top_left, tpl_hw)
            return center_x, center_y
        return None

    def swipe_vertical(self, x, y_start, y_end, step_delay=0.01, hold_delay=0.03, steps=12):
        """
        模拟竖直滑动。
        - x: 滑动时的横坐标（基准坐标系）
        - y_start: 起点纵坐标（基准坐标系）
        - y_end: 终点纵坐标（基准坐标系）
        - 如果要“页面往下翻”，通常要做“手指上滑”，也就是 y_start > y_end
        """
        x_m, y_start_m = self._map_norm_to_client(x, y_start)
        _, y_end_m = self._map_norm_to_client(x, y_end)

        lparam_down = win32api.MAKELONG(x_m, y_start_m)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam_down)
        time.sleep(hold_delay)

        for i in range(1, steps + 1):
            y_cur = int(y_start_m + (y_end_m - y_start_m) * i / steps)
            lparam_move = win32api.MAKELONG(x_m, y_cur)
            win32api.PostMessage(self.HWND, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lparam_move)
            time.sleep(step_delay)

        lparam_up = win32api.MAKELONG(x_m, y_end_m)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONUP, 0, lparam_up)
    
    def collect_view0_features(self, scene_bgr):
        return {
            "main_tower": self.find_button(scene_bgr, "main_tower", roi="roi_main_tower"),
            }
    
    def handle_view0(self):
        self._log("[STATE] 初始塔页，进入主塔")
        self.click_at_without_hover(*self.PT["base"])
        time.sleep(1.0)
        self.click_at_without_hover(*self.PT["hall"])
        time.sleep(2.0)
        self.swipe_vertical(x=390, y_start=1200, y_end=500)
        time.sleep(1.0)
        self.click_at_without_hover(*self.PT["hall_challenge"])
        time.sleep(1.0)
        while True:
            scene_bgr = self.bkgnd_full_window_screenshot()
            feats = self.collect_view0_features(scene_bgr)
            if feats["main_tower"]:
                self._log("[STATE] 检测主塔，准备点击")
                self.click_at_without_hover(*self.PT["enter_main_tower"])
                time.sleep(1)
                self.set_view(1)
                return

    def collect_view1_features(self, scene_bgr):
        return {
            "challenge": self.find_button(scene_bgr, "challenge", roi="roi_challenge"),
            "already_auto_selected": self.find_button(scene_bgr, "already_auto_selected", roi="roi_already_auto_selected"),
            "tower_start_game": self.find_button(scene_bgr, "tower_start_game", roi="roi_tower_start_game"),
            "eye": self.find_button(scene_bgr, "eye", roi="roi_eye"),
            "tower_reach_limited": self.find_button(scene_bgr, "tower_reach_limited", roi="roi_tower_reach_limited"),
            }

    def handle_view1(self):
        scene_bgr = self.bkgnd_full_window_screenshot()
        feats = self.collect_view1_features(scene_bgr)

        if feats["challenge"]:
            self._log("[STATE] 检测到挑战按钮，准备点击")
            pos = feats["challenge"]
            self.click_at_without_hover(pos[0], pos[1])
            time.sleep(1)
            return
        
        if feats["tower_start_game"]:
            self._log("[STATE] 检测到开始游戏按钮，准备点击")
            
            if feats["already_auto_selected"] is None:
                self._log("[STATE] 准备点击自动选择技能")
                self.click_at_without_hover(*self.PT["auto_select"])
                time.sleep(1)

            pos = feats["tower_start_game"]
            self.click_at_without_hover(pos[0], pos[1])
            time.sleep(0.3)
            scene_bgr = self.bkgnd_full_window_screenshot()
            feats = self.collect_view1_features(scene_bgr)

            if feats["tower_reach_limited"]:
                self._log("[STATE] 已达到升层上限，程序即将暂停")
                self.click_at_without_hover(*self.PT["back_home_step_1"])
                time.sleep(1.0)
                self.click_at_without_hover(*self.PT["back_home_step_2"])
                time.sleep(1.0)
                self.click_at_without_hover(*self.PT["back_home_step_3"])
                time.sleep(1.0)
                self.click_at_without_hover(*self.PT["back_home_step_4"])
                time.sleep(1.0)
                self.click_at_without_hover(*self.PT["back_home_step_5"])
                time.sleep(1.0)
                self.stop()
                return
            
            return
        
        if feats["eye"]:
            self._log("[STATE] 已进入游戏界面")
            self.skill_select_init = False
            self.set_view(2)
            return

        time.sleep(0.5)
        # self._log("[STATE] VIEW=1 下未识别到任何按钮")

    def collect_view2_features(self, scene_bgr):
        return {
            "tower_game_over_return": self.find_button(scene_bgr, "tower_game_over_return", roi="roi_tower_game_over_return"),
            "next_level": self.find_button(scene_bgr, "next_level"),
        }
    
    def handle_view2(self):
        # 当前版本不选词条，让系统循环自己选
        # 挑战失败会出现返回按钮
        scene_bgr = self.bkgnd_full_window_screenshot()
        feats = self.collect_view2_features(scene_bgr)

        # self.debug_dump_roi("roi_next_level", scene_bgr)
        if feats["tower_game_over_return"]:
            self._log("[STATE] 检测到挑战失败，准备点击返回")
            pos = feats["tower_game_over_return"]
            self.click_at_without_hover(pos[0], pos[1])
            time.sleep(1)
            self.set_view(1)
            return
        
        if feats["next_level"]:
            self._log("[STATE] 挑战成功，准备进入下一关")
            pos = feats["next_level"]
            self.click_at_without_hover(pos[0], pos[1])
            time.sleep(1)
            self.set_view(1)
            return

        # 如果由于view1没有选择自动选择技能，则需要自动退出
        # 自动选技能-第一版
        self.auto_select_skill()
        time.sleep(2)
        # self._log("[STATE] VIEW=2 下未识别到任何按钮")

    def auto_select_skill(self):
        if self.skill_select_init == False:
            self.skill_select_init = True
            for i in range(5):
                # 进行五轮双技能选择
                self.click_at_without_hover(294, 809)
                time.sleep(0.5)
                self.click_at_without_hover(478, 823)
                time.sleep(0.5)
                self.click_at_without_hover(390, 1105)
                time.sleep(0.5)
            
        # 之后循环点击中间技能，左右先锋技能，机甲
        self.click_at_without_hover(391, 714)
        time.sleep(2)
        self.click_at_without_hover(95, 1178)
        time.sleep(2)
        self.click_at_without_hover(714, 1024)

    def word_click(self):
        while self.run_event.is_set():
            if self.VIEW == 0:
                self.handle_view0()
            elif self.VIEW == 1:
                self.handle_view1()
            elif self.VIEW == 2:
                self.handle_view2()
            else:
                self._log(f"[WARN] 未定义的 VIEW={self.VIEW}，重置为 0")
                # self.set_view(0)

            if not self.run_event.is_set():
                break

            time.sleep(0.1)


if __name__ == "__main__":
    automation = TowerAutomation()
    automation.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        automation.stop()