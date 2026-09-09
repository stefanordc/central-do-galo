alter table public.estatisticas_jogadores_sofascore
  add column if not exists nome_guerra text;

update public.estatisticas_jogadores_sofascore
set nome_guerra = nome
where nome_guerra is null or btrim(nome_guerra) = '';

create index if not exists idx_estatisticas_jogadores_nome_guerra
  on public.estatisticas_jogadores_sofascore (nome_guerra);
