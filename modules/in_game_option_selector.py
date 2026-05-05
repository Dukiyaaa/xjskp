#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import argparse
from typing import Optional, Callable, Dict, Tuple, List, Any

import numpy as np

from pathlib import Path
import os
from template_matcher import TemplateMatcher

def resource_path(rel_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)

DEFAULT_WINDOW_NAME = "\u5411\u50f5\u5c38\u5f00\u70ae"

class InGameOptionSelector:
    """
    战斗内词条/技能选择器（独立模块）：
    - 输入：当前截图 scene_bgr
    - 依赖：TemplateMatcher（模板匹配）、外部 click_fn（点击函数）
    - 输出：本次是否执行了点击/选择动作
    - 特点：不追求高实时，采用低频轮询 + 强确认 + 节流
    """

    MODE_NONE = 0   # 不在选择界面/未知
    MODE_3 = 3      # 三选一：点一次即可
    MODE_4 = 4      # 四选二：选两次再点“确定”

    CARD_ROIS_3 = [
        (5, 476, 249, 975),
        (267, 476, 509, 975),
        (527, 476, 768, 975),
    ]
    CLICK_POINTS_3 = [
        (127, 725),
        (388, 725),
        (648, 725),
    ]
    SKILL_CATEGORY_TEMPLATE_FILES = {
        "electromagnetic": [
            "skill_electromagnetic_big.png",
            "skill_electromagnetic_small.png",
        ],
        "ice": [
            "skill_ice_big.png",
            "skill_ice_small.png",
        ],
        "thermobaric_bomb": [
            "skill_bomb_big.png",
            "skill_bomb_small.png",
        ],
        "hail": [
            "skill_hail_big.png",
            "skill_hail_small.png",
        ],
        "electrode_pillar": [
            "skill_pillar_big.png",
            "skill_pillar_small.png",
        ],
        "matrix": [
            "skill_matrix_big.png",
            "skill_matrix_small.png",
        ],
        "vehicle": [
            "skill_car_big.png",
            "skill_car_small.png",
        ],
        "drone": [
            "skill_drone_big.png",
            "skill_drone_small.png",
        ],
        "fuel": [
            "skill_fuel_big.png",
            "skill_fuel_small.png",
        ],
        "ray": [
            "skill_ray_big.png",
            "skill_ray_small.png",
        ],
        "airdrop": [
            "skill_air_drop_big.png",
            "skill_air_drop_small.png",
        ],
        "gun": [
            "skill_gun.png",
        ],
        "bouncing_projectile": [
            "skill_projectile_big.png",
            "skill_projectile_small.png",
            "skill_bouncing_projectile_big.png",
            "skill_bouncing_projectile_small.png",
        ],
        "laser": [
            "skill_laser_big.png",
            "skill_laser_small.png",
        ],
        "tornado": [
            "skill_tornado_big.png",
            "skill_tornado_small.png",
        ],
        "transition_electron": [
            "skill_transition_electron_big.png",
            "skill_transition_electron_small.png",
        ],
        "air_blade": [
            "skill_air_blade_big.png",
            "skill_air_blade_small.png",
        ],
        "spacetime": [
            "skill_spacetime_big.png",
            "skill_spacetime_small.png",
        ],
    }
    DEFAULT_SKILL_PRIORITY = [
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
    SKILL_CATEGORY_LABELS = {
        "electromagnetic": "\u7535\u78c1",
        "ice": "\u5e72\u51b0\u5f39",
        "thermobaric_bomb": "\u6e29\u538b\u5f39",
        "hail": "\u51b0\u96f9",
        "electrode_pillar": "\u7535\u6781\u67f1",
        "matrix": "\u77e9\u9635",
        "vehicle": "\u8f66",
        "drone": "\u65e0\u4eba\u673a",
        "fuel": "\u71c3\u6cb9",
        "ray": "\u5c04\u7ebf",
        "airdrop": "\u7a7a\u6295",
        "gun": "\u67aa",
        "bouncing_projectile": "\u5f39\u7403",
        "laser": "\u6fc0\u5149",
        "tornado": "\u9f99\u5377\u98ce",
        "transition_electron": "\u8dc3\u8fc1\u7535\u5b50",
        "air_blade": "\u6c14\u5203",
        "spacetime": "\u65f6\u7a7a",
    }

    def __init__(
        self,
        template_matcher,
        base_w: int = 774,
        base_h: int = 1487,
        skill_priority: Optional[List[str]] = None,
    ):
        # --- 基准坐标系（与外部截图 normalize 保持一致） ---
        self.BASE_W = base_w
        self.BASE_H = base_h

        # --- 回调（独立于 WorldAutomation，外部可注入同一个log函数复用） ---
        self.log_cb: Optional[Callable[[str], None]] = None

        # --- 节流（低实时） ---
        self._last_step_ts = 0.0
        self._min_step_interval = 0.30  # 300ms 轮询一次（可调整）

        # 模板路径字典
        self.last_results: List[Dict[str, Any]] = []
        self.last_chosen_index: Optional[int] = None
        self.last_mode = self.MODE_NONE

        template_paths = {
            # ===== 技能选择界面 =====

            # 4选2：确定按钮
            "skill_confirm": resource_path(r"images\template\skill_confirm.png"),

            # 技能名称模板（只截标题条中间）
            "skill_ice_damage": resource_path(r"images\template\skill_ice_damage.png"),
            "skill_high_energy": resource_path(r"images\template\skill_high_energy.png"),
            "skill_guided_laser": resource_path(r"images\template\skill_guided_laser.png"),
            "skill_overload_shield": resource_path(r"images\template\skill_overload_shield.png"),

        }

        self.template_paths = template_paths
        self.template_matcher = template_matcher

        # --- 关键模板名（先占位：后续你往 template_paths 里加对应图片） ---
        # 4选2：底部“0/2确定”按钮
        self.TPL_CONFIRM_BTN = "skill_confirm"
        # 选择界面锚点（例如 “选择技能”文字/背景圆环）——可选
        self.TPL_PICK_ANCHOR = None

        # --- 技能名模板（按优先级顺序存名字）---
        # 例如：["干冰弹增伤", "温压冲击", ...] 对应模板名你自己统一命名
        self.skill_priority: List[str] = list(skill_priority or self.DEFAULT_SKILL_PRIORITY)
        self.skill_templates = self._load_skill_category_templates()

        # --- 标题条ROI（基于 774x1487 的基准坐标）---
        # (x1, y1, x2, y2) —— 这里只留空，后面我们按你截图来填
        self.ROIS_4: List[Tuple[int, int, int, int]] = []  # 四选二：4张卡的标题条ROI
        self.ROIS_3: List[Tuple[int, int, int, int]] = []  # 三选一：3张卡的标题条ROI

        # --- 运行时状态（给 4选2 用：避免重复选同一张） ---
        self._picked_indices: List[int] = []  # 记录本轮已选的卡片 index

    # ========== 基础设施 ==========
    def set_callbacks(self, log_cb=None):
        self.log_cb = log_cb

    def _log(self, msg: str):
        if self.log_cb:
            try:
                self.log_cb(msg)
            except Exception:
                # 回调异常不影响主流程
                print(msg)
        else:
            print(msg)

    def _load_skill_category_templates(self) -> Dict[str, List[Tuple[str, np.ndarray]]]:
        import cv2 as cv

        loaded: Dict[str, List[Tuple[str, np.ndarray]]] = {}
        for category, filenames in self.SKILL_CATEGORY_TEMPLATE_FILES.items():
            category_templates: List[Tuple[str, np.ndarray]] = []
            for filename in filenames:
                path = resource_path(os.path.join("images", "template", filename))
                if not os.path.exists(path):
                    continue
                img = cv.imread(path)
                if img is not None:
                    category_templates.append((filename, img))
            loaded[category] = category_templates
        return loaded

    def classify_card(
        self,
        scene_bgr: np.ndarray,
        roi: Tuple[int, int, int, int],
        threshold: float = 0.82,
    ) -> Dict[str, Any]:
        import cv2 as cv

        x1, y1, x2, y2 = self._clamp_roi(scene_bgr, roi)
        card_bgr = scene_bgr[y1:y2, x1:x2]
        if card_bgr.size == 0:
            return {"category": None, "score": 0.0, "template": None, "hit": False}

        card_gray = cv.cvtColor(card_bgr, cv.COLOR_BGR2GRAY)
        best = {
            "category": None,
            "score": 0.0,
            "template": None,
            "hit": False,
            "best_category": None,
            "best_template": None,
        }

        for category, templates in getattr(self, "skill_templates", {}).items():
            for template_name, tpl_bgr in templates:
                tpl_gray = cv.cvtColor(tpl_bgr, cv.COLOR_BGR2GRAY)
                if card_gray.shape[0] < tpl_gray.shape[0] or card_gray.shape[1] < tpl_gray.shape[1]:
                    continue

                res = cv.matchTemplate(card_gray, tpl_gray, cv.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv.minMaxLoc(res)
                score = float(max_val)
                if score > best["score"]:
                    best = {
                        "category": category if score >= threshold else None,
                        "score": score,
                        "template": template_name if score >= threshold else None,
                        "hit": score >= threshold,
                        "best_category": category,
                        "best_template": template_name,
                    }

        return best

    def classify_cards(
        self,
        scene_bgr: np.ndarray,
        rois: Optional[List[Tuple[int, int, int, int]]] = None,
        threshold: float = 0.82,
    ) -> List[Dict[str, Any]]:
        if rois is None:
            rois = self.ROIS_3 or self.CARD_ROIS_3

        results = []
        for index, roi in enumerate(rois):
            result = self.classify_card(scene_bgr, roi, threshold=threshold)
            result["index"] = index
            result["roi"] = roi
            results.append(result)
        return results

    def choose_card_index(self, results: List[Dict[str, Any]]) -> Optional[int]:
        if len(results) != 3:
            return None

        categories = [result.get("category") for result in results]
        if all(category is None for category in categories):
            return None

        priority = {
            category: index
            for index, category in enumerate(self.skill_priority)
        }

        best_index = None
        best_rank = len(priority)
        for index, category in enumerate(categories):
            if category is None:
                continue

            rank = priority.get(category, len(priority))
            if best_index is None or rank < best_rank:
                best_rank = rank
                best_index = index

        return best_index

    def _throttle_ok(self) -> bool:
        now = time.time()
        if now - self._last_step_ts < self._min_step_interval:
            return False
        self._last_step_ts = now
        return True

    def reset_round(self):
        """重置一次选择轮次状态（比如 4选2 选完后/离开选择界面后调用）"""
        self._picked_indices.clear()

    # ========== 对外接口（后续逐步实现） ==========
    def detect_mode(self, scene_bgr: np.ndarray) -> int:
        """
        判断当前是否处于“选择技能/词条”界面，并区分模式：
          - MODE_4：四选二（存在“确定”按钮）
          - MODE_3：三选一（无“确定”按钮，但存在选择界面锚点/卡片特征）
          - MODE_NONE：不在选择界面
        先占位：下一步实现
        """
        rois_4 = self.ROIS_4
        rois_3 = self.ROIS_3 or self.CARD_ROIS_3

        if rois_4 and self._count_card_like_rois(scene_bgr, rois_4) >= 4:
            return self.MODE_4

        if self._count_card_like_rois(scene_bgr, rois_3) >= 3:
            return self.MODE_3

        return self.MODE_NONE

    def card_roi_stats(self, scene_bgr: np.ndarray, roi: Tuple[int, int, int, int]) -> Dict[str, Any]:
        import cv2 as cv

        x1, y1, x2, y2 = self._clamp_roi(scene_bgr, roi)
        roi_bgr = scene_bgr[y1:y2, x1:x2]
        if roi_bgr.size == 0:
            return {
                "roi": (x1, y1, x2, y2),
                "mean": 0.0,
                "std": 0.0,
                "bright_ratio": 0.0,
                "card_like": False,
            }

        gray = cv.cvtColor(roi_bgr, cv.COLOR_BGR2GRAY)
        mean = float(gray.mean())
        std = float(gray.std())
        bright_ratio = float((gray > 120).mean())
        card_like = mean > 85.0 and std > 35.0 and bright_ratio > 0.25

        return {
            "roi": (x1, y1, x2, y2),
            "mean": mean,
            "std": std,
            "bright_ratio": bright_ratio,
            "card_like": card_like,
        }

    def _count_card_like_rois(self, scene_bgr: np.ndarray, rois: List[Tuple[int, int, int, int]]) -> int:
        return sum(1 for roi in rois if self.card_roi_stats(scene_bgr, roi)["card_like"])

    def _clamp_roi(
        self,
        scene_bgr: np.ndarray,
        roi: Tuple[int, int, int, int],
    ) -> Tuple[int, int, int, int]:
        h, w = scene_bgr.shape[:2]
        x1, y1, x2, y2 = roi
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h))
        return x1, y1, x2, y2

    def step(self, scene_bgr: np.ndarray, click_fn: Callable[[int, int], None]) -> bool:
        """
        单步执行：
        - 由外部循环低频调用（例如每 200~500ms）
        - 内部自己节流、识别模式、按策略选择并点击
        返回：
          True  本次发生了点击
          False 本次未动作（不在界面/节流/未命中）
        先占位：下一步实现
        """
        if not self._throttle_ok():
            return False

        mode = self.detect_mode(scene_bgr)
        self.last_mode = mode
        if mode != self.MODE_3:
            self.last_results = []
            self.last_chosen_index = None
            return False

        results = self.classify_cards(scene_bgr, rois=self.ROIS_3 or self.CARD_ROIS_3)
        chosen_index = self.choose_card_index(results)
        self.last_results = results
        self.last_chosen_index = chosen_index
        if chosen_index is None:
            return False

        x, y = self.CLICK_POINTS_3[chosen_index]
        click_fn(x, y)
        return True


