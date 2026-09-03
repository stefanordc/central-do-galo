# Central do Galo v38 — mídia do Radar do X

- Corrige a coleta de mídia lazy-loaded do X.
- Quando um dos 3 posts selecionados contém `pic.twitter.com` mas chega sem `midia`, o scraper abre a página canônica do tweet e aguarda especificamente URLs `pbs.twimg.com`.
- Mescla mídia encontrada por diferentes parsers do mesmo post em vez de descartá-la.
- Adiciona proxy restrito `/api/x/media` para servir somente imagens do CDN `pbs.twimg.com` pelo backend.
- O frontend usa `/backend/api/x/media?...`, evitando bloqueios do navegador/extensões contra domínios do X.
- Mantém timeline, filtro por perfil, paginação de 20 em 20, admin e SeleniumBase UC.
