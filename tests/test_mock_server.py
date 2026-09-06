from fastapi.testclient import TestClient

from llmpvp_adversarial.mock_server.main import app

client = TestClient(app)


def register(name: str) -> dict:
    resp = client.post("/api/v1/agents/register", json={"name": name})
    assert resp.status_code == 200
    return resp.json()["agent"]


def test_register_returns_active_agent_immediately():
    agent = register("MockAgentA")
    assert agent["status"] == "active"  # mock auto-activates, no claim flow
    assert "api_key" in agent


def test_challenge_creates_active_chess_game():
    a = register("ChallengerA")
    b = register("ChallengerB")
    resp = client.post(
        "/api/v1/games/challenge",
        json={"opponent_name": "ChallengerB", "game_type": "chess"},
        headers={"Authorization": f"Bearer {a['api_key']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"
    assert body["game_type"] == "chess"
    assert body["current_turn"] == "white"


def test_full_chess_game_can_be_played_to_completion():
    a = register("PlayerFoolsA")
    b = register("PlayerFoolsB")
    game = client.post(
        "/api/v1/games/challenge",
        json={"opponent_name": "PlayerFoolsB", "game_type": "chess"},
        headers={"Authorization": f"Bearer {a['api_key']}"},
    ).json()
    white_key = a["api_key"] if game["white"] == a["id"] else b["api_key"]
    black_key = b["api_key"] if white_key == a["api_key"] else a["api_key"]

    moves = ["f3", "e5", "g4"]
    for i, move in enumerate(moves):
        key = white_key if i % 2 == 0 else black_key
        resp = client.post(
            f"/api/v1/games/{game['id']}/move",
            json={"move": move},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 200

    resp = client.post(
        f"/api/v1/games/{game['id']}/move",
        json={"move": "Qh4"},
        headers={"Authorization": f"Bearer {black_key}"},
    )
    assert resp.status_code == 200
    assert resp.json()["game_status"] == "finished"


def test_illegal_move_is_rejected():
    a = register("IllegalA")
    b = register("IllegalB")
    game = client.post(
        "/api/v1/games/challenge",
        json={"opponent_name": "IllegalB", "game_type": "chess"},
        headers={"Authorization": f"Bearer {a['api_key']}"},
    ).json()
    white_key = a["api_key"] if game["white"] == a["id"] else b["api_key"]
    resp = client.post(
        f"/api/v1/games/{game['id']}/move",
        json={"move": "e5"},  # illegal as white's first move
        headers={"Authorization": f"Bearer {white_key}"},
    )
    assert resp.status_code == 400


def test_resign_finishes_the_game():
    a = register("ResignA")
    b = register("ResignB")
    game = client.post(
        "/api/v1/games/challenge",
        json={"opponent_name": "ResignB", "game_type": "chess"},
        headers={"Authorization": f"Bearer {a['api_key']}"},
    ).json()
    resp = client.post(
        f"/api/v1/games/{game['id']}/resign",
        headers={"Authorization": f"Bearer {a['api_key']}"},
    )
    assert resp.status_code == 200
    state = client.get(
        f"/api/v1/games/{game['id']}",
        headers={"Authorization": f"Bearer {a['api_key']}"},
    ).json()
    assert state["status"] == "finished"
    # a resigned; the winner is whichever color a was NOT assigned. Read
    # white/black from the challenge response instead of hardcoding a color,
    # since the mock randomizes white/black like the real backend does.
    a_color = "white" if game["white"] == a["id"] else "black"
    expected_winner = "black" if a_color == "white" else "white"
    assert state["result"] == expected_winner
