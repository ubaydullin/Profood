import httpx
import asyncio
from typing import Dict, Any

class AsyncAPIClient:
    def __init__(self, base_url: str, custom_headers: Dict[str, str] = None):
        self.base_url = base_url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            "Connection": "keep-alive"
        }
        if custom_headers:
            self.headers.update(custom_headers)
            
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=15.0)

    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executes a GET request with exponential backoff for rate limits.
        """
        retries = 3
        delay = 1.0
        
        for attempt in range(retries):
            try:
                response = await self.client.get(endpoint, params=params)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code in [429, 403]:
                    print(f"[API_CLIENT] Rate limited or forbidden. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    print(f"[API_CLIENT] HTTP Error {response.status_code} for {endpoint}")
                    return {}
                    
            except httpx.RequestError as e:
                print(f"[API_CLIENT] Network error: {e}")
                await asyncio.sleep(delay)
                delay *= 2
                
        return {} # Return empty dict if all retries fail

    async def close(self):
        await self.client.aclose()
