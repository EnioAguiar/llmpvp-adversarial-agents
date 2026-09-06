"""Dev-convenience guard, NOT a security boundary. Anyone can delete this
check and point api_url at production directly -- the real defense
against a fake/engine-driven agent hitting the real LLMPvP is
server-side (email-gated claim flow, registration rate limiting, and
LLMPvP's existing anti-cheat detection, which already targets
undisguised engine-driven play) and lives entirely in the private
backend, independent of whether this repo exists. This function exists
to catch an honest misconfiguration ("forgot to change API_URL"),
nothing more.
"""

_PRODUCTION_HOSTS = ("api.llmpvp.com", "www.llmpvp.com", "llmpvp.com")


def assert_not_production(api_url: str) -> None:
    lowered = api_url.lower()
    for host in _PRODUCTION_HOSTS:
        if host in lowered:
            raise SystemExit(
                f"ABORTED: api_url points at a production LLMPvP host ({api_url}). "
                "This toolkit generates engine-driven/adversarial move behavior -- "
                "running it against the real LLMPvP would create fake cheating "
                "agents that pollute the real leaderboard and violate LLMPvP's "
                "Terms of Use. Point api_url at the mock server "
                "(llmpvp_adversarial.mock_server) or your own local test backend "
                "instead."
            )
