# Central do Galo — Radar do X v28

## Mudança principal
O Radar do X agora é uma timeline única, ordenada do post mais recente para o mais antigo.

- 20 publicações por carregamento.
- Botão "Carregar mais publicações".
- Usa o endpoint já existente `GET /api/x/feed?limit=20&offset=N`.
- Mantém o histórico acumulado no Supabase.
- Fotos armazenadas em `posts_x.midia` são exibidas diretamente na timeline quando disponíveis.
- Cada publicação mantém link para a postagem original no X.
- A coleta SeleniumBase UC, o job de 3600s e o intervalo entre contas não foram alterados.
