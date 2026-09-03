# Central do Galo — v10

## Correção de imagens do No Ataque

O fallback do No Ataque usa o RSS público do Google News para descobrir matérias, pois o site do No Ataque retorna HTTP 403 ao coletor.

A partir da v10, quando o RSS não inclui imagem, o coletor consulta apenas a página pública de preview do Google News e procura a thumbnail hospedada em `googleusercontent.com`.

Isso vale tanto para notícias novas quanto para registros já existentes no Supabase que ainda estejam sem `imagem_url`.

### Atualizar as imagens

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python scripts\coletar_noticias.py --fonte noataque-atletico
```

O campo `enriquecidos` indica quantas notícias existentes receberam imagem.

### Rodar o backend

```powershell
python run.py
```

### Rodar o frontend

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\frontend"
npm run dev
```
