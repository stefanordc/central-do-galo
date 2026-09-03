# Central do Galo v33 — correção do filtro do Radar do X

Corrige o endpoint `GET /api/x/feed` quando `usuario` não é informado.

A v31/v32 montava a cláusula SQL com `%s is null`, e o PostgreSQL/psycopg não conseguia inferir o tipo do parâmetro `None`, gerando `IndeterminateDatatype`.

A v33 monta a cláusula de filtro somente quando um perfil foi realmente selecionado. Assim:

- `GET /api/x/feed?limit=20&offset=0` lista todos os perfis;
- `GET /api/x/feed?limit=20&offset=0&usuario=Atletico` filtra por `@Atletico`;
- timeline, proxy do Next.js, embeds, paginação, admin e scraping permanecem inalterados.
