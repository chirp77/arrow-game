# -*- coding: utf-8 -*-
"""game_core.py —— 「一箭又一箭」核心玩法逻辑（纯 Python，不依赖 pygame）。

本模块只负责游戏状态与规则判定，与渲染彻底分离，便于单元测试：

- 棋盘用二维字符列表表示：'U'/'D'/'L'/'R' 为四种方向的箭头，'.' 为空格；
- 路径检测：沿箭头方向逐格前进，途中遇到其他箭头即被阻挡，走出棋盘边界即畅通；
- 点击判定在点击瞬间完成并立即修改状态（飞出消除 / 扣失误），动画只是视觉反馈；
- 撤销只回退"最近一次成功消除"，不影响失误次数。
"""

from __future__ import annotations

from dataclasses import dataclass

EMPTY = "."
# 方向字符 -> 行列方向向量 (dr, dc)
DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
VALID_CELLS = set(DIRS) | {EMPTY}


def has_clear_path(grid: list[list[str]], r: int, c: int) -> bool:
    """纯函数版路径检测：(r, c) 处的箭头沿自身方向到棋盘边界是否畅通。

    要求 (r, c) 在棋盘内。实现要点：先查界、后取值——while 条件先保证
    (nr, nc) 在棋盘内才访问 grid[nr][nc]，一旦走出边界循环结束返回 True，
    因此紧贴边缘朝外的箭头（如第 0 行的 U）第一步就"出界畅通"，不会越界。
    GameModel 和关卡求解器共用此函数，保证判定逻辑只有一份。
    """
    rows, cols = len(grid), len(grid[0])
    ch = grid[r][c]
    if ch == EMPTY:
        return False
    dr, dc = DIRS[ch]
    nr, nc = r + dr, c + dc
    while 0 <= nr < rows and 0 <= nc < cols:
        if grid[nr][nc] != EMPTY:
            return False  # 前进方向上有其他箭头阻挡
        nr, nc = nr + dr, nc + dc
    return True  # 已走出棋盘，一路无阻挡


@dataclass(frozen=True)
class ClickResult:
    """一次点击的判定结果。

    kind: "fly"=前方无阻挡，箭头飞出消除；"blocked"=前方有阻挡，扣一次失误；
          "empty"=点击了空格或棋盘外，不产生任何变化。
    cell: 被点击的格子 (r, c)。
    direction: 该箭头方向向量 (dr, dc)，"empty" 时为 (0, 0)。
    """

    kind: str
    cell: tuple[int, int]
    direction: tuple[int, int] = (0, 0)


class GameModel:
    """单局游戏状态：盘面、失误计数、撤销栈。"""

    def __init__(self, grid: list[list[str]], max_mistakes: int = 3):
        if not grid or not grid[0]:
            raise ValueError("棋盘不能为空")
        width = len(grid[0])
        for row in grid:
            if len(row) != width:
                raise ValueError("棋盘必须是矩形")
            for ch in row:
                if ch not in VALID_CELLS:
                    raise ValueError(f"非法格子字符: {ch!r}")
        self._initial = [list(row) for row in grid]  # 初始盘面深拷贝，供 restart 恢复
        self.grid = [list(row) for row in grid]      # 当前盘面
        self.max_mistakes = max_mistakes
        self.mistakes = max_mistakes
        # 撤销栈：每次成功消除压入 ((r, c), 箭头字符)
        self.undo_stack: list[tuple[tuple[int, int], str]] = []

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0])

    def cell(self, r: int, c: int) -> str:
        """取格子字符，越界视为空格（调用方无需先判边界）。"""
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return EMPTY
        return self.grid[r][c]

    def arrows_left(self) -> int:
        """剩余箭头数。每次扫描盘面现算，不维护计数器，撤销/重开天然同步。"""
        return sum(ch != EMPTY for row in self.grid for ch in row)

    def mistakes_left(self) -> int:
        return self.mistakes

    def has_clear_path(self, r: int, c: int) -> bool:
        """(r, c) 处的箭头沿自身方向到棋盘边界是否畅通（无其他箭头阻挡）。

        委托给模块级纯函数 has_clear_path；越界或空格先行拦截。
        """
        if self.cell(r, c) == EMPTY:
            return False
        return has_clear_path(self.grid, r, c)

    def try_remove(self, r: int, c: int) -> ClickResult:
        """点击 (r, c) 的判定与状态修改（瞬间完成，动画只是反馈）。

        - 空格 / 越界：不产生任何变化，也不扣失误；
        - 前方畅通：箭头被消除，压入撤销栈；
        - 前方被阻挡：箭头不动，消耗一次失误机会。
        """
        ch = self.cell(r, c)
        if ch == EMPTY:
            return ClickResult("empty", (r, c))
        if self.has_clear_path(r, c):
            self.grid[r][c] = EMPTY
            self.undo_stack.append(((r, c), ch))
            return ClickResult("fly", (r, c), DIRS[ch])
        self.mistakes -= 1
        return ClickResult("blocked", (r, c), DIRS[ch])

    def undo(self) -> bool:
        """撤销最近一次成功消除；失误次数不受影响。栈空时返回 False。"""
        if not self.undo_stack:
            return False
        (r, c), ch = self.undo_stack.pop()
        self.grid[r][c] = ch
        return True

    def restart(self) -> None:
        """恢复本关初始状态：盘面、失误数、撤销栈全部重置。"""
        self.grid = [list(row) for row in self._initial]
        self.mistakes = self.max_mistakes
        self.undo_stack.clear()

    def is_cleared(self) -> bool:
        return self.arrows_left() == 0

    def is_failed(self) -> bool:
        return self.mistakes <= 0


class GameSession:
    """跨关卡推进：管理当前关卡号，创建/重开关卡模型。

    关卡数据格式：{"name": str, "grid": list[str], "max_mistakes": int}
    （grid 用字符串行描述，创建模型时转为可变二维列表）
    """

    def __init__(self, levels: list[dict]):
        if not levels:
            raise ValueError("至少需要一个关卡")
        self.levels = levels
        self.index = 0

    @property
    def level_count(self) -> int:
        return len(self.levels)

    @property
    def current_level(self) -> dict:
        return self.levels[self.index]

    def level_name(self) -> str:
        return self.current_level.get("name", f"第{self.index + 1}关")

    def start_current(self) -> GameModel:
        """为当前关卡创建一个新的 GameModel（满失误、初始盘面）。"""
        lv = self.current_level
        return GameModel(lv["grid"], lv.get("max_mistakes", 3))

    def next_level(self) -> bool:
        """进入下一关；已在最后一关时返回 False 且不改变状态。"""
        if self.index + 1 >= len(self.levels):
            return False
        self.index += 1
        return True

    def reset_to_first(self) -> None:
        self.index = 0
