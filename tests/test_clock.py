from datetime import datetime, timedelta

from llmpvp_adversarial.clock import apply_increment, remaining_ms, think_time_ms


def test_no_time_elapsed_keeps_full_time():
    now = datetime(2026, 1, 1)
    assert remaining_ms(600_000, now, now) == 600_000


def test_remaining_ms_subtracts_elapsed():
    start = datetime(2026, 1, 1)
    now = start + timedelta(seconds=10)
    assert remaining_ms(600_000, start, now) == 590_000


def test_remaining_ms_never_negative():
    start = datetime(2026, 1, 1)
    now = start + timedelta(seconds=700)
    assert remaining_ms(600_000, start, now) == 0


def test_think_time_ms_normal_elapsed():
    start = datetime(2026, 1, 1)
    now = start + timedelta(milliseconds=309)
    assert think_time_ms(start, now) == 309


def test_think_time_ms_clamps_negative_elapsed_to_zero():
    start = datetime(2026, 1, 1)
    now = start - timedelta(seconds=5)
    assert think_time_ms(start, now) == 0


def test_apply_increment_adds_to_time_left():
    assert apply_increment(10_000, 2_000) == 12_000


def test_apply_increment_zero_is_noop():
    assert apply_increment(10_000, 0) == 10_000
