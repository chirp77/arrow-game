# -*- coding: utf-8 -*-
"""main.py —— 程序入口：窗口、主循环、场景调度、F12 截图与自检模式。

运行：
    uv run python main.py              # 正常启动游戏
    uv run python main.py --selftest   # 自动化验收：dummy 驱动走完整流程并截图
"""

import os
import sys
import time

import pygame

from config import FPS, WINDOW_H, WINDOW_W
from levels import create_session
from sounds import SoundPlayer, pre_init_mixer
from ui import AllClearScene, GameOverScene, GameScene, LevelClearScene, StartScene

SCREENSHOT_DIR = "screenshots"


class App:
    """应用外壳：持有当前场景、关卡会话与音效，负责场景切换。"""

    def __init__(self):
        self.session = None
        self.model = None
        self.sounds = SoundPlayer()
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("一箭又一箭")
        self.clock = pygame.time.Clock()
        self.scene = StartScene(self)
        self.level_started = time.time()     # 当前关开始时刻（计时功能）
        self.session_started = time.time()   # 本局开始时刻（总用时）
        self.level_elapsed = 0.0             # 当前关结束时冻结的用时
        self.session_elapsed = 0.0           # 全部通关时冻结的总用时

    # ---------------- 场景切换 ----------------
    def show_start(self):
        self.scene = StartScene(self)

    def start_new_game(self):
        """从第 1 关开始新游戏。"""
        self.session = create_session()
        self.session_started = time.time()
        self.start_level()

    def start_level(self):
        """为会话当前关卡创建一个全新模型并进入游戏场景。"""
        self.level_started = time.time()
        self.model = self.session.start_current()
        self.scene = GameScene(self, self.session, self.model)

    def show_level_clear(self):
        self.scene = LevelClearScene(self)

    def show_game_over(self):
        self.scene = GameOverScene(self)

    def show_all_clear(self):
        self.scene = AllClearScene(self)

    def play(self, name):
        self.sounds.play(name)

    # ---------------- 主循环 ----------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_F12:
                    self.save_screenshot()
                    continue
            self.scene.handle_event(event)
        return True

    def save_screenshot(self):
        """F12：把当前画面保存到 screenshots/ 目录。"""
        try:
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            name = time.strftime("%Y%m%d_%H%M%S") + ".png"
            path = os.path.join(SCREENSHOT_DIR, name)
            pygame.image.save(self.screen, path)
            print(f"截图已保存：{path}")
        except OSError as exc:
            print(f"截图失败：{exc}")

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS), 50)  # 截断 dt，防止拖窗后动画瞬跳
            running = self.handle_events()
            self.scene.update(dt)
            self.scene.draw(self.screen, pygame.mouse.get_pos())
            pygame.display.flip()
        pygame.quit()


def main():
    # 音效采样参数必须在 pygame.init() 之前设置
    pre_init_mixer()
    pygame.init()
    app = App()
    app.run()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        from selftest import run_selftest
        sys.exit(run_selftest())
    main()
