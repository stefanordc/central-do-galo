# Central do Galo — Notícias v4

## Novidades

- Estado de Minas removido; No Ataque permanece como fonte do grupo.
- Coletor recente passa a percorrer também páginas adicionais das fontes que suportam paginação.
- Backfill histórico explícito com `--historico`.
- Descoberta por sitemap XML recursivo quando a fonte publica sitemaps e o `robots.txt` permite.
- Busca no histórico por título e resumo (`/api/noticias?q=Savinho`).
- Frontend com campo de pesquisa e botão **Carregar mais notícias**.
- Histórico fica persistido no PostgreSQL/Supabase; execuções futuras ignoram URLs já cadastradas.

## Coleta recente

```powershell
python scripts\coletar_noticias.py --fonte ge-atletico-mg
```

## Preencher histórico de uma fonte

```powershell
python scripts\coletar_noticias.py --fonte ge-atletico-mg --historico
```

O backfill histórico pode demorar bastante. O FalaGalo, por exemplo, possui centenas de páginas de arquivo. O coletor usa pausa entre requisições e respeita `robots.txt`.

## Preencher todas as fontes

```powershell
python scripts\coletar_noticias.py --historico
```

É mais seguro executar uma fonte por vez para acompanhar o progresso e eventuais bloqueios.
