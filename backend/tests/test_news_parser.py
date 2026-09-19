from app.collectors.models import ArticleCandidate
from app.collectors.parser import extract_article_metadata, extract_candidates
from app.collectors.rules import get_rule


def test_extract_ge_candidate() -> None:
    html = """
    <html><body>
      <h2><a href="/futebol/times/atletico-mg/noticia/2026/08/24/noticia-do-galo.ghtml">
        Atlético-MG prepara novidades para o próximo clássico
      </a></h2>
      <a href="/futebol/times/cruzeiro/noticia/2026/08/24/outra.ghtml">Cruzeiro prepara clássico</a>
    </body></html>
    """
    result = extract_candidates(html, get_rule("ge-atletico-mg"))
    assert len(result) == 1
    assert result[0].titulo == "Atlético-MG prepara novidades para o próximo clássico"


def test_extract_jsonld_metadata() -> None:
    candidate = ArticleCandidate(
        titulo="Título inicial",
        url="https://exemplo.com/noticia",
    )
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context":"https://schema.org",
        "@type":"NewsArticle",
        "headline":"Título definitivo",
        "description":"Resumo da notícia.",
        "datePublished":"2026-08-24T14:30:00-03:00",
        "image":{"url":"https://exemplo.com/foto.jpg"},
        "articleSection":"Atlético"
      }
      </script>
    </head></html>
    """
    result = extract_article_metadata(html, candidate)
    assert result.titulo == "Título definitivo"
    assert result.resumo == "Resumo da notícia."
    assert result.imagem_url == "https://exemplo.com/foto.jpg"
    assert result.categoria == "Atlético"
    assert result.publicado_em is not None


def test_extract_itatiaia_candidate() -> None:
    html = """
    <html><body>
      <a href="/esportes/futebol/futebol-nacional/futebol-mineiro/atletico/atletico-ganha-reforco-para-classico/">
        Atlético ganha reforço para clássico contra o Cruzeiro pela Copa do Brasil
      </a>
      <a href="/esportes/futebol/futebol-nacional/futebol-mineiro/cruzeiro/noticia-do-cruzeiro/">
        Cruzeiro prepara novidades para o clássico
      </a>
    </body></html>
    """
    result = extract_candidates(html, get_rule("itatiaia-atletico"))
    assert len(result) == 1
    assert result[0].titulo.startswith("Atlético ganha reforço")


def test_parse_atletico_official_feed() -> None:
    from app.collectors.parser import parse_feed_xml

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Galo pronto para o clássico</title>
          <link>https://atletico.com.br/galo-pronto-para-o-classico/</link>
          <pubDate>Tue, 25 Aug 2026 12:00:00 -0300</pubDate>
          <description><![CDATA[Preparacao do Atletico para a partida.]]></description>
        </item>
      </channel>
    </rss>'''.encode("utf-8")
    result = parse_feed_xml(
        xml,
        get_rule("atletico-oficial"),
        feed_url="https://atletico.com.br/noticias/futebol/feed/",
    )
    assert len(result) == 1
    assert result[0].titulo == "Galo pronto para o clássico"
    assert result[0].url == "https://atletico.com.br/galo-pronto-para-o-classico/"
    assert result[0].publicado_em is not None


def test_falagalo_ignora_paginas_que_nao_sao_noticias() -> None:
    html = """
    <html><body>
      <a href="https://falagalo.com.br/feed/">Feed</a>
      <a href="https://falagalo.com.br/wp-json/">Wp json</a>
      <a href="https://falagalo.com.br/quem-somos/">Quem somos - FalaGalo</a>
      <a href="https://falagalo.com.br/galo-pronto-para-o-classico/">Galo pronto para o clássico</a>
    </body></html>
    """
    result = extract_candidates(html, get_rule("falagalo"))
    assert len(result) == 1
    assert result[0].titulo == "Galo pronto para o clássico"


def test_cnn_ignora_pagina_do_time() -> None:
    html = """
    <html><body>
      <a href="https://www.cnnbrasil.com.br/esportes/futebol/atletico-mineiro/">
        Atlético Mineiro | CNN Brasil
      </a>
      <a href="https://www.cnnbrasil.com.br/esportes/futebol/atletico-mineiro-vence-classico/">
        Atlético-MG vence clássico e avança
      </a>
    </body></html>
    """
    result = extract_candidates(html, get_rule("cnn-atletico"))
    assert len(result) == 1
    assert "vence clássico" in result[0].titulo


def test_noataque_google_news_feed_fallback() -> None:
    from app.collectors.parser import parse_feed_xml

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Atlético define escalação para clássico - No Ataque</title>
          <link>https://news.google.com/rss/articles/ABC123</link>
          <pubDate>Tue, 25 Aug 2026 12:00:00 -0300</pubDate>
          <source url="https://noataque.com.br">No Ataque</source>
        </item>
      </channel>
    </rss>'''.encode("utf-8")
    result = parse_feed_xml(
        xml,
        get_rule("noataque-atletico"),
        feed_url="https://news.google.com/rss/search?q=noataque",
    )
    assert len(result) == 1
    assert result[0].titulo == "Atlético define escalação para clássico"
    assert result[0].url.startswith("https://news.google.com/")


def test_extract_google_news_thumbnail() -> None:
    from app.collectors.parser import extract_google_news_thumbnail

    html = """
    <html><head></head><body>
      <img src="https://www.gstatic.com/images/icons/material/system/2x/menu_grey600_24dp.png">
      <img src="https://lh3.googleusercontent.com/abc123=s0-w300">
    </body></html>
    """
    assert extract_google_news_thumbnail(html) == "https://lh3.googleusercontent.com/abc123=s0-w300"


def test_extract_google_news_thumbnail_prefere_og_image() -> None:
    from app.collectors.parser import extract_google_news_thumbnail

    html = """
    <html><head>
      <meta property="og:image" content="https://lh3.googleusercontent.com/hero=s0-w800">
    </head><body></body></html>
    """
    assert extract_google_news_thumbnail(html) == "https://lh3.googleusercontent.com/hero=s0-w800"



def test_parse_atletico_feed_extrai_imagem_do_content_encoded() -> None:
    from app.collectors.parser import parse_feed_xml

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <item>
          <title>Massa define detalhes do Manto 2026/27</title>
          <link>https://atletico.com.br/massa-define-detalhes-do-manto-2026-27/</link>
          <description><![CDATA[Resumo sem foto.]]></description>
          <content:encoded><![CDATA[
            <figure><img src="https://atletico.com.br/wp-content/uploads/2026/08/manto.jpg" /></figure>
            <p>Texto da matéria</p>
          ]]></content:encoded>
        </item>
      </channel>
    </rss>'''.encode("utf-8")
    result = parse_feed_xml(
        xml,
        get_rule("atletico-oficial"),
        feed_url="https://atletico.com.br/noticias/futebol/feed/",
    )
    assert len(result) == 1
    assert result[0].imagem_url == "https://atletico.com.br/wp-content/uploads/2026/08/manto.jpg"


def test_google_news_thumbnail_escolhe_card_do_titulo_e_ignora_logo_generica() -> None:
    from app.collectors.parser import extract_google_news_thumbnail

    html = '''
    <html><body>
      <img alt="Google News" src="https://lh3.googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc=s0-w300">
      <article>
        <a>PVC vê problema no Atlético e analisa clássico com Cruzeiro</a>
        <img width="220" height="132" src="https://lh3.googleusercontent.com/foto-real=s0-w440-h264">
      </article>
      <article>
        <a>Outra notícia qualquer</a>
        <img width="220" height="132" src="https://lh3.googleusercontent.com/outra=s0-w440-h264">
      </article>
    </body></html>
    '''
    result = extract_google_news_thumbnail(
        html,
        target_title="PVC vê problema no Atlético e analisa clássico com Cruzeiro",
    )
    assert result == "https://lh3.googleusercontent.com/foto-real=s0-w440-h264"

def test_falagalo_usa_rss_como_fonte_principal() -> None:
    rule = get_rule("falagalo")
    assert rule.prefer_feed is True
    assert "https://falagalo.com.br/feed/" in rule.feed_urls


def test_espn_aceita_artigos_em_diferentes_editorias() -> None:
    html = """
    <html><body>
      <a href="https://www.espn.com.br/futebol/santos/artigo/_/id/17234883/atletico-mg-prepara-time">
        Atlético-MG prepara time para a próxima rodada
      </a>
      <a href="https://www.espn.com.br/futebol/copa-do-brasil/artigo/_/id/17234097/galo-busca-vaga">
        Galo busca vaga na Copa do Brasil
      </a>
      <a href="https://www.espn.com.br/futebol/flamengo/artigo/_/id/17230000/noticia-do-flamengo">
        Flamengo prepara time para a próxima rodada
      </a>
    </body></html>
    """
    result = extract_candidates(html, get_rule("espn-atletico-mg"))
    assert len(result) == 2
    assert {item.titulo for item in result} == {
        "Atlético-MG prepara time para a próxima rodada",
        "Galo busca vaga na Copa do Brasil",
    }

def test_parse_espn_json_news_filtra_atletico_por_categoria() -> None:
    from app.collectors.parser import parse_json_news

    payload = """
    {
      "articles": [
        {
          "id": "17271374",
          "headline": "Atlético-MG x Chapecoense: onde assistir ao vivo",
          "description": "O Galo entra em campo pelo Brasileirão.",
          "published": "2026-09-18T18:00:00Z",
          "images": [
            {"type": "header", "url": "https://a.espncdn.com/photo/galo.jpg"}
          ],
          "categories": [
            {"type": "team", "teamId": 7632, "description": "Atlético-MG"}
          ],
          "links": {
            "web": {
              "href": "https://www.espn.com.br/futebol/brasileirao/artigo/_/id/17271374/atletico-mg-x-chapecoense"
            }
          }
        },
        {
          "id": "17270000",
          "headline": "Flamengo prepara novidades para a rodada",
          "description": "Notícia de outro clube.",
          "categories": [
            {"type": "team", "teamId": 819, "description": "Flamengo"}
          ],
          "links": {
            "web": {
              "href": "https://www.espn.com.br/futebol/brasileirao/artigo/_/id/17270000/flamengo-prepara-novidades"
            }
          }
        }
      ]
    }
    """

    result = parse_json_news(
        payload,
        get_rule("espn-atletico-mg"),
        api_url="https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/news",
    )

    assert len(result) == 1
    assert result[0].titulo == "Atlético-MG x Chapecoense: onde assistir ao vivo"
    assert result[0].imagem_url == "https://a.espncdn.com/photo/galo.jpg"
    assert result[0].publicado_em is not None


def test_parse_espn_json_news_aceita_categoria_mesmo_sem_nome_no_titulo() -> None:
    from app.collectors.parser import parse_json_news

    payload = """
    {
      "articles": [
        {
          "headline": "Renan Lodi revela bastidores após classificação",
          "description": "Lateral do time mineiro falou depois da partida.",
          "categories": [
            {"type": "team", "teamId": 7632, "description": "Atlético-MG"}
          ],
          "links": {
            "web": {
              "href": "https://www.espn.com.br/futebol/atletico-mg/artigo/_/id/17269531/renan-lodi-revela-bastidores"
            }
          }
        }
      ]
    }
    """

    result = parse_json_news(
        payload,
        get_rule("espn-atletico-mg"),
        api_url="https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/news",
    )

    assert len(result) == 1
    assert result[0].titulo == "Renan Lodi revela bastidores após classificação"

