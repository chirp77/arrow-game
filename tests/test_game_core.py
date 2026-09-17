# -*- coding: utf-8 -*-
"""test_game_core.py —— 核心玩法逻辑单元测试。

测试编号 T01–T09，对应作业要求的手工测试内容，用 pytest 自动化验证。
运行方式：项目根目录下执行 `uv run pytest`（或 `pytest`）。
"""

import pytest

from game_core import EMPTY, GameModel, GameSession


def make_model(rows, max_mistakes=3):
    return GameModel(rows, max_mistakes)


# ---------------------------------------------------------------------------
# T01 点击前方无阻挡的箭头：箭头飞出棋盘并消失（失误不变）
# ---------------------------------------------------------------------------
def test_click_unblocked_arrow_removes():
    model = make_model(["R..", "...", "..."])
    result = model.try_remove(0, 0)

    assert result.kind == "fly"
    assert result.cell == (0, 0)
    assert model.grid[0][0] == EMPTY          # 箭头消失
    assert model.arrows_left() == 0           # 剩余数减 1
    assert model.mistakes_left() == 3         # 成功飞出不扣失误
    assert model.is_cleared() is True         # 全消后判定通关
    assert model.is_failed() is False


# ---------------------------------------------------------------------------
# T02 点击前方有阻挡的箭头：箭头不消失，失误次数减 1
# ---------------------------------------------------------------------------
def test_click_blocked_arrow_counts_mistake():
    # 同一行两个朝右的箭头：左边的被右边的挡住
    model = make_model(["RR."])
    before = model.mistakes_left()

    result = model.try_remove(0, 0)

    assert result.kind == "blocked"
    assert model.grid[0][0] == "R"            # 箭头仍在盘上
    assert model.arrows_left() == 2           # 剩余数不变
    assert model.mistakes_left() == before - 1  # 失误 -1
    assert model.is_cleared() is False


# ---------------------------------------------------------------------------
# T03 点击位于边缘且朝向棋盘外的箭头：正常消失，不发生越界错误
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "grid, click",
    [
        # 上：第 0 行朝上的箭头
        (["U..", "...", "..."], (0, 0)),
        # 下：最后一行朝下的箭头
        (["...", "...", ".D."], (2, 1)),
        # 左：第 0 列朝左的箭头
        (["...", "L..", "..."], (1, 0)),
        # 右：最后一列朝右的箭头
        (["...", "..R", "..."], (1, 2)),
    ],
    ids=["U@顶行", "D@底行", "L@左列", "R@右列"],
)
def test_edge_arrows_outward_clear_safely(grid, click):
    model = make_model(grid)
    result = model.try_remove(*click)

    assert result.kind == "fly"               # 朝外箭头一步出界，畅通
    assert model.arrows_left() == 0
    assert model.mistakes_left() == 3         # 不扣失误
    # 不抛异常即说明没有越界访问；再补一次极端情况：1x1 盘
    tiny = make_model([["U"]])
    assert tiny.try_remove(0, 0).kind == "fly"


# ---------------------------------------------------------------------------
# T04 消除本关全部箭头：显示通关并进入下一关（关卡推进逻辑）
# ---------------------------------------------------------------------------
def test_clear_all_advances_next_level():
    session = GameSession(
        [
            {"name": "测试关1", "grid": ["R."], "max_mistakes": 3},
            {"name": "测试关2", "grid": ["U."], "max_mistakes": 3},
        ]
    )
    m1 = session.start_current()
    assert m1.try_remove(0, 0).kind == "fly"
    assert m1.is_cleared() is True            # 全消 → 通关

    assert session.next_level() is True       # 进入下一关
    assert session.index == 1
    assert session.level_name() == "测试关2"

    # 最后一关：next_level 返回 False 且不越界
    assert session.next_level() is False
    assert session.index == 1


