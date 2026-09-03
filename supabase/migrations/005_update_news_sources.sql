update public.fontes set nome='Atlético', atualizado_em=now() where slug='atletico-oficial';
update public.fontes set nome='ge', atualizado_em=now() where slug='ge-atletico-mg';
update public.fontes set nome='Itatiaia', atualizado_em=now() where slug='itatiaia-atletico';
update public.fontes set nome='O TEMPO Sports', atualizado_em=now() where slug='otempo-atletico';
update public.fontes set nome='No Ataque', url_base='https://noataque.com.br/clubes/atletico-mg/', atualizado_em=now() where slug='noataque-atletico';
update public.fontes set nome='ESPN', url_base='https://www.espn.com.br/futebol/time/_/id/7632/bra.atltico-mg', atualizado_em=now() where slug='espn-atletico-mg';

insert into public.fontes (nome,slug,tipo,url_base,confiabilidade,oficial,ativo,configuracao)
values
('Rede 98','rede98-atletico','noticia','https://rede98.com.br/esportes/atletico/',90,false,true,'{}'::jsonb),
('Lance!','lance-atletico','noticia','https://www.lance.com.br/atletico-mineiro',90,false,true,'{}'::jsonb),
('CNN Brasil','cnn-atletico','noticia','https://www.cnnbrasil.com.br/tudo-sobre/atletico-mineiro/',90,false,true,'{}'::jsonb)
on conflict (slug) do update
set nome=excluded.nome,
    url_base=excluded.url_base,
    confiabilidade=excluded.confiabilidade,
    ativo=true,
    atualizado_em=now();
