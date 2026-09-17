# -*- coding: utf-8 -*-
"""config.py —— 全局常量：窗口、棋盘几何、颜色、字体候选、动画时长。"""

# 窗口
WINDOW_W, WINDOW_H = 800, 640
FPS = 60

# 棋盘
CELL = 96                     # 每格像素边长
HUD_Y = 26                    # 顶部状态栏文字基线
BTN_Y = 556                   # 底部按钮区 y 坐标

# 颜色（RGB）
BG = (38, 42, 54)             # 背景深灰蓝
BOARD_CELL = (58, 64, 80)     # 棋盘格底色
GRID_LINE = (90, 96, 115)     # 网格线 / 边框
TEXT = (232, 235, 240)        # 主文字
TEXT_DIM = (170, 176, 190)    # 次要文字
CARD = (52, 58, 72)           # 结果卡片
OVERLAY = (0, 0, 0, 160)      # 结果界面遮罩（含 alpha）
BTN = (70, 80, 95)            # 按钮
BTN_HOVER = (92, 106, 126)    # 按钮悬停
BTN_DISABLED = (56, 60, 68)   # 按钮禁用
BTN_TEXT_DISABLED = (118, 124, 136)

# 箭头按方向着色，便于区分
DIR_COLORS = {
    "U": (230, 72, 86),       # 上：红
    "D": (86, 186, 110),      # 下：绿
    "L": (80, 150, 230),      # 左：蓝
    "R": (240, 160, 60),      # 右：橙
}
BLOCK_FLASH = (235, 84, 84)   # 碰撞瞬间箭头闪红

# 剩余失误按数量分色警示
MISTAKE_SAFE = (110, 200, 130)   # ≥3：绿
MISTAKE_WARN = (240, 200, 80)    # =2：黄
MISTAKE_DANGER = (235, 90, 90)   # ≤1：红

# 中文字体候选（按优先级逐级回退）
FONT_CANDIDATES = ("microsoftyahei", "msyh", "simhei", "simsun")

# 动画时长（毫秒）
FLY_MS = 380
SHAKE_MS = 300
