from app.collectors.parser import parse_feed_xml, parse_sitemap_xml
from app.collectors.rules import get_rule


def test_espn_feed_rejects_mma_bantamweight_profile():
    feed = '''<rss><channel><item>
      <title>Ryuho Miyaguchi (Peso galo) Perfil do MMA - ESPN Brasil</title>
      <link>https://news.google.com/rss/articles/mma-profile</link>
    </item><item>
      <title>Galo prepara reforços para o Brasileiro</title>
      <link>https://news.google.com/rss/articles/football</link>
    </item></channel></rss>'''
    items = parse_feed_xml(feed, get_rule('espn-atletico-mg'), feed_url='https://news.google.com/rss/')
    assert [item.titulo for item in items] == ['Galo prepara reforços para o Brasileiro']


def test_noataque_sitemap_rejects_mma_url_and_other_atletico():
    xml = '''<urlset><url><loc>https://noataque.com.br/mma/noticia/2026/10/06/galo-vence-no-ufc/</loc><title>Galo vence no UFC</title></url>
    <url><loc>https://noataque.com.br/futebol/noticia/2026/10/06/atletico-de-madrid-vence/</loc><title>Atlético de Madrid vence</title></url>
    <url><loc>https://noataque.com.br/futebol/noticia/2026/10/06/galo-vence/</loc><title>Galo vence no Brasileiro</title></url></urlset>'''
    _, items = parse_sitemap_xml(xml, get_rule('noataque-atletico'), sitemap_url='https://noataque.com.br/sitemap.xml')
    assert [item.titulo for item in items] == ['Galo vence no Brasileiro']
