# -*- coding: utf-8 -*-
"""selftest.py —— 自动化验收脚本（`python main.py --selftest` 调用）。

用 dummy 视频/音频驱动、不开真实窗口，自动走完整个游戏流程：
开始 → 全部关卡依次按求解器给出的序列通关 → 全部通关 → 失败重开 → 撤销 → 游戏中重开，
每个环节做断言，并保存界面截图到 screenshots/（供 README 与博客使用）。

等价于把作业要求的手工测试 T01–T06 自动化执行一遍。
"""

import os

# 必须在 import pygame 之前设置，SDL 初始化时读取
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from config import CELL
from levels import LEVELS, create_session, solve_level
from sounds import pre_init_mixer
from ui import AllClearScene, GameOverScene, GameScene, LevelClearScene, StartScene

SHOT_DIR = "screenshots"
_shot_count = 0


def shot(app, name):
    """保存当前画面截图。"""
    global _shot_count
    os.makedirs(SHOT_DIR, exist_ok=True)
    pygame.image.save(app.screen, os.path.join(SHOT_DIR, name))
    _shot_count += 1
    print(f"[截图] {name}")


def _pump(app, frames=1, dt=16):
    """推进若干帧：处理事件 + update + draw。"""
    for _ in range(frames):
        for event in pygame.event.get():
            app.scene.handle_event(event)
        app.scene.update(dt)
        app.scene.draw(app.screen, (0, 0))


def click_at(app, pos):
    """向事件队列投递一次鼠标左键按下（走真实的命中检测路径）。"""
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    _pump(app, 1)


def click_cell(app, r, c):
    """点击棋盘格子 (r, c) 的中心。"""
    scene = app.scene
    x = scene.board.left + c * CELL + CELL // 2
    y = scene.board.top + r * CELL + CELL // 2
    click_at(app, (x, y))


def pump_until_idle(app, max_frames=240):
    """推进直到游戏场景动画结束（或已切换到其他场景）。"""
    for _ in range(max_frames):
        _pump(app, 1)
        if getattr(app.scene, "anim", None) is None:
            return
    raise AssertionError("动画超时未结束")


def check(name, cond):
    print(f"[检查] {name}: {'PASS' if cond else 'FAIL'}")
    assert cond, name


def run_selftest():
    import main as main_mod

    pre_init_mixer()
    pygame.init()
    app = main_mod.App()

    # ---- 1. 开始界面（先推帧让淡入动画完成，再截图） ----
    assert isinstance(app.scene, StartScene)
    _pump(app, 40)
    shot(app, "01_start.png")

    # ---- 2. 开始游戏 → 第 1 关（T04 前置） ----
    click_at(app, app.scene.start_button.rect.center)
    assert isinstance(app.scene, GameScene), "点击开始按钮未进入游戏场景"
    assert app.model.arrows_left() == 6 and app.model.mistakes_left() == 5
    shot(app, "02_game_level1.png")

    # ---- 3. 全部关卡依次通关（T01/T03/T04） ----
    for idx in range(len(LEVELS)):
        solution = solve_level(LEVELS[idx]["grid"])
        assert solution, f"第 {idx + 1} 关无解"
        for step, (r, c) in enumerate(solution):
            click_cell(app, r, c)
            pump_until_idle(app)
            if idx == len(LEVELS) - 1 and step == 0:
                shot(app, "02b_game_level20.png")  # 最后一关 6×5 大棋盘截图
        if idx < len(LEVELS) - 1:
            assert isinstance(app.scene, LevelClearScene), f"第 {idx + 1} 关未进入通关界面"
            if idx == 0:
                _pump(app, 30)  # 等卡片弹出动画结束
                shot(app, "03_clear_level1.png")
            click_at(app, app.scene.next_button.rect.center)
            assert isinstance(app.scene, GameScene), f"未进入第 {idx + 2} 关"
        else:
            assert isinstance(app.scene, AllClearScene), "最后一关未进入全部通关界面"
            _pump(app, 30)  # 等卡片弹出动画结束
            shot(app, "05_all_clear.png")
    check("T04 全部 20 关按序通关", True)

    # ---- 4. 回到开始 → 定位到第 2 关做碰撞与失败测试（T02/T05） ----
    click_at(app, app.scene.back_button.rect.center)
    assert isinstance(app.scene, StartScene), "全部通关后未回到开始界面"
    app.session = create_session()
    app.session.index = 1
    app.start_level()
    assert app.model.arrows_left() == 5 and app.model.mistakes_left() == 4

    for i in range(4):
        before = app.model.mistakes_left()
        click_cell(app, 0, 0)          # (0,0) 被 (0,1) 阻挡，必碰撞
        if i == 0:
            _pump(app, 6)              # 晃动动画中间帧
            shot(app, "04_collision.png")
        pump_until_idle(app)
        check(f"T02 第{i + 1}次阻挡点击：失误 {before}->{app.model.mistakes_left()}",
              app.model.mistakes_left() == before - 1)
        assert app.model.grid[0][0] == "R", "被阻挡的箭头不应消失"
    assert isinstance(app.scene, GameOverScene), "失误耗尽未进入失败界面"
    _pump(app, 30)  # 等卡片弹出动画结束
    shot(app, "06_game_over.png")
    check("T05 失误耗尽进入失败界面", True)

    # ---- 5. 失败后重新开始本关（T05/T06） ----
    click_at(app, app.scene.retry_button.rect.center)
    assert isinstance(app.scene, GameScene)
    check("T05 失败后重新开始：状态恢复",
          app.model.mistakes_left() == 4 and app.model.arrows_left() == 5)

    # ---- 6. 撤销（附加功能） ----
    click_cell(app, 0, 3)              # (0,3)U 畅通，飞出
    pump_until_idle(app)
    check("T07 飞走后剩余箭头 -1", app.model.arrows_left() == 4)
    click_at(app, app.scene.undo_btn.rect.center)
    check("T07 撤销恢复箭头", app.model.arrows_left() == 5 and app.model.grid[0][3] == "U")

    # ---- 7. 游戏中重新开始按钮（T06） ----
    click_cell(app, 0, 3)
    pump_until_idle(app)
    click_at(app, app.scene.restart_btn.rect.center)
    check("T06 游戏中重开：布局与失误恢复",
          app.model.arrows_left() == 5 and app.model.mistakes_left() == 4)

    # ---- 8. 点空格与棋盘外：零变化、不扣失误（T08） ----
    click_cell(app, 1, 1)              # 空格
    click_at(app, (100, 100))          # 棋盘外
    check("T08 点空格/棋盘外不扣失误", app.model.mistakes_left() == 4)
    check("T08 点空格/棋盘外箭头数不变", app.model.arrows_left() == 5)

    # ---- 9. 动画期间狂点：输入被冻结，不会重复扣失误 ----
    click_cell(app, 0, 3)              # 起飞动画开始
    _pump(app, 3)                      # 动画进行中
    click_cell(app, 0, 0)              # 此时点击被冻结，应被忽略
    pump_until_idle(app)
    check("动画期间输入冻结", app.model.mistakes_left() == 4)

    pygame.quit()
    print(f"\nSELFTEST OK：全部流程通过，共保存 {_shot_count} 张截图到 {SHOT_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_selftest())
