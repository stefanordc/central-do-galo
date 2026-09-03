insert into public.fontes (
    nome,
    slug,
    tipo,
    url_base,
    confiabilidade,
    oficial,
    ativo,
    configuracao
)
values (
    'Itatiaia - Atlético',
    'itatiaia-atletico',
    'noticia',
    'https://www.itatiaia.com.br/esportes/futebol/futebol-nacional/futebol-mineiro/atletico/',
    95,
    false,
    true,
    '{"coleta":"pagina_atletico"}'::jsonb
)
on conflict (slug) do update
set nome = excluded.nome,
    url_base = excluded.url_base,
    confiabilidade = excluded.confiabilidade,
    oficial = excluded.oficial,
    ativo = excluded.ativo,
    configuracao = public.fontes.configuracao || excluded.configuracao,
    atualizado_em = now();
