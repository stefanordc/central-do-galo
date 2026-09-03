# Radar do X — v37

A timeline não depende mais do `widgets.js` para mostrar mídia.

- O SeleniumBase UC extrai URLs de imagens/thumbnails de `pbs.twimg.com` diretamente do DOM vivo do tweet.
- `posts_x.midia` é atualizado quando a sincronização encontra mídia.
- O frontend renderiza texto cacheado + mídia diretamente, evitando bloqueios `ERR_BLOCKED_BY_CLIENT` do embed nativo.
- Links no conteúdo abrem em nova aba.
- O oEmbed continua sendo armazenado no backend para compatibilidade/fallback, mas a timeline não precisa do script do X para funcionar.

Após instalar a versão, execute `python scripts\sincronizar_x.py` uma vez para preencher mídia dos posts recentes.
