#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from typing import Optional, Callable, Dict, Tuple, List, Any

import numpy as np

from pathlib import Path
import os
from template_matcher import TemplateMatcher

def resource_path(rel_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)

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

    def __init__(
        self,
        template_matcher,
        base_w: int = 774,
        base_h: int = 1487,
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
        self.template_matcher = TemplateMatcher(template_paths)

        # --- 关键模板名（先占位：后续你往 template_paths 里加对应图片） ---
        # 4选2：底部“0/2确定”按钮
        self.TPL_CONFIRM_BTN = "skill_confirm"
        # 选择界面锚点（例如 “选择技能”文字/背景圆环）——可选
        self.TPL_PICK_ANCHOR = None

        # --- 技能名模板（按优先级顺序存名字）---
        # 例如：["干冰弹增伤", "温压冲击", ...] 对应模板名你自己统一命名
        self.skill_priority: List[str] = []

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
        return self.MODE_NONE

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
        return False