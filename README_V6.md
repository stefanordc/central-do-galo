# Central do Galo — Notícias v6

## Mudanças

- Backfill histórico limitado a 25 páginas por fonte por padrão.
- `--max-paginas N` permite alterar o limite manualmente.
- Sitemaps deixaram de ser varridos automaticamente no `--historico`.
- `--sitemaps` ativa a varredura de sitemaps explicitamente.
- Fonte oficial do Atlético tenta primeiro o RSS da categoria Futebol.
- Se o HTML do Atlético responder 403, o RSS pode continuar alimentando a fonte.

## Histórico de todas as fontes (25 páginas cada)

```powershell
python scripts\coletar_noticias.py --historico
```

## Uma fonte

```powershell
python scripts\coletar_noticias.py --fonte ge-atletico-mg --historico
```

## Site oficial

```powershell
python scripts\coletar_noticias.py --fonte atletico-oficial --historico
```

## Sitemaps (opcional)

```powershell
python scripts\coletar_noticias.py --fonte ge-atletico-mg --historico --sitemaps
```
