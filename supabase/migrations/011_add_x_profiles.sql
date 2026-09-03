insert into public.contas_x (nome, usuario, oficial, confiabilidade, ativo)
values
    ('@CentralDoCAM', 'CentralDoCAM', false, 80, true),
    ('@canalbicagalo', 'canalbicagalo', false, 80, true),
    ('@GaloCareca21', 'GaloCareca21', false, 80, true),
    ('@pedfaria', 'pedfaria', false, 80, true),
    ('@lucascbretas', 'lucascbretas', false, 80, true),
    ('@canaldofrossard', 'canaldofrossard', false, 80, true),
    ('@LucasTanaka', 'LucasTanaka', false, 80, true),
    ('@InfoGalo_', 'InfoGalo_', false, 80, true),
    ('@claudiorez', 'claudiorez', false, 80, true),
    ('@ohenriqueandre', 'ohenriqueandre', false, 80, true),
    ('@faelslim', 'faelslim', false, 80, true),
    ('@BrenoGalante', 'BrenoGalante', false, 80, true),
    ('@Igortep', 'Igortep', false, 80, true)
on conflict (usuario) do update
set nome = excluded.nome,
    oficial = excluded.oficial,
    confiabilidade = excluded.confiabilidade,
    ativo = excluded.ativo;
