import httpx
import asyncio
from typing import Optional, Dict, Any

class AsyncAPIClient:
    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=15.0)

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retries: int = 3) -> Optional[httpx.Response]:
        for attempt in range(retries):
            try:
                response = await self.client.get(endpoint, params=params)
                response.raise_for_status()
                return response
            except httpx.HTTPError as e:
                print(f"Error fetching {endpoint}: {e}. Retrying ({attempt+1}/{retries})...")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return None
        
    async def close(self):
        await self.client.aclose()
