-- Run only after 010_multi_user_auth.sql and after every existing dog has been
-- assigned to an auth.users account. The guard deliberately fails instead of
-- silently making legacy data unreachable.

begin;

do $$
begin
    if exists (select 1 from public.dogs where owner_user_id is null) then
        raise exception 'Cannot enforce dog ownership: one or more dogs still have owner_user_id = NULL.';
    end if;
end $$;

alter table public.dogs
    alter column owner_user_id set not null;

commit;
