import cv2 as cv
import numpy as np

import cv2 as cv
import numpy as np


class TemplateMatcher:
    def __init__(self, template_path):
        """
        初始化模板匹配类
        :param template_path: 模板图片路径
        """
        self.template = cv.imread(template_path)
        if self.template is None:
            raise FileNotFoundError(f"模板加载失败：{template_path}")
        print(f"[INFO] 模板加载成功：{template_path}")

    def match_template(self, scene_bgr, threshold=0.90):
        """
        在给定的截图中寻找模板
        :param scene_bgr: 截图图像（BGR格式）
        :param threshold: 匹配的相似度阈值
        :return: 是否匹配，匹配度，最佳匹配位置，模板尺寸
        """
        # 转换为灰度图
        scene_gray = cv.cvtColor(scene_bgr, cv.COLOR_BGR2GRAY)
        tpl_gray = cv.cvtColor(self.template, cv.COLOR_BGR2GRAY)

        # 模板匹配
        res = cv.matchTemplate(scene_gray, tpl_gray, cv.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv.minMaxLoc(res)

        found = max_val >= threshold
        return found, max_val, max_loc, self.template.shape[:2]  # 返回是否匹配，匹配度，位置和模板尺寸

    def draw_match(self, scene_bgr, top_left, tpl_hw, out_path="match_debug.png"):
        """
        绘制匹配结果并保存
        :param scene_bgr: 截图图像
        :param top_left: 模板匹配位置
        :param tpl_hw: 模板尺寸 (h, w)
        :param out_path: 保存路径
        """
        h, w = tpl_hw
        x, y = top_left
        vis = scene_bgr.copy()
        cv.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv.imwrite(out_path, vis)
        print(f"[DEBUG] 已输出标注图：{out_path}")

    def get_center_position(self, top_left, tpl_hw):
        """
        计算模板匹配区域的中心位置
        :param top_left: 模板匹配区域的左上角坐标
        :param tpl_hw: 模板的高度和宽度
        :return: 模板匹配区域的中心位置 (x, y)
        """
        h, w = tpl_hw  # tpl_hw 是 (height, width)
        center_x = top_left[0] + w // 2
        center_y = top_left[1] + h // 2
        return center_x, center_y

    def test_match(self, scene_bgr, threshold=0.90):
        """
        测试模板匹配
        :param scene_bgr: 截图图像
        :param threshold: 匹配的相似度阈值
        """
        # 使用模板匹配进行检测
        found, score, top_left, tpl_hw = self.match_template(scene_bgr, threshold)

        print(f"[MATCH] {'FOUND' if found else 'NOT FOUND'} with score={score:.2f} at {top_left}")

        # 如果匹配成功，绘制标注图
        if found:
            self.draw_match(scene_bgr, top_left, tpl_hw, out_path="match_debug.png")
            # 计算并打印模板匹配区域的中心位置
            center_x, center_y = self.get_center_position(top_left, tpl_hw)
            print(f"[DEBUG] 模板匹配区域的中心位置: ({center_x}, {center_y})")

def main():
    # 选择模板路径
    template_path = r"D:\MAIN\xjskp\my_code\images\template\main_start_game.png"

    # 初始化模板匹配类
    template_matcher = TemplateMatcher(template_path)

    # 获取截图
    scene_bgr = cv.imread(r"D:\MAIN\xjskp\my_code\images\test\main_test.png")
    # 调用模板匹配进行验证
    template_matcher.test_match(scene_bgr, threshold=0.90)

if __name__ == "__main__":
    main()