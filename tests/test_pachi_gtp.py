"""GTP framing tests for the Pachi wrapper -- no pachi binary needed: the
subprocess is faked, so only `_pachi_send`'s own protocol handling is under
test."""
import pytest

from llmpvp_adversarial.engines import _pachi_send


class FakeStdin:
    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data)

    def flush(self):
        pass


class FakeStdout:
    def __init__(self, lines):
        self._lines = list(lines)

    def readline(self):
        return self._lines.pop(0) if self._lines else ""


class FakeProc:
    def __init__(self, response_lines):
        self.stdin = FakeStdin()
        self.stdout = FakeStdout(response_lines)

    def poll(self):
        return None


def test_gtp_error_response_raises():
    proc = FakeProc(["? illegal move\n", "\n"])
    with pytest.raises(RuntimeError, match="GTP error"):
        _pachi_send(proc, "play B z99")


def test_gtp_success_response_returns_lines():
    proc = FakeProc(["= d4\n", "\n"])
    assert _pachi_send(proc, "genmove B") == ["= d4"]
    assert proc.stdin.written == ["genmove B\n"]


def test_stdout_eof_raises():
    proc = FakeProc([])
    with pytest.raises(RuntimeError, match="exited unexpectedly"):
        _pachi_send(proc, "genmove B")
