# -*- coding: utf-8 -*-
"""test_rendering.py —— 界面渲染冒烟测试（dummy 驱动，不弹真实窗口）。

对渲染结果做像素级断言，验证关键元素确实画在正确位置：
- 场景背景、棋盘底色正确；
- 四种方向的箭头画在对应格子中心、颜色正确；
- HUD 区域有文字像素；
- 结果界面的遮罩与卡片出现；
- 碰撞时被挡箭头闪红。
"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from config import BG, BOARD_CELL, CARD, CELL, DIR_COLORS
from levels import create_session
from main import App
from sounds import pre_init_mixer

# 模块级初始化一次
pre_init_mixer()
pygame.init()
_app = App()          # 建好窗口与场景
_screen = _app.screen


def setup_app():
    """重置到第 1 关的新会话，返回 (app, scene)。"""
    _app.session = create_session()
    _app.start_level()
    return _app, _app.scene


def draw(scene):
    scene.draw(_screen, (0, 0))


def sample(x, y):
    return _screen.get_at((int(x), int(y)))[:3]


def count_color(rect, pred):
    """统计 rect 区域内满足 pred(color) 的像素数。"""
    n = 0
    for x in range(rect[0], rect[0] + rect[2], 3):
        for y in range(rect[1], rect[1] + rect[3], 3):
            if pred(sample(x, y)):
                n += 1
    return n


# ---------------------------------------------------------------------------
# 开始界面
# ---------------------------------------------------------------------------
def test_start_scene_renders_title():
    app, _ = setup_app()
    app.show_start()
    app.scene.update(600)   # 越过入场淡入动画（450ms）
    draw(app.scene)

    assert sample(5, 5) == BG                          # 背景色正确
    # 标题区域（"一箭又一箭"，72 号浅色大字）应有大量非背景像素
    title_px = count_color((100, 100, 600, 100), lambda c: c != BG)
    assert title_px > 200, f"标题像素过少：{title_px}"
    # 开始按钮区域有按钮底色
    assert sample(400, 460) != BG


# ---------------------------------------------------------------------------
# 游戏界面：棋盘、四种方向的箭头、HUD
# ---------------------------------------------------------------------------
def test_game_scene_board_and_arrows():
    app, scene = setup_app()          # 第 1 关
    draw(scene)

    # 棋盘底色：棋盘左上角往内一点
    assert sample(scene.board.left + 6, scene.board.top + 6) == BOARD_CELL
    # 第 1 关箭头位置与颜色：".L..R" / "..U.." / "....." / "L.D.R"
    expected = {
        (0, 1): "L", (0, 4): "R", (1, 2): "U", (3, 0): "L", (3, 2): "D", (3, 4): "R",
    }
    for (r, c), ch in expected.items():
        x = scene.board.left + c * CELL + CELL // 2
        y = scene.board.top + r * CELL + CELL // 2
        assert sample(x, y) == DIR_COLORS[ch], f"格子 ({r},{c}) 的 {ch} 箭头颜色不对"
    # 空格子中心是棋盘底色（第 1 关 (1,0) 为空）
    x = scene.board.left + 0 * CELL + CELL // 2
    y = scene.board.top + 1 * CELL + CELL // 2
    assert sample(x, y) == BOARD_CELL
    # HUD 有文字像素（顶部状态栏）
    hud_px = count_color((0, 20, 800, 40), lambda c: c != BG)
    assert hud_px > 50, f"HUD 文字像素过少：{hud_px}"


# ---------------------------------------------------------------------------
# 结果界面：遮罩 + 卡片 + 按钮
# ---------------------------------------------------------------------------
def test_result_scene_overlay_and_card():
    app, scene = setup_app()
    app.show_game_over()
    app.scene.update(300)   # 越过卡片弹出动画（260ms）
    draw(app.scene)

    # 遮罩：背景被半透明黑压暗（38,42,54 -> 约 14,16,21）
    c = sample(5, 5)
    assert c[0] < 20 and c[1] < 22 and c[2] < 28, f"遮罩效果异常：{c}"
    # 卡片底色
    assert sample(400, 210) == CARD
    # 按钮区域出现按钮色（BTN 或悬停/文字色，非卡片色）
    btn_px = count_color((300, 352, 200, 56), lambda c: c != CARD)
    assert btn_px > 100, f"按钮像素过少：{btn_px}"


# ---------------------------------------------------------------------------
# 碰撞反馈：被挡箭头闪红 + 失误扣减
# ---------------------------------------------------------------------------
def test_blocked_click_flashes_red():
    app, scene = setup_app()
    app.session.index = 1          # 第 2 关：".RR.U." 的 (0,0) 被 (0,1) 阻挡
    app.start_level()
    scene = app.scene

    r, c = 0, 0
    x = scene.board.left + c * CELL + CELL // 2
    y = scene.board.top + r * CELL + CELL // 2
    scene.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y)))
    assert scene.anim_state == "shake"
    assert app.model.mistakes_left() == 3     # 失误 4 -> 3
    scene.update(50)                          # 晃动进行中（t≈0.17）
    draw(scene)

    # 被挡箭头所在格内出现闪红色像素（红 > 200 且绿 < 150，排除橙色原色）
    cell_rect = (scene.board.left + c * CELL, scene.board.top + r * CELL, CELL, CELL)
    flash_px = count_color(cell_rect, lambda c: c[0] > 200 and c[1] < 150)
    assert flash_px > 30, f"闪红像素过少：{flash_px}"


# ---------------------------------------------------------------------------
# 飞出动画：点击后进入 fly 状态、盘面已消除、动画中箭头渐隐位置变化
# ---------------------------------------------------------------------------
def test_fly_click_enters_animation_and_clears_cell():
    app, scene = setup_app()       # 第 1 关
    r, c = 0, 1                     # (0,1) 为 L，左侧畅通
    x = scene.board.left + c * CELL + CELL // 2
    y = scene.board.top + r * CELL + CELL // 2
    scene.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y)))

    assert scene.anim_state == "fly"
    assert app.model.grid[0][1] == "."       # 判定瞬间已消除
    assert app.model.mistakes_left() == 5    # 飞出不扣失误
    pos1 = scene.anim.pos()
    scene.update(100)
    pos2 = scene.anim.pos()
    assert pos2 != pos1, "飞出动画位置未变化"
    assert scene.anim.alpha() <= 255         # 渐隐参数合法
