from app.services.x_scrape_service import XScrapeService


def test_extrair_posts_html_ignora_fixado_e_repost() -> None:
    html = '''
    <html><body>
      <article data-testid="tweet">
        <div data-testid="socialContext">Fixado</div>
        <a href="/Atletico/status/100"><time datetime="2026-08-27T10:00:00.000Z"></time></a>
        <div data-testid="tweetText">Fixado antigo</div>
      </article>
      <article data-testid="tweet">
        <a href="/Outro/status/999"><time datetime="2026-08-27T11:00:00.000Z"></time></a>
        <div data-testid="tweetText">Repost de terceiro</div>
      </article>
      <article data-testid="tweet">
        <a href="/Atletico/status/200"><time datetime="2026-08-27T12:00:00.000Z"></time></a>
        <div data-testid="tweetText">Post real do Galo</div>
        <div data-testid="reply" aria-label="12 Replies"></div>
        <div data-testid="retweet" aria-label="34 Reposts"></div>
        <div data-testid="like" aria-label="1,2K Likes"></div>
      </article>
    </body></html>
    '''
    posts = XScrapeService.extrair_posts_html(html, "Atletico", limite=3)
    assert len(posts) == 1
    assert posts[0].post_id == "200"
    assert posts[0].url == "https://x.com/Atletico/status/200"
    assert posts[0].texto == "Post real do Galo"
    assert posts[0].metricas["reply_count"] == 12
    assert posts[0].metricas["retweet_count"] == 34
    assert posts[0].metricas["like_count"] == 1200


def test_sanitizar_oembed_remove_script() -> None:
    html = (
        '<blockquote class="twitter-tweet"><p>Galo</p></blockquote>'
        '<script src="https://platform.x.com/widgets.js"></script>'
    )
    limpo = XScrapeService.sanitizar_oembed_html(html)
    assert limpo is not None
    assert "twitter-tweet" in limpo
    assert "<script" not in limpo.lower()


def test_detectar_bloqueio_login() -> None:
    motivo = XScrapeService._detectar_bloqueio(
        '<a href="/i/flow/login">Log in to X</a>'
    )
    assert motivo is not None
    assert "login" in motivo.lower()


def test_extrair_posts_syndication_html_ordena_e_filtra_autor() -> None:
    payload = {
        "props": {
            "pageProps": {
                "timeline": {
                    "entries": [
                        {
                            "type": "tweet",
                            "entry_id": "tweet-200",
                            "sort_index": "200",
                            "content": {
                                "tweet": {
                                    "id_str": "200",
                                    "created_at": "Wed, 27 Aug 2026 14:00:00 +0000",
                                    "full_text": "Segundo post",
                                    "favorite_count": 20,
                                    "reply_count": 2,
                                    "retweet_count": 3,
                                    "quote_count": 1,
                                    "entities": {"media": []},
                                    "user": {
                                        "screen_name": "Atletico",
                                        "name": "Atlético",
                                        "profile_image_url_https": "https://pbs.twimg.com/profile.jpg",
                                        "verified": True,
                                        "is_blue_verified": False,
                                    },
                                }
                            },
                        },
                        {
                            "type": "tweet",
                            "entry_id": "tweet-999",
                            "sort_index": "999",
                            "content": {
                                "tweet": {
                                    "id_str": "999",
                                    "created_at": "Wed, 27 Aug 2026 15:00:00 +0000",
                                    "full_text": "Post de terceiro",
                                    "favorite_count": 99,
                                    "reply_count": 9,
                                    "retweet_count": 9,
                                    "quote_count": 9,
                                    "entities": {"media": []},
                                    "user": {"screen_name": "Outro", "name": "Outro"},
                                }
                            },
                        },
                        {
                            "type": "tweet",
                            "entry_id": "tweet-300",
                            "sort_index": "300",
                            "content": {
                                "tweet": {
                                    "id_str": "300",
                                    "created_at": "Wed, 27 Aug 2026 16:00:00 +0000",
                                    "full_text": "Post mais recente",
                                    "favorite_count": 30,
                                    "reply_count": 4,
                                    "retweet_count": 5,
                                    "quote_count": 2,
                                    "entities": {"media": []},
                                    "user": {
                                        "screen_name": "Atletico",
                                        "name": "Atlético",
                                        "profile_image_url_https": "https://pbs.twimg.com/profile.jpg",
                                        "verified": True,
                                    },
                                }
                            },
                        },
                    ]
                }
            }
        }
    }
    import json

    html = (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + '</script></body></html>'
    )
    posts = XScrapeService.extrair_posts_syndication_html(html, "Atletico", limite=3)
    assert [post.post_id for post in posts] == ["300", "200"]
    assert posts[0].url == "https://x.com/Atletico/status/300"
    assert posts[0].metricas["like_count"] == 30
    assert posts[0].autor_verificado is True


