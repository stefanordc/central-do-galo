# Central do Galo — Notícias v5

Atualização da fonte oficial do Clube Atlético Mineiro.

- Fonte oficial: https://atletico.com.br/noticias/futebol/
- O coletor `atletico-oficial` usa essa seção como listagem principal.
- O banco de produção já foi atualizado.

## Coleta

```powershell
cd backend
python scripts\coletar_noticias.py --fonte atletico-oficial
```

Para carga histórica:

```powershell
python scripts\coletar_noticias.py --fonte atletico-oficial --historico
```
