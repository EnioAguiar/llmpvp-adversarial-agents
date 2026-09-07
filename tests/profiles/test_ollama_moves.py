import json

import httpx
import pytest


def test_legal_chess_moves_san_lists_all_opening_moves():
    from llmpvp_adversarial.profiles.ollama_moves import legal_chess_moves_san

    import chess

    fen = chess.Board().fen()
    moves = legal_chess_moves_san(fen)
    assert "e4" in moves
    assert len(moves) == 20  # 20 legal first moves in chess


def test_chess_move_picks_from_ollama_response(monkeypatch):
    from llmpvp_adversarial.profiles import ollama_moves

    def fake_post(self, url, json=None, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"message": {"content": '{"move": "e4"}'}}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    import chess

    fen = chess.Board().fen()
    move = ollama_moves.chess_move(fen)
    assert move == "e4"


def test_chess_move_raises_after_max_attempts_on_illegal_response(monkeypatch):
    from llmpvp_adversarial.profiles import ollama_moves

    def fake_post(self, url, json=None, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"message": {"content": '{"move": "not-a-real-move"}'}}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    import chess

    fen = chess.Board().fen()
    with pytest.raises(ollama_moves.HonestMoveError):
        ollama_moves.chess_move(fen)
