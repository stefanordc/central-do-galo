# Central do Galo — Notícias v8

## Correções desta versão

- Remove pseudo-notícias institucionais do FalaGalo e CNN.
- Adiciona bloqueio defensivo também na API, para que esses itens nunca sejam exibidos.
- Fotografias de notícias voltam a ser exibidas em cores originais.
- A regra de não usar azul permanece para a interface/identidade visual do portal.
- Corrige o fallback do No Ataque: o coletor consulta RSS público do Google News sem depender do HTML 403 do No Ataque.
- Mantém `https://noataque.com.br/clubes/atletico-mg/` como URL oficial da fonte.

## Testar No Ataque

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python scripts\coletar_noticias.py --fonte noataque-atletico
```

## Rodar backend

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python run.py
```

## Rodar frontend

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\frontend"
npm run dev
```
