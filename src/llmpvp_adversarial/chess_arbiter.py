from dataclasses import dataclass

import chess


class IllegalMoveError(Exception):
    pass


@dataclass
class MoveResult:
    fen_after: str
    san: str
    uci: str
    is_check: bool


@dataclass
class Outcome:
    result: str  # "white" | "black" | "draw"
    reason: str


def apply_move(fen: str, move_str: str) -> MoveResult:
    board = chess.Board(fen)
    move: chess.Move | None = None
    try:
        move = board.parse_san(move_str)
    except ValueError:
        try:
            candidate = chess.Move.from_uci(move_str)
        except ValueError:
            raise IllegalMoveError(f"'{move_str}' is not a legal move in this position")
        if candidate not in board.legal_moves:
            raise IllegalMoveError(f"'{move_str}' is not a legal move in this position")
        move = candidate

    san = board.san(move)
    uci = move.uci()
    board.push(move)
    return MoveResult(fen_after=board.fen(), san=san, uci=uci, is_check=board.is_check())


def game_outcome(uci_moves: list[str]) -> Outcome | None:
    board = chess.Board()
    for uci in uci_moves:
        board.push_uci(uci)
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None
    if outcome.winner is True:
        result = "white"
    elif outcome.winner is False:
        result = "black"
    else:
        result = "draw"
    return Outcome(result=result, reason=outcome.termination.name.lower())
