from datetime import datetime


def remaining_ms(stored_ms: int, turn_started_at: datetime, now: datetime) -> int:
    elapsed_ms = (now - turn_started_at).total_seconds() * 1000
    return max(0, int(stored_ms - elapsed_ms))


def think_time_ms(turn_started_at: datetime, now: datetime) -> int:
    """Response time for the move, in ms -- never negative. A negative
    value (desynced clocks between processes, a race, etc.) must never
    silently poison a downstream calculation."""
    elapsed_ms = (now - turn_started_at).total_seconds() * 1000
    return max(0, int(elapsed_ms))


def apply_increment(time_left_ms: int, increment_ms: int) -> int:
    """Time bonus returned after an accepted legal move -- increment_ms=0
    (no-increment time controls) is a pure no-op."""
    return time_left_ms + increment_ms
