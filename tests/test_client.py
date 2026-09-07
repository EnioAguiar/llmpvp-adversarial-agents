import threading
import time

import pytest
import uvicorn

from llmpvp_adversarial.client import SimClient
from llmpvp_adversarial.mock_server.main import app


@pytest.fixture(scope="module")
def live_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    yield "http://127.0.0.1:8765"
    server.should_exit = True
    thread.join(timeout=5)


def test_register_returns_agent_dict(live_server):
    client = SimClient(api_url=live_server)
    agent = client.register("ClientTestAgent1")
    assert agent["name"] == "ClientTestAgent1"
    assert "api_key" in agent
    assert "id" in agent


def test_challenge_and_submit_move_full_roundtrip(live_server):
    client = SimClient(api_url=live_server)
    a = client.register("ClientTestAgentA")
    b = client.register("ClientTestAgentB")
    game = client.challenge(a["api_key"], "ClientTestAgentB")
    white_key = a["api_key"] if game["white"] == a["id"] else b["api_key"]
    result = client.submit_move(white_key, game["id"], "e4")
    assert result["success"] is True


def test_production_url_is_rejected_at_construction():
    with pytest.raises(SystemExit):
        SimClient(api_url="https://api.llmpvp.com")
