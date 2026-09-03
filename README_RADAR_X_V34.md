# Central do Galo v34 — carregamento progressivo do Radar do X

- Mantém timeline, filtro por perfil, paginação de 20 e oEmbed nativo.
- Os 2 primeiros tweets iniciam a renderização nativa imediatamente.
- Os demais só hidratam o widget do X quando se aproximam da viewport (IntersectionObserver).
- Enquanto o embed nativo carrega, o texto cacheado fica visível.
- Evita disparar 20 iframes/imagens/vídeos do X simultaneamente.
- Adiciona preconnect/dns-prefetch para platform.x.com, syndication.twitter.com e pbs.twimg.com.
