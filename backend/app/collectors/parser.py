from __future__ import annotations

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from email.utils import parsedate_to_datetime
from typing import Any, Iterable
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.collectors.models import ArticleCandidate, ArticleMetadata
from app.collectors.rules import CollectorRule


TRACKING_QUERY_PREFIXES = ("utm_", "fbclid", "gclid", "mc_")
URL_KEYS = ("url", "href", "canonicalUrl", "canonical_url", "webUrl", "web_url")
TITLE_KEYS = ("headline", "title", "name", "text", "description")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    path = re.sub(r"/{2,}", "/", parts.path)
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urlencode(filtered_query),
            "",
        )
    )


def _title_from_url(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    slug = unquote(path.rsplit("/", 1)[-1])
    slug = re.sub(r"\.(?:ghtml|html?|php)$", "", slug, flags=re.IGNORECASE)
    slug = re.sub(r"[-_]+", " ", slug)
    return clean_text(slug).capitalize() or "Notícia do Atlético"


def _date_from_url(url: str) -> datetime | None:
    match = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/", url)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _candidate_allowed(
    title: str,
    url: str,
    rule: CollectorRule,
    *,
    allow_feed_proxy: bool = False,
) -> bool:
    if rule.blocked_url_pattern and rule.blocked_url_pattern.search(url):
        return False
    if rule.blocked_title_pattern and rule.blocked_title_pattern.search(title):
        return False

    matches_article = bool(rule.article_pattern.match(url))
    matches_proxy = bool(
        allow_feed_proxy
        and rule.feed_proxy_pattern
        and rule.feed_proxy_pattern.match(url)
    )
    if not matches_article and not matches_proxy:
        return False

    if rule.required_title_pattern and not rule.required_title_pattern.search(title):
        return False
    return True


def _walk_json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json_objects(child)


def _json_value_as_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in URL_KEYS:
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _json_title(item: dict[str, Any]) -> str:
    for key in TITLE_KEYS:
        value = item.get(key)
        if isinstance(value, str):
            title = clean_text(value)
            if len(title) >= 10:
                return title
    return ""


