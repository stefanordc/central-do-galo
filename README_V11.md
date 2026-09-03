# Central do Galo — v11

Correção do erro `AttributeError: NewsCollectorRunner has no attribute _google_news_thumbnail`.

O coletor do No Ataque agora pesquisa a matéria na interface pública do Google News e extrai a thumbnail de preview sem acessar a página bloqueada do No Ataque.

## Atualizar imagens do No Ataque

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python scripts\coletar_noticias.py --fonte noataque-atletico
```
