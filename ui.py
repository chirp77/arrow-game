# -*- coding: utf-8 -*-
"""ui.py —— 界面层：场景、按钮、棋盘与箭头绘制（依赖 pygame）。

五个场景：StartScene（开始）/ GameScene（游戏）/ LevelClearScene（通关）/
GameOverScene（失败）/ AllClearScene（全部通关），由 main.App 统一调度。
全部游戏规则判定都在 game_core / levels 中完成，本层只做渲染与输入转发。
"""

import math
import random
import time

import pygame

from animation import FlyAnimation, ShakeAnimation
from config import (
    BG, BLOCK_FLASH, BOARD_CELL, BTN, BTN_DISABLED, BTN_HOVER,
    BTN_TEXT_DISABLED, BTN_Y, CARD, CELL, DIR_COLORS, FONT_CANDIDATES,
    GRID_LINE, HUD_Y, MISTAKE_DANGER, MISTAKE_SAFE, MISTAKE_WARN, OVERLAY,
    TEXT, TEXT_DIM, WINDOW_H, WINDOW_W,
)
from game_core import DIRS, EMPTY

# ---------------------------------------------------------------------------
# 字体：中文系统字体逐级回退
# ---------------------------------------------------------------------------
_FONT_CACHE = {}
_FONT_PICKED = None


def get_font(size, bold=False):
    """按候选列表取第一个可用的中文字体；全失败则退回 pygame 内置字体。"""
    global _FONT_PICKED
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    font = None
    for name in FONT_CANDIDATES:
        path = pygame.font.match_font(name)
        if path:
            font = pygame.font.Font(path, size)
            if _FONT_PICKED is None:
                _FONT_PICKED = name
                print(f"字体：使用 {name}（{path}）")
            break
    if font is None:
        font = pygame.font.Font(None, size)  # 兜底：内置字体（不支持中文）
        if _FONT_PICKED is None:
            print("警告：未找到中文字体，界面文字可能无法显示！")
    font.set_bold(bold)
    _FONT_CACHE[key] = font
    return font