# ---------------------------------------------------------------------------
# T05 失误次数耗尽：判定失败，允许重新开始
# ---------------------------------------------------------------------------
def test_mistakes_exhausted_fails():
    model = make_model(["RR."], max_mistakes=1)
    result = model.try_remove(0, 0)           # 被阻挡，失误 1 → 0

    assert result.kind == "blocked"
    assert model.mistakes_left() == 0
    assert model.is_failed() is True

    model.restart()                           # 重新开始恢复满状态
    assert model.is_failed() is False
    assert model.mistakes_left() == 1


# ---------------------------------------------------------------------------
# T06 游戏进行中重新开始：箭头布局和失误次数恢复
# ---------------------------------------------------------------------------
def test_restart_restores_initial_state():
    model = make_model(["RR.", "..."], max_mistakes=3)
    initial = [list(row) for row in model.grid]

    model.try_remove(0, 1)                    # 右侧箭头飞出
    model.try_remove(0, 0)                    # 被挡，扣失误
    model.restart()

    assert model.grid == initial              # 布局恢复
    assert model.arrows_left() == 2
    assert model.mistakes_left() == 3         # 失误恢复
    assert model.undo() is False              # 撤销栈已清空
    assert model.is_cleared() is False
    assert model.is_failed() is False


# ---------------------------------------------------------------------------
# T07 撤销：恢复最近消除的箭头，但不恢复失误（附加功能）
# ---------------------------------------------------------------------------
def test_undo_restores_arrow_not_mistakes():
    model = make_model(["RR."], max_mistakes=3)
    model.try_remove(0, 1)                    # 右侧飞出
    model.try_remove(0, 0)                    # 左侧此时畅通，也飞出
    model.undo()

    assert model.grid[0][0] == "R"            # 最近消除的箭头回来了
    assert model.grid[0][1] == EMPTY          # 更早消除的不受影响
    assert model.arrows_left() == 1
    assert model.mistakes_left() == 3         # 失误不变

    assert model.undo() is True
    assert model.undo() is False              # 空栈撤销失败，不抛异常


def test_undo_does_not_restore_mistakes():
    model = make_model(["RR."], max_mistakes=3)
    model.try_remove(0, 0)                    # 被挡，失误 3 → 2
    assert model.undo() is False              # 失误不产生撤销记录
    assert model.mistakes_left() == 2


# ---------------------------------------------------------------------------
# T08 点击空格或棋盘外：零变化、不扣失误、不抛异常
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("click", [(1, 1), (-1, 0), (0, 3), (3, 0)])
def test_click_empty_or_out_of_bounds_no_effect(click):
    model = make_model(["R..", "...", "..."])
    before_grid = [list(row) for row in model.grid]

    result = model.try_remove(*click)

    assert result.kind == "empty"
    assert model.grid == before_grid          # 状态零变化
    assert model.mistakes_left() == 3
    assert model.undo() is False


# ---------------------------------------------------------------------------
# T09 撤销严格 LIFO：只回退最近一次消除
# ---------------------------------------------------------------------------
def test_undo_preserves_other_cells():
    # 两个互不干扰的箭头
    model = make_model(["R..", "...", "U.."])
    model.try_remove(0, 0)                    # A 飞出
    model.try_remove(2, 0)                    # B 飞出
    model.undo()                              # 只回退 B

    assert model.grid[0][0] == EMPTY          # A 仍为空
    assert model.grid[2][0] == "U"            # B 恢复
    assert model.arrows_left() == 1


# ---------------------------------------------------------------------------
# 其他防御性测试
# ---------------------------------------------------------------------------
def test_invalid_grid_rejected():
    with pytest.raises(ValueError):
        GameModel([["R", "X"]])               # 非法字符
    with pytest.raises(ValueError):
        GameModel([["R.."], [".."]])          # 非矩形
    with pytest.raises(ValueError):
        GameModel([])                         # 空盘
    with pytest.raises(ValueError):
        GameSession([])                       # 无关卡


def test_has_clear_path_basic():
    model = make_model(["R.R", "...", "..."])
    assert model.has_clear_path(0, 0) is False   # 右侧 (0,2) 有箭头
    assert model.has_clear_path(0, 2) is True    # 右侧一路畅通
    assert model.has_clear_path(1, 1) is False   # 空格无路径
