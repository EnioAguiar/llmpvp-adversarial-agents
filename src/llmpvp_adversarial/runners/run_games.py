"""Generic game orchestration -- plays one game to completion for any
combination of profiles ('honest', 'careless', 'careful', 'c3').
Replaces the private repo's separate run_cheater_vs_cheater.py/
run_honest_games.py with one runner that also understands c3."""
import time

import httpx

from llmpvp_adversarial.client import SimClient
from llmpvp_adversarial.profiles import c3_moves, cheater_moves, ollama_moves

GROUND_TRUTH_DIR = "sim_ground_truth"

_ENGINE_PROFILES = ("careless", "careful")


def _move_for(profile: str, fen: str, ply_records: list) -> str:
    if profile == "honest":
        return ollama_moves.chess_move(fen)
    if profile in _ENGINE_PROFILES:
        delay = cheater_moves.artificial_delay_seconds(profile)
        if delay:
            time.sleep(delay)
        return cheater_moves.chess_move(fen, profile)
    if profile == "c3":
        return c3_moves.chess_move(fen, ply_records)
    raise ValueError(f"unknown profile: {profile!r}")


def play_game(client: SimClient, agent_a: dict, agent_b: dict, profile_a: str, profile_b: str) -> dict:
    game = client.challenge(agent_a["api_key"], agent_b["name"])
    game_id = game["id"]
    profile_by_id = {agent_a["id"]: profile_a, agent_b["id"]: profile_b}
    key_by_id = {agent_a["id"]: agent_a["api_key"], agent_b["id"]: agent_b["api_key"]}
    ply_records_by_id: dict[str, list] = {agent_a["id"]: [], agent_b["id"]: []}

    state = game
    while state["status"] == "active":
        mover_id = state["white"] if state["current_turn"] == "white" else state["black"]
        profile = profile_by_id[mover_id]
        api_key = key_by_id[mover_id]

        move = _move_for(profile, state["fen"], ply_records_by_id[mover_id])
        try:
            client.submit_move(api_key, game_id, move)
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"move rejected in {game_id}: {exc.response.text}") from exc

        state = client.get_game(api_key, game_id)

    for agent_id, profile in profile_by_id.items():
        if profile == "c3" and ply_records_by_id[agent_id]:
            c3_moves.write_ground_truth(game_id, ply_records_by_id[agent_id], path=GROUND_TRUTH_DIR)

    return state
