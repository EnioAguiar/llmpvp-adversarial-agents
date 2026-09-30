# llmpvp-adversarial-agents

Cheater-profile move generators (C1/C2/C3) and a minimal mock server for
[LLMPvP](https://llmpvp.com), a bring-your-own-LLM ranked chess/Go arena.

## What this is for

LLMPvP's anti-cheat research needs realistic adversarial agent behavior to
calibrate against. This repo is the public, contributable half of that research:
algorithms and simulators live here; calibration thresholds, real game data, and
LLMPvP's production detection code do not, and never will (see "What stays private"
below).

## What's here

Paths below are relative to `src/llmpvp_adversarial/`.

- **`profiles/cheater_moves.py`** — C1 ("careless": pure engine, no disguise) and C2
  ("careful": engine + artificial delay + mixed move quality) — the original targets
  LLMPvP's anti-cheat signals were designed against.
- **`profiles/c3_moves.py`** — C3: a genuinely-reasoning small local model (via
  [Ollama](https://ollama.com)) that may choose, on its own judgement, to request a
  one-off engine suggestion for specific moves — a more realistic, harder-to-catch
  adversary than C1/C2. The consultation rate is additionally capped in code (default:
  a trailing bound of 20% of that agent's own plies; once the cap would be exceeded the
  option is simply dropped from the prompt), because asking a small model to consult
  "sparingly" did not hold in practice. Records per-ply ground truth (`consulted:
  true/false` + the position's engine evaluation in centipawns) so measuring detection
  recall against it is possible.
- **`profiles/ollama_moves.py`** — the honest baseline C1/2/3 are compared against:
  same small local model, always reasoning for itself, never consulting an engine.
- **`mock_server/`** — a minimal FastAPI server implementing just enough of LLMPvP's
  public API (`docs.llmpvp.com`) to play a full chess game: register, challenge, read
  game state, move, resign. **Not the real LLMPvP** — no rating, no anti-cheat, no
  persistence at all (state lives in process memory), registration hands back an
  immediately usable agent instead of the real `pending_claim` + claim flow, and the
  clock is tracked but never enforced, so a slow local model never loses on time
  mid-experiment. Chess only: any `game_type` other than `"chess"` is rejected with a
  400, wiring Go in through `go_arbiter.py` is not done.
  Exists so you can test a new profile end-to-end without needing access to LLMPvP's
  private backend.
- **`engines.py`** — standalone Stockfish (chess, via `python-chess`'s UCI wrapper)
  and Pachi (Go, via GTP subprocess) callers, config'd through env vars, no
  dependency on any private LLMPvP module.
- **`chess_arbiter.py` / `go_arbiter.py` / `clock.py`** — the game rules and clock
  arithmetic the mock server runs on, ported from LLMPvP's backend so a profile is
  exercised against the same rules the real arena applies. `chess_arbiter.py` is
  verbatim, `clock.py` differs only in its docstrings, and `go_arbiter.py` adds an
  optional-import guard (`PYSPIEL_AVAILABLE`, so a chess-only install imports fine)
  plus reworked `legal_moves`/`board_grid` implementations.
- **`client.py`** (`SimClient`, a thin HTTP wrapper over that wire format) and
  **`runners/run_games.py`** (`play_game`, which plays one game to completion for any
  pair of the profiles `honest`/`careless`/`careful`/`c3` and writes C3's ground truth
  to `sim_ground_truth/<game_id>.json`).

## What stays private

Calibrated thresholds, real game/agent data, and LLMPvP's production anti-cheat
detection code (which signals are computed, at what numeric cutoffs) are
intentionally never published here. Publishing that would hand a careful cheater the
exact recipe to evade detection. What's public here — "how to generate adversarial
move behavior" — doesn't teach anything LLMPvP's already-public API docs don't
already make possible in a few dozen lines; publishing reference implementations
just lowers the bar for building MORE realistic ones for research, which is the
whole point.

## A note on `safety_gate.py`

`safety_gate.assert_not_production` is a **developer convenience**, not a security
boundary — anyone can delete the check and point this at the real LLMPvP API. Please
don't: doing so creates fake cheating agents that pollute the real leaderboard and
violates LLMPvP's Terms of Use. The actual defense against that (independent of
whether this repo exists) is server-side: LLMPvP's agent-claim flow, registration
rate limiting, and its existing engine-correlation anti-cheat signal (run on demand
against an agent already flagged by an independent path), which already specifically
targets undisguised engine-driven play.

## Installing

```bash
pip install -e .           # chess only
pip install -e ".[go]"     # + Go support (requires open_spiel, a heavy C++ dependency)
pip install -e ".[dev]"    # + pytest
```

Chess-only install has zero heavy native dependencies. Go support is opt-in because
`open_spiel` lacks prebuilt wheels for several platforms.

`profiles/cheater_moves.py` and `profiles/c3_moves.py` additionally need a
`stockfish` binary on `PATH` (or set `STOCKFISH_PATH`). `profiles/c3_moves.py` and
`profiles/ollama_moves.py` need a running [Ollama](https://ollama.com) daemon
(`ollama run llama3.2`, or set `OLLAMA_MODEL`/`OLLAMA_URL`).

## Running a game against the mock server

```bash
# Terminal 1
.venv/bin/uvicorn llmpvp_adversarial.mock_server.main:app --port 8765

# Terminal 2
python -c "
from llmpvp_adversarial.client import SimClient
from llmpvp_adversarial.runners.run_games import play_game

client = SimClient()
a = client.register('MyNewProfileTest')
b = client.register('Opponent')
result = play_game(client, a, b, 'c3', 'careless')
print(result)
"
```

## Contributing a new profile

Add `profiles/c4_moves.py` (or whatever), following the same shape as `c3_moves.py`:
a `chess_move(fen, ...) -> str` function, a branch for it in
`runners/run_games.py::_move_for`, tests under `tests/profiles/`, and — if your
profile mixes honest and adversarial moves within one game like C3 does — per-ply
ground truth so detection recall against it is actually measurable. PRs welcome.

## License

MIT — see `LICENSE`.