def normalize_scene(scene_bgr: np.ndarray, base_w: int = 774, base_h: int = 1487) -> np.ndarray:
    h, w = scene_bgr.shape[:2]
    if (w, h) == (base_w, base_h):
        return scene_bgr

    import cv2 as cv
    return cv.resize(scene_bgr, (base_w, base_h), interpolation=cv.INTER_LINEAR)


def capture_window_screenshot(window_name: str, base_w: int = 774, base_h: int = 1487) -> np.ndarray:
    from ctypes import windll

    import win32con
    import win32gui
    import win32ui

    windll.user32.SetProcessDPIAware()

    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd == 0:
        raise RuntimeError(f"Window not found: {window_name}")

    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.2)

    rect = win32gui.GetClientRect(hwnd)
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid client size: {width}x{height}")

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    save_bitmap = win32ui.CreateBitmap()

    try:
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        if result != 1:
            raise RuntimeError("PrintWindow failed")

        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)
        capture = np.frombuffer(bmpstr, dtype=np.uint8).reshape(
            (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)
        )
        capture = np.ascontiguousarray(capture)[..., :-1]
        return normalize_scene(capture, base_w=base_w, base_h=base_h)
    finally:
        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)


def click_window_at(window_name: str, x: int, y: int, base_w: int = 774, base_h: int = 1487) -> None:
    import win32api
    import win32con
    import win32gui

    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd == 0:
        raise RuntimeError(f"Window not found: {window_name}")

    rect = win32gui.GetClientRect(hwnd)
    cw, ch = rect[2] - rect[0], rect[3] - rect[1]
    nx = int(x * cw / base_w)
    ny = int(y * ch / base_h)
    lparam = win32api.MAKELONG(nx, ny)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)


