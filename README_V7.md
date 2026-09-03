# Central do Galo — v7

## Alterações

- Logo oficial do projeto adicionada ao cabeçalho.
- Favicon/ícone da aba do navegador configurado.
- Paleta da interface sem azul: preto, branco, cinza e dourado.
- Imagens externas das notícias são exibidas em escala de cinza para impedir azul vindo das fotos/fontes.
- Removidos cinco registros que não eram notícias: página do time da CNN, `Wp json`, `Feed`, `Quem somos - FalaGalo` e página institucional do FalaGalo.
- Regras dos coletores atualizadas para impedir que essas páginas voltem ao banco.
- No Ataque continua cadastrado em `https://noataque.com.br/clubes/atletico-mg/`.
- Como a listagem do No Ataque retorna HTTP 403 para o coletor HTTP, foi adicionado um fallback de descoberta via RSS público do Google News filtrado para o domínio No Ataque. Não há tentativa de burlar o bloqueio do site.
- Site oficial do Atlético não tenta abrir o HTML quando o RSS oficial já respondeu com sucesso.

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

Backend: http://127.0.0.1:8000

## Rodar frontend

Em outro terminal:

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\frontend"
npm run dev
```

Frontend: http://localhost:3000
