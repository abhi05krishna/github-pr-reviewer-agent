import os
import time
from datetime import datetime
from pathlib import Path

import httpx
import jwt

BACKEND_DIR = Path(__file__).resolve().parents[2]   # .../backend

# installation_id -> (token, expiry as a unix timestamp)
_token_cache: dict[int, tuple[str, float]] = {}
REFRESH_MARGIN_SECONDS = 300   # refresh 5 minutes before expiry


def _parse_expiry(iso_text: str) -> float:
    return datetime.fromisoformat(iso_text.replace("Z", "+00:00")).timestamp()


def _generate_app_jwt() -> str:
    """Proves to GitHub 'I am this App'. Secrets are read here, when needed,
    not when the file is imported."""
    app_id = os.environ["GITHUB_APP_ID"]
    key_path = Path(os.environ["GITHUB_PRIVATE_KEY_PATH"])
    if not key_path.is_absolute():
        key_path = BACKEND_DIR / key_path
    private_key = key_path.read_text()

    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + (9 * 60), "iss": app_id}
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    """Returns a cached token while it's still fresh, otherwise fetches a new one."""
    cached = _token_cache.get(installation_id)
    if cached and cached[1] - time.time() > REFRESH_MARGIN_SECONDS:
        return cached[0]

    app_jwt = _generate_app_jwt()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        data = resp.json()

    _token_cache[installation_id] = (data["token"], _parse_expiry(data["expires_at"]))
    return data["token"]