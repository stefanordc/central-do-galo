from app.collectors.parser import parse_sitemap_xml
from app.collectors.rules import get_rule


def test_parse_ge_sitemap_urlset():
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
      <url>
        <loc>https://ge.globo.com/futebol/times/atletico-mg/noticia/2026/08/25/teste-do-galo.ghtml</loc>
        <news:news>
          <news:publication_date>2026-08-25T12:00:00-03:00</news:publication_date>
          <news:title>Atlético testa novidade para clássico</news:title>
        </news:news>
      </url>
      <url>
        <loc>https://ge.globo.com/futebol/times/cruzeiro/noticia/2026/08/25/outra.ghtml</loc>
      </url>
    </urlset>'''.encode("utf-8")

    nested, candidates = parse_sitemap_xml(
        xml,
        get_rule("ge-atletico-mg"),
        sitemap_url="https://ge.globo.com/sitemap/ge/test.xml",
    )

    assert nested == []
    assert len(candidates) == 1
    assert candidates[0].titulo == "Atlético testa novidade para clássico"
    assert candidates[0].descoberta_por == "sitemap"


def test_parse_sitemap_index():
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://ge.globo.com/sitemap/ge/a.xml</loc></sitemap>
      <sitemap><loc>https://ge.globo.com/sitemap/ge/b.xml</loc></sitemap>
    </sitemapindex>'''.encode("utf-8")

    nested, candidates = parse_sitemap_xml(
        xml,
        get_rule("ge-atletico-mg"),
        sitemap_url="https://ge.globo.com/sitemap/ge/sitemap.xml",
    )

    assert len(nested) == 2
    assert candidates == []
