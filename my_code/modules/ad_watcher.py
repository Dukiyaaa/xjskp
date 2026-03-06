#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
from typing import Optional, Callable, Dict, Tuple, List, Any

import numpy as np

from template_matcher import *
from world_automation import *

def resource_path(rel_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)


class AdWatcher:
    """
    定时自动看广告（独立模块）：
    - 低实时：每隔一段时间巡检一次是否出现“广告入口/广告弹窗/广告可领奖励”
    - 核心：模板匹配识别 + 点击操作（click_fn 由外部注入）
    - 不负责截图：scene_bgr 由外部传入（你也可以后续改成内部持有 hwnd 自己截图）
    """

    def __init__(self, world: WorldAutomation, scan_interval: int = 300):
        self.world_automation = world
        # --- 回调 ---
        self.log_cb: Optional[Callable[[str], None]] = None

        # --- 广告模板（先占位：你后面补图） ---
        # 你可以按你当前 images/template 命名规则去放：
        template_paths = {
            # 体力模板
            "power": resource_path(r"images\template\power.png"),
            # 点击体力后的免费按钮模板
            "power_free": resource_path(r"images\template\power_free.png"),
            # 开始看广告后的广告模板
            "ad": resource_path(r"images\template\ad.png"),
            # 开始看广告后的关闭模板
            "ad_close": resource_path(r"images\template\ad_close.png"),
            # 获得奖励模板
            "reward_got": resource_path(r"images\template\reward_got.png"),
            "ad_cancel":resource_path(r"images\template\ad_cancel.png"),
        }

        self.template_paths = template_paths
        self.template_matcher = TemplateMatcher(template_paths)

        # 限定ROI
        # ROI: (x1, y1, x2, y2)  —— 基于 774x1487
        self.ROI_POWER = (420, 110, 520, 190)
        self.ROI_POWER_FREE = (112, 703, 360, 784)
        self.ROI_AD = (40, 120, 125, 175)  #
        self.ROI_AD_CLOSE = (630, 112, 773, 189)
        self.ROI_REWARD_GOT = (164, 106, 348, 188)
        self.ROI_AD_CANCEL = (600, 120, 770, 300)
        # ROI映射
        self.TPL_ROI = {
            "power": self.ROI_POWER,
            "power_free": self.ROI_POWER_FREE,
            "ad_close": self.ROI_AD_CLOSE,
            "reward_got": self.ROI_REWARD_GOT,
            "ad": self.ROI_AD,
            "ad_cancel": self.ROI_AD_CANCEL
        }

        # --- 阈值（先占位，后面你可调） ---
        self.THR_ENTRY = 0.90
        self.THR_CLOSE = 0.90
        self.THR_CLAIM = 0.90
        self.THR_SKIP = 0.90

        # 线程控制
        self.power_running = False
        self.power_stop_event = threading.Event()
        self.on_power_done = None  # Callable[[bool, str], None]

    def start_power_ads(self, max_rounds: int = 5, cooldown: int = 300):
        """启动体力广告线程（重复调用会忽略）"""
        if self.power_running:
            return

        self.power_running = True
        self.power_stop_event.clear()

        threading.Thread(
            target=self.ad_power,
            kwargs={"max_rounds": max_rounds, "cooldown": cooldown},
            daemon=True
        ).start()

    def stop_power_ads(self):
        """请求停止：会打断等待期并尽快退出"""
        if not self.power_running:
            return
        self.power_running = False
        self.power_stop_event.set()

    # ========== 基础设施 ==========
    def set_callbacks(self, log_cb=None, on_power_done=None):
        self.log_cb = log_cb
        self.on_power_done = on_power_done

    def _emit_power_done(self, ok: bool, reason: str = ""):
        cb = getattr(self, "on_power_done", None)
        if cb:
            try:
                cb(ok, reason)
            except Exception:
                pass

    def _log(self, msg: str):
        msg = f"[AD] {msg}"
        if self.log_cb:
            try:
                self.log_cb(msg)
            except Exception:
                print(msg)
        else:
            print(msg)

    def debug_dump_roi(self, scene_bgr: np.ndarray, roi: Tuple[int, int, int, int], name: str):
        x1, y1, x2, y2 = roi
        h, w = scene_bgr.shape[:2]

        # 防御：裁剪前 clamp，避免越界
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            self._log(f"[ROI][BAD] {name} roi={roi} => empty after clamp")
            return

        roi_img = scene_bgr[y1:y2, x1:x2].copy()
        out = f"debug_roi_{name}_{x1}_{y1}_{x2}_{y2}.png"

        import cv2 as cv
        cv.imwrite(out, roi_img)
        self._log(f"[ROI] saved => {out} size={roi_img.shape[1]}x{roi_img.shape[0]}")

    def debug_roi_score(self, scene_bgr: np.ndarray, tpl_name: str, roi: Tuple[int, int, int, int]):
        import cv2 as cv

        tpl = self.template_matcher.templates.get(tpl_name)
        if tpl is None:
            self._log(f"[ROI_SCORE][ERR] tpl {tpl_name} not loaded")
            return

        x1, y1, x2, y2 = roi
        h, w = scene_bgr.shape[:2]
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            self._log(f"[ROI_SCORE][BAD] {tpl_name} roi={roi} empty")
            return

        roi_img = scene_bgr[y1:y2, x1:x2]
        if roi_img.size == 0:
            self._log(f"[ROI_SCORE][BAD] {tpl_name} roi_img empty")
            return

        roi_gray = cv.cvtColor(roi_img, cv.COLOR_BGR2GRAY)
        tpl_gray = cv.cvtColor(tpl, cv.COLOR_BGR2GRAY)

        if roi_gray.shape[0] < tpl_gray.shape[0] or roi_gray.shape[1] < tpl_gray.shape[1]:
            self._log(
                f"[ROI_SCORE][SMALL] {tpl_name} roi={roi} roi_size={roi_gray.shape[::-1]} < tpl_size={tpl_gray.shape[::-1]}")
            return

        res = cv.matchTemplate(roi_gray, tpl_gray, cv.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv.minMaxLoc(res)
        self._log(f"[ROI_SCORE] {tpl_name} roi={roi} max={max_val:.3f} loc={max_loc}")

    def ad_find_button(self, scene_bgr, template_name, thr=0.90):
        roi = self.TPL_ROI.get(template_name)
        if roi:
            found, score, top_left, tpl_hw = self.template_matcher.match_template_in_roi(
                scene_bgr, template_name, roi, threshold=thr
            )
        else:
            found, score, top_left, tpl_hw = self.template_matcher.match_template(
                scene_bgr, template_name, threshold=thr
            )
        if found:
            return self.template_matcher.get_center_position(top_left, tpl_hw)
        return None

    def snap(self):
        """
        截图（统一入口）
        """
        return self.world_automation.bkgnd_full_window_screenshot()

    def click_xy(self, xy, delay: float = 0.4):
        """
        点击坐标
        """
        if xy is None:
            return
        self.world_automation.click_at(xy[0], xy[1])
        time.sleep(delay)

    def find(self, scene_bgr, name: str, thr: float = 0.90):
        return self.ad_find_button(scene_bgr, name, thr=thr)

    def wait_until(self, name: str, timeout=30, interval=1.0, thr=0.90, stop_flag=None):
        t0 = time.time()
        last_scene = None

        while time.time() - t0 < timeout:

            if stop_flag and stop_flag():
                return None, last_scene

            last_scene = self.snap()
            xy = self.find(last_scene, name, thr=thr)

            if xy:
                return xy, last_scene

            time.sleep(interval)

        return None, last_scene

    def watch_ad_and_close(self, timeout=120):
        """
        已进入广告页后：
        等 reward_got -> 点击 ad_close
        """
        self._log("开始等待广告结束")
        t0 = time.time()
        # 先确认广告页存在
        ad_close_xy, _ = self.wait_until(
            "ad_close",
            timeout=60,
            interval=1.0,
        )
        if not ad_close_xy:
            self._log("未检测到 ad_close，可能未进入广告页")
            return False
        # 等 reward_got
        while time.time() - t0 < timeout:
            reward_xy, _ = self.wait_until(
                "reward_got",
                timeout=30,
                interval=1.0,
            )
            if reward_xy:
                self._log("广告播放完成")
                # 不要 sleep 太久，避免界面切走；给一点点缓冲即可
                time.sleep(0.4)
                # 关键：多找几次 close（每次都重新截图）
                for i in range(30):
                    scene = self.snap()
                    ad_close_xy = self.find(scene, "ad_close", thr=self.THR_CLOSE)
                    if ad_close_xy:
                        self._log(f"第{i + 1}次尝试命中 ad_close，点击关闭")
                        self.click_xy(ad_close_xy, delay=0.6)
                        self._log("广告关闭完成")
                        return True
                    self._log(f"第{i + 1}次尝试未找到 ad_close，继续等...")
                    time.sleep(0.5)
                # 多次都没找到再失败
                self._log("reward_got 出现，但多次尝试仍未找到 ad_close")
                return False
            self._log("reward_got 未出现，继续等待")
        self._log("广告等待超时")
        return False

    # 体力看广告
    def ad_power(self, max_rounds: int = 5, cooldown: int = 300):
        """
        自动看体力广告，直到没有免费为止
        循环看广告的完整流程：主页-找power-进去找power_free-看广告，等退出-退出后先退回到主页-过一段时间(6分钟)重复之前的步骤，直到显示power_free已用光，最多重复5次
        """
        self._log("开始自动看体力广告")

        rounds = 0
        try:
            while self.power_running and rounds < max_rounds:
                # 确保当前在主页面
                scene = self.snap()
                # ---------- 找 power ----------
                power_xy = self.find(scene, "power")

                if not power_xy:
                    ok = False
                    reason = "power_not_found"
                    self._log("未找到 power，结束")
                    return False

                self.click_xy(power_xy, delay=1.0)
                # ---------- 找 power_free ----------
                power_free_xy, _ = self.wait_until(
                    "power_free",
                    timeout=10,
                    interval=0.8,
                    thr=self.THR_ENTRY,  #
                    stop_flag=lambda: not self.power_running,
                )

                if not power_free_xy:
                    ok = True
                    reason = "no_free_power"
                    self._log("未检测到免费体力，可能已售罄，流程结束")
                    return True

                self._log("找到免费体力，开始看广告")
                self.click_xy(power_free_xy, delay=1.0)

                ok = self.watch_ad_and_close(timeout=120)

                if not ok:
                    ok = False
                    reason = "watch_failed"
                    self._log("广告流程异常，结束")
                    return False

                # 看完后,要点一下空白地方,要用power那个位置
                time.sleep(4)
                self.click_xy(power_xy, delay=1.0)

                # ---------- 点击叉号回到主页,过六分钟再重复之前的步骤,直到显示没有power_free了----------
                # 回到主页
                ad_cancel_xy, _ = self.wait_until(
                    "ad_cancel",
                    timeout=10,
                    interval=0.8,
                    thr=self.THR_ENTRY,  #
                    stop_flag=lambda: not self.power_running,
                )

                if not ad_cancel_xy:
                    ok = False
                    reason = "ad_cancel_not_found"
                    self._log("未检测到退出按钮，结束")
                    return False

                self._log("找到退出按钮,即将返回主页")
                self.click_xy(ad_cancel_xy, delay=1.0)
                rounds += 1
                self._log(f"第 {rounds}/{max_rounds} 次广告完成，继续检测")

                self._log(f"冷却等待 {cooldown}s 后继续下一轮（可随时停止）")
                # 可中断等待：stop 时立刻返回
                if self.power_stop_event.wait(cooldown):
                    ok = True
                    reason = "stopped"
                    self._log("冷却期收到停止信号，退出")
                    return True
            if rounds >= max_rounds:
                self._log("[WARN] 达到最大轮数保护，停止")
            return True

        finally:
            # 统一收尾：确保 GUI 状态正确
            self.power_running = False
            self._log("自动体力广告已停止")
            self._emit_power_done(ok, reason)


if __name__ == "__main__":
    import time

    print("=== power ads loop test ===")

    world_automation = WorldAutomation()
    watcher = AdWatcher(world_automation, scan_interval=1)
    watcher.set_callbacks(log_cb=print)

    # 你要验证的是“重复看体力广告直到没免费”
    # 这里直接同步跑，方便看日志和定位问题
    watcher.power_running = True
    #
    try:
        ok = watcher.ad_power(max_rounds=5)  # 保护：最多30次
        print("[TEST] ad_power result:", ok)
    except KeyboardInterrupt:
        print("[TEST] KeyboardInterrupt -> stop")
    finally:
        watcher.power_running = False

        time.sleep(0.5)

    print("=== done ===")

    # ad_cancel_xy, _ = watcher.wait_until(
    #     "ad_cancel",
    #     timeout=10,
    #     interval=0.8,
    #     thr=watcher.THR_ENTRY,  #
    #     stop_flag=lambda: not watcher.power_running,
    # )
    #
    # if not ad_cancel_xy:
    #     print("未检测到退出按钮，结束")
    #
    # print("找到退出按钮,即将返回主页")
    # watcher.click_xy(ad_cancel_xy, delay=1.0)
    # # 1) 先确认 ROI 是否裁对
    # watcher.debug_dump_roi(scene_bgr, watcher.ROI_AD, "ad")
    # watcher.debug_dump_roi(scene_bgr, watcher.ROI_AD_CLOSE, "ad_close")
    # watcher.debug_dump_roi(scene_bgr, watcher.ROI_REWARD_GOT, "reward_got")
    #
    # # 2) 再看 ROI 内模板匹配的最大分数（不要求命中）
    # watcher.debug_roi_score(scene_bgr, "ad", watcher.ROI_AD)
    # watcher.debug_roi_score(scene_bgr, "ad_close", watcher.ROI_AD_CLOSE)
    # watcher.debug_roi_score(scene_bgr, "reward_got", watcher.ROI_REWARD_GOT)