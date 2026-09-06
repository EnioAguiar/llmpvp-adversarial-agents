import pytest

from llmpvp_adversarial.go_arbiter import PYSPIEL_AVAILABLE

pytestmark = pytest.mark.skipif(not PYSPIEL_AVAILABLE, reason="requires 'go' extra (open_spiel)")


def test_new_board_state_is_empty():
    from llmpvp_adversarial.go_arbiter import current_turn_color, new_board_state

    state = new_board_state(9, 7.5)
    assert current_turn_color(9, 7.5, state) == "black"  # Go starts with black


def test_apply_move_and_legal_moves_roundtrip():
    from llmpvp_adversarial.go_arbiter import apply_move, legal_moves, new_board_state

    state = new_board_state(9, 7.5)
    moves = legal_moves(9, 7.5, state)
    assert "pass" in moves
    result = apply_move(9, 7.5, state, "pass")
    assert result.is_pass is True


def test_illegal_move_raises():
    from llmpvp_adversarial.go_arbiter import IllegalGoMoveError, apply_move, new_board_state

    state = new_board_state(9, 7.5)
    with pytest.raises(IllegalGoMoveError):
        apply_move(9, 7.5, state, "z99")


def test_import_without_pyspiel_raises_clear_error(monkeypatch):
    import llmpvp_adversarial.go_arbiter as mod

    monkeypatch.setattr(mod, "PYSPIEL_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="pip install -e '.\\[go\\]'"):
        mod.new_board_state(9, 7.5)
