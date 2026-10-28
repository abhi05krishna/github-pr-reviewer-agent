import asyncio
import time
from datetime import datetime, timezone

from app.core import github_client


def test_cached_token_is_reused_without_network():
    github_client._token_cache[999] = ("cached-token", time.time() + 3600)
    assert asyncio.run(github_client.get_installation_token(999)) == "cached-token"


def test_expiry_is_parsed():
    expected = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc).timestamp()
    assert github_client._parse_expiry("2026-10-21T10:00:00Z") == expected