# Central do Galo — Radar do X v31

## Alterações

- Timeline reduzida para acompanhar a largura real do embed nativo do X (máximo de 550 px).
- Menos espaço vazio à direita de cada tweet.
- Novo seletor suspenso de perfis no topo do Radar do X.
- Opção "Todos os perfis" mantém a timeline global.
- Ao selecionar um perfil, a API pagina somente os posts daquele usuário.
- Paginação continua em blocos de 20 publicações.
- Ordem permanece da publicação mais recente para a mais antiga.
- Layout responsivo preservado.

## API

`GET /api/x/feed` agora aceita opcionalmente `usuario=<handle>`.
