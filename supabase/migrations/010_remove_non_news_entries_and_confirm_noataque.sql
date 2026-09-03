-- Central do Galo v7
-- Remove páginas institucionais/feeds que foram classificadas incorretamente como notícia.
delete from public.noticias
where lower(titulo) in (
    lower('Atlético Mineiro | CNN Brasil'),
    lower('Wp json'),
    lower('Feed'),
    lower('Quem somos - FalaGalo'),
    lower('FalaGalo - Atlético Mineiro - Galo - Notícias - Tudo sobre o Galo')
)
or url in (
    'https://www.cnnbrasil.com.br/esportes/futebol/atletico-mineiro/',
    'https://falagalo.com.br/wp-json/',
    'https://falagalo.com.br/feed/',
    'https://falagalo.com.br/quem-somos/',
    'https://falagalo.com.br/https-falagalo-com-br/'
);

update public.fontes
set
    url_base = 'https://noataque.com.br/clubes/atletico-mg/',
    atualizado_em = now()
where slug = 'noataque-atletico';
