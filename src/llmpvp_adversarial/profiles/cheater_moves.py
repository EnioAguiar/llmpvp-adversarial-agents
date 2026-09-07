"""C1 ('careless') and C2 ('careful') cheater profiles -- pure engine,
zero AI reasoning. C1 is the target the original anti-cheat design
always meant to catch (engine wired in without bothering to disguise
it); C2 is the boundary the system was never meant to guarantee
catching (disguise via delay + mixed move quality, not proof)."""
import random

from llmpvp_adversarial.engines import stockfish_best_move, stockfish_weighted_move

_PROFILES = ("careless", "careful")


def _validate_profile(profile: str) -> None:
    if profile not in _PROFILES:
        raise ValueError(f"invalid profile: {profile!r} -- must be 'careless' or 'careful'")


def artificial_delay_seconds(profile: str) -> float:
    _validate_profile(profile)
    if profile == "careless":
        return 0.0
    return random.uniform(1.5, 4.0)


def chess_move(fen: str, profile: str) -> str:
    _validate_profile(profile)
    if profile == "careless":
        return stockfish_best_move(fen, time_seconds=0.3)
    return stockfish_weighted_move(fen, time_seconds=0.3, multipv=4, weights=[0.55, 0.25, 0.13, 0.07])
