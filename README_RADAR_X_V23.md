# Radar do X — v23

## Fonte de descoberta

A v23 usa `x.com/<usuario>` em um perfil dedicado do Chrome com sessão autenticada persistente. O login é feito manualmente uma única vez por `backend/scripts/inicializar_x_login.py`. Depois disso, o job reutiliza a sessão em modo headless.

O parser usa o DOM real do X:

- `article[data-testid="tweet"]`
- `a[href*="/status/"]`
- `div[data-testid="tweetText"]`
- `time[datetime]`

Reposts de terceiros e post fixado são ignorados; somente URLs cujo autor seja o perfil monitorado entram no cache.

## Embed

A descoberta serve apenas para obter URL/ID/data/texto. A aparência continua sendo gerada pelo endpoint oficial `https://publish.x.com/oembed`, e o HTML é cacheado em `posts_x` no Supabase.

## Segurança e limitações

- Não armazena usuário/senha no código.
- Não extrai cookies do perfil pessoal do Chrome.
- A sessão fica somente em `backend/.x_chrome_profile/`, ignorada pelo Git.
- Não usa CAPTCHA bypass, proxy rotativo ou técnicas de evasão.
- Scraping pode violar os Termos do X e quebrar quando o site alterar o DOM; use como solução temporária.
