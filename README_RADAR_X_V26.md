# Central do Galo — Radar do X v26

## Correção

Os logs da v25 mostraram `articles=0`, mas o `body` já continha o perfil e o texto das publicações. Isso confirma que a página pública do X foi renderizada e que o problema estava no parser dependente de `<article>`.

A v26 mantém SeleniumBase UC headless e sem login, mas passa a extrair diretamente do DOM vivo os links canônicos `/<usuario>/status/<id>`. A tag `article` virou apenas fallback.

Também foram mantidos:

- oEmbed oficial para renderização;
- Supabase e estrutura de cache existentes;
- 3 posts por conta;
- intervalo de 3600s;
- 30s entre contas;
- filtro de post fixado, repost de terceiro e reply;
- captura `.html`, `.txt` e `.png` quando a coleta falhar.

## Teste

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python scripts\diagnosticar_x.py
```

O log esperado deve mostrar `status_links > 0` e `posts_live > 0` para `@Atletico`.
