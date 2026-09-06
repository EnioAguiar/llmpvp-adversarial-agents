"""Standalone Stockfish (chess) and Pachi (Go) wrappers -- no coupling to
any private LLMPvP backend module. Config is env vars with sane
defaults, never a shared app.config import (there is no shared app in
this repo)."""
import os
import random
import shutil
import subprocess

import chess
import chess.engine

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")
PACHI_PATH = os.environ.get("PACHI_PATH", "pachi")
PACHI_THREADS = int(os.environ.get("PACHI_THREADS", "2"))
PACHI_MAX_TREE_SIZE_MB = int(os.environ.get("PACHI_MAX_TREE_SIZE_MB", "400"))


def stockfish_best_move(fen: str, time_seconds: float = 0.3) -> str:
    board = chess.Board(fen)
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        result = engine.play(board, chess.engine.Limit(time=time_seconds))
    return board.san(result.move)


def stockfish_weighted_move(
    fen: str, time_seconds: float, multipv: int, weights: list[float]
) -> str:
    board = chess.Board(fen)
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        info = engine.analyse(board, chess.engine.Limit(time=time_seconds), multipv=multipv)
    candidates = [entry["pv"][0] for entry in info if entry.get("pv")]
    if not candidates:
        return board.san(random.choice(list(board.legal_moves)))
    move = random.choices(candidates, weights=weights[: len(candidates)], k=1)[0]
    return board.san(move)


def stockfish_eval_cp(fen: str, time_seconds: float = 0.1) -> int:
    """Centipawn evaluation from the side-to-move's perspective. Used by
    the C3 profile to decide (via the prompt) whether the position looks
    bad enough to consider consulting the engine."""
    board = chess.Board(fen)
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        info = engine.analyse(board, chess.engine.Limit(time=time_seconds))
    score = info["score"].pov(board.turn)
    return score.score(mate_score=10_000)


def _pachi_gtp_coord(coord: str) -> str:
    return "pass" if coord == "pass" else coord.upper()


def _pachi_from_gtp_coord(coord: str) -> str:
    normalized = coord.strip().lower()
    if normalized in ("", "pass", "resign"):
        return "pass"
    return normalized


def _pachi_gtp_color(color: str) -> str:
    return "B" if color == "black" else "W"


def _pachi_send(proc: subprocess.Popen, command: str) -> list[str]:
    proc.stdin.write(command + "\n")
    proc.stdin.flush()
    lines = []
    while True:
        line = proc.stdout.readline()
        if line == "":
            # EOF: the pachi process exited before completing its response.
            returncode = proc.poll()
            raise RuntimeError(
                f"pachi process exited unexpectedly (returncode={returncode}) "
                f"while responding to {command!r}"
            )
        if line.strip() == "":
            if lines:
                break
            continue
        lines.append(line.strip())
    return lines


def pachi_best_move(
    board_size: int, komi: float, moves: list[tuple[str, str]], color_to_move: str, sims: int
) -> str:
    """moves: [(color, coord), ...] in order, color = 'black'/'white',
    coord = lowercase e.g. 'd4'/'pass'. Returns the same format."""
    resolved_path = shutil.which(PACHI_PATH)
    if resolved_path is None:
        raise RuntimeError(
            f"pachi binary not found on PATH (looked for '{PACHI_PATH}'). "
            "Install Pachi and set PACHI_PATH if it's not named 'pachi'."
        )
    args = [
        PACHI_PATH,
        "--nodcnn",
        "-t",
        f"={sims}",
        f"threads={PACHI_THREADS},max_tree_size={PACHI_MAX_TREE_SIZE_MB},resign_threshold=0",
    ]
    proc = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        bufsize=1, text=True,
        # Pachi loads data files (joseki/pattern dictionaries) relative to
        # its own working directory; run it from its install dir so it
        # finds them regardless of the caller's cwd.
        cwd=os.path.dirname(os.path.abspath(resolved_path)),
    )
    try:
        _pachi_send(proc, f"boardsize {board_size}")
        _pachi_send(proc, f"komi {komi}")
        _pachi_send(proc, "clear_board")
        for color, coord in moves:
            _pachi_send(proc, f"play {_pachi_gtp_color(color)} {_pachi_gtp_coord(coord)}")
        response = _pachi_send(proc, f"genmove {_pachi_gtp_color(color_to_move)}")
        gtp_coord = response[0].partition(" ")[2].strip()
        return _pachi_from_gtp_coord(gtp_coord)
    finally:
        try:
            _pachi_send(proc, "quit")
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
            proc.wait(timeout=3)
        for stream in (proc.stdin, proc.stdout):
            try:
                stream.close()
            except Exception:
                pass
