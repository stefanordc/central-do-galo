from __future__ import annotations

import gzip
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx

from app.collectors.http_client import RobotsCache, build_http_client
from app.collectors.models import ArticleCandidate, ArticleMetadata
from app.collectors.parser import (
    extract_article_metadata,
    extract_google_news_thumbnail,
    extract_candidates,
    parse_feed_xml,
    parse_sitemap_xml,
)
from app.collectors.rules import RULES, CollectorRule, get_rule
from app.services.news_classifier import save_news_categories
from app.services.news_service import (
    atualizar_imagem_noticia_por_url,
    obter_fonte_por_slug,
    salvar_noticia,
    urls_ja_cadastradas,
    urls_sem_imagem,
)


@dataclass(slots=True)
class CollectionResult:
    fonte: str
    candidatos: int = 0
    novos_encontrados: int = 0
    inseridos: int = 0
    enriquecidos: int = 0
    ignorados_robots: int = 0
    erros: int = 0
    paginas_lidas: int = 0
    sitemaps_lidos: int = 0
    mensagem: str = "ok"


class NewsCollectorRunner:
    def __init__(self, delay_seconds: float = 0.6, max_history_pages: int = 25) -> None:
        self.delay_seconds = max(delay_seconds, 0.0)
        self.max_history_pages = max(1, max_history_pages)

    def _google_news_thumbnail(
        self,
        *,
        client: httpx.Client,
        candidate: ArticleCandidate,
    ) -> str | None:
        """Busca a thumbnail pública da matéria na interface do Google News.

        O No Ataque bloqueia nosso acesso HTTP direto com 403. Por isso, esta
        rotina não abre a matéria no veículo: ela pesquisa o título no próprio
        Google News e extrai somente a imagem de preview hospedada pelo Google.
        """
        title = (candidate.titulo or "").strip()
        if not title:
            return None

        query = quote_plus(f'"{title}" "No Ataque"')
        search_url = (
            "https://news.google.com/search"
            f"?q={query}&hl=pt-BR&gl=BR&ceid=BR%3Apt-419"
        )

        try:
            response = client.get(
                search_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                    "Referer": "https://news.google.com/",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(
                f"[noataque-atletico] thumbnail não encontrada no Google News "
                f"para {candidate.url}: {exc}"
            )
            return None

        return extract_google_news_thumbnail(response.text, target_title=title)

    def _process_candidates(
        self,
        *,
        client: httpx.Client,
        robots: RobotsCache,
        source: dict,
        rule: CollectorRule,
        candidates: list[ArticleCandidate],
        result: CollectionResult,
    ) -> None:
        if not candidates:
            return

        unique_by_url = {candidate.url: candidate for candidate in candidates}
        candidates = list(unique_by_url.values())
        result.candidatos += len(candidates)

        # O No Ataque é descoberto por um índice externo porque a página do veículo
        # retorna 403 para o nosso coletor. As imagens retornadas pelo índice não são
        # confiáveis o suficiente para representar a foto oficial da matéria. Portanto,
        # não gravamos nenhuma thumbnail externa para essa fonte; o frontend usa a logo
        # do Central do Galo como fallback visual.
        if rule.slug == "noataque-atletico":
            for candidate in candidates:
                candidate.imagem_url = None

        existing = urls_ja_cadastradas(candidate.url for candidate in candidates)
        existing_missing = urls_sem_imagem(candidate.url for candidate in candidates)

        for candidate in candidates:
            if (
                candidate.imagem_url
                and candidate.url in existing_missing
                and atualizar_imagem_noticia_por_url(candidate.url, candidate.imagem_url)
            ):
                result.enriquecidos += 1

        new_candidates = [candidate for candidate in candidates if candidate.url not in existing]
        result.novos_encontrados += len(new_candidates)

        for candidate in new_candidates:
            base_article = ArticleMetadata(
                titulo=candidate.titulo,
                url=candidate.url,
                publicado_em=candidate.publicado_em,
                resumo=candidate.resumo,
                imagem_url=candidate.imagem_url,
                metadados={
                    "coleta": "discovery",
                    "descoberta_por": candidate.descoberta_por,
                    "conteudo_integral_armazenado": False,
                },
            )

            try:
                noticia_id = salvar_noticia(
                    fonte_id=source["id"],
                    oficial=bool(source["oficial"]),
                    article=base_article,
                )
                save_news_categories(
                    noticia_id=noticia_id,
                    titulo=base_article.titulo,
                    resumo=base_article.resumo,
                )
                result.inseridos += 1
            except Exception as exc:
                print(f"[{rule.slug}] erro ao salvar {candidate.url}: {exc}")
                result.erros += 1
                continue

            # Feeds já entregam título, URL, data e resumo. Não abrimos cada
            # matéria novamente só para enriquecer os metadados, evitando carga
            # desnecessária e bloqueios 403 em sites que oferecem RSS.
            if candidate.descoberta_por.startswith("feed"):
                if self.delay_seconds:
                    time.sleep(self.delay_seconds)
                continue

            if not robots.can_fetch(candidate.url):
                result.ignorados_robots += 1
                continue

            try:
                response = client.get(candidate.url)
                response.raise_for_status()
                article = extract_article_metadata(response.text, candidate)
                noticia_id = salvar_noticia(
                    fonte_id=source["id"],
                    oficial=bool(source["oficial"]),
                    article=article,
                )
                save_news_categories(
                    noticia_id=noticia_id,
                    titulo=article.titulo,
                    resumo=article.resumo,
                )
                result.enriquecidos += 1
            except Exception as exc:
                print(f"[{rule.slug}] metadados não enriquecidos em {candidate.url}: {exc}")

            if self.delay_seconds:
                time.sleep(self.delay_seconds)

    def _fetch_listing_candidates(
        self,
        *,
        client: httpx.Client,
        robots: RobotsCache,
        rule: CollectorRule,
        url: str,
        discovered_by: str,
        result: CollectionResult,
    ) -> list[ArticleCandidate] | None:
        if not robots.can_fetch(url):
            result.ignorados_robots += 1
            return None

        try:
            response = client.get(url)
            if response.status_code in {404, 410}:
                return []
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"[{rule.slug}] erro ao acessar {url}: {exc}")
            result.erros += 1
            return None

        result.paginas_lidas += 1
        return extract_candidates(
            response.text,
            rule,
            base_url=url,
            discovered_by=discovered_by,
        )

    def _fetch_feed_candidates(
        self,
        *,
        client: httpx.Client,
        robots: RobotsCache,
        rule: CollectorRule,
        url: str,
        discovered_by: str,
        result: CollectionResult,
    ) -> list[ArticleCandidate] | None:
        # Um feed-proxy é um índice RSS público de terceiro (ex.: Google News)
        # usado somente para descobrir links quando o veículo bloqueia nosso HTTP.
        # Nesse caso não consultamos o robots.txt do índice; não há tentativa de
        # contornar o robots/403 do site de origem.
        is_feed_proxy = bool(
            rule.feed_proxy_pattern and rule.feed_proxy_pattern.match(url)
        )
        if not is_feed_proxy and not robots.can_fetch(url):
            result.ignorados_robots += 1
            return None

        try:
            response = client.get(
                url,
                headers={"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5"},
            )
            if response.status_code in {404, 410}:
                return []
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"[{rule.slug}] feed não acessível {url}: {exc}")
            return None

        result.paginas_lidas += 1
        return parse_feed_xml(
            response.content,
            rule,
            feed_url=url,
            discovered_by=discovered_by,
        )

    def _collect_current_feeds(
        self,
        *,
        client: httpx.Client,
        robots: RobotsCache,
        source: dict,
        rule: CollectorRule,
        result: CollectionResult,
    ) -> bool:
        feed_worked = False
        for feed_url in rule.feed_urls:
            candidates = self._fetch_feed_candidates(
                client=client,
                robots=robots,
                rule=rule,
                url=feed_url,
                discovered_by="feed",
                result=result,
            )
            if candidates is None:
                continue
            feed_worked = True
            self._process_candidates(
                client=client,
                robots=robots,
                source=source,
                rule=rule,
                candidates=candidates,
                result=result,
            )
        return feed_worked

    def _collect_feed_history(
        self,
        *,
        client: httpx.Client,
        robots: RobotsCache,
        source: dict,
        rule: CollectorRule,
        result: CollectionResult,
    ) -> None:
        if not rule.history_feed_templates:
            return

        last_page = min(rule.history_max_pages, self.max_history_pages)
        for template in rule.history_feed_templates:
            previous_signature: tuple[str, ...] | None = None
            empty_pages = 0

            for page in range(2, last_page + 1):
                page_url = template.format(page=page)
                candidates = self._fetch_feed_candidates(
                    client=client,
                    robots=robots,
                    rule=rule,
                    url=page_url,
                    discovered_by=f"feed-pagination:{page}",
                    result=result,
                )
                if candidates is None:
                    break
                if not candidates:
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                    continue

                empty_pages = 0
                signature = tuple(sorted(candidate.url for candidate in candidates))
                if signature == previous_signature:
                    break
                previous_signature = signature

                self._process_candidates(
                    client=client,
                    robots=robots,
                    source=source,
                    rule=rule,
                    candidates=candidates,
                    result=result,
                )
                print(
                    f"[{rule.slug}] feed página {page}/{last_page} | "
                    f"candidatos={len(candidates)} | inseridos_total={result.inseridos}"
                )
                if self.delay_seconds:
                    time.sleep(self.delay_seconds)

    def _collect_paginated_history(
        self,
        *,
        client: httpx.Client,
        robots: RobotsCache,
        source: dict,
        rule: CollectorRule,
        result: CollectionResult,
        historical: bool,
    ) -> None:
        if not rule.history_page_templates:
            return

        if historical:
            last_page = min(rule.history_max_pages, self.max_history_pages)
        else:
            last_page = max(rule.recent_pages, 1)

        for template in rule.history_page_templates:
            previous_signature: tuple[str, ...] | None = None
            empty_pages = 0

            for page in range(2, last_page + 1):
                page_url = template.format(page=page)
                candidates = self._fetch_listing_candidates(
                    client=client,
                    robots=robots,
                    rule=rule,
                    url=page_url,
                    discovered_by=f"pagination:{page}",
                    result=result,
                )

                if candidates is None:
                    break
                if not candidates:
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                    continue

                empty_pages = 0
                signature = tuple(sorted(candidate.url for candidate in candidates))
                if signature == previous_signature:
                    # Alguns sites ignoram ?page=N e devolvem sempre a primeira página.
                    break
                previous_signature = signature

                self._process_candidates(
                    client=client,
                    robots=robots,
                    source=source,
                    rule=rule,
                    candidates=candidates,
                    result=result,
                )

                if historical:
                    print(
                        f"[{rule.slug}] página {page} | "
                        f"candidatos={len(candidates)} | inseridos_total={result.inseridos}"
                    )

                if self.delay_seconds:
                    time.sleep(self.delay_seconds)

    def _collect_sitemaps(
        self,
        *,
        client: httpx.Client,
        robots: RobotsCache,
        source: dict,
        rule: CollectorRule,
        result: CollectionResult,
    ) -> None:
        initial: list[str] = list(rule.explicit_sitemaps)
        if rule.use_robots_sitemaps:
            initial.extend(robots.sitemap_urls(rule.listing_url))

        queue = deque(dict.fromkeys(initial))
        visited: set[str] = set()
        max_sitemap_documents = 10000

        while queue and len(visited) < max_sitemap_documents:
            sitemap_url = queue.popleft()
            if sitemap_url in visited:
                continue
            visited.add(sitemap_url)

            if not robots.can_fetch(sitemap_url):
                result.ignorados_robots += 1
                continue

            try:
                response = client.get(sitemap_url)
                if response.status_code in {404, 410}:
                    continue
                response.raise_for_status()
                content = response.content
                if content[:2] == b"\x1f\x8b" or sitemap_url.lower().endswith(".gz"):
                    content = gzip.decompress(content)
            except Exception as exc:
                print(f"[{rule.slug}] sitemap não lido {sitemap_url}: {exc}")
                result.erros += 1
                continue

            result.sitemaps_lidos += 1
            nested, candidates = parse_sitemap_xml(
                content,
                rule,
                sitemap_url=sitemap_url,
            )
            for nested_url in nested:
                if nested_url not in visited:
                    queue.append(nested_url)

            self._process_candidates(
                client=client,
                robots=robots,
                source=source,
                rule=rule,
                candidates=candidates,
                result=result,
            )

            if result.sitemaps_lidos == 1 or result.sitemaps_lidos % 10 == 0:
                print(
                    f"[{rule.slug}] sitemaps={result.sitemaps_lidos} | "
                    f"fila={len(queue)} | inseridos_total={result.inseridos}"
                )

            if self.delay_seconds:
                time.sleep(self.delay_seconds)

    def collect_source(
        self,
        slug: str,
        *,
        historical: bool = False,
        include_sitemaps: bool = False,
    ) -> CollectionResult:
        rule = get_rule(slug)
        source = obter_fonte_por_slug(slug)
        result = CollectionResult(fonte=slug)

        if not source:
            result.mensagem = "fonte não cadastrada ou inativa"
            result.erros += 1
            return result

        with build_http_client() as client:
            robots = RobotsCache(client)

            feed_worked = self._collect_current_feeds(
                client=client,
                robots=robots,
                source=source,
                rule=rule,
                result=result,
            )

            # Algumas fontes oferecem feed suficiente para a coleta e bloqueiam
            # o HTML (caso do site oficial). Quando prefer_feed=True e o feed
            # funcionou, não fazemos uma segunda requisição desnecessária.
            if rule.prefer_feed and feed_worked:
                candidates = []
                listing_worked = False
            else:
                candidates = self._fetch_listing_candidates(
                    client=client,
                    robots=robots,
                    rule=rule,
                    url=rule.listing_url,
                    discovered_by="listing",
                    result=result,
                )

                listing_worked = candidates is not None
                if candidates:
                    self._process_candidates(
                        client=client,
                        robots=robots,
                        source=source,
                        rule=rule,
                        candidates=candidates,
                        result=result,
                    )

            if not listing_worked and not feed_worked:
                result.mensagem = "robots.txt não permite ou fonte não pôde ser lida"
                return result

            if historical:
                # Cada fonte fica limitada a, no máximo, 25 páginas por padrão.
                self._collect_feed_history(
                    client=client,
                    robots=robots,
                    source=source,
                    rule=rule,
                    result=result,
                )

            if listing_worked:
                self._collect_paginated_history(
                    client=client,
                    robots=robots,
                    source=source,
                    rule=rule,
                    result=result,
                    historical=historical,
                )

            # Sitemaps não entram mais automaticamente no --historico, porque um
            # único sitemap pode conter milhares de URLs. Use --sitemaps de forma
            # explícita quando quiser uma varredura adicional.
            if historical and include_sitemaps:
                self._collect_sitemaps(
                    client=client,
                    robots=robots,
                    source=source,
                    rule=rule,
                    result=result,
                )

        if historical:
            result.mensagem = (
                f"backfill concluído (máximo {self.max_history_pages} páginas por fonte)"
            )
        elif feed_worked and not listing_worked:
            result.mensagem = "RSS coletado; listagem HTML não acessível"
        return result

    def collect_all(
        self,
        *,
        historical: bool = False,
        include_sitemaps: bool = False,
    ) -> list[CollectionResult]:
        return [
            self.collect_source(
                slug,
                historical=historical,
                include_sitemaps=include_sitemaps,
            )
            for slug in RULES
        ]
