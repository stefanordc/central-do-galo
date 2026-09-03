# Central do Galo v17 — X API + oEmbed cacheado

## O que mudou

- As timelines incorporadas por perfil foram removidas.
- `contas_x` passou a guardar dados de sincronização da X API.
- `posts_x` passou a guardar métricas, mídia, status e HTML nativo do oEmbed.
- `GET /api/x/posts?limit_por_conta=3` retorna as 3 publicações mais recentes por conta.
- `GET /api/x/feed` retorna o histórico em ordem cronológica global.
- `POST /api/x/sync` executa a sincronização oficial com X API v2 + publish.x.com/oembed.
- `backend/scripts/sincronizar_x.py` permite executar a sincronização manualmente.
- `n8n/central-do-galo-x-sync.json` é um workflow-base para atualização a cada 15 minutos.
- O frontend usa `widgets.js` uma única vez para transformar o HTML oEmbed cacheado em embeds nativos.
- Se o embed falhar, o frontend exibe um fallback com a conta/post e link para o X.

## Variáveis necessárias

Adicione ao `backend/.env`:

```env
X_BEARER_TOKEN=SEU_TOKEN_DA_X_API
X_SYNC_SECRET=UM_SEGREDO_FORTE_PARA_O_N8N
X_SYNC_TIMEOUT_SECONDS=30
X_SYNC_FETCH_LIMIT=10
```

## Primeira sincronização

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python scripts\sincronizar_x.py
```

Após a primeira sincronização, os IDs das contas, fotos, posts e embeds ficam cacheados no Supabase.

## Backend

```powershell
python run.py
```

Endpoints:

- `GET http://127.0.0.1:8000/api/x/contas`
- `GET http://127.0.0.1:8000/api/x/posts?limit_por_conta=3`
- `GET http://127.0.0.1:8000/api/x/feed`
- `POST http://127.0.0.1:8000/api/x/sync`

## Frontend

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\frontend"
npm run dev
```

Abra `http://localhost:3000` e acesse a seção **X**.
