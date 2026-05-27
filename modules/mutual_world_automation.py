#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import threading
import time
from datetime import datetime
from ctypes import windll
from typing import Callable, Dict, Optional, Tuple, List

import cv2 as cv
import numpy as np
import win32api
import win32con
import win32gui
import win32ui

try:
    from template_matcher import TemplateMatcher
except ImportError:
    from .template_matcher import TemplateMatcher

try:
    from in_game_option_selector import InGameOptionSelector
except ImportError:
    from .in_game_option_selector import InGameOptionSelector


def resource_path(rel_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)


def format_skill_choice_log(results, chosen_index) -> str:
    labels = InGameOptionSelector.SKILL_CATEGORY_LABELS
    parts = []
    for result in results:
        card_no = result.get("index", 0) + 1
        category = result.get("category")
        label = labels.get(category, category) if category else "未知"
        score = result.get("score", 0.0)
        parts.append(f"卡{card_no}:{label}({score:.2f})")

    if chosen_index is None:
        chosen = "未选择"
    else:
        chosen_result = results[chosen_index]
        category = chosen_result.get("category")
        label = labels.get(category, category) if category else "未知"
        chosen = f"卡{chosen_index + 1}:{label}"

    return f"[SKILL] 识别结果：{' | '.join(parts)}；最终点击：{chosen}"


