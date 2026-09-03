from app.services.x_sync_service import XSyncService


def test_sanitizar_oembed_remove_script() -> None:
    html = (
        '<blockquote class="twitter-tweet"><p>Galo</p></blockquote>'
        '<script src="https://platform.x.com/widgets.js"></script>'
    )
    limpo = XSyncService.sanitizar_oembed_html(html)

    assert limpo is not None
    assert "twitter-tweet" in limpo
    assert "<script" not in limpo.lower()


def test_sanitizar_oembed_vazio() -> None:
    assert XSyncService.sanitizar_oembed_html(None) is None
    assert XSyncService.sanitizar_oembed_html("") is None
