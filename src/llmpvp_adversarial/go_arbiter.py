from dataclasses import dataclass

try:
    import pyspiel
    PYSPIEL_AVAILABLE = True
except ImportError:
    PYSPIEL_AVAILABLE = False

DEFAULT_KOMI = 7.5


class IllegalGoMoveError(Exception):
    pass


@dataclass
class GoMoveResult:
    board_state: str
    move: str  # normalized lowercase coordinate, e.g. "d4" or "pass"
    is_pass: bool


@dataclass
class GoOutcome:
    result: str  # "black" | "white" | "draw"
    reason: str


def _require_pyspiel() -> None:
    if not PYSPIEL_AVAILABLE:
        raise RuntimeError(
            "Go support requires the 'go' extra: pip install -e '.[go]' "
            "(open_spiel is not installed)"
        )


def _load_game(board_size: int, komi: float):
    _require_pyspiel()
    return pyspiel.load_game("go", {"board_size": board_size, "komi": komi})


def new_board_state(board_size: int, komi: float) -> str:
    game = _load_game(board_size, komi)
    return game.new_initial_state().serialize()


def _reconstruct(board_size: int, komi: float, board_state: str):
    game = _load_game(board_size, komi)
    state = game.deserialize_state(board_state)
    return game, state


def apply_move(board_size: int, komi: float, board_state: str, move_str: str) -> GoMoveResult:
    _, state = _reconstruct(board_size, komi, board_state)

    coord = move_str.strip().lower()
    token = "PASS" if coord == "pass" else coord
    color = "B" if state.current_player() == 0 else "W"

    try:
        action = state.string_to_action(f"{color} {token}")
    except pyspiel.SpielError:
        raise IllegalGoMoveError(f"'{move_str}' is not a legal move in this position")

    state.apply_action(action)
    return GoMoveResult(
        board_state=state.serialize(),
        move=token.lower() if token != "PASS" else "pass",
        is_pass=(token == "PASS"),
    )


def game_outcome(board_size: int, komi: float, board_state: str) -> GoOutcome | None:
    _, state = _reconstruct(board_size, komi, board_state)
    if not state.is_terminal():
        return None
    returns = state.returns()
    if returns[0] > returns[1]:
        result = "black"
    elif returns[1] > returns[0]:
        result = "white"
    else:
        result = "draw"
    return GoOutcome(result=result, reason="scoring")


def legal_moves(board_size: int, komi: float, board_state: str) -> list[str]:
    _, state = _reconstruct(board_size, komi, board_state)
    moves = [state.action_to_string(state.current_player(), a) for a in state.legal_actions()]
    return [m.split(" ")[-1].lower() for m in moves]


def board_ascii(board_size: int, komi: float, board_state: str) -> str:
    _, state = _reconstruct(board_size, komi, board_state)
    return str(state)


STONE_CHARS = {"X": "b", "O": "w", "+": "."}


def board_grid(board_size: int, komi: float, board_state: str) -> str:
    """Human-readable grid derived from the opaque OpenSpiel board_state.
    One row per rank, from `board_size` (top) to 1 (bottom) -- same visual
    order as `str(state)`. Each char: '.' empty, 'b' black, 'w' white."""
    ascii_board = board_ascii(board_size, komi, board_state)
    rows = []
    for line in ascii_board.splitlines():
        stripped = line.strip()
        if not stripped or not stripped[0].isdigit():
            continue
        cells = stripped.split(" ", 1)[1] if " " in stripped else ""
        row = "".join(STONE_CHARS.get(c, ".") for c in cells if c in STONE_CHARS)
        if row:
            rows.append(row)
    return "\n".join(rows)


def current_turn_color(board_size: int, komi: float, board_state: str) -> str:
    _, state = _reconstruct(board_size, komi, board_state)
    return "black" if state.current_player() == 0 else "white"
