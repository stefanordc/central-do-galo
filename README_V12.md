# Central do Galo - v12

## Correções de imagens

- Atlético oficial: extrai imagem de `media:*`, `enclosure` e também de `<img>` dentro de `content:encoded`/`description` do RSS WordPress.
- Notícias oficiais já existentes sem foto são atualizadas quando o feed histórico é executado novamente.
- No Ataque: a busca de thumbnail no Google News passa a localizar o card correspondente ao título da notícia.
- O ícone genérico do Google News usado incorretamente pela v11 é rejeitado.
- Imagens corretas do No Ataque podem substituir a imagem genérica já salva no banco.

## Atualização recomendada

```powershell
python scripts\coletar_noticias.py --fonte noataque-atletico
python scripts\coletar_noticias.py --fonte atletico-oficial --historico --max-paginas 25
```