def save_skill_select_capture(
    window_name: str = DEFAULT_WINDOW_NAME,
    output_dir: Optional[str] = None,
    delay: float = 0.0,
) -> str:
    if delay > 0:
        print(f"[CAPTURE] waiting {delay:.1f}s before screenshot...")
        time.sleep(delay)

    scene_bgr = capture_window_screenshot(window_name)

    if output_dir is None:
        output_dir = resource_path(r"images\test")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"skill_select_capture_{ts}.png"

    import cv2 as cv
    ok = cv.imwrite(str(out_path), scene_bgr)
    if not ok:
        raise RuntimeError(f"Failed to save screenshot: {out_path}")

    return str(out_path)


def debug_detect_mode(image_path: str) -> int:
    import cv2 as cv

    scene_bgr = cv.imread(image_path)
    if scene_bgr is None:
        raise RuntimeError(f"Failed to read image: {image_path}")

    selector = InGameOptionSelector.__new__(InGameOptionSelector)
    selector.ROIS_3 = []
    selector.ROIS_4 = []

    mode = selector.detect_mode(scene_bgr)
    print(f"[DETECT] image={image_path}")
    print(f"[DETECT] size={scene_bgr.shape[1]}x{scene_bgr.shape[0]}")
    print(f"[DETECT] mode={mode}")

    for idx, roi in enumerate(selector.CARD_ROIS_3, 1):
        stats = selector.card_roi_stats(scene_bgr, roi)
        print(
            "[DETECT] card3_{idx} roi={roi} mean={mean:.1f} std={std:.1f} "
            "bright={bright:.3f} card_like={card_like}".format(
                idx=idx,
                roi=stats["roi"],
                mean=stats["mean"],
                std=stats["std"],
                bright=stats["bright_ratio"],
                card_like=stats["card_like"],
            )
        )

    return mode


