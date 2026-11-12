-- =============================================================================
-- ROLLBACK PAKET PERBAIKAN 1 (hanya bila perlu membatalkan)
-- =============================================================================
-- Urutan: kembalikan dulu kode aplikasi (revert commit di GitHub), baru
-- jalankan bagian ini. Tidak menyentuh data RPS apa pun.

-- Bagian B: lepas pengaman wajib AI
drop trigger if exists trg_rps_cek_penggunaan_ai on public.rps;
drop function if exists public.cek_penggunaan_ai_saat_diajukan();

-- Bagian A: hapus fungsi statistik (aplikasi lama tidak memakainya)
drop function if exists public.statistik_pengisian_rps(uuid);
