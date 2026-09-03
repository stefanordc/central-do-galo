insert into public.fontes (
    nome,
    slug,
    tipo,
    url_base,
    url_feed,
    confiabilidade,
    oficial,
    ativo,
    configuracao
)
values (
    'GaloTV | Atlético',
    'youtube-atletico',
    'youtube',
    'https://www.youtube.com/@atletico',
    null,
    100,
    true,
    true,
    jsonb_build_object(
        'plataforma', 'youtube',
        'handle', '@atletico',
        'videos_url', 'https://www.youtube.com/@atletico/videos',
        'shorts_url', 'https://www.youtube.com/@atletico/shorts',
        'streams_url', 'https://www.youtube.com/@atletico/streams'
    )
)
on conflict (slug) do update
set nome = excluded.nome,
    tipo = excluded.tipo,
    url_base = excluded.url_base,
    confiabilidade = excluded.confiabilidade,
    oficial = excluded.oficial,
    ativo = true,
    configuracao = public.fontes.configuracao || excluded.configuracao,
    atualizado_em = now();
