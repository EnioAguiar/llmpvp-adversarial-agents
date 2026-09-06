"""Minimal in-memory LLMPvP-shaped API -- real chess rules (ported
arbiter), zero rating/anti-cheat/webhook/persistence. Not the real
LLMPvP: exists only so llmpvp-adversarial-agents profiles have a public,
runnable target with no dependency on the private backend.

Chess only: `game_type` is hardcoded to "chess" and any other value
(e.g. "go") is rejected with a 400. Go support (wiring in
`go_arbiter.py`, guarded by `PYSPIEL_AVAILABLE`) is intentionally out of
scope here -- see the mock server README section for details."""
import random
import uuid
from datetime import datetime, timezone

import chess
from fastapi import FastAPI, Header, HTTPException

from llmpvp_adversarial.chess_arbiter import IllegalMoveError, apply_move, game_outcome
from llmpvp_adversarial.clock import remaining_ms

app = FastAPI(title="llmpvp-adversarial-agents mock server")

_agents: dict[str, dict] = {}  # api_key -> {id, name, status}
_agents_by_name: dict[str, str] = {}  # name -> api_key
_games: dict[str, dict] = {}

STARTING_CLOCK_MS = 600_000


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _require_agent(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    api_key = authorization.removeprefix("Bearer ")
    agent = _agents.get(api_key)
    if agent is None:
        raise HTTPException(status_code=401, detail="Unknown API key")
    return agent


@app.post("/api/v1/agents/register")
def register(payload: dict) -> dict:
    name = payload["name"]
    if name in _agents_by_name:
        raise HTTPException(status_code=409, detail=f"Agent name '{name}' already taken")
    api_key = uuid.uuid4().hex
    agent_id = uuid.uuid4().hex
    agent = {"id": agent_id, "name": name, "status": "active", "api_key": api_key}
    _agents[api_key] = agent
    _agents_by_name[name] = api_key
    return {"agent": agent}


@app.post("/api/v1/games/challenge")
def challenge(payload: dict, authorization: str | None = Header(default=None)) -> dict:
    challenger = _require_agent(authorization)
    opponent_key = _agents_by_name.get(payload["opponent_name"])
    if opponent_key is None:
        raise HTTPException(status_code=404, detail="Opponent not found")
    opponent = _agents[opponent_key]

    if payload.get("game_type", "chess") != "chess":
        raise HTTPException(status_code=400, detail="Mock server only supports chess without the 'go' extra wired in yet")

    challenger_is_white = random.choice([True, False])
    white, black = (challenger, opponent) if challenger_is_white else (opponent, challenger)

    game_id = uuid.uuid4().hex
    game = {
        "id": game_id,
        "game_type": "chess",
        "white": white["id"],
        "black": black["id"],
        "status": "active",
        "result": None,
        "fen": chess.Board().fen(),
        "current_turn": "white",
        "white_time_ms": STARTING_CLOCK_MS,
        "black_time_ms": STARTING_CLOCK_MS,
        "turn_started_at": _now(),
        "moves": [],
    }
    _games[game_id] = game
    return _public_game_view(game)


def _public_game_view(game: dict) -> dict:
    view = {k: v for k, v in game.items() if k != "turn_started_at"}
    return view


@app.get("/api/v1/games/{game_id}")
def get_game(game_id: str, authorization: str | None = Header(default=None)) -> dict:
    _require_agent(authorization)
    game = _games.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return _public_game_view(game)


@app.post("/api/v1/games/{game_id}/move")
def move(game_id: str, payload: dict, authorization: str | None = Header(default=None)) -> dict:
    agent = _require_agent(authorization)
    game = _games.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if game["status"] != "active":
        raise HTTPException(status_code=400, detail="Game is already finished")

    color = "white" if agent["id"] == game["white"] else "black" if agent["id"] == game["black"] else None
    if color is None or game["current_turn"] != color:
        raise HTTPException(status_code=400, detail="Not your turn")

    now = _now()
    stored_ms = game["white_time_ms"] if color == "white" else game["black_time_ms"]
    time_left = remaining_ms(stored_ms, game["turn_started_at"], now)

    try:
        result = apply_move(game["fen"], payload["move"])
    except IllegalMoveError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    game["fen"] = result.fen_after
    game["moves"].append({"color": color, "san": result.san, "uci": result.uci})
    if color == "white":
        game["white_time_ms"] = time_left
    else:
        game["black_time_ms"] = time_left
    game["current_turn"] = "black" if color == "white" else "white"
    game["turn_started_at"] = now

    uci_moves = [m["uci"] for m in game["moves"]]
    outcome = game_outcome(uci_moves)
    if outcome is not None:
        game["status"] = "finished"
        game["result"] = outcome.result

    return {
        "success": True,
        "move": result.san,
        "game_status": game["status"],
        "your_time_remaining_ms": time_left,
    }


@app.post("/api/v1/games/{game_id}/resign")
def resign(game_id: str, authorization: str | None = Header(default=None)) -> dict:
    agent = _require_agent(authorization)
    game = _games.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    color = "white" if agent["id"] == game["white"] else "black"
    game["status"] = "finished"
    game["result"] = "black" if color == "white" else "white"
    return _public_game_view(game)
