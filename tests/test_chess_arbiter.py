import pytest

from llmpvp_adversarial.chess_arbiter import IllegalMoveError, apply_move, game_outcome


def test_apply_move_accepts_san():
    result = apply_move(chess_startpos(), "e4")
    assert result.san == "e4"
    assert result.uci == "e2e4"
    assert result.is_check is False


def test_apply_move_accepts_uci():
    result = apply_move(chess_startpos(), "e2e4")
    assert result.uci == "e2e4"


def test_apply_move_rejects_illegal_move():
    with pytest.raises(IllegalMoveError):
        apply_move(chess_startpos(), "e5")  # black to move first is e4/d4/etc, not e5 from start


def test_game_outcome_none_mid_game():
    assert game_outcome(["e2e4", "e7e5"]) is None


def test_game_outcome_detects_checkmate():
    # Fool's mate
    moves = ["f2f3", "e7e5", "g2g4", "d8h4"]
    outcome = game_outcome(moves)
    assert outcome is not None
    assert outcome.result == "black"
    assert outcome.reason == "checkmate"


def chess_startpos() -> str:
    import chess

    return chess.Board().fen()
