from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx


USER_AGENT = "CentralDoGalo/0.4 (+news-aggregator; respectful crawler)"


class RobotsCache:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self._cache: dict[str, RobotFileParser | bool] = {}
        self._sitemaps: dict[str, tuple[str, ...]] = {}

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    def _load(self, origin: str) -> RobotFileParser | bool:
        cached = self._cache.get(origin)
        if cached is not None:
            return cached

        robots_url = f"{origin}/robots.txt"
        try:
            response = self.client.get(robots_url)
        except httpx.HTTPError:
            self._cache[origin] = False
            self._sitemaps[origin] = ()
            return False

        if response.status_code == 404:
            self._cache[origin] = True
            self._sitemaps[origin] = ()
            return True

        if response.status_code != 200:
            # Política conservadora: se o site não permite nem consultar robots.txt,
            # não tentamos contornar a restrição.
            self._cache[origin] = False
            self._sitemaps[origin] = ()
            return False

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        self._cache[origin] = parser

        sitemaps: list[str] = []
        for line in response.text.splitlines():
            if line.lower().startswith("sitemap:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    sitemaps.append(value)
        self._sitemaps[origin] = tuple(dict.fromkeys(sitemaps))
        return parser

    def can_fetch(self, url: str) -> bool:
        origin = self._origin(url)
        parsed = self._load(origin)
        if isinstance(parsed, bool):
            return parsed
        return parsed.can_fetch(USER_AGENT, url)

    def sitemap_urls(self, url: str) -> tuple[str, ...]:
        origin = self._origin(url)
        self._load(origin)
        return self._sitemaps.get(origin, ())


def build_http_client() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
        },
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
    )
