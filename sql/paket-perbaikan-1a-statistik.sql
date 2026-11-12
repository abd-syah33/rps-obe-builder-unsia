-- =============================================================================
-- PAKET PERBAIKAN 1, BAGIAN A (BUG-02): Statistik Panel BPM sama dengan Admin
-- =============================================================================
-- Jalankan di Supabase -> SQL Editor SEBELUM kode aplikasi baru dirilis.
-- Murni TAMBAHAN (fungsi baru), tidak mengubah tabel/policy apa pun, jadi
-- aplikasi lama tetap berjalan normal. Aman dijalankan berulang.
--
-- Masalah: policy RLS BPM hanya membaca rps berstatus disetujui/divalidasi,
-- dan BPM tidak boleh membaca tabel pengguna/whitelist_pendaftaran. Statistik
-- lama membaca tabel-tabel itu langsung, sehingga di mata BPM semua RPS
-- Draft/Diajukan terhitung "Belum Diisi" dan nama koordinator tidak dikenali.
--
-- Solusi: fungsi SECURITY DEFINER yang HANYA mengembalikan status per Mata
-- Kuliah + nama koordinator (bukan isi RPS). Policy RLS tidak dilonggarkan:
-- BPM tetap tidak bisa membaca isi RPS yang belum disetujui Kaprodi.
--
-- Hak akses: Admin & BPM semua Prodi (target_prodi_id boleh null); Kaprodi
-- hanya Prodi yang diampu (wajib mengisi target_prodi_id); lainnya ditolak.
-- =============================================================================

create or replace function public.statistik_pengisian_rps(target_prodi_id uuid default null)
returns table(
    kode_mk text,
    nama_mk text,
    prodi_id uuid,
    prodi_nama text,
    tahun_kurikulum integer,
    koordinator_user_id uuid,
    koordinator_nip text,
    koordinator_nama text,
    status text
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
begin
    if not (
        public.is_admin()
        or public.is_bpm()
        or (target_prodi_id is not null and public.is_kaprodi_of(target_prodi_id))
    ) then
        raise exception 'Anda tidak berwenang melihat statistik pengisian RPS ini.';
    end if;

    return query
    select
        mk.kode_mk::text,
        mk.nama_mk::text,
        mk.prodi_id,
        coalesce(p.nama, '-')::text,
        mk.tahun_kurikulum,
        mk.koordinator_user_id,
        mk.koordinator_nip::text,
        (case
            when mk.koordinator_user_id is not null then
                case when pg.id is null then '(akun tidak dikenali)'
                     else coalesce(nullif(btrim(pg.nama), ''), nullif(btrim(pg.email), ''), '-')
                end
            when nullif(btrim(mk.koordinator_nip), '') is not null then
                coalesce(w.nama, 'NIP ' || mk.koordinator_nip || ' (belum daftar akun)')
            else null
        end)::text,
        (case when r.id is null then 'belum' else coalesce(r.status, 'draft') end)::text
    from public.mata_kuliah mk
    left join public.prodi p on p.id = mk.prodi_id
    left join public.pengguna pg on pg.id = mk.koordinator_user_id
    left join public.whitelist_pendaftaran w on w.nip = mk.koordinator_nip
    left join lateral (
        select rr.id, rr.status from public.rps rr
        where rr.mata_kuliah_id = mk.id
        order by rr.updated_at desc
        limit 1
    ) r on true
    where target_prodi_id is null or mk.prodi_id = target_prodi_id;
end;
$$;

revoke all on function public.statistik_pengisian_rps(uuid) from public, anon;
grant execute on function public.statistik_pengisian_rps(uuid) to authenticated;