def test_extrair_posts_mirror_html_deduplica_e_ordena_snowflake() -> None:
    html = """
    <html><body>
      <a href="/Atletico/status/2092786798845984772">14 horas atrás</a>
      <a href="/Atletico/status/2092786798845984772">View Details</a>
      <a href="/Atletico/status/2092981512438272443">1 hora atrás</a>
      <a href="/Atletico/status/2092981512438272443">View Details</a>
      <a href="/Outro/status/999999999999999999">terceiro</a>
      <a href="/Atletico/status/2092957030415749202">3 horas atrás</a>
    </body></html>
    """
    posts = XScrapeService.extrair_posts_mirror_html(html, "Atletico", limite=3)
    assert [post.post_id for post in posts] == [
        "2092981512438272443",
        "2092957030415749202",
        "2092786798845984772",
    ]
    assert posts[0].url == "https://x.com/Atletico/status/2092981512438272443"
    assert posts[0].publicado_em is not None
    assert posts[0].publicado_em.isoformat().startswith("2026-08-27T14:24:12")


def test_datetime_from_snowflake_confere_html_real_fornecido() -> None:
    dt = XScrapeService._datetime_from_snowflake("2092957030415749202")
    assert dt is not None
    assert dt.isoformat().startswith("2026-08-27T12:46:55")


def test_extrair_posts_html_fallback_role_article_e_ignora_reply() -> None:
    html = '''
    <html><body>
      <article role="article">
        <div>Replying to @Outro</div>
        <a href="/Atletico/status/2093000000000000001">
          <time datetime="2026-08-27T15:00:00.000Z"></time>
        </a>
        <div data-testid="tweetText">Resposta que não deve entrar</div>
      </article>
      <article role="article">
        <a href="/Atletico/status/2093000000000000002">
          <time datetime="2026-08-27T16:00:00.000Z"></time>
        </a>
        <div data-testid="tweetText">Publicação própria</div>
      </article>
    </body></html>
    '''
    posts = XScrapeService.extrair_posts_html(html, "Atletico", limite=3)
    assert [post.post_id for post in posts] == ["2093000000000000002"]


def test_detectar_bloqueio_login_wall_publico() -> None:
    motivo = XScrapeService._detectar_bloqueio(
        "<html><body>Don't miss what's happening. Log in to X</body></html>",
        "Don't miss what's happening",
        "https://x.com/Atletico",
    )
    assert motivo == "X exibiu login-wall para acesso anônimo"


def test_detectar_bloqueio_fluxo_login_por_url() -> None:
    motivo = XScrapeService._detectar_bloqueio(
        "<html></html>",
        "",
        "https://x.com/i/flow/login?redirect_after_login=%2FAtletico",
    )
    assert motivo == "X redirecionou para fluxo de login"


def test_normalizar_posts_dom_vivo_sem_article() -> None:
    rows = [
        {
            "href": "/Atletico/status/2092981512438272443",
            "datetime": "2026-08-27T14:24:12.000Z",
            "text": "Post mais recente",
            "social_context": "",
            "root_text": "Atlético @Atletico Post mais recente",
            "metrics": {"reply": "12 Replies", "retweet": "34 Reposts", "like": "1,2K Likes"},
            "photos": ["https://pbs.twimg.com/media/exemplo.jpg"],
        },
        {
            "href": "/Atletico/status/2092957030415749202",
            "datetime": "2026-08-27T12:46:55.000Z",
            "text": "Post anterior",
            "social_context": "",
            "root_text": "Atlético @Atletico Post anterior",
            "metrics": {},
            "photos": [],
        },
        {
            "href": "/Atletico/status/2092786798845984772",
            "datetime": "2026-08-27T01:30:29.000Z",
            "text": "Resposta",
            "social_context": "",
            "root_text": "Em resposta a @Outro Resposta",
            "metrics": {},
            "photos": [],
        },
        {
            "href": "/Outro/status/999999999999999999",
            "datetime": "2026-08-27T15:00:00.000Z",
            "text": "Terceiro",
            "social_context": "",
            "root_text": "Outro",
            "metrics": {},
            "photos": [],
        },
    ]

    posts = XScrapeService._normalizar_posts_dom_vivo(rows, "Atletico", limite=3)
    assert [post.post_id for post in posts] == [
        "2092981512438272443",
        "2092957030415749202",
    ]
    assert posts[0].texto == "Post mais recente"
    assert posts[0].metricas["reply_count"] == 12
    assert posts[0].metricas["retweet_count"] == 34
    assert posts[0].metricas["like_count"] == 1200
    assert posts[0].midia == [{"type": "photo", "url": "https://pbs.twimg.com/media/exemplo.jpg"}]


def test_texto_do_oembed_html_recupera_texto_do_tweet() -> None:
    html = (
        '<blockquote class="twitter-tweet"><p lang="pt" dir="ltr">'
        'Galo pronto para o jogo! <a href="https://t.co/abc">pic.twitter.com/abc</a>'
        '</p>&mdash; Atlético (@Atletico) <a href="https://x.com/Atletico/status/1">data</a>'
        '</blockquote>'
    )
    texto = XScrapeService.texto_do_oembed_html(html)
    assert texto == "Galo pronto para o jogo! pic.twitter.com/abc"
