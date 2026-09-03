# Radar do X — diagnóstico e sincronização (v19)

## Causa corrigida

Na v18, a ausência global de `X_BEARER_TOKEN` fazia o startup do FastAPI executar um `UPDATE` em **todas** as contas ativas, definindo `status_sync = 'config_erro'`.

O frontend interpretava `config_erro` como:

> Radar do X ainda não está configurado para sincronizar esta conta.

Isso era enganoso: as contas estavam cadastradas e ativas; o erro era a falta da credencial global da X API.

Na v19:

- o startup sem Bearer Token apenas registra um erro global no log;
- o status individual das contas não é alterado;
- o frontend consulta `/api/x/status` e informa explicitamente quando a credencial global está ausente;
- `sync_erro` passa a ser retornado junto da conta;
- o job manual lista as contas encontradas antes de tentar a X API;
- 401/403/429 continuam sendo tratados explicitamente pelo sincronizador.

## Contas de validação

A migration `014_fix_x_profile_sync_registration.sql` garante estas contas ativas:

- @Atletico
- @pedfaria
- @ohenriqueandre
- @Igortep
- @GaloCareca21
- @InfoGalo_

> O handle usado no projeto é `@Igortep` (I maiúsculo). `@lgortep` (L minúsculo) não é o cadastro atual.

## Diagnóstico

```powershell
python scripts\diagnosticar_x.py
```

Sem `X_BEARER_TOKEN`, o script lista cada conta e registra `fetch NÃO EXECUTADO`, deixando claro que o bloqueio é de credencial, não de cadastro.

Com token configurado, ele testa primeiro `@Atletico`. Somente se houver sincronização e ao menos um embed válido no Supabase ele prossegue para as outras cinco contas.

## Sincronização manual das seis contas

```powershell
python scripts\sincronizar_x.py --contas Atletico,pedfaria,ohenriqueandre,Igortep,GaloCareca21,InfoGalo_
```

## Scraping do X

**Não foi implementado nesta versão.**

Scraping não oficial do X/Twitter pode violar os Termos de Uso da plataforma e pode resultar em bloqueio de IP, bloqueio de conta, desafios anti-bot e quebra frequente do coletor. Portanto, não deve ser tratado como solução definitiva de produção.

Somente após confirmação explícita do responsável pelo projeto deve ser criada uma implementação temporária. Se isso ocorrer, ela deve usar rate limit próprio, cache agressivo, identificação de User-Agent e continuar gravando na mesma estrutura `contas_x` / `posts_x`, para não exigir alterações no frontend.
