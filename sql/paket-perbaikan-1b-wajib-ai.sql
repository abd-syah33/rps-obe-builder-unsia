-- =============================================================================
-- PAKET PERBAIKAN 1, BAGIAN B (BUG-01): Level & Deskripsi Penggunaan AI wajib
-- =============================================================================
-- Jalankan di Supabase -> SQL Editor SETELAH kode aplikasi baru dirilis
-- (aplikasi baru sudah memeriksa hal yang sama dengan pesan yang ramah, jadi
-- pengaman ini praktis hanya bekerja bila ada yang mengajukan di luar
-- aplikasi). Aman dijalankan berulang.
--
-- Sengaja memakai TRIGGER, bukan mengganti fungsi ajukan_rps(): definisi
-- ajukan_rps() di database produksi bisa berbeda dari sql/schema.sql (mis.
-- ada tambahan kunci Admin), jadi menimpanya berisiko menghapus aturan yang
-- tidak tercatat. Trigger ini berlaku pada SETIAP perubahan status menjadi
-- 'diajukan', apa pun fungsi yang melakukannya.
--
-- RPS yang SUDAH berstatus diajukan/disetujui/divalidasi tidak tersentuh
-- (keputusan 12 Nov 2026: RPS final dibiarkan). Aturan hanya berlaku saat
-- RPS diajukan atau diajukan ulang.
--
-- Harus sama dengan validasi_rps.py: LEVEL_AI_PILIHAN & MIN_DESKRIPSI_AI.
-- =============================================================================

create or replace function public.cek_penggunaan_ai_saat_diajukan()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    v_level text;
    v_deskripsi text;
begin
    if new.status = 'diajukan'
       and (tg_op = 'INSERT' or old.status is distinct from 'diajukan') then

        v_level := btrim(coalesce(new.data -> 'info_umum' ->> 'level_ai', ''));
        v_deskripsi := regexp_replace(
            btrim(coalesce(new.data -> 'info_umum' ->> 'deskripsi_ai', '')), '\s+', ' ', 'g'
        );

        if v_level not in ('Tanpa AI', 'Assisted AI', 'Free AI') then
            raise exception 'Level Penggunaan AI wajib dipilih sebelum RPS diajukan (tab Daftar Pustaka).';
        end if;

        if char_length(v_deskripsi) < 20 then
            raise exception 'Deskripsi Penggunaan AI wajib diisi minimal 20 karakter sebelum RPS diajukan (tab Daftar Pustaka).';
        end if;
    end if;

    return new;
end;
$$;

drop trigger if exists trg_rps_cek_penggunaan_ai on public.rps;
create trigger trg_rps_cek_penggunaan_ai
    before insert or update on public.rps
    for each row execute function public.cek_penggunaan_ai_saat_diajukan();
