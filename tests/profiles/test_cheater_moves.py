import shutil

import chess
import pytest

pytestmark = pytest.mark.skipif(shutil.which("stockfish") is None, reason="requires stockfish on PATH")


def test_careless_profile_has_zero_delay():
    from llmpvp_adversarial.profiles.cheater_moves import artificial_delay_seconds

    assert artificial_delay_seconds("careless") == 0.0


def test_careful_profile_has_nonzero_delay():
    from llmpvp_adversarial.profiles.cheater_moves import artificial_delay_seconds

    delay = artificial_delay_seconds("careful")
    assert 1.5 <= delay <= 4.0


def test_invalid_profile_raises():
    from llmpvp_adversarial.profiles.cheater_moves import artificial_delay_seconds

    with pytest.raises(ValueError):
        artificial_delay_seconds("not-a-real-profile")


def test_chess_move_returns_legal_san_for_both_profiles():
    from llmpvp_adversarial.profiles.cheater_moves import chess_move

    fen = chess.Board().fen()
    for profile in ("careless", "careful"):
        move_san = chess_move(fen, profile)
        board = chess.Board(fen)
        assert board.parse_san(move_san) in board.legal_moves
