# Radar do X — v22

## Mudança da fonte de descoberta

O endpoint `syndication.twitter.com` passou a retornar HTTP 429. A v22 deixa de usá-lo como fonte.

Fluxo atual:

1. Consulta páginas públicas de espelhos (`TwStalker`, com `Sotwe` como fallback).
2. Extrai somente links no padrão `/<usuario>/status/<tweet_id>`.
3. Deduplica e calcula a data pelo Snowflake do tweet.
4. Converte a URL canônica `https://x.com/<usuario>/status/<id>` pelo `publish.x.com/oembed`.
5. Salva HTML nativo e metadados no `posts_x` do Supabase.
6. O frontend continua renderizando o embed oficial do X via `widgets.js`.

O HTML fornecido para `@Atletico` confirma o padrão `article[data-testid="tweet"]` e links `/Atletico/status/<id>`. A parser do DOM do X continua no projeto para compatibilidade/testes, mas a coleta automática não depende mais de o X entregar esse DOM ao navegador headless.

## Risco

A descoberta depende de páginas de terceiros não oficiais. Elas podem mudar, bloquear requisições ou ficar indisponíveis. O cache do Supabase reduz a dependência em tempo real. O embed exibido ao usuário continua vindo do X.

## Teste

```powershell
python scripts\diagnosticar_x.py
```

Se `@Atletico` produzir 3 URLs e os 3 oEmbeds forem válidos, o script continua para as demais contas.
