import threading
import time
import re
import shutil

import httpx
import pytest
import uvicorn

pytestmark = pytest.mark.skipif(shutil.which("stockfish") is None, reason="requires stockfish on PATH")


@pytest.fixture(scope="module")
def live_server():
    from llmpvp_adversarial.mock_server.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8766, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    yield "http://127.0.0.1:8766"
    server.should_exit = True
    thread.join(timeout=5)


def test_careless_vs_careful_game_reaches_a_conclusion(live_server, monkeypatch):
    from llmpvp_adversarial.client import SimClient
    from llmpvp_adversarial.runners.run_games import play_game

    client = SimClient(api_url=live_server)
    a = client.register("RunnerCareless")
    b = client.register("RunnerCareful")

    final_state = play_game(client, a, b, "careless", "careful")
    assert final_state["status"] == "finished"


def test_c3_game_writes_ground_truth_sidecar(live_server, monkeypatch, tmp_path):
    from llmpvp_adversarial.client import SimClient
    from llmpvp_adversarial.runners import run_games

    # NOTE: patching httpx.Client.post globally (as the brief's Step 1 test
    # literally does) also intercepts SimClient's own calls to the live mock
    # server (register/challenge/move), not just the Ollama-bound calls this
    # fixture is meant to fake -- breaking `client.register()` before
    # `play_game` is ever reached, regardless of `run_games.py`'s
    # correctness. Scope the fake to the Ollama chat endpoint only and let
    # everything else hit the real live_server, which is what the test
    # actually intends to exercise. Also, a hardcoded "e4" reply (as the
    # brief's Step 1 test literally has it) is only legal on White's very
    # first move -- every subsequent C3 turn would get an illegal-move
    # reprompt loop and exhaust _MAX_ATTEMPTS. Parse the actual legal-move
    # list out of the prompt instead and always answer with one of them, so
    # the game can run to a real conclusion.
    real_post = httpx.Client.post

    def fake_post(self, url, json=None, **kwargs):
        if url == "/api/chat":
            prompt = json["messages"][1]["content"]
            legal_moves = re.search(r"Legal moves: ([^\n]+)", prompt).group(1).split(", ")
            request = httpx.Request("POST", url)
            return httpx.Response(
                200, json={"message": {"content": f'{{"move": "{legal_moves[0]}"}}'}}, request=request
            )
        return real_post(self, url, json=json, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(run_games, "GROUND_TRUTH_DIR", str(tmp_path))
    client = SimClient(api_url=live_server)
    a = client.register("RunnerC3")
    b = client.register("RunnerCarelessOpp")

    final_state = run_games.play_game(client, a, b, "c3", "careless")
    assert final_state["status"] == "finished"

    sidecar_files = list(tmp_path.glob("*.json"))
    assert len(sidecar_files) == 1
