import time
import os
import jwt
import httpx

APP_ID = os.environ["GITHUB_APP_ID"]
PRIVATE_KEY_PATH = os.environ["GITHUB_PRIVATE_KEY_PATH"]

def _generate_app_jwt() -> str:
    """Proves to GitHub 'I am this App' - valid for 10 minutes max."""
    with open(PRIVATE_KEY_PATH, "r") as f:
        private_key = f.read()

    now = int(time.time())
    payload = {
        "iat": now - 60,        # issued-at, 60s in the past to allow for clock drift
        "exp": now + (9 * 60),  # expires in 9 minutes
        "iss": APP_ID,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    """Exchanges the App's JWT for a short-lived token scoped to one
    specific repo installation - this is the token we actually use
    to call the GitHub API on that repo's behalf."""
    app_jwt = _generate_app_jwt()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        return resp.json()["token"]