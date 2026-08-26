# -*- coding: utf-8 -*-
"""
Skrip verifikasi Fase 1 - jalankan SETELAH:
  1. Project Supabase dibuat
  2. sql/schema.sql sudah dijalankan lewat SQL Editor
  3. config/supabase.txt sudah diisi (salin dari config/supabase.txt.example)

Cara jalan:
    pip install supabase
    python scripts/test_supabase_connection.py

Yang diperiksa: koneksi berhasil, dan keempat tabel (prodi, mata_kuliah, cpl,
rps) sudah ada dan bisa dibaca (masih kosong itu normal - baru diisi di Fase 3).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from supabase_config import load_supabase_config  # noqa: E402

try:
    from supabase import create_client
except ImportError:
    print("Package 'supabase' belum terpasang. Jalankan dulu: pip install supabase")
    sys.exit(1)


def main():
    cfg = load_supabase_config()
    if not cfg["url"] or not cfg["anon_key"]:
        print(
            "config/supabase.txt belum diisi (atau belum ada).\n"
            "Salin config/supabase.txt.example -> config/supabase.txt, lalu isi "
            "SUPABASE_URL dan SUPABASE_ANON_KEY dari dashboard project Supabase."
        )
        sys.exit(1)

    client = create_client(cfg["url"], cfg["anon_key"])

    tables = ["prodi", "mata_kuliah", "cpl", "rps"]
    print(f"Menyambung ke {cfg['url']} ...\n")

    all_ok = True
    for table in tables:
        try:
            resp = client.table(table).select("*").limit(5).execute()
            print(f"  [OK] tabel '{table}' bisa diakses - {len(resp.data)} baris terbaca (contoh, maks 5).")
        except Exception as e:
            all_ok = False
            print(f"  [GAGAL] tabel '{table}': {e}")

    print()
    if all_ok:
        print("Semua tabel Fase 1 sudah siap. Lanjut ke Fase 2 (Login & Peran) kapan saja.")
    else:
        print(
            "Ada tabel yang belum bisa diakses - cek lagi apakah sql/schema.sql "
            "sudah dijalankan penuh tanpa error di SQL Editor."
        )


if __name__ == "__main__":
    main()