def debug_classify_skills(image_path: str, threshold: float = 0.82) -> List[Dict[str, Any]]:
    import cv2 as cv

    scene_bgr = cv.imread(image_path)
    if scene_bgr is None:
        raise RuntimeError(f"Failed to read image: {image_path}")

    selector = InGameOptionSelector(template_matcher=None)
    mode = selector.detect_mode(scene_bgr)
    results = selector.classify_cards(scene_bgr, threshold=threshold)

    print(f"[SKILL] image={image_path}")
    print(f"[SKILL] mode={mode}")
    for category, templates in selector.skill_templates.items():
        names = [name for name, _ in templates]
        print(f"[SKILL] templates[{category}]={names}")

    for result in results:
        print(
            "[SKILL] card_{idx} category={category} score={score:.3f} "
            "template={template} hit={hit} best={best_category}/{best_template}".format(
                idx=result["index"] + 1,
                category=result["category"],
                score=result["score"],
                template=result["template"],
                hit=result["hit"],
                best_category=result.get("best_category"),
                best_template=result.get("best_template"),
            )
        )

    return results


def format_skill_results(mode: int, results: List[Dict[str, Any]]) -> str:
    if mode == InGameOptionSelector.MODE_NONE:
        return "mode=0"

    parts = []
    for result in results:
        card_no = result["index"] + 1
        category = result["category"]
        label = InGameOptionSelector.SKILL_CATEGORY_LABELS.get(category, category) if category else "\u65e0"
        parts.append(f"card{card_no}={label}")
    return " | ".join(parts)


