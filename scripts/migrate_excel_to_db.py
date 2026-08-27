# -*- coding: utf-8 -*-
"""
Fase 3 - migrasi SEKALI JALAN: baca semua file data/*.xlsx (format lama),
masukkan isinya ke tabel prodi/mata_kuliah/cpl di Supabase.

PENTING: skrip ini pakai SUPABASE_SERVICE_ROLE_KEY (bypass Row Level
Security) karena perlu menulis data master sebelum ada admin yang login
lewat aplikasi. JANGAN PERNAH pakai service_role key ini dari app.py yang
diakses banyak Dosen - key ini punya akses penuh tanpa dibatasi RLS sama sekali.

Aman dijalankan berulang kali (idempotent) - pakai upsert berdasarkan
constraint unique yang sudah ada di skema (prodi.nama; mata_kuliah unik per
(kode_mk, tahun_kurikulum); cpl unik per (prodi_id, kode_cpl, tahun_kurikulum)),
jadi data yang sudah ada akan di-update, bukan digandakan.

Penyesuaian - Kurikulum ganda: semua data di folder data/ ini mewakili
kurikulum 2021 (default). Untuk mengimpor Excel kurikulum lain (mis. 2026),
siapkan file Excel dengan format sama di folder terpisah lalu jalankan
dengan --tahun dan --data-dir, contoh:

    python scripts/migrate_excel_to_db.py --tahun 2021
    python scripts/migrate_excel_to_db.py --tahun 2026 --data-dir data_2026

Cara jalan (default, kurikulum 2021):
    python scripts/migrate_excel_to_db.py
"""

import argparse
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from supabase_config import load_supabase_config  # noqa: E402

try:
    from supabase import create_client
except ImportError:
    print("Package 'supabase' belum terpasang. Jalankan dulu: pip install supabase")
    sys.exit(1)

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def clean_kode(raw):
    """"Kode MK" di Excel kadang kebaca sebagai float (mis. 200001104.0)
    kalau kolomnya campur dengan sel kosong - bersihkan jadi string bulat."""
    if isinstance(raw, float) and raw.is_integer():
        return str(int(raw))
    return str(raw).strip()


def clean_int(value):
    if pd.isna(value):
        return None
    return int(value)


def clean_str(value):
    return "" if pd.isna(value) else str(value).strip()


def main():
    parser = argparse.ArgumentParser(description="Migrasi data master Excel -> Supabase")
    parser.add_argument("--tahun", type=int, default=2021, help="Tahun kurikulum untuk data ini (default: 2021)")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Folder berisi file .xlsx (default: data/)")
    args = parser.parse_args()

    cfg = load_supabase_config()
    if not cfg["url"] or not cfg["service_role_key"]:
        print(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY belum diisi di config/supabase.txt.\n"
            "Ambil service_role key dari dashboard Supabase: Project Settings -> Data API."
        )
        sys.exit(1)

    client = create_client(cfg["url"], cfg["service_role_key"])

    files = sorted(glob.glob(os.path.join(args.data_dir, "*.xlsx")))
    if not files:
        print(f"Tidak ada file .xlsx di {args.data_dir}")
        sys.exit(1)

    print(f"Mengimpor sebagai kurikulum tahun {args.tahun} dari folder {args.data_dir}")

    for path in files:
        prodi_nama = os.path.splitext(os.path.basename(path))[0]
        print(f"\n=== {prodi_nama} ===")

        prodi_resp = client.table("prodi").upsert({"nama": prodi_nama}, on_conflict="nama").execute()
        prodi_id = prodi_resp.data[0]["id"]
        print(f"  prodi id: {prodi_id}")

        mk_df = pd.read_excel(path, sheet_name="Mata Kuliah")
        n_mk = 0
        for _, row in mk_df.iterrows():
            if pd.isna(row.get("Nama Mata Kuliah")):
                continue
            client.table("mata_kuliah").upsert(
                {
                    "prodi_id": prodi_id,
                    "tahun_kurikulum": args.tahun,
                    "nama_mk": clean_str(row["Nama Mata Kuliah"]),
                    "kode_mk": clean_kode(row["Kode MK"]),
                    "sks": clean_int(row.get("SKS")),
                    "semester": clean_int(row.get("Semester")),
                    # Terima dua kemungkinan nama header Excel - file lama pakai
                    # "Ranah Topik", file baru (kalau sudah disesuaikan) pakai
                    # "Rumpun MK" - kolom database-nya sekarang bernama rumpun_mk.
                    "rumpun_mk": clean_str(row.get("Rumpun MK") if "Rumpun MK" in row else row.get("Ranah Topik")),
                },
                on_conflict="kode_mk,tahun_kurikulum",
            ).execute()
            n_mk += 1
        print(f"  {n_mk} mata kuliah di-upsert")

        cpl_df = pd.read_excel(path, sheet_name="CPL")
        n_cpl = 0
        for _, row in cpl_df.iterrows():
            if pd.isna(row.get("Kode CPL")):
                continue
            client.table("cpl").upsert(
                {
                    "prodi_id": prodi_id,
                    "tahun_kurikulum": args.tahun,
                    "kode_cpl": clean_str(row["Kode CPL"]),
                    "deskripsi": clean_str(row.get("Deskripsi CPL")),
                },
                on_conflict="prodi_id,kode_cpl,tahun_kurikulum",
            ).execute()
            n_cpl += 1
        print(f"  {n_cpl} CPL di-upsert")

    print("\nSelesai. Cek tabel prodi/mata_kuliah/cpl di Supabase Table Editor untuk verifikasi.")


if __name__ == "__main__":
    main()