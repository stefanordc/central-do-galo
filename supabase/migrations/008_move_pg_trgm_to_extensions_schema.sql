-- Compatibilidade para bancos onde pg_trgm tenha sido criado no schema public.
create schema if not exists extensions;

do $$
begin
    if exists (
        select 1
        from pg_extension e
        join pg_namespace n on n.oid = e.extnamespace
        where e.extname = 'pg_trgm'
          and n.nspname = 'public'
    ) then
        execute 'alter extension pg_trgm set schema extensions';
    end if;
end;
$$;
