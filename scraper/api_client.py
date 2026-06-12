from curl_cffi import requests
import asyncio
from typing import Dict, Any

class AsyncAPIClient:
    def __init__(self, base_url: str, custom_headers: Dict[str, str] = None):
        self.base_url = base_url
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "accept": "application/json, text/plain, */*",
            "accept-language": "ru",
            "connection": "keep-alive"
        }
        if custom_headers:
            self.headers.update(custom_headers)
            
        # Using impersonate="chrome" to mimic a real browser TLS fingerprint
        self.client = requests.AsyncSession(impersonate="chrome", headers=self.headers, timeout=15.0)
        # requests.AsyncSession doesn't have a base_url parameter like httpx, so we handle it in get()

    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executes a GET request with exponential backoff for rate limits.
        """
        retries = 3
        delay = 1.0
        
        for attempt in range(retries):
            try:
                # Combine base_url and endpoint
                url = self.base_url.rstrip('/') + '/' + endpoint.lstrip('/')
                response = await self.client.get(url, params=params)
                
                if response.status_code == 200:
                    try:
                        return response.json()
                    except:
                        # If it's not JSON (e.g. Cloudflare captcha page)
                        print(f"[API_CLIENT] Valid 200, but not JSON. Possible Cloudflare bypass failed.")
                        return {}
                elif response.status_code in [429, 403]:
                    print(f"[API_CLIENT] Rate limited or forbidden (Code {response.status_code}). Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    print(f"[API_CLIENT] HTTP Error {response.status_code} for {endpoint}")
                    print(f"[API_CLIENT] Error Body: {response.text[:200]}")
                    return {}
                    
            except Exception as e:
                print(f"[API_CLIENT] Network error: {e}")
                await asyncio.sleep(delay)
                delay *= 2
                
        return {} # Return empty dict if all retries fail

    async def close(self):
        self.client.close()