def format_chosen_result(results: List[Dict[str, Any]], chosen_index: Optional[int]) -> str:
    if chosen_index is None:
        return "\u6700\u7ec8\u9009\u62e9\u4e86\u65e0"

    category = results[chosen_index].get("category")
    label = InGameOptionSelector.SKILL_CATEGORY_LABELS.get(category, category) if category else "\u65e0"
    return f"\u6700\u7ec8\u9009\u62e9\u4e86card{chosen_index + 1}:{label}"


def results_key(results: List[Dict[str, Any]]) -> Tuple[Any, ...]:
    return tuple(result.get("category") for result in results)


def watch_game_window(
    window_name: str = DEFAULT_WINDOW_NAME,
    interval: float = 0.5,
    threshold: float = 0.82,
    print_idle: bool = False,
    auto_click: bool = False,
    skill_priority: Optional[List[str]] = None,
    stable_required: int = 2,
    max_wait: float = 2.0,
) -> None:
    selector = InGameOptionSelector(template_matcher=None, skill_priority=skill_priority)
    template_summary = {
        category: [name for name, _ in templates]
        for category, templates in selector.skill_templates.items()
    }

    print(f"[WATCH] window={window_name}")
    print(f"[WATCH] interval={interval}s threshold={threshold}")
    print(f"[WATCH] auto_click={auto_click}")
    print(f"[WATCH] stable_required={stable_required} max_wait={max_wait}s")
    print(f"[WATCH] priority={selector.skill_priority}")
    print(f"[WATCH] templates={template_summary}")
    print("[WATCH] press Ctrl+C to stop")

    last_line = None
    last_results_key = None
    stable_count = 0
    first_seen_ts = None
    while True:
        try:
            scene_bgr = capture_window_screenshot(window_name)
            mode = selector.detect_mode(scene_bgr)
            if mode == selector.MODE_NONE:
                last_results_key = None
                stable_count = 0
                first_seen_ts = None
                if print_idle:
                    line = "mode=0"
                else:
                    time.sleep(interval)
                    continue
            else:
                rois = selector.ROIS_3 or selector.CARD_ROIS_3
                if mode == selector.MODE_4 and selector.ROIS_4:
                    rois = selector.ROIS_4
                results = selector.classify_cards(scene_bgr, rois=rois, threshold=threshold)
                chosen_index = selector.choose_card_index(results) if mode == selector.MODE_3 else None
                key = results_key(results)
                all_unknown = all(category is None for category in key)
                if all_unknown:
                    last_results_key = None
                    stable_count = 0
                    first_seen_ts = None
                    if print_idle:
                        line = "mode=3 card1=无 | card2=无 | card3=无 | 最终选择了无"
                    else:
                        time.sleep(interval)
                        continue

                now = time.monotonic()
                if key == last_results_key:
                    stable_count += 1
                else:
                    last_results_key = key
                    stable_count = 1
                    first_seen_ts = now

                has_unknown = any(category is None for category in key)
                wait_elapsed = 0.0 if first_seen_ts is None else now - first_seen_ts

                ready_to_click = False
                decision_reason = "waiting"
                if chosen_index is not None:
                    if not has_unknown and stable_count >= stable_required:
                        ready_to_click = True
                        decision_reason = "stable"
                    elif has_unknown and wait_elapsed >= max_wait:
                        ready_to_click = True
                        decision_reason = "timeout"

                line = (
                    f"{format_skill_results(mode, results)} | "
                    f"{format_chosen_result(results, chosen_index)} | "
                    f"stable={stable_count} reason={decision_reason}"
                )

                if auto_click and ready_to_click:
                    x, y = selector.CLICK_POINTS_3[chosen_index]
                    click_window_at(window_name, x, y)
                    print(
                        f"[WATCH] {time.strftime('%H:%M:%S')} clicked card{chosen_index + 1} "
                        f"reason={decision_reason}"
                    )
                    last_line = None
                    last_results_key = None
                    stable_count = 0
                    first_seen_ts = None
                    time.sleep(max(interval, 0.8))
                    continue

            if line != last_line:
                print(f"[WATCH] {time.strftime('%H:%M:%S')} {line}")
                last_line = line

            time.sleep(interval)
        except KeyboardInterrupt:
            print("[WATCH] stopped")
            return
        except Exception as e:
            print(f"[WATCH][ERROR] {e}")
            time.sleep(max(interval, 1.0))


