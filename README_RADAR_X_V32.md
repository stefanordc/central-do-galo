# Central do Galo v32 — correção de comunicação frontend/backend

A v32 mantém a timeline, os embeds nativos do X, paginação de 20 posts e filtro por perfil.

## Correção

O navegador não chama mais `http://127.0.0.1:8000` diretamente. O frontend usa `/backend/...`, e o Next.js encaminha a requisição ao FastAPI via `next.config.mjs`.

Isso evita falhas de CORS/origem/hostname que apareciam como `Failed to fetch` no navegador.

## Execução

Backend:

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python run.py
```

Frontend:

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\frontend"
npm run dev
```

O backend continua obrigatório e deve estar disponível em `127.0.0.1:8000` por padrão.
