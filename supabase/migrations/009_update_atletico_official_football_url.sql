update public.fontes
set url_base = 'https://atletico.com.br/noticias/futebol/',
    atualizado_em = now()
where slug = 'atletico-oficial';
