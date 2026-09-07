"""Honest baseline: a small local LLM (Ollama) genuinely chooses the
move from a closed list of legal options -- never random.choice, never
a fixed heuristic. This is the control the cheater profiles are
compared against, and the base c3_moves.py extends with an optional
engine-consultation branch."""
import json
import os

import chess
import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
_MAX_ATTEMPTS = 5

_CHESS_SYSTEM = (
    "You are playing chess. You will be given a FEN position and a list "
    "of legal moves in SAN notation. Choose exactly one move from the "
    "list using your own judgement about which move is best. Respond "
    'with JSON only: {"move": "<one of the legal moves, exactly as given>"}.'
)


class HonestMoveError(RuntimeError):
    """The local model failed to choose a legal move after several
    attempts -- must never silently fall back to a random/heuristic
    move, that would corrupt the honest baseline this profile exists to
    provide."""


def _ollama_chat(system: str, prompt: str) -> dict:
    resp = httpx.Client(base_url=OLLAMA_URL, timeout=60.0).post(
        "/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        },
    )
    resp.raise_for_status()
    return json.loads(resp.json()["message"]["content"])


def legal_chess_moves_san(fen: str) -> list[str]:
    board = chess.Board(fen)
    return [board.san(m) for m in board.legal_moves]


def chess_move(fen: str, legal_moves: list[str] | None = None) -> str:
    moves = legal_moves if legal_moves is not None else legal_chess_moves_san(fen)
    if len(moves) == 1:
        return moves[0]

    prompt = f"FEN: {fen}\nLegal moves: {', '.join(moves)}"
    for _attempt in range(_MAX_ATTEMPTS):
        try:
            response = _ollama_chat(_CHESS_SYSTEM, prompt)
            candidate = response.get("move")
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            continue
        if candidate in moves:
            return candidate
        prompt = (
            f"FEN: {fen}\nLegal moves: {', '.join(moves)}\n"
            f"Your previous answer '{candidate}' was not one of the legal "
            "moves listed. Choose exactly one from the list."
        )
    raise HonestMoveError(
        f"model failed to choose a legal move from {moves} after {_MAX_ATTEMPTS} attempts"
    )