def extract_candidates(
    html: str,
    rule: CollectorRule,
    *,
    base_url: str | None = None,
    discovered_by: str = "listing",
) -> list[ArticleCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = base_url or rule.listing_url
    by_url: dict[str, ArticleCandidate] = {}

    def add(raw_url: str, raw_title: str | None = None) -> None:
        try:
            absolute = urljoin(base_url, unescape(raw_url).replace("\\/", "/"))
            url = canonicalize_url(absolute)
        except Exception:
            return

        title = clean_text(raw_title) or _title_from_url(url)
        if not _candidate_allowed(title, url, rule):
            return

        previous = by_url.get(url)
        candidate = ArticleCandidate(
            titulo=title,
            url=url,
            publicado_em=_date_from_url(url),
            descoberta_por=discovered_by,
        )
        if previous is None or len(candidate.titulo) > len(previous.titulo):
            by_url[url] = candidate

    # 1) Links renderizados na página.
    for anchor in soup.find_all("a", href=True):
        title = clean_text(anchor.get_text(" ", strip=True))
        if not title:
            title = clean_text(anchor.get("aria-label") or anchor.get("title"))
        add(str(anchor["href"]), title)

    # 2) Estados JSON/JSON-LD usados por páginas React/Next/Globo.
    for script in soup.find_all("script"):
        raw = script.string or script.get_text(strip=True)
        if not raw or len(raw) < 10:
            continue

        payload: Any = None
        if script.get("type") in {"application/ld+json", "application/json"}:
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                payload = None

        if payload is not None:
            for item in _walk_json_objects(payload):
                title = _json_title(item)
                for key in URL_KEYS:
                    raw_url = _json_value_as_url(item.get(key))
                    if raw_url:
                        add(raw_url, title)

    # 3) URLs que estejam serializadas/escapadas no HTML e não apareçam como <a>.
    # O filtro article_pattern impede que URLs de outros conteúdos entrem no banco.
    raw_html = html.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
    for match in re.finditer(r"https?://[^\s\"'<>]+", raw_html):
        raw_url = match.group(0).rstrip("),.;]")
        add(raw_url)

    candidates = list(by_url.values())
    if rule.recent_limit is not None:
        candidates = candidates[: rule.recent_limit]
    return candidates




def _html_fragment_image(fragment: str) -> str | None:
    if not fragment:
        return None
    soup = BeautifulSoup(fragment, "html.parser")

    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            raw = img.get(attr)
            if not raw:
                continue
            url = clean_text(unescape(str(raw)))
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith(("http://", "https://")):
                return url

        srcset = img.get("srcset") or img.get("data-srcset")
        if srcset:
            choices = []
            for part in str(srcset).split(","):
                candidate = clean_text(part.strip().split(" ", 1)[0])
                if candidate.startswith("//"):
                    candidate = "https:" + candidate
                if candidate.startswith(("http://", "https://")):
                    choices.append(candidate)
            if choices:
                return choices[-1]

    return None


def parse_feed_xml(
    content: bytes | str,
    rule: CollectorRule,
    *,
    feed_url: str,
    discovered_by: str = "feed",
) -> list[ArticleCandidate]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    by_url: dict[str, ArticleCandidate] = {}

    def child_text(element: ET.Element, *names: str) -> str:
        wanted = set(names)
        for child in element.iter():
            if _local_name(child.tag) in wanted and child.text:
                value = clean_text(child.text)
                if value:
                    return value
        return ""

    def child_raw_texts(element: ET.Element, *names: str) -> list[str]:
        wanted = set(names)
        values: list[str] = []
        for child in element.iter():
            if _local_name(child.tag) in wanted and child.text:
                raw = str(child.text).strip()
                if raw:
                    values.append(raw)
        return values

    def feed_date(element: ET.Element) -> datetime | None:
        raw = child_text(element, "pubDate", "published", "updated", "date")
        if not raw:
            return None
        parsed = _parse_datetime(raw)
        if parsed is not None:
            return parsed
        try:
            return parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None

    item_names = {"item", "entry"}
    for item in root.iter():
        if _local_name(item.tag) not in item_names:
            continue

        title = child_text(item, "title")
        raw_url = child_text(item, "link")
        if not raw_url:
            for child in item.iter():
                if _local_name(child.tag) == "link" and child.attrib.get("href"):
                    raw_url = clean_text(child.attrib["href"])
                    if raw_url:
                        break
        if not raw_url:
            raw_url = child_text(item, "guid", "id")
        if not raw_url:
            continue

        try:
            url = canonicalize_url(urljoin(feed_url, raw_url))
        except Exception:
            continue

        title = title or _title_from_url(url)

        if rule.slug == "noataque-atletico":
            source_name = child_text(item, "source")
            if source_name and "no ataque" not in source_name.lower():
                continue
            title = re.sub(r"\s+-\s+No Ataque$", "", title, flags=re.IGNORECASE).strip()

        if not _candidate_allowed(title, url, rule, allow_feed_proxy=True):
            continue

        summary_html = child_text(item, "description", "summary", "encoded", "content")
        summary = clean_text(
            BeautifulSoup(summary_html, "html.parser").get_text(" ", strip=True)
        ) if summary_html else ""

        image_url = None
        for child in item.iter():
            local = _local_name(child.tag)
            if local in {"content", "thumbnail", "enclosure"}:
                candidate_url = child.attrib.get("url") or child.attrib.get("href")
                media_type = (child.attrib.get("type") or "").lower()
                medium = (child.attrib.get("medium") or "").lower()
                if candidate_url and (
                    local == "thumbnail"
                    or media_type.startswith("image/")
                    or medium == "image"
                ):
                    image_url = clean_text(candidate_url) or None
                    if image_url:
                        break

        if not image_url:
            fragments = (
                child_raw_texts(item, "encoded")
                + child_raw_texts(item, "content")
                + child_raw_texts(item, "description")
                + child_raw_texts(item, "summary")
            )
            for fragment in fragments:
                image_url = _html_fragment_image(fragment)
                if image_url:
                    break

        by_url[url] = ArticleCandidate(
            titulo=title,
            url=url,
            publicado_em=feed_date(item) or _date_from_url(url),
            descoberta_por=discovered_by,
            resumo=summary or None,
            imagem_url=image_url,
        )

    return list(by_url.values())

def _normalize_match_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return clean_text(value)


def _image_candidates_from_container(container: Any) -> list[tuple[int, str]]:
    candidates: list[tuple[int, str]] = []
    for img in container.find_all("img"):
        alt = _normalize_match_text(str(img.get("alt") or ""))
        classes = _normalize_match_text(" ".join(img.get("class") or []))
        if "google news" in alt or "google noticias" in alt or "logo" in classes:
            continue

        width = 0
        height = 0
        raw_width = str(img.get("width") or "")
        raw_height = str(img.get("height") or "")
        if raw_width.isdigit():
            width = int(raw_width)
        if raw_height.isdigit():
            height = int(raw_height)

        raw_urls: list[str] = []
        for attr in ("src", "data-src", "data-lazy-src"):
            raw = img.get(attr)
            if raw:
                raw_urls.append(str(raw))
        srcset = img.get("srcset") or img.get("data-srcset")
        if srcset:
            raw_urls.extend(part.strip().split(" ", 1)[0] for part in str(srcset).split(","))

        for raw in raw_urls:
            url = clean_text(unescape(raw))
            if url.startswith("//"):
                url = "https:" + url
            if not url.startswith(("http://", "https://")):
                continue
            host = urlsplit(url).netloc.lower()
            if "googleusercontent.com" not in host:
                continue
            if "J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc" in url:
                continue
            url_lower = url.lower()
            if any(token in url_lower for token in ("favicon", "logo", "icon")):
                continue
            if width and width < 80:
                continue
            if height and height < 60:
                continue
            score = width * height
            size_match = re.search(r"(?:=|-)w(\d+).*?h(\d+)", url)
            if size_match:
                score = max(score, int(size_match.group(1)) * int(size_match.group(2)))
            candidates.append((score, url))

    candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    return candidates


def extract_google_news_thumbnail(html: str, target_title: str | None = None) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    if target_title:
        target_norm = _normalize_match_text(target_title)
        target_tokens = {
            token for token in target_norm.split()
            if len(token) >= 4 and token not in {"para", "contra", "como", "mais", "sobre", "atletico"}
        }
        ranked: list[tuple[float, Any]] = []
        containers = list(soup.find_all("article"))
        if not containers:
            containers = list(soup.find_all(["c-wiz", "div"]))

        for container in containers:
            block_text = _normalize_match_text(container.get_text(" ", strip=True))
            if not block_text:
                continue
            if target_norm and target_norm in block_text:
                score = 1.0
            else:
                tokens = set(block_text.split())
                score = len(target_tokens & tokens) / max(len(target_tokens), 1)
            if score >= 0.55:
                ranked.append((score, container))

        for anchor in soup.find_all("a"):
            anchor_text = _normalize_match_text(anchor.get_text(" ", strip=True))
            if not anchor_text:
                continue
            tokens = set(anchor_text.split())
            overlap = len(target_tokens & tokens) / max(len(target_tokens), 1)
            if target_norm in anchor_text or overlap >= 0.7:
                parent = anchor
                for depth in range(1, 7):
                    parent = getattr(parent, "parent", None)
                    if parent is None:
                        break
                    ranked.append((0.95 - depth * 0.03, parent))

        ranked.sort(key=lambda item: item[0], reverse=True)
        seen_ids: set[int] = set()
        for _score, container in ranked:
            ident = id(container)
            if ident in seen_ids:
                continue
            seen_ids.add(ident)
            images = _image_candidates_from_container(container)
            if images:
                return images[0][1]
        return None

    for attr, value in (("property", "og:image"), ("name", "twitter:image")):
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            url = clean_text(str(tag.get("content")))
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith(("http://", "https://")):
                return url

    images = _image_candidates_from_container(soup)
    return images[0][1] if images else None

def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_child_text(element: ET.Element, local_name: str) -> str | None:
    for child in element.iter():
        if _local_name(child.tag) == local_name and child.text:
            text = clean_text(child.text)
            if text:
                return text
    return None


def parse_sitemap_xml(
    content: bytes | str,
    rule: CollectorRule,
    *,
    sitemap_url: str,
) -> tuple[list[str], list[ArticleCandidate]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return [], []

    root_name = _local_name(root.tag)
    nested_sitemaps: list[str] = []
    candidates: list[ArticleCandidate] = []

    if root_name == "sitemapindex":
        for child in root:
            if _local_name(child.tag) != "sitemap":
                continue
            loc = _first_child_text(child, "loc")
            if loc:
                nested_sitemaps.append(canonicalize_url(urljoin(sitemap_url, loc)))
        return list(dict.fromkeys(nested_sitemaps)), []

    if root_name != "urlset":
        return [], []

    seen: set[str] = set()
    for item in root:
        if _local_name(item.tag) != "url":
            continue

        loc = _first_child_text(item, "loc")
        if not loc:
            continue
        url = canonicalize_url(urljoin(sitemap_url, loc))
        if url in seen or not rule.article_pattern.match(url):
            continue

        title = _first_child_text(item, "title") or _title_from_url(url)
        if rule.required_title_pattern and not rule.required_title_pattern.search(title):
            continue

        published_raw = (
            _first_child_text(item, "publication_date")
            or _first_child_text(item, "lastmod")
        )
        published = _parse_datetime(published_raw) or _date_from_url(url)

        seen.add(url)
        candidates.append(
            ArticleCandidate(
                titulo=title,
                url=url,
                publicado_em=published,
                descoberta_por="sitemap",
            )
        )

    return [], candidates


def _find_article_json_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    preferred_types = {
        "NewsArticle",
        "Article",
        "BlogPosting",
        "ReportageNewsArticle",
        "AnalysisNewsArticle",
    }

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        for item in _walk_json_objects(payload):
            item_type = item.get("@type")
            if isinstance(item_type, list):
                types = set(str(v) for v in item_type)
            else:
                types = {str(item_type)} if item_type else set()
            if types & preferred_types:
                return item

    return None


def _meta_content(soup: BeautifulSoup, *selectors: tuple[str, str]) -> str | None:
    for attr, value in selectors:
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            text = clean_text(str(tag["content"]))
            if text:
                return text
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = clean_text(str(value))
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_image(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list) and value:
        return _extract_image(value[0])
    if isinstance(value, dict):
        return _extract_image(value.get("url") or value.get("contentUrl"))
    return None


def extract_article_metadata(
    html: str,
    candidate: ArticleCandidate,
) -> ArticleMetadata:
    soup = BeautifulSoup(html, "html.parser")
    json_ld = _find_article_json_ld(soup) or {}

    title = clean_text(str(json_ld.get("headline") or ""))
    if not title:
        title = _meta_content(
            soup,
            ("property", "og:title"),
            ("name", "twitter:title"),
        ) or candidate.titulo
    if not title:
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True) if h1 else "")

    summary = clean_text(str(json_ld.get("description") or "")) or _meta_content(
        soup,
        ("name", "description"),
        ("property", "og:description"),
        ("name", "twitter:description"),
    )

    image_url = _extract_image(json_ld.get("image")) or _meta_content(
        soup,
        ("property", "og:image"),
        ("name", "twitter:image"),
    )

    published = _parse_datetime(json_ld.get("datePublished"))
    if published is None:
        published = _parse_datetime(
            _meta_content(
                soup,
                ("property", "article:published_time"),
                ("name", "date"),
            )
        )
    if published is None:
        published = candidate.publicado_em or _date_from_url(candidate.url)

    category = clean_text(str(json_ld.get("articleSection") or "")) or _meta_content(
        soup,
        ("property", "article:section"),
    )

    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical_url = candidate.url
    if canonical_tag and canonical_tag.get("href"):
        canonical_url = canonicalize_url(urljoin(candidate.url, canonical_tag["href"]))

    return ArticleMetadata(
        titulo=title or candidate.titulo,
        url=canonical_url,
        resumo=summary or None,
        imagem_url=image_url,
        categoria=category or None,
        publicado_em=published,
        metadados={
            "coleta": "metadata_only",
            "descoberta_por": candidate.descoberta_por,
            "conteudo_integral_armazenado": False,
        },
    )
