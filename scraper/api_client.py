"""Async HTTP client with TLS fingerprint impersonation.

Uses curl_cffi to impersonate real browser TLS signatures,
bypassing Cloudflare and similar anti-bot protections.
"""

from curl_cffi import requests
import asyncio
from typing import Any


class AsyncAPIClient:
    """HTTP client with browser-like TLS fingerprint and retry logic.

    Args:
        base_url: Base URL for all requests. Endpoints are appended to this.
        custom_headers: Optional headers to override defaults.
    """

    def __init__(
        self,
        base_url: str,
        custom_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url
        self.headers: dict[str, str] = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "accept": "application/json, text/plain, */*",
            "accept-language": "ru",
            "connection": "keep-alive",
        }
        if custom_headers:
            self.headers.update(custom_headers)

        # Using impersonate="chrome" to mimic a real browser TLS fingerprint
        self.client = requests.AsyncSession(
            impersonate="chrome",
            headers=self.headers,
            timeout=15.0,
        )

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        return_text: bool = False,
        cookies: dict[str, str] | None = None,
        full_url: str | None = None,
    ) -> Any:
        """Execute a GET request with exponential backoff for rate limits.

        Args:
            endpoint: URL path appended to base_url (ignored if full_url set).
            params: Optional query parameters.
            return_text: If True, return raw text instead of parsed JSON.
            cookies: Optional cookies dict to send with request.
            full_url: If set, use this URL instead of base_url + endpoint.

        Returns:
            Parsed JSON dict, raw text string, or empty dict on failure.
        """
        retries = 3
        delay = 1.0

        for attempt in range(retries):
            try:
                if full_url:
                    url = full_url
                else:
                    url = self.base_url.rstrip("/") + "/" + endpoint.lstrip("/")

                kwargs: dict[str, Any] = {"params": params}
                if cookies:
                    kwargs["cookies"] = cookies

                response = await self.client.get(url, **kwargs)

                if response.status_code == 200:
                    if return_text:
                        return response.text
                    try:
                        return response.json()
                    except Exception:
                        print(
                            "[API_CLIENT] Valid 200, but not JSON. "
                            "Possible Cloudflare bypass failed."
                        )
                        return {}
                elif response.status_code in [429, 403]:
                    print(
                        f"[API_CLIENT] Rate limited or forbidden "
                        f"(Code {response.status_code}). "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    print(
                        f"[API_CLIENT] HTTP Error {response.status_code} "
                        f"for {url[:100]}"
                    )
                    if response.text:
                        print(f"[API_CLIENT] Body: {response.text[:200]}")
                    return {}

            except Exception as e:
                print(f"[API_CLIENT] Network error: {e}")
                await asyncio.sleep(delay)
                delay *= 2

        return {}

    async def post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        cookies: dict[str, str] | None = None,
        full_url: str | None = None,
    ) -> Any:
        """Execute a POST request with exponential backoff.

        Args:
            endpoint: URL path appended to base_url (ignored if full_url set).
            json_data: Optional JSON body to send.
            params: Optional query parameters.
            cookies: Optional cookies dict.
            full_url: If set, use this URL instead of base_url + endpoint.

        Returns:
            Parsed JSON dict, or empty dict on failure.
        """
        retries = 3
        delay = 1.0

        for attempt in range(retries):
            try:
                if full_url:
                    url = full_url
                else:
                    url = self.base_url.rstrip("/") + "/" + endpoint.lstrip("/")

                kwargs: dict[str, Any] = {}
                if json_data is not None:
                    kwargs["json"] = json_data
                if params:
                    kwargs["params"] = params
                if cookies:
                    kwargs["cookies"] = cookies

                response = await self.client.post(url, **kwargs)

                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception:
                        print(f"[API_CLIENT] POST 200 but not JSON for {url[:100]}")
                        return {}
                elif response.status_code in [429, 403]:
                    print(
                        f"[API_CLIENT] POST rate limited "
                        f"(Code {response.status_code}). "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    print(
                        f"[API_CLIENT] POST HTTP Error "
                        f"{response.status_code} for {url[:100]}"
                    )
                    return {}

            except Exception as e:
                print(f"[API_CLIENT] POST network error: {e}")
                await asyncio.sleep(delay)
                delay *= 2

        return {}

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        await self.client.close()