def main():
    parser = argparse.ArgumentParser(
        description="Watch the game window and print in-game skill-select recognition results."
    )
    parser.add_argument(
        "--window",
        default=DEFAULT_WINDOW_NAME,
        help="Exact window title used by FindWindow.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory to save the screenshot. Defaults to modules/images/test.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to wait before capturing, useful for switching to the skill screen.",
    )
    parser.add_argument(
        "--debug-detect",
        default=None,
        help="Read an existing screenshot and print skill-select mode detection details.",
    )
    parser.add_argument(
        "--debug-skills",
        default=None,
        help="Read an existing screenshot and print skill category matching details.",
    )
    parser.add_argument(
        "--skill-threshold",
        type=float,
        default=0.82,
        help="Template-match threshold used by skill classification.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Seconds between watch screenshots.",
    )
    parser.add_argument(
        "--idle",
        action="store_true",
        help="Also print when no skill-select screen is detected.",
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Save one screenshot and exit instead of watching continuously.",
    )
    parser.add_argument(
        "--auto-click",
        action="store_true",
        help="Click the selected card when ready. This is enabled by default.",
    )
    parser.add_argument(
        "--no-click",
        action="store_false",
        dest="auto_click",
        help="Only print recognition results; do not click.",
    )
    parser.add_argument(
        "--priority",
        default=None,
        help="Comma-separated category priority, e.g. electromagnetic,gun,ice.",
    )
    parser.add_argument(
        "--stable-required",
        type=int,
        default=2,
        help="Consecutive identical full-recognition frames required before clicking.",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=2.0,
        help="Max seconds to wait before choosing from recognized cards when some cards are unknown.",
    )
    parser.set_defaults(auto_click=True)
    args = parser.parse_args()
    skill_priority = None
    if args.priority:
        skill_priority = [
            item.strip()
            for item in args.priority.split(",")
            if item.strip()
        ]

    if args.debug_detect:
        debug_detect_mode(args.debug_detect)
        return

    if args.debug_skills:
        debug_classify_skills(args.debug_skills, threshold=args.skill_threshold)
        return

    if not args.capture:
        watch_game_window(
            window_name=args.window,
            interval=args.interval,
            threshold=args.skill_threshold,
            print_idle=args.idle,
            auto_click=args.auto_click,
            skill_priority=skill_priority,
            stable_required=args.stable_required,
            max_wait=args.max_wait,
        )
        return

    out_path = save_skill_select_capture(
        window_name=args.window,
        output_dir=args.out_dir,
        delay=args.delay,
    )
    print(f"[CAPTURE] saved: {out_path}")


if __name__ == "__main__":
    main()
