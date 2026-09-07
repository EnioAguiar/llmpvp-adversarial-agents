import json
import shutil

import chess
import httpx
import pytest

pytestmark = pytest.mark.skipif(shutil.which("stockfish") is None, reason="requires stockfish on PATH")


def test_chess_move_records_self_reasoned_ply(monkeypatch, tmp_path):
    from llmpvp_adversarial.profiles import c3_moves

    def fake_post(self, url, json=None, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"message": {"content": '{"move": "e4"}'}}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    records: list[c3_moves.PlyRecord] = []
    fen = chess.Board().fen()
    move = c3_moves.chess_move(fen, records)

    assert move == "e4"
    assert len(records) == 1
    assert records[0].consulted is False
    assert records[0].move == "e4"
    assert isinstance(records[0].eval_cp, int)


def test_chess_move_records_consulted_ply_when_model_requests_it(monkeypatch):
    from llmpvp_adversarial.profiles import c3_moves

    call_count = {"n": 0}

    def fake_post(self, url, json=None, **kwargs):
        call_count["n"] += 1
        request = httpx.Request("POST", url)
        if call_count["n"] == 1:
            return httpx.Response(200, json={"message": {"content": '{"consult_engine": true}'}}, request=request)
        return httpx.Response(200, json={"message": {"content": '{"move": "e4"}'}}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    records: list[c3_moves.PlyRecord] = []
    fen = chess.Board().fen()
    move = c3_moves.chess_move(fen, records)

    assert len(records) == 1
    assert records[0].consulted is True


def test_chess_move_never_exceeds_the_consultation_rate_cap(monkeypatch):
    """The model requesting consult_engine on EVERY call must not push the
    cumulative consultation rate above the cap -- enforced by removing the
    option from the prompt (the mock simulates a model that always tries
    to consult when the option is offered, and complies when it isn't)."""
    from llmpvp_adversarial.profiles import c3_moves

    def fake_post(self, url, json=None, **kwargs):
        request = httpx.Request("POST", url)
        system_content = json["messages"][0]["content"]
        if "consult_engine" in system_content:
            return httpx.Response(200, json={"message": {"content": '{"consult_engine": true}'}}, request=request)
        return httpx.Response(200, json={"message": {"content": '{"move": "e4"}'}}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    records: list[c3_moves.PlyRecord] = []
    fen = chess.Board().fen()
    for _ in range(20):
        c3_moves.chess_move(fen, records, max_consultation_rate=0.2)

    assert len(records) == 20
    consulted = sum(1 for r in records if r.consulted)
    assert consulted / len(records) <= 0.2


def test_write_ground_truth_produces_readable_json(tmp_path):
    from llmpvp_adversarial.profiles import c3_moves

    records = [
        c3_moves.PlyRecord(ply=1, consulted=False, eval_cp=15, move="e4"),
        c3_moves.PlyRecord(ply=2, consulted=True, eval_cp=-320, move="Qh4"),
    ]
    path = c3_moves.write_ground_truth("game123", records, path=str(tmp_path))

    with open(path) as f:
        data = json.load(f)
    assert data["game_id"] == "game123"
    assert len(data["plies"]) == 2
    assert data["plies"][1]["consulted"] is True


def test_chess_move_recovers_when_model_keeps_requesting_consult_engine_past_quota(monkeypatch):
    """Regression: a model that already ignored 'use sparingly' once has
    every reason to keep asking for consult_engine even after the system
    prompt stops offering it, and without an explicit corrective message,
    it fell into the generic 'invalid move' reprompt (never explains WHY)
    and burned all _MAX_ATTEMPTS, killing the game with HonestMoveError."""
    from llmpvp_adversarial.profiles import c3_moves

    call_count = {"n": 0}

    def fake_post(self, url, json=None, **kwargs):
        call_count["n"] += 1
        request = httpx.Request("POST", url)
        if call_count["n"] < 4:
            return httpx.Response(200, json={"message": {"content": '{"consult_engine": true}'}}, request=request)
        return httpx.Response(200, json={"message": {"content": '{"move": "e4"}'}}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    records = [c3_moves.PlyRecord(ply=1, consulted=True, eval_cp=0, move="e4")]
    fen = chess.Board().fen()
    move = c3_moves.chess_move(fen, records, max_consultation_rate=0.2)

    assert move == "e4"
    assert len(records) == 2
    assert records[1].consulted is False
    assert call_count["n"] == 4
