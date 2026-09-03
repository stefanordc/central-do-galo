# Central do Galo — Radar do X v35

Correção do carregamento progressivo dos embeds nativos do X.

- Remove dependência do IntersectionObserver para ativar os embeds.
- Carrega os 3 primeiros embeds imediatamente.
- Ativa mais 2 embeds a cada 1,2 segundo até completar os itens já carregados da timeline.
- Mantém o HTML do oEmbed visível enquanto widgets.js transforma o tweet, evitando cards presos no fallback.
- Mantém filtro por perfil, paginação de 20 em 20, proxy `/backend`, admin e scraper SeleniumBase UC.
