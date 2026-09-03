-- Garante o cadastro/ativação dos perfis usados na validação do Radar do X.
-- Observação: o handle correto já utilizado no projeto é @Igortep (I maiúsculo),
-- não @lgortep (L minúsculo).

insert into public.contas_x (nome, usuario, oficial, confiabilidade, ativo)
values
    ('Atlético', 'Atletico', true, 100, true),
    ('@pedfaria', 'pedfaria', false, 80, true),
    ('@ohenriqueandre', 'ohenriqueandre', false, 80, true),
    ('@Igortep', 'Igortep', false, 80, true),
    ('@GaloCareca21', 'GaloCareca21', false, 80, true),
    ('@InfoGalo_', 'InfoGalo_', false, 80, true)
on conflict (usuario) do update
set nome = excluded.nome,
    oficial = excluded.oficial,
    confiabilidade = excluded.confiabilidade,
    ativo = true;

-- A v18 usava config_erro para representar a ausência GLOBAL de X_BEARER_TOKEN.
-- Isso fazia o frontend sugerir, incorretamente, que cada conta não estava configurada.
-- Na v19 essa condição não altera mais o status individual das contas.
update public.contas_x
set status_sync = 'pendente',
    sync_erro = null
where ativo = true
  and status_sync = 'config_erro'
  and sync_erro ilike '%X_BEARER_TOKEN%';