def draw_text(surface, text, size, center=None, topleft=None, topright=None,
              midtop=None, color=TEXT, bold=False):
    """便捷文本绘制：指定一个锚点（center / topleft / topright / midtop）。"""
    img = get_font(size, bold).render(text, True, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    elif topleft is not None:
        rect.topleft = topleft
    elif topright is not None:
        rect.topright = topright
    elif midtop is not None:
        rect.midtop = midtop
    surface.blit(img, rect)
    return rect


def draw_text_alpha(surface, text, size, center, color, alpha, bold=False):
    """带透明度渐显的文本（界面淡入动效用）。"""
    img = get_font(size, bold).render(text, True, color)
    img.set_alpha(max(0, min(255, int(alpha))))
    surface.blit(img, img.get_rect(center=center))


def mistakes_color(n):
    """剩余失误的颜色警示：≥3 绿、2 黄、≤1 红。"""
    if n >= 3:
        return MISTAKE_SAFE
    if n == 2:
        return MISTAKE_WARN
    return MISTAKE_DANGER


# ---------------------------------------------------------------------------
# 箭头绘制
# ---------------------------------------------------------------------------
def draw_arrow(surface, center, ch, color, scale=1.0):
    """以 center 为中心画一个指向 ch 方向（U/D/L/R）的细长箭头（细杆 + 修长箭头）。

    以"朝右"为基准形状，再按方向向量旋转：右不动、左镜像、上/下旋转 ±90°。
    scale 控制整体缩放（1.0 为棋盘大小，图例/装饰用小数值）。
    """
    x, y = center
    dr, dc = DIRS[ch]

    def rot(px, py):
        """像素偏移按网格方向 (dr, dc) 旋转（推导见 README 实现思路）。"""
        ox, oy = px - x, py - y
        return (x + ox * dc - oy * dr, y + ox * dr + oy * dc)

    def off(sx, sy):
        """基准偏移量（朝右）按 scale 缩放后的绝对坐标。"""
        return rot(x + sx * scale, y + sy * scale)

    # 细杆：高 9px（比旧版 14px 更纤细），箭头：更长更尖的三角头
    shaft = [off(-24, -4.5), off(14, -4.5), off(14, 4.5), off(-24, 4.5)]
    head = [off(14, -18), off(37, 0), off(14, 18)]
    pygame.draw.polygon(surface, color, shaft)
    pygame.draw.polygon(surface, color, head)
    # 高光：杆上缘一条更浅的细线，增加立体感
    lighten = tuple(int(c + (255 - c) * 0.45) for c in color)
    hl = [off(-24, -4.5), off(12, -4.5), off(12, -2.2), off(-24, -2.2)]
    pygame.draw.polygon(surface, lighten, hl)


def draw_arrow_alpha(surface, center, ch, color, alpha, scale=1.0):
    """带透明度的箭头（飞出渐隐用）：画到临时 SRCALPHA 表面再 blit。"""
    tmp = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    draw_arrow(tmp, (CELL // 2, CELL // 2), ch, color, scale)
    tmp.set_alpha(alpha)
    surface.blit(tmp, (center[0] - CELL // 2, center[1] - CELL // 2))


# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------
class Button:
    """矩形文字按钮：普通 / 悬停 / 禁用 三种视觉状态。"""

    def __init__(self, rect, text, on_click, font_size=26):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.on_click = on_click
        self.font_size = font_size
        self.enabled = True

    def handle_event(self, event):
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.enabled and self.rect.collidepoint(event.pos)):
            self.on_click()
            return True
        return False

    def draw(self, surface, mouse_pos):
        hovered = self.enabled and self.rect.collidepoint(mouse_pos)
        if not self.enabled:
            color, text_color = BTN_DISABLED, BTN_TEXT_DISABLED
        elif hovered:
            color, text_color = BTN_HOVER, TEXT
        else:
            color, text_color = BTN, TEXT
        pygame.draw.rect(surface, color, self.rect, border_radius=10)
        draw_text(surface, self.text, self.font_size, center=self.rect.center, color=text_color)


# ---------------------------------------------------------------------------
# 棋盘几何
# ---------------------------------------------------------------------------
def board_rect(cols, rows):
    """棋盘矩形：水平居中，垂直中心位于窗口中部偏上。"""
    w, h = cols * CELL, rows * CELL
    left = (WINDOW_W - w) // 2
    top = 300 - h // 2
    return pygame.Rect(left, top, w, h)


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------
class StartScene:
    """开始界面：漂浮箭头装饰背景、标题与说明依次淡入、开始按钮。"""

    def __init__(self, app):
        self.app = app
        self.elapsed = 0.0
        self.start_button = Button(pygame.Rect(300, 430, 200, 60), "开始游戏",
                                   app.start_new_game, font_size=30)
        # 背景漂浮箭头：随机方向 / 位置 / 速度 / 相位，缓慢向上漂移
        rng = random.Random(20260915)  # 固定种子，每次启动观感一致
        self.decos = []
        for _ in range(14):
            self.decos.append({
                "ch": rng.choice("UDLR"),
                "x": rng.uniform(30, WINDOW_W - 30),
                "y": rng.uniform(0, WINDOW_H),
                "speed": rng.uniform(12, 28),       # 像素/秒
                "phase": rng.uniform(0, math.tau),  # 透明度脉动相位
                "scale": rng.uniform(0.28, 0.45),
            })

    def handle_event(self, event):
        self.start_button.handle_event(event)

    def update(self, dt):
        self.elapsed += dt
        for d in self.decos:
            d["y"] -= d["speed"] * dt / 1000.0
            if d["y"] < -40:  # 漂出顶部后回到底部重新漂
                d["y"] = WINDOW_H + 40
                d["x"] = random.uniform(30, WINDOW_W - 30)

    def draw(self, surface, mouse_pos):
        surface.fill(BG)
        # 背景漂浮箭头：低透明度缓慢脉动，不抢主体
        for d in self.decos:
            alpha = 60 + 55 * math.sin(self.elapsed / 480 + d["phase"])
            draw_arrow_alpha(surface, (int(d["x"]), int(d["y"])), d["ch"],
                             DIR_COLORS[d["ch"]], alpha, d["scale"])
        # 标题、副标题与规则依次淡入（入场动效）
        t = self.elapsed / 450
        draw_text_alpha(surface, "一箭又一箭", 72, (WINDOW_W // 2, 150), TEXT,
                        255 * t, bold=True)
        draw_text_alpha(surface, "点击箭头，让它们全部飞出棋盘！", 28,
                        (WINDOW_W // 2, 240), TEXT, 255 * max(0.0, t - 0.15))
        rules = [
            "箭头会沿所指方向直线飞出棋盘",
            "前方有箭头阻挡时会碰撞，并消耗一次失误机会",
            "失误次数用尽则本关失败，清空全部箭头即可过关",
        ]
        y = 306
        for i, line in enumerate(rules):
            draw_text_alpha(surface, line, 20, (WINDOW_W // 2, y), TEXT_DIM,
                            255 * max(0.0, t - 0.3 - 0.12 * i))
            y += 34
        if self.elapsed >= 380:  # 按钮最后入场
            self.start_button.draw(surface, mouse_pos)
        draw_text(surface, "F12 截图 · Esc 退出", 16, center=(WINDOW_W // 2, 604), color=TEXT_DIM)


class GameScene:
    """游戏主界面：HUD、棋盘、点击消除、飞出/碰撞动画、撤销与重开按钮。"""

    def __init__(self, app, session, model):
        self.app = app
        self.session = session
        self.model = model
        self.board = board_rect(model.cols, model.rows)
        self.anim_state = "idle"      # idle / fly / shake
        self.anim = None              # FlyAnimation / ShakeAnimation
        self.anim_cell = None         # 正在动画的格子 (r, c)
        self.fly_char = None          # 飞出动画的箭头字符快照
        self._board_cache = None
        self._fx_layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        self.particles = []           # 飞出拖尾粒子 [x, y, vx, vy, life, max_life]
        self.float_text = None        # 碰撞飘字 {"cell": (r, c), "age": ms}
        self.undo_btn = Button(pygame.Rect(268, BTN_Y, 120, 48), "撤销", self._on_undo)
        self.restart_btn = Button(pygame.Rect(412, BTN_Y, 120, 48), "重新开始", self._on_restart)

    # ---------------- 输入 ----------------
    def handle_event(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.anim_state != "idle":
            return  # 动画期间冻结一切输入，防止重复判定
        if self.undo_btn.handle_event(event) or self.restart_btn.handle_event(event):
            return
        cell = self.pixel_to_cell(event.pos)
        if cell is None:
            return  # 棋盘外点击直接忽略
        ch = self.model.cell(*cell)
        if ch == EMPTY:
            return  # 空格点击：无任何变化，也不扣失误
        result = self.model.try_remove(*cell)
        if result.kind == "fly":
            self.app.play("fly")
            self.fly_char = ch
            self.anim = FlyAnimation(self.cell_center(*cell), result.direction, self.board)
            self.anim_state = "fly"
            self.anim_cell = cell
            self._board_cache = None   # 盘面已变化，重建棋盘缓存
        elif result.kind == "blocked":
            self.app.play("collide")
            self.anim = ShakeAnimation(self.cell_center(*cell), result.direction)
            self.anim_state = "shake"
            self.anim_cell = cell
            self.float_text = {"cell": cell, "age": 0.0}  # 碰撞飘字提示扣失误

    def update(self, dt):
        self._update_particles(dt)
        if self.float_text is not None:
            self.float_text["age"] += dt
            if self.float_text["age"] >= 700:
                self.float_text = None
        if self.anim is None:
            return
        self.anim.update(dt)
        if not self.anim.finished:
            return
        # 动画结束才推进流程：飞完判通关，晃完判失败
        if self.anim_state == "fly":
            if self.model.is_cleared():
                self.app.play("clear")
                # 关卡结束瞬间冻结计时，结果界面的用时不再变化
                self.app.level_elapsed = time.time() - self.app.level_started
                self.app.session_elapsed = time.time() - self.app.session_started
                if self.session.index + 1 < self.session.level_count:
                    self.app.show_level_clear()   # 还有下一关：通关界面
                else:
                    self.app.show_all_clear()     # 最后一关：全部通关界面
                return
        else:  # shake
            if self.model.is_failed():
                self.app.play("over")
                # 失败同样冻结计时
                self.app.level_elapsed = time.time() - self.app.level_started
                self.app.show_game_over()
                return
        self.anim = None
        self.anim_state = "idle"
        self.anim_cell = None

    def _update_particles(self, dt):
        """飞出时在箭头身后撒拖尾粒子，粒子随帧漂移并自动消亡。"""
        if self.anim_state == "fly":
            n = max(1, int(dt / 8))  # 约每 8ms 一颗
            px, py = self.anim.pos()
            for _ in range(min(n, 4)):
                # 与飞行方向相反的小速度 + 随机抖动，形成彗尾
                vx = -self.anim.dx * random.uniform(30, 70) + random.uniform(-25, 25)
                vy = -self.anim.dy * random.uniform(30, 70) + random.uniform(-25, 25)
                self.particles.append([px + random.uniform(-4, 4),
                                       py + random.uniform(-4, 4),
                                       vx, vy, 260.0, 260.0])
        for p in self.particles:
            p[4] -= dt
            p[0] += p[2] * dt / 1000.0
            p[1] += p[3] * dt / 1000.0
        self.particles = [p for p in self.particles if p[4] > 0]

    def _on_undo(self):
        if self.model.undo():
            self.app.play("undo")
            self._board_cache = None

    def _on_restart(self):
        self.model.restart()
        self.app.level_started = time.time()  # 重开本关，计时同时归零
        self._board_cache = None

    # ---------------- 绘制 ----------------
    def draw(self, surface, mouse_pos):
        surface.fill(BG)
        self._draw_hud(surface)
        self._ensure_board_cache()
        surface.blit(self._board_cache, self.board.topleft)
        if self.anim_state == "idle":
            self._draw_hover(surface, mouse_pos)
        elif self.anim_state == "shake":
            self._draw_shake(surface)
        elif self.anim_state == "fly":
            self._draw_fly(surface)
        self._draw_fx(surface)      # 粒子、冲击环、飘字（特效叠加层）
        self._draw_legend(surface)  # 方向颜色图例
        # 底部按钮（撤销栈空时置灰）
        self.undo_btn.enabled = bool(self.model.undo_stack)
        self.undo_btn.draw(surface, mouse_pos)
        self.restart_btn.draw(surface, mouse_pos)

    def _draw_hud(self, surface):
        draw_text(surface, f"第 {self.session.index + 1} 关 · {self.session.level_name()}",
                  26, topleft=(40, HUD_Y), bold=True)
        draw_text(surface, f"剩余箭头：{self.model.arrows_left()}",
                  26, center=(WINDOW_W // 2, HUD_Y + 14))
        # 剩余失误按数量分色（绿/黄/红），计时排在失误左侧
        rect = draw_text(surface, f"剩余失误：{self.model.mistakes_left()}",
                         26, topright=(WINDOW_W - 40, HUD_Y),
                         color=mistakes_color(self.model.mistakes_left()))
        sec = max(0, int(time.time() - self.app.level_started))
        draw_text(surface, f"用时 {sec // 60:02d}:{sec % 60:02d}",
                  18, topright=(rect.left - 18, HUD_Y + 4), color=TEXT_DIM)

    def _draw_fx(self, surface):
        """特效叠加层：飞出拖尾粒子、碰撞冲击环、失误飘字。"""
        fx = self._fx_layer
        fx.fill((0, 0, 0, 0))
        # 拖尾粒子
        for p in self.particles:
            alpha = int(255 * p[4] / p[5])
            pygame.draw.circle(fx, (*DIR_COLORS[self.fly_char], alpha),
                               (int(p[0]), int(p[1])), 4)
        # 碰撞冲击环：从箭头向外扩散的红圈
        if self.anim_state == "shake":
            ring = self.anim.ring()
            if ring is not None:
                radius, alpha = ring
                r, c = self.anim_cell
                pygame.draw.circle(fx, (*BLOCK_FLASH, alpha),
                                   self.cell_center(r, c), int(radius), width=3)
        # 失误飘字：上浮并渐隐
        if self.float_text is not None:
            age = self.float_text["age"]
            r, c = self.float_text["cell"]
            cx, cy = self.cell_center(r, c)
            img = get_font(22, True).render("失误 -1", True, BLOCK_FLASH)
            img.set_alpha(max(0, int(255 * (1 - age / 700))))
            fx.blit(img, img.get_rect(center=(cx, cy - 18 - age * 0.06)))
        surface.blit(fx, (0, 0))

    def _draw_legend(self, surface):
        """棋盘下方两角的方向颜色图例，帮助新玩家分辨四种箭头。"""
        items = [("U", "上"), ("D", "下")]
        x = 80
        for ch, label in items:
            draw_arrow(surface, (x - 14, BTN_Y + 24), ch, DIR_COLORS[ch], scale=0.22)
            draw_text(surface, label, 18, center=(x + 12, BTN_Y + 24), color=TEXT_DIM)
            x += 88
        x = WINDOW_W - 160
        for ch, label in [("L", "左"), ("R", "右")]:
            draw_arrow(surface, (x - 14, BTN_Y + 24), ch, DIR_COLORS[ch], scale=0.22)
            draw_text(surface, label, 18, center=(x + 12, BTN_Y + 24), color=TEXT_DIM)
            x += 88

    def _draw_hover(self, surface, mouse_pos):
        """鼠标悬停在箭头上时加一层白色高光，提示可点击。"""
        cell = self.pixel_to_cell(mouse_pos)
        if cell is None or self.model.cell(*cell) == EMPTY:
            return
        r, c = cell
        glow = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        glow.fill((255, 255, 255, 26))
        surface.blit(glow, (self.board.left + c * CELL, self.board.top + r * CELL))

    def _draw_shake(self, surface):
        """晃动中的箭头：覆盖原格底色，按抖动偏移重画（前半段闪红）。"""
        r, c = self.anim_cell
        center = self.cell_center(r, c)
        ox, oy = self.anim.offset()
        cover = pygame.Rect(self.board.left + c * CELL, self.board.top + r * CELL, CELL, CELL)
        pygame.draw.rect(surface, BOARD_CELL, cover)
        ch = self.model.grid[r][c]
        color = self.anim.flash_color(DIR_COLORS[ch])
        draw_arrow(surface, (center[0] + ox, center[1] + oy), ch, color)

    def _draw_fly(self, surface):
        """飞出中的箭头：按插值位置与透明度绘制。"""
        pos = self.anim.pos()
        draw_arrow_alpha(surface, pos, self.fly_char, DIR_COLORS[self.fly_char], self.anim.alpha())

    def _ensure_board_cache(self):
        """棋盘静态内容缓存到一张 Surface，盘面变化时重建。"""
        if self._board_cache is not None:
            return
        surf = pygame.Surface(self.board.size)
        surf.fill(BOARD_CELL)
        for i in range(1, self.model.cols):
            x = i * CELL
            pygame.draw.line(surf, GRID_LINE, (x, 0), (x, self.board.height))
        for i in range(1, self.model.rows):
            y = i * CELL
            pygame.draw.line(surf, GRID_LINE, (0, y), (self.board.width, y))
        pygame.draw.rect(surf, GRID_LINE, surf.get_rect(), width=2)
        for r in range(self.model.rows):
            for c in range(self.model.cols):
                ch = self.model.grid[r][c]
                if ch != EMPTY:
                    draw_arrow(surf, (c * CELL + CELL // 2, r * CELL + CELL // 2),
                               ch, DIR_COLORS[ch])
        self._board_cache = surf

    # ---------------- 坐标换算 ----------------
    def cell_center(self, r, c):
        return (self.board.left + c * CELL + CELL // 2,
                self.board.top + r * CELL + CELL // 2)

    def pixel_to_cell(self, pos):
        if not self.board.collidepoint(pos):
            return None
        c = (pos[0] - self.board.left) // CELL
        r = (pos[1] - self.board.top) // CELL
        return (r, c)


class _ResultScene:
    """通关 / 失败 / 全部通关 界面的公共部分：遮罩 + 卡片（弹出动画）。"""

    card = pygame.Rect(220, 180, 360, 280)
    POP_MS = 260  # 卡片弹出动画时长

    def __init__(self):
        self.age = 0.0  # 入场后经过的毫秒，驱动弹出动画

    def update(self, dt):
        self.age += dt

    def draw_base(self, surface, title, subtitle, button, mouse_pos):
        # 弹出动画：卡片整体上移 + 渐显（ease-out 缓动）
        t = min(1.0, self.age / self.POP_MS)
        ease = 1 - (1 - t) ** 2
        slide = int(26 * (1 - ease))
        alpha = int(255 * min(1.0, self.age / 200))
        # 全部内容画到临时表面，统一施加透明度
        layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        layer.fill(BG)
        mask = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        mask.fill(OVERLAY)
        layer.blit(mask, (0, 0))
        card = self.card.move(0, -slide)
        pygame.draw.rect(layer, CARD, card, border_radius=16)
        draw_text(layer, title, 44, center=(WINDOW_W // 2, 240 - slide), bold=True)
        draw_text(layer, subtitle, 22, center=(WINDOW_W // 2, 300 - slide), color=TEXT_DIM)
        # 按钮跟随卡片一起弹出（临时移动 rect，画完立即恢复，不影响点击判定）
        orig = button.rect
        button.rect = button.rect.move(0, -slide)
        button.draw(layer, mouse_pos)
        button.rect = orig
        layer.set_alpha(alpha)
        surface.blit(layer, (0, 0))


class LevelClearScene(_ResultScene):
    """通关界面：显示本关用时，进入下一关。"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.next_button = Button(pygame.Rect(300, 352, 200, 56), "下一关", self._next, font_size=28)

    def _next(self):
        if self.app.session.next_level():
            self.app.start_level()
        else:
            self.app.show_all_clear()  # 最后一关：直接进入全部通关（正常不会走到）

    def handle_event(self, event):
        self.next_button.handle_event(event)

    def draw(self, surface, mouse_pos):
        idx = self.app.session.index
        subtitle = f"本关用时 {self.app.level_elapsed:.1f} 秒 · 剩余失误 {self.app.model.mistakes_left()}"
        self.draw_base(surface, f"第 {idx + 1} 关通过！", subtitle, self.next_button, mouse_pos)


class GameOverScene(_ResultScene):
    """失败界面：重新开始本关。"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.retry_button = Button(pygame.Rect(300, 352, 200, 56), "重新开始本关",
                                   self._retry, font_size=24)

    def _retry(self):
        self.app.start_level()  # 会话停留在当前关，重建模型

    def handle_event(self, event):
        self.retry_button.handle_event(event)

    def draw(self, surface, mouse_pos):
        idx = self.app.session.index
        self.draw_base(surface, "失误次数用尽",
                       f"第 {idx + 1} 关失败 · 本关用时 {self.app.level_elapsed:.1f} 秒",
                       self.retry_button, mouse_pos)


class AllClearScene(_ResultScene):
    """全部通关界面：显示总用时，回到开始界面。"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.back_button = Button(pygame.Rect(300, 352, 200, 56), "回到开始界面",
                                  self.app.show_start, font_size=24)

    def handle_event(self, event):
        self.back_button.handle_event(event)

    def draw(self, surface, mouse_pos):
        total = self.app.session.level_count
        self.draw_base(surface, "恭喜通关！",
                       f"你完成了全部 {total} 关，总用时 {self.app.session_elapsed:.0f} 秒",
                       self.back_button, mouse_pos)
