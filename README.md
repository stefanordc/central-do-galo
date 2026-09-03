# Central do Galo

Portal do Atlético-MG com notícias, vídeos, Radar do X e áreas de dados.

## Execução local

### Backend

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python run.py
```

API: `http://127.0.0.1:8000`

### Frontend

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\frontend"
npm run dev
```

Site: `http://localhost:3000`

## YouTube

A coleta usa SeleniumBase UC em modo headless, sem login, e lê somente o conteúdo público das abas configuradas em `fontes.configuracao`.

Teste manual:

```powershell
cd backend
python scripts\sincronizar_youtube.py
```

Em caso de falha de DOM, arquivos de diagnóstico são salvos em `backend/.youtube_debug/`.
