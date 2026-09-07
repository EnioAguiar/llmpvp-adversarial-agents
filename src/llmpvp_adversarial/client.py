"""Thin HTTP client for the LLMPvP wire format (real backend or the
mock server in this repo) -- purely mechanical, no move-choosing logic."""
import httpx

from llmpvp_adversarial.safety_gate import assert_not_production


class SimClient:
    def __init__(self, api_url: str = "http://127.0.0.1:8765"):
        assert_not_production(api_url)
        self.api_url = api_url
        self._http = httpx.Client(base_url=api_url, timeout=30.0)

    def _auth(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}"}

    def register(self, name: str) -> dict:
        resp = self._http.post("/api/v1/agents/register", json={"name": name})
        resp.raise_for_status()
        return resp.json()["agent"]

    def challenge(self, api_key: str, opponent_name: str, game_type: str = "chess") -> dict:
        resp = self._http.post(
            "/api/v1/games/challenge",
            json={"opponent_name": opponent_name, "game_type": game_type},
            headers=self._auth(api_key),
        )
        resp.raise_for_status()
        return resp.json()

    def get_game(self, api_key: str, game_id: str) -> dict:
        resp = self._http.get(f"/api/v1/games/{game_id}", headers=self._auth(api_key))
        resp.raise_for_status()
        return resp.json()

    def submit_move(self, api_key: str, game_id: str, move: str) -> dict:
        resp = self._http.post(
            f"/api/v1/games/{game_id}/move", json={"move": move}, headers=self._auth(api_key)
        )
        resp.raise_for_status()
        return resp.json()

    def resign(self, api_key: str, game_id: str) -> dict:
        resp = self._http.post(f"/api/v1/games/{game_id}/resign", headers=self._auth(api_key))
        resp.raise_for_status()
        return resp.json()
