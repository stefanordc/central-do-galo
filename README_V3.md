# Central do Galo — Notícias v3

## O que mudou

- Nomes de fontes sem o sufixo "- Atlético".
- URLs corrigidas para ESPN e No Ataque.
- Novas fontes: Rede 98, Lance! e CNN Brasil.
- Novos coletores para No Ataque, Rede 98, Lance!, CNN Brasil e ESPN.
- Categorias normalizadas no banco.
- Classificação automática de novas notícias por regras.
- Uma notícia pode ter mais de uma categoria.
- Filtro por categoria e fonte no frontend.
- API aceita `categoria` e `fonte` em `/api/noticias`.
- Endpoint `/api/categorias`.

## Categorias iniciais

- Pré-jogo
- Pós-jogo
- Financeiro
- Mercado
- Departamento médico
- Treinos
- Entrevistas
- Bastidores
- Institucional
- Arena MRV
- Base
- Futebol feminino
- Torcida
- Geral

## Executar

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

## Testar fontes individualmente

```powershell
python scripts\coletar_noticias.py --fonte rede98-atletico
python scripts\coletar_noticias.py --fonte lance-atletico
python scripts\coletar_noticias.py --fonte cnn-atletico
python scripts\coletar_noticias.py --fonte noataque-atletico
python scripts\coletar_noticias.py --fonte espn-atletico-mg
```

A coleta respeita `robots.txt`. Se uma fonte bloquear o coletor, ela é ignorada sem tentativa de contornar a restrição.
