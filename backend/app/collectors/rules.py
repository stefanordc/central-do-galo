from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class CollectorRule:
    slug: str
    listing_url: str
    article_pattern: re.Pattern[str]
    required_title_pattern: re.Pattern[str] | None = None
    blocked_title_pattern: re.Pattern[str] | None = None
    blocked_url_pattern: re.Pattern[str] | None = None
    feed_proxy_pattern: re.Pattern[str] | None = None
    prefer_feed: bool = False
    recent_limit: int | None = None
    recent_pages: int = 3
    feed_urls: tuple[str, ...] = ()
    history_feed_templates: tuple[str, ...] = ()
    history_page_templates: tuple[str, ...] = ()
    history_max_pages: int = 25
    explicit_sitemaps: tuple[str, ...] = ()
    use_robots_sitemaps: bool = True


RULES: dict[str, CollectorRule] = {
    "atletico-oficial": CollectorRule(
        slug="atletico-oficial",
        listing_url="https://atletico.com.br/noticias/futebol/",
        article_pattern=re.compile(
            r"^https://atletico\.com\.br/(?!noticias(?:/|$)|$|busca(?:/|$)|"
            r"imprensa(?:/|$)|super-app(?:/|$)|clube(?:/|$)|futebol(?:/|$)|"
            r"titulos(?:/|$)|a-massa(?:/|$)|comercial(?:/|$))[^/?#]+/$",
            re.IGNORECASE,
        ),
        feed_urls=("https://atletico.com.br/noticias/futebol/feed/",),
        prefer_feed=True,
        history_feed_templates=("https://atletico.com.br/noticias/futebol/feed/?paged={page}",),
    ),
    "ge-atletico-mg": CollectorRule(
        slug="ge-atletico-mg",
        listing_url="https://ge.globo.com/futebol/times/atletico-mg/",
        article_pattern=re.compile(
            r"^https://ge\.globo\.com/futebol/times/atletico-mg/noticia/"
            r"\d{4}/\d{2}/\d{2}/.+\.ghtml$",
            re.IGNORECASE,
        ),
        recent_pages=10,
        history_page_templates=(
            "https://ge.globo.com/futebol/times/atletico-mg/index/feed/pagina-{page}.ghtml",
        ),
        explicit_sitemaps=("https://ge.globo.com/sitemap/ge/sitemap.xml",),
    ),
    "itatiaia-atletico": CollectorRule(
        slug="itatiaia-atletico",
        listing_url=(
            "https://www.itatiaia.com.br/esportes/futebol/futebol-nacional/"
            "futebol-mineiro/atletico/"
        ),
        article_pattern=re.compile(
            r"^https://www\.itatiaia\.com\.br/esportes/futebol/futebol-nacional/"
            r"futebol-mineiro/atletico/[^/?#]+/$",
            re.IGNORECASE,
        ),
        history_page_templates=(
            "https://www.itatiaia.com.br/esportes/futebol/futebol-nacional/futebol-mineiro/atletico/?page={page}",
        ),
    ),
    "otempo-atletico": CollectorRule(
        slug="otempo-atletico",
        listing_url="https://www.otempo.com.br/sports/atletico",
        article_pattern=re.compile(
            r"^https://(?:www\.)?otempo\.com\.br/sports/atletico/"
            r"\d{4}/\d{1,2}/\d{1,2}/[^?#]+$",
            re.IGNORECASE,
        ),
        history_page_templates=(
            "https://www.otempo.com.br/sports/atletico?page={page}",
        ),
    ),
    "falagalo": CollectorRule(
        slug="falagalo",
        listing_url="https://falagalo.com.br/category/noticias/",
        article_pattern=re.compile(
            r"^https://falagalo\.com\.br/(?!category(?:/|$)|tag(?:/|$)|author(?:/|$)|"
            r"page(?:/|$)|falagalo(?:/|$)|transparencia(?:/|$)|feed(?:/|$)|"
            r"wp-json(?:/|$)|quem-somos(?:/|$)|contato(?:/|$)|politica(?:/|$)|"
            r"https-falagalo-com-br(?:/|$)|$)[^/?#]+/$",
            re.IGNORECASE,
        ),
        blocked_title_pattern=re.compile(
            r"^(?:feed|wp json|quem somos(?:\s*-\s*falagalo)?|"
            r"falagalo\s*-\s*atl[eé]tico mineiro\s*-\s*galo\s*-\s*not[ií]cias\s*-\s*tudo sobre o galo)$",
            re.IGNORECASE,
        ),
        recent_pages=3,
        history_page_templates=("https://falagalo.com.br/category/noticias/page/{page}/",),
    ),
    "noataque-atletico": CollectorRule(
        slug="noataque-atletico",
        listing_url="https://noataque.com.br/clubes/atletico-mg/",
        article_pattern=re.compile(
            r"^https://noataque\.com\.br/.+/noticia/\d{4}/\d{2}/\d{2}/[^/?#]+/$",
            re.IGNORECASE,
        ),
        required_title_pattern=re.compile(r"\b(atl[eé]tico(?:-mg)?|galo)\b", re.IGNORECASE),
        feed_urls=(
            "https://news.google.com/rss/search?q=site%3Anoataque.com.br+Atl%C3%A9tico&hl=pt-BR&gl=BR&ceid=BR%3Apt-419",
            "https://news.google.com/rss/search?q=site%3Anoataque.com.br+Atl%C3%A9tico-MG&hl=pt-BR&gl=BR&ceid=BR%3Apt-419",
            "https://news.google.com/rss/search?q=site%3Anoataque.com.br+Galo&hl=pt-BR&gl=BR&ceid=BR%3Apt-419",
        ),
        feed_proxy_pattern=re.compile(r"^https://news\.google\.com/", re.IGNORECASE),
        prefer_feed=True,
        history_page_templates=("https://noataque.com.br/clubes/atletico-mg/page/{page}/",),
    ),
    "rede98-atletico": CollectorRule(
        slug="rede98-atletico",
        listing_url="https://rede98.com.br/esportes/atletico/",
        article_pattern=re.compile(
            r"^https://rede98\.com\.br/esportes/atletico/[^/?#]+/$",
            re.IGNORECASE,
        ),
        history_page_templates=("https://rede98.com.br/esportes/atletico/page/{page}/",),
    ),
    "lance-atletico": CollectorRule(
        slug="lance-atletico",
        listing_url="https://www.lance.com.br/atletico-mineiro",
        blocked_url_pattern=re.compile(
            r"^https://www\.lance\.com\.br/?$",
            re.IGNORECASE,
        ),
        article_pattern=re.compile(
            r"^https://www\.lance\.com\.br/(?!atletico-mineiro/?$)[a-z0-9-]+/[^?#]+\.html$",
            re.IGNORECASE,
        ),
        required_title_pattern=re.compile(r"\b(atl[eé]tico(?:-mg)?|galo)\b", re.IGNORECASE),
        history_page_templates=("https://www.lance.com.br/atletico-mineiro?page={page}",),
        explicit_sitemaps=(
            "https://www.lance.com.br/sitemap/articles-current.xml",
            "https://www.lance.com.br/sitemap/news/today.xml",
        ),
    ),
    "cnn-atletico": CollectorRule(
        slug="cnn-atletico",
        listing_url="https://www.cnnbrasil.com.br/tudo-sobre/atletico-mineiro/",
        article_pattern=re.compile(
            r"^https://www\.cnnbrasil\.com\.br/esportes/[^?#]+/$",
            re.IGNORECASE,
        ),
        blocked_url_pattern=re.compile(
            r"^https://www\.cnnbrasil\.com\.br/esportes/futebol/atletico-mineiro/?$",
            re.IGNORECASE,
        ),
        blocked_title_pattern=re.compile(r"^atl[eé]tico mineiro\s*\|\s*cnn brasil$", re.IGNORECASE),
        required_title_pattern=re.compile(r"\b(atl[eé]tico(?:-mg)?|galo)\b", re.IGNORECASE),
        history_page_templates=(
            "https://www.cnnbrasil.com.br/tudo-sobre/atletico-mineiro/page/{page}/",
        ),
    ),
    "espn-atletico-mg": CollectorRule(
        slug="espn-atletico-mg",
        listing_url="https://www.espn.com.br/futebol/time/_/id/7632/bra.atltico-mg",
        article_pattern=re.compile(
            r"^https://www\.espn\.com\.br/futebol/(?:atletico-mg/)?artigo/_/id/\d+/[^?#]+$",
            re.IGNORECASE,
        ),
        required_title_pattern=re.compile(r"\b(atl[eé]tico(?:-mg)?|galo)\b", re.IGNORECASE),
    ),
}


def get_rule(slug: str) -> CollectorRule:
    try:
        return RULES[slug]
    except KeyError as exc:
        raise ValueError(f"Fonte sem coletor ativo: {slug}") from exc
