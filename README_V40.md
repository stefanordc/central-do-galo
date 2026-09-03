# Central do Galo — v40 | Página de Vídeos

## Canal inicial
- GaloTV / Atlético
- Vídeos: https://www.youtube.com/@atletico/videos
- Shorts: https://www.youtube.com/@atletico/shorts
- Transmissões: https://www.youtube.com/@atletico/streams

## Implementado
- 10 vídeos, 10 Shorts e 10 transmissões por seção.
- Coleta pública de metadados com yt-dlp; nenhum vídeo é baixado.
- Cache no Supabase usando as tabelas `fontes` e `videos` já existentes.
- Sincronização automática a cada 15 minutos.
- Script manual `backend/scripts/sincronizar_youtube.py`.
- Reprodução pelo player incorporado oficial do YouTube.
- O usuário permanece no Central do Galo ao iniciar a reprodução.
- Ao trocar entre Notícias, Vídeos e X, o player continua montado e vira mini-player.
- Ao voltar para Vídeos, o mesmo player retorna ao tamanho grande sem reiniciar o vídeo.
- Layout responsivo inspirado na página inicial do YouTube.

## Primeira execução
```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
pip install -r requirements.txt
python scripts\sincronizar_youtube.py
python run.py
```

Em outro terminal:
```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\frontend"
npm run dev
```

Depois acesse `http://localhost:3000` e clique em **Vídeos**.
