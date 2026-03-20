import httpx

from app.core.interfaces.downloader import AbstractDownloader


class HttpxDownloader(AbstractDownloader):
    async def download(self, url: str) -> bytes:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
