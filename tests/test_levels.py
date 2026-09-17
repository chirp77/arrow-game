# -*- coding: utf-8 -*-
"""test_levels.py —— 关卡数据合法性与可解性门禁测试。

保证每个关卡都"可以正常通关"：数据合法、求解器找到解、
且解序列逐步重放时每一步都是合法的畅通消除。
新增关卡必须通过本文件全部测试才能合入。
"""

from game_core import EMPTY, VALID_CELLS, GameModel, has_clear_path
from levels import LEVELS, solve_level


def arrow_count(grid):
    return sum(ch != EMPTY for row in grid for ch in row)


# ---------------------------------------------------------------------------
# 关卡数据合法性
# ---------------------------------------------------------------------------
def test_level_count_and_shape():
    assert len(LEVELS) >= 3                    # 作业要求至少 3 个可通关关卡
    assert len(LEVELS) >= 20                   # 用户需求：扩充到 20 关

    for i, lv in enumerate(LEVELS, 1):
        grid = lv["grid"]
        assert lv.get("name"), f"第 {i} 关缺少名称"
        assert grid and grid[0], f"第 {i} 关棋盘为空"
        width = len(grid[0])
        assert 0 < len(grid) <= 6 and 0 < width <= 6, f"第 {i} 关棋盘尺寸异常"
        for row in grid:
            assert len(row) == width, f"第 {i} 关棋盘不是矩形"
            for ch in row:
                assert ch in VALID_CELLS, f"第 {i} 关存在非法字符 {ch!r}"
        assert lv.get("max_mistakes", 0) > 0, f"第 {i} 关失误次数非法"
        assert arrow_count(grid) > 0, f"第 {i} 关没有箭头"


# ---------------------------------------------------------------------------
# 可解性：每关都必须存在合法通关顺序
# ---------------------------------------------------------------------------
def test_every_level_solvable():
    for i, lv in enumerate(LEVELS, 1):
        grid = lv["grid"]
        solution = solve_level(grid)
        assert solution is not None, f"第 {i} 关「{lv['name']}」无解！"
        assert len(solution) == arrow_count(grid), (
            f"第 {i} 关解长度 {len(solution)} != 箭头数 {arrow_count(grid)}"
        )


# ---------------------------------------------------------------------------
# 解序列重放：按求解器给出的顺序逐步点击，每步必须合法且最终通关
# ---------------------------------------------------------------------------
def test_solution_replay_clears_board():
    for i, lv in enumerate(LEVELS, 1):
        model = GameModel(lv["grid"], lv["max_mistakes"])
        for step, (r, c) in enumerate(solve_level(lv["grid"]), 1):
            assert model.has_clear_path(r, c), (
                f"第 {i} 关第 {step} 步点击 ({r},{c}) 前方有阻挡，解序列非法"
            )
            result = model.try_remove(r, c)
            assert result.kind == "fly"
        assert model.is_cleared(), f"第 {i} 关按解序列未通关"
        assert model.mistakes_left() == lv["max_mistakes"], "合法解不应消耗失误"


# ---------------------------------------------------------------------------
# 求解器正确性：死锁盘必须判定为无解（防止"可解性误判"）
# ---------------------------------------------------------------------------
def test_solver_rejects_deadlock_cases():
    # 同排互指：两个箭头互相指向对方，双双被挡，无解
    assert solve_level(["RL"]) is None
    # 同列互指（中间留空）：D 与 U 对望，互相阻挡，无解
    assert solve_level(["..D", "...", "..U"]) is None
    # 对照：非死锁盘必须有解
    assert solve_level(["R."]) == [(0, 0)]
    assert solve_level(["..D", "...", "..."]).count((0, 2)) == 1  # 单箭头必有解


# ---------------------------------------------------------------------------
# 连锁关的顺序约束：上排 → 必须从最右开始解
# ---------------------------------------------------------------------------
def test_chain_level_forces_rightmost_first():
    grid = ["RRR..", ".....", ".....", "....."]
    solution = solve_level(grid)
    # 初始只有 (0,2) 畅通，第一步必须是它
    assert solution[0] == (0, 2)
    assert solution == [(0, 2), (0, 1), (0, 0)]


# ---------------------------------------------------------------------------
# 每关人工设计的"教学点"抽查：验证关键阻挡关系确实存在
# ---------------------------------------------------------------------------
def test_level2_teaches_blocking():
    lv = LEVELS[1]
    model = GameModel(lv["grid"], lv["max_mistakes"])
    assert not model.has_clear_path(0, 0)       # (0,0) 被 (0,1) 挡住
    assert not model.has_clear_path(0, 1)       # (0,1) 被 (0,3) 挡住
    assert model.has_clear_path(0, 3)           # (0,3) 畅通，必须先消它


def test_level4_dependency_chain():
    lv = LEVELS[3]
    model = GameModel(lv["grid"], lv["max_mistakes"])
    # 初始畅通：三个
    assert model.has_clear_path(1, 1)
    assert model.has_clear_path(1, 3)
    assert model.has_clear_path(2, 2)
    # 依赖链：消 (1,1) 前 (0,1) 不通；消 (0,4) 前 (3,4) 不通
    assert not model.has_clear_path(0, 1)
    assert not model.has_clear_path(3, 4)
