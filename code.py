#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

import win32gui
import win32ui
import win32con
import win32api
import numpy as np
import cv2 as cv
import tkinter as tk
from tkinter import ttk
import threading
from tkinter import messagebox
import time
import os
import sys
from ctypes import windll
import random

# 游戏窗口位置和大小
X_POS = 0
Y_POS = 0
WIDTH = 400
HEIGHT = 750

# 运行状态开关
IS_RUNNING = False  

# 窗口相关全局变量
HWND = win32gui.FindWindow(None, "向僵尸开炮")    #获取标题为“向僵尸开炮”窗口的句柄

# 全局字典存储预加载的模板图片
TEMPLATE_IMGS = {}

if HWND == 0:
    messagebox.showinfo("错误", "未找到标题为“向僵尸开炮”的窗口")
else:
    # 移动游戏窗口到左上角,实现精准定位，True的作用是立即对被移动 / 调整大小后的窗口进行重绘（刷新）
    messagebox.showinfo("成功", "已找到标题为“向僵尸开炮”的窗口")
    win32gui.MoveWindow(HWND, X_POS, Y_POS, WIDTH, HEIGHT, True)

# # ---------------------- 后台截图函数（优化后：消除冗余操作） ----------------------
def bkgnd_full_window_screenshot(hwnd: int = HWND) -> np.ndarray:
    print("[DEBUG] 开始截图...")

    # 抑制系统缩放
    windll.user32.SetProcessDPIAware()
    print("[DEBUG] DPI设置完成")

    # 获取窗口矩形
    rect = win32gui.GetWindowRect(hwnd)
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    print(f"[DEBUG] 窗口位置和尺寸: 左上({rect[0]}, {rect[1]}), 宽高({width}x{height})")

    # 获取设备上下文
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    print("[DEBUG] 设备上下文创建完成")

    # 创建位图
    save_bit_map = win32ui.CreateBitmap()
    save_bit_map.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(save_bit_map)
    print("[DEBUG] 内存位图创建完成")

    # 截图到位图
    result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
    if result != 1:
        print("[WARNING] PrintWindow 截图可能失败")
    else:
        print("[DEBUG] PrintWindow 截图成功")

    # 获取位图信息
    bmpinfo = save_bit_map.GetInfo()
    bmpstr = save_bit_map.GetBitmapBits(True)
    capture = np.frombuffer(bmpstr, dtype=np.uint8).reshape(
        (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4))
    capture = np.ascontiguousarray(capture)[..., :-1]

    # 临时保存图片用于调试
    cv.imwrite("debug_screenshot.png", capture)
    print("[DEBUG] 截图已保存为 debug_screenshot.png，可打开查看")

    # 释放资源
    win32gui.DeleteObject(save_bit_map.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    print("[DEBUG] 资源释放完成")

    return capture

# 调用截图函数，得到截图 numpy 数组
img = bkgnd_full_window_screenshot()

# 可以用 OpenCV 显示一下
cv.imshow("image", img)
cv.waitKey(0)
cv.destroyAllWindows()
# # ---------------------- 模板匹配相关函数（优化后：单次截图复用+灰度图+预加载） ----------------------
# # 资源路径获取函数
# def get_resource_path(relative_path):
#     """适配PyInstaller的资源路径获取"""
#     if hasattr(sys, '_MEIPASS'):
#         # 打包后：临时目录
#         base_path = sys._MEIPASS
#     else:
#         # 开发环境：当前目录
#         base_path = os.path.abspath(".")
#     return os.path.join(base_path, relative_path)

# def preload_templates():
#     """预加载所有模板图片，减少磁盘I/O开销"""
#     template_paths = [
#         "skill_brow.png", "fanhui.png", "30blood.png", "jingying.png",
#         "lingqu.png","start.png", "retry_net.png", "continue.png","fightagain.png",
#         "00.png", "01.png", "02.png", "03.png",
#         "04.png", "05.png", "06.png", "07.png", 
#         "08.png", "09.png","10.png", "11.png", 
#         "12.png", "13.png"
#     ]
    
#     for path in template_paths:
#         full_path = get_resource_path(path)
#         img = cv.imread(full_path)
#         if img is not None:
#             TEMPLATE_IMGS[path] = img
#     print("所有模板图片预加载完成")

# # 彩色图找图函数，彩色图匹配
# def find_color_img(scene, color_img_name):
#     # 从预加载字典中获取图片，无需重复读取
#     color_img = TEMPLATE_IMGS.get(color_img_name)
#     if color_img is None:
#         return None, None

#     # 高斯模糊去噪声
#     scene_blur = cv.GaussianBlur(scene, (3, 3), 0)
#     color_blur = cv.GaussianBlur(color_img, (3, 3), 0)

#     # 彩色图模板匹配（归一化相关系数法，抗亮度变化）
#     result = cv.matchTemplate(scene_blur, color_blur, cv.TM_CCOEFF_NORMED)

#     # 获取最佳匹配位置
#     min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
#     top_left = max_loc
#     return top_left, max_val, color_img

# # 技能找图函数，灰度图匹配
# def find_skill_img(scene, skill_img_name):
#     # 从预加载字典中获取图片，避免重复读取磁盘
#     skill_img = TEMPLATE_IMGS.get(skill_img_name)
#     # 图片不存在直接返回
#     if skill_img is None:
#         return None, None, None
    
#     # 彩色图转灰度图（核心优化：减少3倍计算量）
#     try:
#         scene_gray = cv.cvtColor(scene, cv.COLOR_BGR2GRAY)
#         skill_gray = cv.cvtColor(skill_img, cv.COLOR_BGR2GRAY)
#     except:
#         return None, None, None

#     # 高斯模糊去噪声
#     scene_blur = cv.GaussianBlur(scene_gray, (3, 3), 0)
#     skill_blur = cv.GaussianBlur(skill_gray, (3, 3), 0)

#     # 灰度图模板匹配（归一化相关系数法，抗亮度变化，速度更快）
#     result = cv.matchTemplate(scene_blur, skill_blur, cv.TM_CCOEFF_NORMED)

#     # 获取最佳匹配位置
#     min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
#     top_left = max_loc

#     return top_left, max_val, skill_img

# # ---------------------- 鼠标点击函数（保持原有功能） ----------------------
# def send_mouse_click(x, y):
#     """向指定窗口发送鼠标点击事件，微信小程序窗口会自动激活、置顶"""
#     lParam = win32api.MAKELONG(x, y)
#     win32api.PostMessage(HWND, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
#     time.sleep(0.05)
#     win32api.PostMessage(HWND, win32con.WM_LBUTTONUP, 0, lParam)

# # ---------------------- 核心逻辑函数 ----------------------
# def find_skill_location_and_click():
#     global IS_RUNNING
#     IS_RUNNING = True
#     # print("开始自动持续查找并点击技能...")

#     while IS_RUNNING:
#         # 全局循环间隔，合理控制CPU占用（可按需调整为3-5秒）
#         time.sleep(3)
#         has_found_skill = False  # 标记是否找到技能

#         # 关键：单次截图，所有模板匹配复用该截图，消除重复截图浪费
#         scene = bkgnd_full_window_screenshot()
#         # cv.imwrite("scene.png", scene)

#         if scene is None:
#             continue  # 截图失败则跳过本次循环

#         top_left, max_val, img = find_color_img(scene, "jingying.png")
#         if max_val >= 0.9 and IS_RUNNING:
#             print("发现精英掉落页面")
#             time.sleep(4)
#             # 计算图片中心坐标（更精准点击）
#             img_width = img.shape[1]
#             img_height = img.shape[0]
#             click_x = top_left[0] + img_width // 2
#             click_y = top_left[1] + img_height // 2
#             send_mouse_click(click_x, click_y)

#         top_left, max_val, img = find_color_img(scene, "lingqu.png")
#         if max_val >= 0.9 and IS_RUNNING:
#             print("发现 领取 按钮")
#             time.sleep(2)
#             # 关闭领取对话框
#             send_mouse_click(505,180)

#         top_left, max_val, img = find_color_img(scene, "retry_net.png")
#         if max_val >= 0.9 and IS_RUNNING:
#             print("发现重新连接按钮")
#             time.sleep(4)
#             # 计算图片中心坐标（更精准点击）
#             img_width = img.shape[1]
#             img_height = img.shape[0]
#             click_x = top_left[0] + img_width // 2
#             click_y = top_left[1] + img_height // 2
#             send_mouse_click(click_x, click_y)

#         top_left, max_val, img = find_color_img(scene, "fightagain.png")
#         if max_val >= 0.9 and IS_RUNNING:
#             print("发现继续战斗按钮")
#             time.sleep(4)
#             # 计算图片中心坐标（更精准点击）
#             img_width = img.shape[1]
#             img_height = img.shape[0]
#             click_x = top_left[0] + img_width // 2
#             click_y = top_left[1] + img_height // 2
#             send_mouse_click(click_x, click_y)

#         top_left, max_val, img = find_color_img(scene, "continue.png")
#         if max_val >= 0.9 and IS_RUNNING:
#             print("发现继续游戏按钮")
#             time.sleep(4)
#             # 计算图片中心坐标（更精准点击）
#             img_width = img.shape[1]
#             img_height = img.shape[0]
#             click_x = top_left[0] + img_width // 2
#             click_y = top_left[1] + img_height // 2
#             send_mouse_click(click_x, click_y)
        
#         top_left, max_val, img = find_color_img(scene, "fanhui.png")
#         if max_val >= 0.9 and IS_RUNNING:
#             print("发现 返回 按钮")
#             time.sleep(3)
#             if checkbox2_var.get() == 1:
#                 time.sleep(2)
#                 print("勾选了循环闯关，点击 返回 按钮")
#                 img_width = img.shape[1]
#                 img_height = img.shape[0]
#                 click_x = top_left[0] + img_width // 2
#                 click_y = top_left[1] + img_height // 2
#                 send_mouse_click(click_x, click_y)
#             else:
#                 print("发现 返回按钮，未勾选循环闯关，停止工具运行")
#                 stop()
#                 break

#         top_left, max_val, img = find_color_img(scene, "start.png")
#         if max_val >= 0.9 and IS_RUNNING:
#             print("发现 开始游戏 按钮")
#             time.sleep(3)
#             if checkbox2_var.get() == 1:
#                 time.sleep(2)
#                 print("勾选了循环闯关，点击 开始游戏 按钮")
#                 img_width = img.shape[1]
#                 img_height = img.shape[0]
#                 click_x = top_left[0] + img_width // 2
#                 click_y = top_left[1] + img_height // 2
#                 send_mouse_click(click_x, click_y)

#         # 未出现选择技能窗口，就继续下一次循环
#         top_left_skill, max_val_skill, img = find_color_img(scene, "skill_brow.png")
#         if max_val_skill <= 0.9 and IS_RUNNING:
#             print("未出现选择技能")
#             continue # 跳过其他检查，继续下一次循环

#         # 恢复30%血量
#         if checkbox1_var.get() == 1:
#             top_left, max_val, img = find_skill_img(scene, "30blood.png")
#             if max_val >= 0.9 and IS_RUNNING:
#                 # 计算图片中心坐标（更精准点击）
#                 img_width = img.shape[1]
#                 img_height = img.shape[0]
#                 click_x = top_left[0] + img_width // 2
#                 click_y = top_left[1] + img_height // 2
#                 send_mouse_click(click_x, click_y)
#                 print("已恢复30%血量")
#                 has_found_skill = True

#         # 核心：循环遍历4个下拉列表，实现索引→图片→匹配点击
#         for idx, combobox in enumerate(combobox_list):
#             # 获取选中项的索引（关键：索引对应图片名称）
#             try:
#                 skill_index = combobox.current()  # 获取当前选中项的索引（0-13）
#                 # 拼接模板图片名称（索引0→00.png，索引1→01.png...）
#                 img_name = f"{skill_index:02d}.png"
#             except:
#                 continue  # 获取索引失败则跳过

#             top_left, max_val, img = find_skill_img(scene, img_name)
#             if max_val >= 0.9 and IS_RUNNING:
#                 # 计算图片中心坐标（精准点击，避免点击边缘）
#                 img_width = img.shape[1]
#                 img_height = img.shape[0]
#                 click_x = top_left[0] + img_width // 2
#                 click_y = top_left[1] + img_height // 2
#                 # 执行点击
#                 send_mouse_click(click_x, click_y)
#                 print(f"已点击技能：{combobox.get()}")
#                 has_found_skill = True
#                 break

#         # 未找到勾选的技能时，执行默认操作
#         if not has_found_skill and IS_RUNNING:
#             print("未找到勾选的技能，随机点选技能")
#             send_mouse_click(random.choice([95, 278, 460]), 490)



# # # -----------------------------寰球救援功能--------------------------
# # def huanqiujiuyuan_skill_location_and_click():
# #     global IS_RUNNING
# #     IS_RUNNING = True

# #     while IS_RUNNING:
# #         # 全局循环间隔，合理控制CPU占用（可按需调整为2-5秒）
# #         time.sleep(1.5)
# #         has_found_skill = False  # 标记是否找到技能

# #         # 关键：单次截图，所有模板匹配复用该截图，消除重复截图浪费
# #         scene = bkgnd_full_window_screenshot()
# #         # cv.imwrite("scene.png", scene)

# #         if scene is None:
# #             continue  # 截图失败则跳过本次循环

# #         top_left, max_val, img = find_color_img(scene, "liaotian.png")
# #         if max_val >= 0.9 and IS_RUNNING:
# #             print("发现 寰球救援聊天 按钮")
# #             # 计算图片中心坐标（更精准点击）
# #             img_width = img.shape[1]
# #             img_height = img.shape[0]
# #             click_x = top_left[0] + img_width // 2
# #             click_y = top_left[1] + img_height // 2
# #             send_mouse_click(click_x, click_y)
# #             # 点击招募
# #             time.sleep(1.5)
# #             send_mouse_click(90, 280)
        
# #         top_left, max_val, img = find_color_img(scene, "hq_nd01.png")
# #         if max_val >= 0.9 and IS_RUNNING:
# #             if nandu1_var.get() == 1:
# #                 img_width = img.shape[1]
# #                 img_height = img.shape[0]
# #                 click_x = top_left[0] + img_width // 2
# #                 click_y = top_left[1] + img_height // 2
# #                 print("发现 难度1招募，已点击")
# #                 send_mouse_click(click_x, click_y)
   


# #         # 未出现选择技能窗口，就继续下一次循环
# #         top_left_skill, max_val_skill, img = find_color_img(scene, "skill_brow.png")
# #         if max_val_skill <= 0.9 and IS_RUNNING:
# #             print("未出现寰球救援 选择技能")
# #             continue # 跳过其他检查，继续下一次循环

# #         # 核心：循环遍历4个下拉列表，实现索引→图片→匹配点击
# #         for idx, combobox in enumerate(combobox_list):
# #             # 获取选中项的索引（关键：索引对应图片名称）
# #             try:
# #                 skill_index = combobox.current()  # 获取当前选中项的索引（0-13）
# #                 # 拼接模板图片名称（索引0→00.png，索引1→01.png...）
# #                 img_name = f"{skill_index:02d}.png"
# #             except:
# #                 continue  # 获取索引失败则跳过

# #             top_left, max_val, img = find_skill_img(scene, img_name)
# #             if max_val >= 0.9 and IS_RUNNING:
# #                 # 计算图片中心坐标（精准点击，避免点击边缘）
# #                 img_width = img.shape[1]
# #                 img_height = img.shape[0]
# #                 click_x = top_left[0] + img_width // 2
# #                 click_y = top_left[1] + img_height // 2
# #                 # 执行点击
# #                 send_mouse_click(click_x, click_y)
# #                 print(f"已点击寰球救援技能：{combobox.get()}")
# #                 has_found_skill = True
# #                 break

# #         # 未找到勾选的技能时，执行默认操作
# #         if not has_found_skill and IS_RUNNING:
# #             print("未找到寰球救援勾选的技能，随机点选技能")
# #             send_mouse_click(random.choice([95, 278, 460]), 490)


# # ---------------------- 线程启动与停止函数----------------------
# def start_thread():
#     """启动后台线程，持续模拟鼠标点击"""
#     print("开始闯关模式")
#     thread = threading.Thread(target=find_skill_location_and_click)
#     thread.daemon = True  # 设为守护线程，主程序退出时自动结束
#     thread.start()
#     start_button.config(state="disabled")  # 点击后禁用按钮

# def stop():
#     """停止后台操作，启用开始按钮"""
#     global IS_RUNNING
#     IS_RUNNING = False
#     start_button.config(state="normal")
#     messagebox.showinfo("提示", "工具已停止运行")

# # def start_hq_thread():
# #     """启动后台线程，持续模拟鼠标点击"""
# #     print("开始 寰球救援 模式")
# #     thread = threading.Thread(target=huanqiujiuyuan_skill_location_and_click)
# #     thread.daemon = True  # 设为守护线程，主程序退出时自动结束
# #     thread.start()
# #     hq_start_button.config(state="disabled")  # 点击后禁用按钮

# # def stop_hq():
# #     """停止后台操作，启用开始按钮"""
# #     global IS_RUNNING
# #     IS_RUNNING = False
# #     hq_start_button.config(state="normal")
# #     messagebox.showinfo("提示", "寰球救援模式  已停止")



# # ---------------------- 主窗口创建----------------------
# root = tk.Tk()
# root.title("游戏辅助工具  意见反馈：★面包★  QQ：3708703")
# root.resizable(False, False)
# root.geometry("500x280+750+300")

# # 标签：提示信息
# weapon_label = tk.Label(root, text="【 配置技能 】")
# weapon_label.place(x=10, y=5)

# # 创建标签和下拉列表框1
# SKILLS = [
#     "00 枪械",
#     "01 温压弹（火系弹道技能）",
#     "02 干冰弹（冰系弹道技能）",
#     "03 电磁穿刺（电系技能）",
#     "04 装甲车（物理系地面技能）",
#     "05 高能射线（能量系激光技能）",
#     "06 制导激光（能量系激光技能）",
#     "07 冰暴发生器（冰系爆炸技能）",
#     "08 跃迁电子（电系技能）",
#     "09 旋风加农（风系技能）",
#     "10 空投轰炸（物理系爆炸技能）",
#     "11 压缩气刃（风系弹道技能）",
#     "12 燃油弹（火系地面技能）",
#     "13 无人机冲击（物理系技能）",
# ]

# # 2. 初始化下拉框列表，用于存储4个combobox实例（与原逻辑一致）
# combobox_list = []

# # 3. 循环批量创建标签+下拉框（4次循环对应4个技能）
# for i in range(4):
#     # 创建标签：文本为“技能X：”，y坐标从30开始，每次递增30
#     label = tk.Label(root, text=f"技能{i+1}：")
#     label.place(x=20, y=30 + i * 30)
    
#     # 创建下拉框：复用公共技能列表
#     combobox = ttk.Combobox(
#         root,
#         values=SKILLS,       # 公共技能选项
#         height=14            # 最多显示14项，超出滚动
#     )
#     combobox.current(i)      # 默认选中第i项（原逻辑：技能1选0、技能2选1...）
#     combobox.state(["readonly"])  # 只读不允许编辑
#     # 布局：x/y坐标
#     combobox.place(x=80, y=30 + i * 30, width=180, height=25)
    
#     # 将下拉框实例添加到列表，方便后续遍历
#     combobox_list.append(combobox)


# # 复选框引用变量
# checkbox1_var = tk.IntVar()
# checkbox2_var = tk.IntVar()
# # nandu1_var = tk.IntVar()



# checkbox1 = tk.Checkbutton(root, text="恢复30%血量", variable=checkbox1_var, onvalue=1, offvalue=0)
# checkbox1.place(x=280, y=25)
# checkbox2 = tk.Checkbutton(root, text="循环闯关（单人模式）", variable=checkbox2_var, onvalue=1, offvalue=0)
# checkbox2.place(x=280, y=45)

# # checkbox1 = tk.Checkbutton(root, text="恢复30%血量", variable=checkbox1_var, onvalue=1, offvalue=0)
# # checkbox1.place(x=20, y=150)
# # checkbox2 = tk.Checkbutton(root, text="循环闯关（单人模式）", variable=checkbox2_var, onvalue=1, offvalue=0)
# # checkbox2.place(x=20, y=170)

# # 闯关功能按钮
# start_button = tk.Button(root, text="开始", command=start_thread)
# start_button.place(x=30, y=200, width=50, height=40)

# stop_button = tk.Button(root, text="停止", command=stop)
# stop_button.place(x=100, y=200, width=50, height=40)


# # auto_huanqiujiuyuan_label = tk.Label(root, text="【寰球救援自动加入招募】\n须先进入难度选择界面，再点击开始")
# # auto_huanqiujiuyuan_label.place(x=280, y=5)
# # nandu1_checkbox = tk.Checkbutton(root, text="难度1（角色战力推荐1200+勾选）", variable=nandu1_var, onvalue=1, offvalue=0)
# # nandu1_checkbox.place(x=280, y=50)
# # nandu2_checkbox = tk.Checkbutton(root, text="难度2", variable=nandu2_var, onvalue=1, offvalue=0)
# # nandu2_checkbox.place(x=280, y=50)

# # hq_start_button = tk.Button(root, text="寰球救援\n开始循环", command=start_hq_thread)
# # hq_start_button.place(x=280, y=200, width=80, height=40)

# # hq_stop_button = tk.Button(root, text="寰球救援\n停止", command=stop_hq)
# # hq_stop_button.place(x=380, y=200, width=80, height=40)


# # 版本标签
# tt_label = tk.Label(root, text="工具免费使用 适配电脑端微信小程序：向僵尸开炮")
# tt_label.config(fg="red")
# tt_label.place(x=10, y=250)

# version_label = tk.Label(root, text="最后更新日期：2026.1.30")
# version_label.place(x=330, y=250)

# # ---------------------- 程序入口 ----------------------
# if __name__ == "__main__":
#     # 预加载所有模板图片
#     preload_templates()
#     # 启动主循环
#     root.mainloop()