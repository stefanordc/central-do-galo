# Radar do X — v21

## Correção

A coleta direta de `https://x.com/<perfil>` por Chrome headless foi removida como fonte principal porque, nos testes reais, o X carregou a página sem os `article[data-testid="tweet"]` públicos e em alguns casos causou timeout do renderer.

A v21 usa como fonte de descoberta:

`https://syndication.twitter.com/srv/timeline-profile/screen-name/<perfil>`

A resposta HTML é lida apenas para extrair o JSON público `__NEXT_DATA__` usado pela camada de syndication/embed. Não há login, CAPTCHA bypass, proxy, rotação de IP ou tentativa de contornar proteção.

Depois de descobrir até 3 URLs recentes por conta, o fluxo continua usando:

`https://publish.x.com/oembed`

para gerar o HTML nativo do post e gravá-lo em `posts_x` no Supabase.

## Limites conservadores

- 3 posts por conta;
- cache no Supabase;
- intervalo padrão de 1 hora entre jobs;
- 30 segundos entre contas;
- 1 retry com backoff de 10 segundos;
- HTTP 401/403/429 é registrado explicitamente e não é contornado.

## Teste

```powershell
python scripts\diagnosticar_x.py
```

O diagnóstico testa `@Atletico` primeiro. Só continua para as outras contas se pelo menos um embed válido for gravado no Supabase.

## Risco

Esse endpoint não é uma API pública contratual do X. Ele pode mudar, retornar 429 ou deixar de funcionar. A solução continua sendo um fallback temporário e deve manter cache agressivo e baixa frequência.
