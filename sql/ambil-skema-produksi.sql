-- =============================================================================
-- AMBIL SKEMA PRODUKSI (hanya membaca, tidak mengubah apa pun)
-- =============================================================================
-- Tujuan: sql/schema.sql di repo tertinggal dari database produksi (mis. kolom
-- rps.dikunci_admin dan fungsi set_kunci_admin() tidak tercatat). Hasil query
-- ini dipakai sebagai sumber kebenaran sebelum RPS Builder v2 dibangun.
--
-- Cara pakai: Supabase -> SQL Editor -> tempel seluruh isi file ini -> Run ->
-- tombol unduh hasil (CSV). Kirim berkas CSV-nya. Tidak berisi data RPS,
-- password, atau kunci API: hanya struktur (kolom, fungsi, policy, trigger).
-- =============================================================================
select * from (
    select '1-RLS' as jenis, c.relname::text as nama,
           case when c.relrowsecurity then 'RLS aktif' else 'RLS MATI' end as definisi
    from pg_class c
    where c.relnamespace = 'public'::regnamespace and c.relkind = 'r'

    union all
    select '2-KOLOM', table_name || '.' || column_name,
           data_type || coalesce(' default ' || column_default, '')
           || case when is_nullable = 'NO' then ' not null' else '' end
    from information_schema.columns
    where table_schema = 'public'

    union all
    select '3-CONSTRAINT', conrelid::regclass::text || '.' || conname, pg_get_constraintdef(oid)
    from pg_constraint
    where connamespace = 'public'::regnamespace

    union all
    select '4-INDEX', tablename || '.' || indexname, indexdef
    from pg_indexes
    where schemaname = 'public'

    union all
    select '5-POLICY', tablename || '.' || policyname,
           'for ' || cmd || ' to ' || array_to_string(roles, ',')
           || ' using (' || coalesce(qual, '-') || ') with check (' || coalesce(with_check, '-') || ')'
    from pg_policies
    where schemaname = 'public'

    union all
    select '6-TRIGGER', event_object_schema || '.' || event_object_table || '.' || trigger_name,
           action_timing || ' ' || event_manipulation || ' ' || action_statement
    from information_schema.triggers
    where event_object_schema in ('public', 'auth')

    union all
    select '7-FUNGSI', p.proname::text || '(' || pg_get_function_identity_arguments(p.oid) || ')',
           pg_get_functiondef(p.oid)
    from pg_proc p
    join pg_language l on l.oid = p.prolang
    where p.pronamespace = 'public'::regnamespace and p.prokind = 'f'
      and l.lanname in ('plpgsql', 'sql')  -- lewati fungsi C bawaan ekstensi (pgcrypto dll.)

    union all
    select '8-GRANT', routine_name || ' -> ' || grantee, privilege_type
    from information_schema.routine_privileges
    where routine_schema = 'public' and grantee in ('anon', 'authenticated')
) s
order by jenis, nama;
