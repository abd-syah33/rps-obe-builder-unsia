# -*- coding: utf-8 -*-
"""
Skrip SEKALI JALAN (opsional, aman diulang) - rapikan spasi berantakan
(spasi ganda, spasi tak-putus/non-breaking space, baris kosong berulang)
pada data yang SUDAH TERSIMPAN dari SEBELUM db_master._clean_single_line_text()
ada - lihat perubahan terkait di db_master.py & app.py.

Memakai fungsi pembersih yang PERSIS SAMA (db_master._clean_single_line_text) yang
sudah dipakai aplikasi untuk data baru, supaya hasilnya konsisten - bukan
menuliskan ulang logika regex terpisah di sini.

Menyentuh HANYA bagian "tabel atas" dokumen RPS (identitas + CPL/CPMK +
Daftar Pustaka) - SENGAJA TIDAK menyentuh tabel 16 Pertemuan (Sub-CPMK,
Materi, Indikator per minggu) sama sekali, sesuai permintaan:
  - cpl.deskripsi
  - rps.data->info_umum->deskripsi_mk
  - rps.data->cpmk_data->*->deskripsi
  - rps.data->referensi_data->*->sitasi

PENTING: skrip ini pakai SUPABASE_SERVICE_ROLE_KEY (bypass Row Level
Security) karena perlu menyentuh data SEMUA Prodi/Dosen sekaligus, bukan
cuma milik satu akun. JANGAN PERNAH pakai key ini dari app.py yang diakses
banyak Dosen.

Cara jalan:
    python scripts/bersihkan_spasi_lama.py            # tampilkan dulu apa yang AKAN diubah (aman, tidak menulis)
    python scripts/bersihkan_spasi_lama.py --terapkan # baru benar-benar menyimpan perubahan
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from supabase_config import load_supabase_config  # noqa: E402
from db_master import _clean_single_line_text  # noqa: E402

try:
    from supabase import create_client
except ImportError:
    print("Package 'supabase' belum terpasang. Jalankan dulu: pip install supabase")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--terapkan", action="store_true",
        help="Benar-benar simpan perubahan. Tanpa opsi ini, skrip cuma MENAMPILKAN apa yang akan diubah (aman).",
    )
    args = parser.parse_args()

    cfg = load_supabase_config()
    if not cfg["url"] or not cfg["service_role_key"]:
        print(
            "SUPABASE_URL atau SUPABASE_SERVICE_ROLE_KEY belum diisi di config/supabase.txt.\n"
            "Ambil service_role key dari dashboard Supabase: Project Settings -> Data API."
        )
        sys.exit(1)
    client = create_client(cfg["url"], cfg["service_role_key"])

    mode = "MENERAPKAN perubahan" if args.terapkan else "PRATINJAU saja (belum menyimpan apa pun)"
    print(f"=== Mode: {mode} ===\n")

    # -----------------------------------------------------------------
    # 1. Tabel cpl.deskripsi
    # -----------------------------------------------------------------
    print("--- Memeriksa tabel cpl ---")
    cpl_rows = client.table("cpl").select("id, kode_cpl, deskripsi").execute().data or []
    n_cpl_berubah = 0
    for row in cpl_rows:
        asli = row.get("deskripsi") or ""
        bersih = _clean_single_line_text(asli)
        if bersih != asli:
            n_cpl_berubah += 1
            print(f"  [{row['kode_cpl']}] {asli[:60]!r} -> {bersih[:60]!r}")
            if args.terapkan:
                client.table("cpl").update({"deskripsi": bersih}).eq("id", row["id"]).execute()
    print(f"  Total CPL yang {'diperbaiki' if args.terapkan else 'akan diperbaiki'}: {n_cpl_berubah}\n")

    # -----------------------------------------------------------------
    # 2. Tabel rps.data (JSONB, field teks panjang di dalamnya)
    # -----------------------------------------------------------------
    print("--- Memeriksa tabel rps ---")
    rps_rows = client.table("rps").select("id, data").execute().data or []
    n_rps_berubah = 0
    for row in rps_rows:
        data = row.get("data") or {}
        if not data:
            continue
        berubah = False

        info_umum = data.get("info_umum") or {}
        if info_umum.get("deskripsi_mk"):
            bersih = _clean_single_line_text(info_umum["deskripsi_mk"])
            if bersih != info_umum["deskripsi_mk"]:
                info_umum["deskripsi_mk"] = bersih
                berubah = True

        cpmk_data = data.get("cpmk_data") or {}
        for k, v in cpmk_data.items():
            if v and v.get("deskripsi"):
                bersih = _clean_single_line_text(v["deskripsi"])
                if bersih != v["deskripsi"]:
                    v["deskripsi"] = bersih
                    berubah = True

        # SENGAJA TIDAK menyentuh pertemuan_data (Sub-CPMK/Materi/Indikator
        # per minggu, tabel 16 Pertemuan) - di luar cakupan pembersihan ini.

        referensi_data = data.get("referensi_data") or []
        for r in referensi_data:
            if r and r.get("sitasi"):
                bersih = _clean_single_line_text(r["sitasi"])
                if bersih != r["sitasi"]:
                    r["sitasi"] = bersih
                    berubah = True

        if berubah:
            n_rps_berubah += 1
            print(f"  RPS {row['id']} - ada field yang dirapikan")
            if args.terapkan:
                client.table("rps").update({"data": data}).eq("id", row["id"]).execute()

    print(f"  Total RPS yang {'diperbaiki' if args.terapkan else 'akan diperbaiki'}: {n_rps_berubah}\n")

    if not args.terapkan and (n_cpl_berubah or n_rps_berubah):
        print("Ini baru pratinjau - jalankan lagi dengan --terapkan untuk benar-benar menyimpan.")


if __name__ == "__main__":
    main()