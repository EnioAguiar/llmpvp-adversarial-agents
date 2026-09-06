import pytest

from llmpvp_adversarial.safety_gate import assert_not_production


def test_localhost_is_allowed():
    assert_not_production("http://127.0.0.1:8765")  # must not raise


def test_arbitrary_local_port_is_allowed():
    assert_not_production("http://localhost:9000")  # must not raise


def test_production_domain_blocked_unconditionally():
    with pytest.raises(SystemExit, match="api.llmpvp.com"):
        assert_not_production("https://api.llmpvp.com")


def test_production_domain_blocked_even_with_https_and_path():
    with pytest.raises(SystemExit):
        assert_not_production("https://api.llmpvp.com/api/v1")


def test_www_alias_also_blocked():
    with pytest.raises(SystemExit):
        assert_not_production("https://www.llmpvp.com")
