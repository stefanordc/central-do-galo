# Central do Galo v18 — correção do Radar do X

## Causa raiz encontrada

Na inspeção do Supabase, `posts_x` estava com **0 registros** e todas as contas do `contas_x` estavam sem `x_user_id`, sem `ultimo_post_id` e sem `ultima_sincronizacao`. Portanto o problema acontecia antes do frontend/oEmbed: o job nunca havia populado o cache.

Na v17 também havia dois pontos que escondiam o diagnóstico:

1. O workflow n8n entregue era apenas um template (`active: false`) e o FastAPI não possuía job automático do X.
2. Falhas de oEmbed eram capturadas com `except Exception: pass`, portanto eram engolidas sem log.

A fonte continua oficial: X API v2 (`api.x.com/2`) para descobrir posts e `publish.x.com/oembed` para gerar o HTML nativo.

## O que foi corrigido

- Job Python automático no FastAPI, por padrão a cada 15 minutos (`X_SYNC_ENABLED=true`).
- O job só inicia se `X_BEARER_TOKEN` estiver configurado.
- Se o token estiver ausente, o backend registra erro explícito em vez de falhar silenciosamente.
- Logging por etapa: lookup do usuário, busca de posts, status HTTP, oEmbed, upsert no Supabase, reparo de embeds e resumo final.
- Tratamento explícito para HTTP 401, 403 e 429 da X API.
- O rate-limit reset é incluído no erro quando o X enviar o header correspondente.
- Validação do oEmbed: URL de status, HTTP, JSON, HTML não vazio e presença de `twitter-tweet`/`blockquote`.
- Falhas de oEmbed são gravadas em `posts_x.metadados.oembed_erro` e aparecem no log.
- Novo endpoint `GET /api/x/status` para ver cache e configuração sem expor o token.
- `POST /api/x/sync?conta=Atletico` permite testar uma conta isoladamente.
- `python scripts/sincronizar_x.py --conta Atletico` faz o mesmo no terminal.
- Novo `python scripts/diagnosticar_x.py`, que verifica configuração, Supabase e testa somente @Atletico.
- O frontend diferencia cache vazio de embed quebrado; não chama tudo de "Publicação indisponível".

## Variáveis do backend

Adicione ao `backend/.env`:

```env
X_BEARER_TOKEN=SEU_BEARER_TOKEN_DA_X_API
X_SYNC_SECRET=UM_SEGREDO_FORTE
X_SYNC_ENABLED=true
X_SYNC_INTERVAL_SECONDS=900
X_SYNC_INITIAL_DELAY_SECONDS=5
X_SYNC_TIMEOUT_SECONDS=30
X_SYNC_FETCH_LIMIT=10
```

Se preferir que o n8n seja o único scheduler, use:

```env
X_SYNC_ENABLED=false
```

## Diagnóstico recomendado

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python scripts\diagnosticar_x.py
```

O script **não imprime o token**.

### Primeiro teste: somente @Atletico

```powershell
python scripts\sincronizar_x.py --conta Atletico
```

Depois confira:

```text
http://127.0.0.1:8000/api/x/status
http://127.0.0.1:8000/api/x/posts?limit_por_conta=3
```

Se @Atletico estiver com posts e `embeds_ok > 0`, execute as demais:

```powershell
python scripts\sincronizar_x.py
```

## Logs esperados

Exemplo de sucesso:

```text
[ @Atletico ] resolvendo username na X API
[ @Atletico ] buscando posts recentes (primeira carga)
[oEmbed] resposta HTTP 200
[ @Atletico ] Supabase upsert post=... inserido=True embed=ok
[ @Atletico ] fim: novos=... embeds=... status=ok
```

Exemplos de erro agora explícitos:

```text
401: credencial X inválida, expirada ou não reconhecida
403: credencial sem permissão/acesso para este endpoint ou recurso
429: rate limit da X API atingido
```
