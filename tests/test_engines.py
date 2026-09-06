import shutil

import chess
import pytest

pytestmark = pytest.mark.skipif(shutil.which("stockfish") is None, reason="requires stockfish on PATH")


def test_stockfish_best_move_returns_legal_san():
    from llmpvp_adversarial.engines import stockfish_best_move

    fen = chess.Board().fen()
    move_san = stockfish_best_move(fen, time_seconds=0.1)
    board = chess.Board(fen)
    assert board.parse_san(move_san) in board.legal_moves


def test_stockfish_eval_cp_is_near_zero_at_startpos():
    from llmpvp_adversarial.engines import stockfish_eval_cp

    fen = chess.Board().fen()
    cp = stockfish_eval_cp(fen, time_seconds=0.1)
    assert -100 <= cp <= 100  # startpos is roughly balanced


def test_stockfish_weighted_move_returns_legal_san():
    from llmpvp_adversarial.engines import stockfish_weighted_move

    fen = chess.Board().fen()
    move_san = stockfish_weighted_move(fen, time_seconds=0.1, multipv=3, weights=[0.6, 0.3, 0.1])
    board = chess.Board(fen)
    assert board.parse_san(move_san) in board.legal_moves


def test_pachi_best_move_without_binary_raises_clear_error(monkeypatch):
    import llmpvp_adversarial.engines as mod

    monkeypatch.setattr(mod.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="pachi"):
        mod.pachi_best_move(9, 7.5, [], "black", sims=100)