class MutualWorldAutomation:
    ROLE_TICKET = "ticket"
    ROLE_NON_TICKET = "non_ticket"

    ROLE_ALIASES = {
        "ticket": ROLE_TICKET,
        "host": ROLE_TICKET,
        "\u51fa\u7968\u4f4d": ROLE_TICKET,
        "non_ticket": ROLE_NON_TICKET,
        "guest": ROLE_NON_TICKET,
        "\u975e\u51fa\u7968\u4f4d": ROLE_NON_TICKET,
    }

    BASE_W, BASE_H = 774, 1487

    PT = {
        "start_game": (384, 1239),
        "ticket_start_game_after_friend_join": (402, 1359),
        "game_over_return": (393, 1324),
        "team_invitation_accept": (582, 377),
        "team_invitation_refuse": (582, 445),
        "invite_fallback": (621, 1235),
        "leave_step1": (81, 1411),
        "leave_step2": (526, 928),
        "friend_tab": (335, 1394),
        "invite_panel_close": (720, 277),
        "friend_row_invite_x": (590, 0),
        "battle_auto_exit_menu": (69, 137),
        "battle_auto_exit_confirm": (209, 1346),
    }

    ROI = {
        "roi_main_chat": (687, 799, 784, 896),
        "roi_start_game": (237, 1164, 545, 1268),
        "roi_fight": (299, 1345, 476, 1489),
        "roi_master_left": (504, 1185, 589, 1271),
        "roi_team_exit": (20, 1347, 150, 1474),
        "roi_game_over_return": (250, 1260, 535, 1370),
        "roi_friend_list": (48, 302, 776, 528),
        "friend_rows": [
            (77, 353, 776, 522),
            (77, 522, 776, 691),
            (77, 691, 776, 860),
            (77, 860, 776, 1029),
            (77, 1029, 776, 1198),
        ],
    }

    def __init__(
        self,
        window_name: str = "\u5411\u50f5\u5c38\u5f00\u70ae",
        role: str = ROLE_TICKET,
        friend_name: str = "",
        friend_template_path: str = "",
        friend_invite_point: Optional[Tuple[int, int]] = None,
        friend_match_threshold: float = 0.85,
        skill_priority: Optional[List[str]] = None,
        smart_option_enabled: bool = False,
        battle_auto_exit_minutes: float = 0.0,
        auto_resize_window: bool = False,
    ):
        self.window_name = window_name
        self.role = self.normalize_role(role)
        self.friend_name = friend_name
        self.friend_template_path = friend_template_path
        self.friend_invite_point = friend_invite_point
        self.friend_match_threshold = friend_match_threshold
        self.skill_priority = list(skill_priority or InGameOptionSelector.DEFAULT_SKILL_PRIORITY)
        self.smart_option_enabled = bool(smart_option_enabled)
        self.battle_auto_exit_minutes = max(0.0, float(battle_auto_exit_minutes or 0.0))

        self.log_cb: Optional[Callable[[str], None]] = None
        self.current_page_cb: Optional[Callable[[str], None]] = None

        self.template_paths = {
            "invite": resource_path(r"images\template\invite.png"),
            "start_game": resource_path(r"images\template\start_game.png"),
            "main_chat": resource_path(r"images\template\main_chat.png"),
            "main_chat_notice": resource_path(r"images\template\main_chat_notice.png"),
            "main_chat_army": resource_path(r"images\template\main_chat_army.png"),
            "fight": resource_path(r"images\template\fight.png"),
            "game_has_started": resource_path(r"images\template\game_has_started.png"),
            "chart": resource_path(r"images\template\chart.png"),
            "game_over_return": resource_path(r"images\template\game_over_return.png"),
            "team_exit": resource_path(r"images\template\team_exit.png"),
            "master_left": resource_path(r"images\template\master_left.png"),
            "team_invitation": resource_path(r"images\template\team_invitation.png"),
            "team_invitation_accept_btn": resource_path(r"images\template\team_invitation_accept_btn.png"),
            "copy_invitation": resource_path(r"images\template\copy_invitation.png"),
        }
        self.template_matcher = TemplateMatcher(self.template_paths)
        self._load_friend_template()
        self.option_selector = InGameOptionSelector(
            template_matcher=None,
            skill_priority=self.skill_priority,
        )

        self.run_event = threading.Event()
        self.worker_thread = None

        self._last_click_ts = 0.0
        self._min_click_interval = 0.05
        self._last_invite_ts = 0.0
        self._last_action_ts = 0.0
        self._invite_pending = False
        self._battle_started_ts = None
        self._battle_auto_exit_done = False

        self.invite_retry_interval = 8.0
        self.start_after_invite_delay = 4.0
        self.loop_interval = 0.6

        self.HWND = win32gui.FindWindow(None, window_name)
        if self.HWND == 0:
            raise RuntimeError(f"cannot find window: {window_name}")

        if auto_resize_window:
            win32gui.MoveWindow(self.HWND, 0, 0, 400, 750, True)

        if win32gui.IsIconic(self.HWND):
            win32gui.ShowWindow(self.HWND, win32con.SW_RESTORE)
            time.sleep(0.2)

    @classmethod
    def normalize_role(cls, role: str) -> str:
        value = (role or "").strip()
        normalized = cls.ROLE_ALIASES.get(value, value)
        if normalized not in (cls.ROLE_TICKET, cls.ROLE_NON_TICKET):
            raise ValueError("role must be ticket/non_ticket, or \u51fa\u7968\u4f4d/\u975e\u51fa\u7968\u4f4d")
        return normalized

    def set_callbacks(self, log_cb=None, current_page_cb=None):
        self.log_cb = log_cb
        # self.option_selector.set_callbacks(log_cb=self._log)
        self.current_page_cb = current_page_cb

    def set_friend_invite_point(self, point: Optional[Tuple[int, int]]):
        self.friend_invite_point = point

    def set_friend_template_path(self, path: str):
        self.friend_template_path = path or ""
        self._load_friend_template()

    def set_skill_priority(self, priority: List[str]):
        if not priority:
            return
        self.skill_priority = list(priority)
        self.option_selector.skill_priority = list(priority)

    def set_battle_auto_exit_minutes(self, minutes: float):
        self.battle_auto_exit_minutes = max(0.0, float(minutes or 0.0))

    def _load_friend_template(self) -> bool:
        path = (self.friend_template_path or "").strip()
        if not path:
            self.template_matcher.templates.pop("friend", None)
            return False
        img = cv.imread(path)
        if img is None:
            self.template_matcher.templates.pop("friend", None)
            self._log(f"[WARN] 队友模板加载失败: {path}")
            return False
        self.template_matcher.templates["friend"] = img
        self._log(f"队友模板已加载: {path}")
        return True

    def _log(self, msg: str):
        msg = f"[MUTUAL_WORLD] {msg}"
        if self.log_cb:
            self.log_cb(msg)
        else:
            print(msg)

    def _emit_page(self, page: str):
        if self.current_page_cb:
            try:
                self.current_page_cb(page)
            except Exception as exc:
                self._log(f"[PAGE_CB_ERROR] {exc}")

    def start(self, role: Optional[str] = None, log_cb=None, current_page_cb=None):
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self._log("[WARN] 互环模式已经在运行")
            return

        if role is not None:
            self.role = self.normalize_role(role)
        if log_cb is not None or current_page_cb is not None:
            self.set_callbacks(log_cb=log_cb, current_page_cb=current_page_cb)

        self.run_event.set()
        self._last_invite_ts = 0.0
        self._last_action_ts = 0.0
        self._invite_pending = False
        self._battle_started_ts = None
        self._battle_auto_exit_done = False

        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()
        self._log(f"已启动 | 身份={self.role} | 队友={self.friend_name or '未设置'}")

    def stop(self):
        self.run_event.clear()
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        self.worker_thread = None
        self._log("已停止")

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
            self._log("[WARNING] PrintWindow failed")

        bmpinfo = save_bit_map.GetInfo()
        bmpstr = save_bit_map.GetBitmapBits(True)
        capture = np.frombuffer(bmpstr, dtype=np.uint8).reshape((bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4))
        capture = np.ascontiguousarray(capture)[..., :-1]

        win32gui.DeleteObject(save_bit_map.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(self.HWND, hwnd_dc)
        return self.normalize_scene(capture)

    def _map_norm_to_client(self, x, y):
        rect = win32gui.GetClientRect(self.HWND)
        cw, ch = rect[2] - rect[0], rect[3] - rect[1]
        return int(x * cw / self.BASE_W), int(y * ch / self.BASE_H)

    def click_at_without_hover(self, x, y):
        now = time.time()
        if now - self._last_click_ts < self._min_click_interval:
            return
        self._last_click_ts = now

        x, y = self._map_norm_to_client(x, y)
        lparam = win32api.MAKELONG(x, y)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.03)
        win32api.PostMessage(self.HWND, win32con.WM_LBUTTONUP, 0, lparam)

    def swipe_vertical(self, x, y_start, y_end, step_delay=0.01, hold_delay=0.03, steps=12):
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
        if not found:
            return None
        return self.template_matcher.get_center_position(top_left, tpl_hw)

    def collect_features(self, scene_bgr) -> Dict[str, Optional[Tuple[int, int]]]:
        return {
            "invite": self.find_button(scene_bgr, "invite", threshold=0.82),
            "start_game": self.find_button(scene_bgr, "start_game", roi="roi_start_game"),
            "main_chat": self.find_button(scene_bgr, "main_chat", roi="roi_main_chat"),
            "main_chat_notice": self.find_button(scene_bgr, "main_chat_notice", roi="roi_main_chat"),
            "main_chat_army": self.find_button(scene_bgr, "main_chat_army", roi="roi_main_chat"),
            "fight": self.find_button(scene_bgr, "fight", roi="roi_fight"),
            "game_has_started": self.find_button(scene_bgr, "game_has_started"),
            "chart": self.find_button(scene_bgr, "chart"),
            "game_over_return": self.find_button(scene_bgr, "game_over_return"),
            "team_exit": self.find_button(scene_bgr, "team_exit", roi="roi_team_exit"),
            "master_left": self.find_button(scene_bgr, "master_left", roi="roi_master_left"),
            "team_invitation": self.find_button(scene_bgr, "team_invitation"),
            "team_invitation_accept_btn": self.find_button(scene_bgr, "team_invitation_accept_btn"),
            "copy_invitation": self.find_button(scene_bgr, "copy_invitation"),
        }

    def is_team_page(self, feats: Dict[str, Optional[Tuple[int, int]]]) -> bool:
        return bool(feats.get("invite") or feats.get("team_exit") or feats.get("master_left"))

    def is_battle_page(self, feats: Dict[str, Optional[Tuple[int, int]]]) -> bool:
        return bool(feats.get("game_has_started") or feats.get("chart"))

    def is_home_page(self, feats: Dict[str, Optional[Tuple[int, int]]]) -> bool:
        has_main_chat = bool(
            feats.get("main_chat")
            or feats.get("main_chat_notice")
            or feats.get("main_chat_army")
        )
        return bool(has_main_chat and feats.get("fight"))

    def is_invitation_popup(self, feats: Dict[str, Optional[Tuple[int, int]]]) -> bool:
        return bool(feats.get("team_invitation_accept_btn") or feats.get("team_invitation"))

    def _safe_click(self, point, reason: str, sleep_after: float = 0.5):
        self._log(f"点击 {reason} 坐标={point}")
        self.click_at_without_hover(point[0], point[1])
        self._last_action_ts = time.time()
        time.sleep(sleep_after)

    def _handle_result(self, feats) -> bool:
        pos = feats.get("game_over_return")
        if not pos:
            return False
        self._emit_page("result")
        self._log("战斗结束，点击返回")
        time.sleep(5.0)
        self._safe_click(self.PT["game_over_return"], "game_over_return", sleep_after=3.0)
        self._invite_pending = False
        self._battle_started_ts = None
        self._battle_auto_exit_done = False
        return True

    def _invite_friend(self, feats):
        pos = feats.get("master_left") or feats.get("invite") or self.PT["invite_fallback"]
        self._safe_click(pos, "open_invite_panel", sleep_after=0.8)
        self._safe_click(self.PT["friend_tab"], "friend_tab", sleep_after=0.8)
        invited = self._scan_friend_list_and_invite()
        self._safe_click(self.PT["invite_panel_close"], "invite_panel_close", sleep_after=0.8)
        self._last_invite_ts = time.time()
        self._invite_pending = invited
        return invited

    def _friend_list_signature(self, scene_bgr):
        x1, y1, x2, y2 = self.ROI["friend_rows"][0]
        roi_img = scene_bgr[y1:y2, x1:x2]
        small = cv.resize(roi_img, (64, 96), interpolation=cv.INTER_AREA)
        return small

    def debug_dump_roi(self, roi_name="roi_friend_list", scene_bgr=None):
        if roi_name == "friend_rows":
            return self.debug_dump_friend_rows(scene_bgr=scene_bgr)

        if roi_name not in self.ROI:
            self._log(f"[DEBUG] ROI 不存在: {roi_name}")
            return None

        if scene_bgr is None:
            scene_bgr = self.bkgnd_full_window_screenshot()

        x1, y1, x2, y2 = self.ROI[roi_name]
        roi_img = scene_bgr[y1:y2, x1:x2]

        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
        os.makedirs(debug_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        roi_path = os.path.join(debug_dir, f"{roi_name}_{ts}.png")
        full_path = os.path.join(debug_dir, f"{roi_name}_full_{ts}.png")

        full_img = scene_bgr.copy()
        cv.rectangle(full_img, (x1, y1), (x2, y2), (0, 0, 255), 3)

        cv.imwrite(roi_path, roi_img)
        cv.imwrite(full_path, full_img)
        self._log(f"[DEBUG] 已保存ROI裁剪图: {roi_path}")
        self._log(f"[DEBUG] 已保存ROI框选图: {full_path}")
        return roi_path, full_path

    def debug_dump_friend_rows(self, scene_bgr=None):
        if scene_bgr is None:
            scene_bgr = self.bkgnd_full_window_screenshot()

        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
        os.makedirs(debug_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_img = scene_bgr.copy()
        saved_paths = []

        for idx, (x1, y1, x2, y2) in enumerate(self.ROI["friend_rows"], start=1):
            roi_img = scene_bgr[y1:y2, x1:x2]
            roi_path = os.path.join(debug_dir, f"friend_row_{idx}_{ts}.png")
            cv.imwrite(roi_path, roi_img)
            saved_paths.append(roi_path)

            cv.rectangle(full_img, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv.putText(
                full_img,
                str(idx),
                (x1 + 8, y1 + 32),
                cv.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                2,
                cv.LINE_AA,
            )

        full_path = os.path.join(debug_dir, f"friend_rows_full_{ts}.png")
        cv.imwrite(full_path, full_img)
        self._log(f"[DEBUG] 已保存好友行框选图: {full_path}")
        for path in saved_paths:
            self._log(f"[DEBUG] 已保存好友行裁剪图: {path}")
        return saved_paths, full_path

    def _friend_match_score_in_roi(self, scene_bgr, roi):
        tpl = self.template_matcher.templates.get("friend")
        if tpl is None:
            return None, None, None

        x1, y1, x2, y2 = roi
        roi_img = scene_bgr[y1:y2, x1:x2]
        if roi_img.size == 0:
            return None, None, None

        scene_gray = cv.cvtColor(roi_img, cv.COLOR_BGR2GRAY)
        tpl_gray = cv.cvtColor(tpl, cv.COLOR_BGR2GRAY)
        if scene_gray.shape[0] < tpl_gray.shape[0] or scene_gray.shape[1] < tpl_gray.shape[1]:
            return None, None, None

        res = cv.matchTemplate(scene_gray, tpl_gray, cv.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv.minMaxLoc(res)
        top_left = (max_loc[0] + x1, max_loc[1] + y1)
        center = self.template_matcher.get_center_position(top_left, tpl.shape[:2])
        return float(max_val), top_left, center

    def debug_friend_row_match_scores(self, scene_bgr=None):
        if scene_bgr is None:
            scene_bgr = self.bkgnd_full_window_screenshot()

        if "friend" not in self.template_matcher.templates:
            self._log("[DEBUG] 未加载队友模板，无法计算匹配分数")
            return None

        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
        os.makedirs(debug_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_img = scene_bgr.copy()
        rows = []

        for idx, row_roi in enumerate(self.ROI["friend_rows"], start=1):
            x1, y1, x2, y2 = row_roi
            score, top_left, center = self._friend_match_score_in_roi(scene_bgr, row_roi)
            rows.append((idx, row_roi, score, top_left, center))

            color = (0, 255, 0) if score is not None and score >= self.friend_match_threshold else (0, 0, 255)
            cv.rectangle(full_img, (x1, y1), (x2, y2), color, 3)
            label = f"{idx}: {score:.3f}" if score is not None else f"{idx}: n/a"
            cv.putText(
                full_img,
                label,
                (x1 + 8, y1 + 32),
                cv.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
                cv.LINE_AA,
            )
            if top_left and center:
                tpl_h, tpl_w = self.template_matcher.templates["friend"].shape[:2]
                cv.rectangle(full_img, top_left, (top_left[0] + tpl_w, top_left[1] + tpl_h), (255, 0, 0), 2)
                cv.circle(full_img, center, 5, (255, 0, 0), -1)

            score_text = "n/a" if score is None else f"{score:.4f}"
            self._log(f"[DEBUG] 第{idx}个用户框 阈值={self.friend_match_threshold:.2f} score={score_text} top_left={top_left} center={center}")

        full_path = os.path.join(debug_dir, f"friend_rows_match_scores_{ts}.png")
        cv.imwrite(full_path, full_img)
        self._log(f"[DEBUG] 已保存逐框匹配分数图: {full_path}")
        return rows, full_path

    def _scan_friend_list_and_invite(self, max_swipes=10):
        if "friend" not in self.template_matcher.templates:
            self._log("未配置队友模板，无法邀请指定队友")
            return False

        last_sig = None
        same_count = 0
        for idx in range(max_swipes + 1):
            scene_bgr = self.bkgnd_full_window_screenshot()
            for row_idx, row_roi in enumerate(self.ROI["friend_rows"], start=1):
                friend_pos = self._find_friend_in_scene(scene_bgr, roi=row_roi)
                if friend_pos:
                    invite_x = self.PT["friend_row_invite_x"][0]
                    invite_y = (row_roi[1] + row_roi[3]) // 2
                    self._log(f"第{row_idx}个用户框匹配到指定队友，位置={friend_pos}，点击邀请")
                    self._safe_click((invite_x, invite_y), "friend_row_invite", sleep_after=1.0)
                    return True

            sig = self._friend_list_signature(scene_bgr)
            if last_sig is not None:
                diff = float(np.mean(cv.absdiff(sig, last_sig)))
                if diff < 1.0:
                    same_count += 1
                else:
                    same_count = 0
                if same_count >= 2:
                    self._log("好友列表已滑到底，未找到指定队友")
                    return False
            last_sig = sig

            if idx >= max_swipes:
                break

            self._log("当前区域未找到指定队友，往上划169继续查找")
            self.swipe_vertical(x=390, y_start=528, y_end=359)
            time.sleep(0.8)

        self._log("扫描好友列表后仍未找到指定队友")
        return False

    def _find_friend_in_scene(self, scene_bgr, roi=None):
        if "friend" not in self.template_matcher.templates:
            return None
        return self.find_button(scene_bgr, "friend", roi=roi, threshold=self.friend_match_threshold)

    def _accept_invitation_if_from_friend(self, feats) -> bool:
        if not self.is_invitation_popup(feats):
            return False

        self._emit_page("invitation")
        scene_bgr = self.bkgnd_full_window_screenshot()
        friend_pos = self._find_friend_in_scene(scene_bgr)

        if "friend" not in self.template_matcher.templates:
            self._log("检测到邀请弹窗，但未配置队友模板，拒绝邀请")
            self._safe_click(self.PT["team_invitation_refuse"], "team_invitation_refuse", sleep_after=0.8)
            time.sleep(self.loop_interval)
            return True

        if not friend_pos:
            self._log("检测到邀请弹窗，但不是指定队友，拒绝邀请")
            self._safe_click(self.PT["team_invitation_refuse"], "team_invitation_refuse", sleep_after=0.8)
            time.sleep(self.loop_interval)
            return True

        self._log(f"匹配到指定队友邀请，位置={friend_pos}，接受邀请")
        pos = feats.get("team_invitation_accept_btn") or self.PT["team_invitation_accept"]
        self._safe_click(pos, "team_invitation_accept", sleep_after=1.0)
        return True

    def _leave_team_to_home(self):
        self._log("队友已离开队伍，退出组队页")
        self._safe_click(self.PT["leave_step1"], "leave_team", sleep_after=1.0)
        # self._safe_click(self.PT["leave_step2"], "confirm_leave_team", sleep_after=1.5)
        self._battle_started_ts = None
        self._battle_auto_exit_done = False
        self._invite_pending = False

    def _battle_auto_exit_if_due(self, now: Optional[float] = None) -> bool:
        if self.battle_auto_exit_minutes <= 0 or self._battle_started_ts is None:
            return False
        if self._battle_auto_exit_done:
            return False

        now = now or time.time()
        elapsed = now - self._battle_started_ts
        limit_seconds = self.battle_auto_exit_minutes * 60.0
        if elapsed < limit_seconds:
            return False

        self._battle_auto_exit_done = True
        self._log(
            f"[BATTLE] auto exit after {elapsed / 60.0:.1f}min "
            f"(limit={self.battle_auto_exit_minutes:.1f}min)"
        )
        self._safe_click(self.PT["battle_auto_exit_menu"], "battle_auto_exit_menu", sleep_after=0.8)
        time.sleep(0.5)
        self._safe_click(self.PT["battle_auto_exit_confirm"], "battle_auto_exit_confirm", sleep_after=1.5)
        return True

    def _handle_battle(self, scene_bgr, now: Optional[float] = None):
        self._emit_page("battle")
        if self._battle_started_ts is None:
            self._battle_started_ts = now or time.time()
            self._battle_auto_exit_done = False
            self.option_selector.reset_round()
            self._log("[BATTLE] started")

        if self._battle_auto_exit_if_due(now=now):
            time.sleep(self.loop_interval)
            return

        if not self.smart_option_enabled:
            time.sleep(self.loop_interval)
            return

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
            self._log(f"[SKILL][ERROR] intelligent option selector failed: {exc}")

        time.sleep(self.loop_interval)

    def _handle_ticket(self, feats, scene_bgr):
        now = time.time()

        if self._handle_result(feats):
            return

        if self.is_battle_page(feats):
            self._handle_battle(scene_bgr, now=now)
            return

        if False and self.is_battle_page(feats):
            self._emit_page("battle")
            if self._battle_started_ts is None:
                self._battle_started_ts = now
                self._log("已进入战斗，等待结算")
            time.sleep(self.loop_interval)
            return

        if self.is_team_page(feats):
            self._emit_page("team")
            invite_elapsed = now - self._last_invite_ts if self._last_invite_ts else None
            invite_elapsed_text = "未邀请" if invite_elapsed is None else f"{invite_elapsed:.1f}s"
            self._log(
                "[DEBUG] 组队页识别："
                f"master_left={feats.get('master_left')} "
                f"start_game={feats.get('start_game')} "
                f"invite={feats.get('invite')} "
                f"team_exit={feats.get('team_exit')} "
                f"invite_pending={self._invite_pending} "
                f"invite_elapsed={invite_elapsed_text} "
                f"start_delay={self.start_after_invite_delay:.1f}s "
                f"retry_interval={self.invite_retry_interval:.1f}s"
            )
            if not feats.get("master_left") and now - self._last_invite_ts >= self.start_after_invite_delay:
                self._log("队友已入队，点击开始游戏")
                self._safe_click(self.PT["ticket_start_game_after_friend_join"], "start_game", sleep_after=2.0)
                self._invite_pending = False
                return

            if feats.get("master_left") and ((not self._invite_pending) or (now - self._last_invite_ts >= self.invite_retry_interval)):
                self._log("组队页存在空位，开始邀请指定队友")
                invited = self._invite_friend(feats)
                if not invited:
                    time.sleep(self.invite_retry_interval)
                return

            self._log("等待队友入队")
            time.sleep(self.loop_interval)
            return

        self._emit_page("unknown")
        time.sleep(self.loop_interval)

    def _handle_non_ticket(self, feats, scene_bgr):
        if self._handle_result(feats):
            return

        if self._accept_invitation_if_from_friend(feats):
            return

        if self.is_battle_page(feats):
            self._handle_battle(scene_bgr)
            return

        if self.is_home_page(feats) and feats.get("copy_invitation"):
            self._emit_page("waiting_invite")
            self._log("主页检测到邀请入口，打开邀请弹窗")
            self._safe_click(feats["copy_invitation"], "copy_invitation", sleep_after=0.5)
            scene_bgr = self.bkgnd_full_window_screenshot()
            popup_feats = self.collect_features(scene_bgr)
            if self._accept_invitation_if_from_friend(popup_feats):
                return
            time.sleep(self.loop_interval)
            return

        if False and self.is_battle_page(feats):
            self._emit_page("battle")
            if self._battle_started_ts is None:
                self._battle_started_ts = time.time()
                self._log("已进入战斗，等待结算")
            time.sleep(self.loop_interval)
            return

        if self.is_team_page(feats):
            self._emit_page("team")
            if feats.get("master_left"):
                self._leave_team_to_home()
                return
            self._log("已在队伍中，等待出票位开始游戏")
            time.sleep(self.loop_interval)
            return

        self._emit_page("waiting_invite")
        time.sleep(self.loop_interval)

    def _run_loop(self):
        while self.run_event.is_set():
            try:
                scene_bgr = self.bkgnd_full_window_screenshot()
                feats = self.collect_features(scene_bgr)
                if self.role == self.ROLE_TICKET:
                    self._handle_ticket(feats, scene_bgr)
                else:
                    self._handle_non_ticket(feats, scene_bgr)
            except Exception as exc:
                self._log(f"[ERROR] {exc}")
                time.sleep(1.0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-roi", action="store_true")
    parser.add_argument("--debug-friend-scores", action="store_true")
    parser.add_argument("--roi-name", default="roi_friend_list")
    parser.add_argument("--role", default=MutualWorldAutomation.ROLE_TICKET)
    parser.add_argument("--window-name", default="\u5411\u50f5\u5c38\u5f00\u70ae")
    parser.add_argument("--friend-template", default="")
    parser.add_argument("--friend-threshold", type=float, default=0.85)
    args = parser.parse_args()

    bot = MutualWorldAutomation(
        window_name=args.window_name,
        role=args.role,
        friend_template_path=args.friend_template,
        friend_match_threshold=args.friend_threshold,
    )
    if args.debug_friend_scores:
        bot.debug_friend_row_match_scores()
    elif args.debug_roi:
        bot.debug_dump_roi(args.roi_name)
    else:
        bot.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            bot.stop()
