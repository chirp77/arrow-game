# -*- coding: utf-8 -*-
"""animation.py —— 飞出与碰撞动画（纯数学计算，配合 pygame 绘制）。

动画基于时间（毫秒）驱动，主循环传入截断后的 dt，窗口拖拽恢复时不会瞬跳。
"""

import math

from config import FLY_MS, SHAKE_MS


class FlyAnimation:
    """箭头飞出棋盘动画：缓入加速 + 后段渐隐。"""

    def __init__(self, start_px, direction, board_rect, duration_ms=FLY_MS):
        self.start = start_px
        self.elapsed = 0.0
        self.duration = duration_ms
        # 网格方向 (dr, dc) 转像素方向 (dx, dy)
        dr, dc = direction
        self.dx, self.dy = dc, dr
        # 目标点：沿方向越过棋盘边界后再飞 80px，产生"飞出屏幕"效果
        if dc == 0:  # 竖直飞出
            if dr == -1:
                dist = start_px[1] - board_rect.top
            else:
                dist = board_rect.bottom - start_px[1]
        else:        # 水平飞出
            if dc == -1:
                dist = start_px[0] - board_rect.left
            else:
                dist = board_rect.right - start_px[0]
        extra = 80
        self.end = (start_px[0] + self.dx * (dist + extra),
                    start_px[1] + self.dy * (dist + extra))

    @property
    def t(self):
        return min(1.0, self.elapsed / self.duration)

    @property
    def finished(self):
        return self.elapsed >= self.duration

    def update(self, dt):
        self.elapsed += dt

    def pos(self):
        """缓入插值（t*t）：起步慢、越飞越快，符合"箭"的直觉。"""
        t = self.t
        e = t * t
        return (self.start[0] + (self.end[0] - self.start[0]) * e,
                self.start[1] + (self.end[1] - self.start[1]) * e)

    def alpha(self):
        """后 40% 时间从 255 渐隐到 0。"""
        t = self.t
        if t < 0.6:
            return 255
        return max(0, int(255 * (1 - (t - 0.6) / 0.4)))


class ShakeAnimation:
    """碰撞晃动动画：沿与箭头方向垂直的轴抖动，幅度随时间衰减。"""

    def __init__(self, center_px, direction, duration_ms=SHAKE_MS):
        self.center = center_px
        self.elapsed = 0.0
        self.duration = duration_ms
        # 垂直轴（像素空间）：上/下箭头左右抖，左/右箭头上下抖
        dr, dc = direction
        self.ax, self.ay = dr, -dc

    @property
    def t(self):
        return min(1.0, self.elapsed / self.duration)

    @property
    def finished(self):
        return self.elapsed >= self.duration

    def update(self, dt):
        self.elapsed += dt

    def offset(self):
        """当前抖动偏移量（像素）：幅度从 10px 衰减到 0，约 8 次往返。"""
        t = self.t
        amp = 10 * (1 - t)
        k = math.sin(t * math.tau * 8)
        return (self.ax * amp * k, self.ay * amp * k)

    def flash_color(self, base_color, flash=(235, 84, 84)):
        """碰撞前半段向闪红渐变，后半段恢复原色。"""
        t = self.t
        k = max(0.0, 1 - t * 2)  # t=0 全红，t=0.5 起恢复原色
        return tuple(int(c + (f - c) * k) for c, f in zip(base_color, flash))

    def ring(self):
        """碰撞冲击环：前 60% 时间从箭头向外扩散的红圈，返回 (半径, 透明度)。

        结束后返回 None，调用方跳过绘制。
        """
        t = self.t
        if t >= 0.6:
            return None
        radius = 20 + t * 30  # 从 20px 扩散到约 38px
        alpha = int(200 * (1 - t / 0.6))
        return radius, alpha
