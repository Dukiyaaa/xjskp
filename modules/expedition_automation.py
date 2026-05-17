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
from in_game_option_selector import InGameOptionSelector


def format_skill_choice_log(results, chosen_index) -> str:
    labels = InGameOptionSelector.SKILL_CATEGORY_LABELS
    parts = []
    for result in results:
        card_no = result.get("index", 0) + 1
        category = result.get("category")
        label = labels.get(category, category) if category else "unknown"
        score = result.get("score", 0.0)
        parts.append(f"card{card_no}:{label}({score:.2f})")

    if chosen_index is None:
        chosen = "none"
    else:
        chosen_result = results[chosen_index]
        category = chosen_result.get("category")
        label = labels.get(category, category) if category else "unknown"
        chosen = f"card{chosen_index + 1}:{label}"

    return f"[SKILL] result: {' | '.join(parts)}; clicked: {chosen}"


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
        self.smart_option_enabled = False
        self.skill_priority = list(InGameOptionSelector.DEFAULT_SKILL_PRIORITY)

        template_paths = {
            "expedition_start_game": resource_path(r"images\template\expedition_start_game.png"),
            "expedition_start_game_2": resource_path(r"images\template\expedition_start_game_2.png"),
            "expedition_ready": resource_path(r"images\template\expedition_ready.png"),
            "cancel_ready": resource_path(r"images\template\cancel_ready.png"),
            "home_start_game": resource_path(r"images\template\start_game.png"),
            "fight": resource_path(r"images\template\fight.png"),
            "expidition": resource_path(r"images\template\expidition.png"),
            "start_road": resource_path(r"images\template\start_road.png"),
            "game_over_return": resource_path(r"images\template\game_over_return.png"),
            "game_has_started": resource_path(r"images\template\game_has_started.png"),
            "chart": resource_path(r"images\template\chart.png"),
            "cancel": resource_path(r"images\template\cancel.png"),
            "cancel_time_act": resource_path(r"images\template\cancel_time_act.png"),
            "upgrade_coin": resource_path(r"images\template\upgrade_coin.png"),
            "reconnect": resource_path(r"images\template\reconnect.png"),
        }

        self.template_paths = template_paths
        self.template_matcher = TemplateMatcher(template_paths)
        self.option_selector = InGameOptionSelector(
            template_matcher=None,
            skill_priority=self.skill_priority,
        )

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
        self.VIEW_UNKNOWN = -1
        self.SCAN_INTERVAL = 600
        self.SCAN_RETRY = 3
        self.SCAN_RETRY_GAP = 2.0
        self._battle_started_ts = None
        self._last_ready_click_ts = 0.0
        self._cancel_ready_started_ts = None
        self._cancel_ready_timeout = 40.0

        # 底部按钮区域：包含“开始游戏”和“准备”
        self.ROI = {
            "roi_bottom_button": (205, 1305, 609, 1470),
            "roi_home_start_game": (237, 1164, 545, 1268),
            "roi_fight": (299, 1345, 476, 1489),
            "roi_start_road": (270, 711, 549, 783),
        }

        # 底部按钮兜底点击点，当前主要使用模板匹配返回的位置点击
        self.PT = {
            "bottom_button": (396, 1381),
            "space_continue_blank": (401, 1250),
            "fighter_refresh_step1": (695, 1385),
            "fighter_refresh_step2": (249, 1212),
            "base": (508, 1421),
            "hall": (171, 696),
            "expedition_challenge": (621, 1175),
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

    def set_skill_priority(self, priority):
        if not priority:
            return
        self.skill_priority = list(priority)
        self.option_selector.skill_priority = list(priority)

    def start(self, log_cb=None, current_page_cb=None):
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self._log("[WARN] ExpeditionAutomation 已在运行中，忽略重复 start()")
            return

        if log_cb is not None or current_page_cb is not None:
            self.set_callbacks(log_cb=log_cb, current_page_cb=current_page_cb)

        self.run_event.set()
        self.VIEW = 0
        self._battle_started_ts = None
        self.option_selector.reset_round()
        self._cancel_ready_started_ts = None

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
            "start_game_2": self.find_button(
                scene_bgr,
                "expedition_start_game_2",
                roi="roi_bottom_button",
                threshold=0.85
            ),
            "ready": self.find_button(
                scene_bgr,
                "expedition_ready",
                roi="roi_bottom_button",
                threshold=0.85
            ),
            "cancel_ready": self.find_button(
                scene_bgr,
                "cancel_ready",
                roi="roi_bottom_button",
                threshold=0.85
            ),
        }

    def collect_battle_features(self, scene_bgr):
        return {
            "start_road": self.find_button(
                scene_bgr,
                "start_road",
                roi="roi_start_road",
                threshold=0.85
            ),
            "game_over_return": self.find_button(
                scene_bgr,
                "game_over_return",
                threshold=0.85
            ),
            "game_has_started": self.find_button(
                scene_bgr,
                "game_has_started",
                threshold=0.85
            ),
            "chart": self.find_button(
                scene_bgr,
                "chart",
                threshold=0.85
            ),
        }

    def is_battle_page(self, battle_feats):
        return bool(battle_feats.get("game_has_started") or battle_feats.get("chart"))

    def detect_ad_popup(self, scene_bgr):
        for name in ("cancel", "cancel_time_act"):
            pos = self.find_button(scene_bgr, name)
            if pos is not None:
                return {"is_ad": True, "close_name": name, "close_pos": pos}
        return {"is_ad": False, "close_name": None, "close_pos": None}

    def handle_ad_popup(self, scene_bgr, sleep_after=1.0) -> bool:
        ad_info = self.detect_ad_popup(scene_bgr)
        if not ad_info["is_ad"]:
            return False
        self._log(f"[STATE] ad/activity popup detected: {ad_info['close_name']}, close")
        x, y = ad_info["close_pos"]
        self.click_at_without_hover(x, y)
        time.sleep(sleep_after)
        return True

    def detect_upgrade_popup(self, scene_bgr):
        pos = self.find_button(scene_bgr, "upgrade_coin")
        if pos is not None:
            return {"is_upgrade": True, "close_name": "upgrade_coin", "close_pos": pos}
        return {"is_upgrade": False, "close_name": None, "close_pos": None}

    def handle_upgrade_popup(self, scene_bgr, sleep_after=1.0) -> bool:
        upgrade_info = self.detect_upgrade_popup(scene_bgr)
        if not upgrade_info["is_upgrade"]:
            return False
        self._log(f"[STATE] upgrade popup detected: {upgrade_info['close_name']}, close")
        x, y = upgrade_info["close_pos"]
        self.click_at_without_hover(x, y + 100)
        time.sleep(sleep_after)
        return True

    def detect_reconnect_popup(self, scene_bgr):
        pos = self.find_button(scene_bgr, "reconnect")
        if pos is not None:
            return {"is_reconnect": True, "close_name": "reconnect", "close_pos": pos}
        return {"is_reconnect": False, "close_name": None, "close_pos": None}

    def handle_reconnect_popup(self, scene_bgr, sleep_after=1.0) -> bool:
        reconnect_info = self.detect_reconnect_popup(scene_bgr)
        if not reconnect_info["is_reconnect"]:
            return False
        self._log(f"[STATE] reconnect popup detected: {reconnect_info['close_name']}, click")
        x, y = reconnect_info["close_pos"]
        self.click_at_without_hover(x, y)
        time.sleep(sleep_after)
        return True

    def collect_home_features(self, scene_bgr):
        return {
            "home_start_game": self.find_button(
                scene_bgr,
                "home_start_game",
                roi="roi_home_start_game",
                threshold=0.85
            ),
            "fight": self.find_button(
                scene_bgr,
                "fight",
                roi="roi_fight",
                threshold=0.85
            ),
        }

    def is_home_page(self, home_feats):
        return bool(home_feats.get("home_start_game") and home_feats.get("fight"))

    def collect_expedition_entry_features(self, scene_bgr):
        return {
            "expidition": self.find_button(
                scene_bgr,
                "expidition",
                threshold=0.85
            ),
        }

    def is_expedition_entry_page(self, entry_feats):
        return bool(entry_feats.get("expidition"))

    def detect_view(self, scene_bgr):
        self._log("[STATE] scheduled page scan")

        if self.detect_ad_popup(scene_bgr)["is_ad"]:
            self._log("[STATE] popup blocks page scan: ad/activity")
            return self.VIEW_UNKNOWN
        if self.detect_upgrade_popup(scene_bgr)["is_upgrade"]:
            self._log("[STATE] popup blocks page scan: upgrade")
            return self.VIEW_UNKNOWN
        if self.detect_reconnect_popup(scene_bgr)["is_reconnect"]:
            self._log("[STATE] popup blocks page scan: reconnect")
            return self.VIEW_UNKNOWN

        battle_feats = self.collect_battle_features(scene_bgr)
        if (
            self.is_battle_page(battle_feats)
            or battle_feats["start_road"]
            or battle_feats["game_over_return"]
        ):
            self._log("[STATE] scan result: battle/result page")
            return 1

        home_feats = self.collect_home_features(scene_bgr)
        if self.is_home_page(home_feats):
            self._log("[STATE] scan result: home page")
            return 0

        entry_feats = self.collect_expedition_entry_features(scene_bgr)
        if self.is_expedition_entry_page(entry_feats):
            self._log("[STATE] scan result: expedition entry page")
            return 0

        view0_feats = self.collect_view0_features(scene_bgr)
        if (
            view0_feats["ready"]
            or view0_feats["cancel_ready"]
            or view0_feats["start_game"]
            or view0_feats["start_game_2"]
        ):
            self._log("[STATE] scan result: expedition team page")
            return 0

        self._log("[STATE] scan result: unknown")
        return self.VIEW_UNKNOWN

    def scan_view_with_retry(self):
        for i in range(1, self.SCAN_RETRY + 1):
            if not self.run_event.is_set():
                return self.VIEW_UNKNOWN

            try:
                scene_bgr = self.bkgnd_full_window_screenshot()
                if self.handle_ad_popup(scene_bgr, sleep_after=1.0):
                    continue
                if self.handle_upgrade_popup(scene_bgr, sleep_after=1.0):
                    continue
                if self.handle_reconnect_popup(scene_bgr, sleep_after=1.0):
                    continue

                v = self.detect_view(scene_bgr)
                self._log(f"[SCAN] try {i}/{self.SCAN_RETRY} => {v}")
                if v != self.VIEW_UNKNOWN:
                    return v
            except Exception as exc:
                self._log(f"[SCAN_ERROR] try {i}/{self.SCAN_RETRY}: {exc}")

            self._log(f"[SCAN] unknown page, retry in {self.SCAN_RETRY_GAP:.1f}s")
            time.sleep(self.SCAN_RETRY_GAP)

        return self.VIEW_UNKNOWN

    def click_expedition_challenge(self):
        self._log("[STATE] expedition entry detected, click challenge")
        self.click_at_without_hover(*self.PT["expedition_challenge"])
        time.sleep(2.0)
        self._battle_started_ts = None
        self._cancel_ready_started_ts = None
        self.option_selector.reset_round()
        self.set_view(0)

    def enter_expedition_from_home(self):
        self._log("[STATE] home page detected, enter expedition team page")
        self.click_at_without_hover(*self.PT["base"])
        time.sleep(1.0)
        self.click_at_without_hover(*self.PT["hall"])
        time.sleep(2.0)
        self.click_expedition_challenge()

    def refresh_fighter_room(self):
        self.click_at_without_hover(*self.PT["fighter_refresh_step1"])
        time.sleep(0.5)
        self.click_at_without_hover(*self.PT["fighter_refresh_step2"])
        time.sleep(1.0)
        self._cancel_ready_started_ts = None

    def handle_view0(self):
        scene_bgr = self.bkgnd_full_window_screenshot()
        feats = self.collect_view0_features(scene_bgr)
        battle_feats = self.collect_battle_features(scene_bgr)
        home_feats = self.collect_home_features(scene_bgr)
        entry_feats = self.collect_expedition_entry_features(scene_bgr)

        if self.is_home_page(home_feats):
            self.enter_expedition_from_home()
            return

        if self.is_expedition_entry_page(entry_feats):
            self.click_expedition_challenge()
            return

        if (
            self.is_battle_page(battle_feats)
            or battle_feats["start_road"]
            or battle_feats["game_over_return"]
        ):
            self._log("[STATE] VIEW=0 detected battle/result page, switch to VIEW=1")
            self.set_view(1)
            time.sleep(0.2)
            return

        if self.role == "ticket":
            if feats["start_game"]:
                self._log("[STATE] VIEW=0 出票位：检测到开始游戏，准备点击")
                x, y = feats["start_game"]
                self.click_at_without_hover(x, y)
                time.sleep(1.0)
                self.set_view(1)
                self._battle_started_ts = None
                return

            self._log("[STATE] VIEW=0 出票位：未检测到开始游戏按钮")
            time.sleep(0.5)
            return

        if self.role == "fighter":
            if feats["ready"]:
                self._log("[STATE] VIEW=0 打手位：检测到准备，准备点击")
                x, y = feats["ready"]
                self.click_at_without_hover(x, y)
                self._last_ready_click_ts = time.time()
                self._cancel_ready_started_ts = None
                time.sleep(1.0)
                self.set_view(1)
                self._battle_started_ts = None
                self._log("[STATE] VIEW=1 fighter: ready clicked, waiting for battle")
                return

            if feats["start_game"] or feats["start_game_2"]:
                self._log("[STATE] VIEW=0 fighter: start game marker detected instead of ready, refresh room")
                self.refresh_fighter_room()
                return

            self._log("[STATE] VIEW=0 打手位：未检测到准备按钮")
            time.sleep(0.5)
            return

    def handle_view1(self):
        scene_bgr = self.bkgnd_full_window_screenshot()
        feats = self.collect_view0_features(scene_bgr)
        battle_feats = self.collect_battle_features(scene_bgr)
        home_feats = self.collect_home_features(scene_bgr)
        entry_feats = self.collect_expedition_entry_features(scene_bgr)

        if self.is_home_page(home_feats):
            self.enter_expedition_from_home()
            return

        if self.is_expedition_entry_page(entry_feats):
            self.click_expedition_challenge()
            return

        if battle_feats["start_road"]:
            self._log("[STATE] VIEW=1 battle ended: detected start_road, click blank continue")
            self.click_at_without_hover(*self.PT["space_continue_blank"])
            self._battle_started_ts = None
            self._cancel_ready_started_ts = None
            self.option_selector.reset_round()
            time.sleep(1.0)
            return

        if battle_feats["game_over_return"]:
            self._log("[STATE] VIEW=1 battle ended: detected game_over_return, wait 5s then click return")
            time.sleep(5.0)
            x, y = battle_feats["game_over_return"]
            self.click_at_without_hover(x, y)
            self._battle_started_ts = None
            self._cancel_ready_started_ts = None
            self.option_selector.reset_round()
            time.sleep(1.0)
            return

        room_button = feats["start_game"] if self.role == "ticket" else None
        if self.role == "fighter" and feats["ready"]:
            if time.time() - self._last_ready_click_ts >= 3.0:
                self._log("[STATE] VIEW=1 ready button detected after battle, reset to VIEW=0")
                self._battle_started_ts = None
                self.option_selector.reset_round()
                self.set_view(0)
                time.sleep(0.5)
                return

        if self.role == "fighter" and (feats["start_game"] or feats["start_game_2"]):
            self._log("[STATE] VIEW=1 fighter: start game marker detected after ready, refresh room")
            self._battle_started_ts = None
            self.option_selector.reset_round()
            self.refresh_fighter_room()
            return

        if self.is_battle_page(battle_feats):
            self._cancel_ready_started_ts = None

        if self.role == "fighter":
            if feats["cancel_ready"]:
                if self._cancel_ready_started_ts is None:
                    self._cancel_ready_started_ts = time.time()
                    self._log("[STATE] VIEW=1 fighter: cancel_ready detected, start timeout")
                elif time.time() - self._cancel_ready_started_ts >= self._cancel_ready_timeout:
                    self._log("[STATE] VIEW=1 fighter: cancel_ready timeout, refresh room")
                    self._battle_started_ts = None
                    self.option_selector.reset_round()
                    self.refresh_fighter_room()
                    return
            else:
                self._cancel_ready_started_ts = None

        if room_button:
            self._log("[STATE] VIEW=1 room button detected, reset to VIEW=0")
            self._battle_started_ts = None
            self.option_selector.reset_round()
            self.set_view(0)
            time.sleep(0.5)
            return

        if self._battle_started_ts is None:
            self._battle_started_ts = time.time()
            self.option_selector.reset_round()
            self._log(
                "[STATE] VIEW=1 battle monitor started; "
                f"smart option={'enabled' if self.smart_option_enabled else 'disabled'}"
            )

        if self.smart_option_enabled:
            try:
                if self.option_selector.step(
                    scene_bgr,
                    self.click_at_without_hover,
                    refresh_scene_fn=self.bkgnd_full_window_screenshot,
                ):
                    self._log(
                        format_skill_choice_log(
                            self.option_selector.last_results,
                            self.option_selector.last_chosen_index,
                        )
                    )
            except Exception as exc:
                self._log(f"[SKILL][ERROR] smart option failed: {exc}")

        time.sleep(0.5)

    def word_click(self):
        next_scan_ts = time.monotonic() + self.SCAN_INTERVAL
        while self.run_event.is_set():
            now = time.monotonic()
            if now >= next_scan_ts:
                try:
                    v = self.scan_view_with_retry()
                    if v != self.VIEW_UNKNOWN:
                        self._log(f"[SCAN] success => set_view({v})")
                        self.set_view(v)
                    else:
                        self._log("[SCAN] all retries failed, keep current VIEW")
                except Exception as exc:
                    self._log(f"[SCAN_ERROR] {exc}")
                next_scan_ts = now + self.SCAN_INTERVAL

            if self.VIEW == 0:
                self.handle_view0()
            elif self.VIEW == 1:
                self.handle_view1()
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
