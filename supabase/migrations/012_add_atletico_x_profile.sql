insert into public.contas_x (nome, usuario, oficial, confiabilidade, ativo)
values ('Atlético', 'Atletico', true, 100, true)
on conflict (usuario) do update
set nome = excluded.nome,
    oficial = excluded.oficial,
    confiabilidade = excluded.confiabilidade,
    ativo = excluded.ativo;
