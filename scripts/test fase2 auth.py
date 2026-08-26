# -*- coding: utf-8 -*-
"""
Skrip verifikasi Fase 2 - jalankan SETELAH bagian "FASE 2" di sql/schema.sql
dijalankan (dari SQL Editor Supabase, sekali lagi jalankan seluruh isi
schema.sql - aman, semua "create if not exists"/"drop ... if exists").

Cara jalan (interaktif, akan menanyakan email & password di terminal):
    python scripts/test_fase2_auth.py

Yang diperiksa:
  1. Bisa Daftar (sign up) & Masuk (sign in) lewat Supabase Auth
  2. Baris di tabel `pengguna` otomatis dibuat oleh trigger dengan role default 'dosen'
  3. Setelah login, tabel data master (prodi/mata_kuliah/cpl) bisa dibaca (RLS
     mengizinkan siapa pun yang authenticated)
  4. Tanpa login (anon), tabel-tabel itu TIDAK bisa dibaca (RLS bekerja) -
     dicek balik dengan client anon terpisah

Catatan: kalau project Supabase masih mengaktifkan "Confirm email" (default),
akun baru harus konfirmasi lewat link di email dulu sebelum bisa sign in -
skrip ini akan kasih tahu kalau itu terjadi. Untuk uji cepat internal, bisa
dimatikan sementara di Authentication -> Providers -> Email -> "Confirm email".
"""

import getpass
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
        print("config/supabase.txt belum diisi - lihat README Fase 1.")
        sys.exit(1)

    print("=== Uji tanpa login (anon) - harusnya SEMUA tabel KOSONG/ditolak karena RLS ===")
    anon_client = create_client(cfg["url"], cfg["anon_key"])
    for table in ("prodi", "mata_kuliah", "cpl"):
        try:
            resp = anon_client.table(table).select("*").limit(1).execute()
            n = len(resp.data)
            status = "OK (RLS memang mengosongkan hasil)" if n == 0 else "PERINGATAN: masih kebaca tanpa login!"
            print(f"  '{table}': {n} baris - {status}")
        except Exception as e:
            print(f"  '{table}': ditolak ({e}) - ini juga hasil yang benar")

    print("\n=== Masuk / Daftar ===")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")

    client = create_client(cfg["url"], cfg["anon_key"])
    try:
        auth_resp = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        print("Sign in gagal, coba daftar akun baru dengan email/password ini...")
        try:
            client.auth.sign_up({"email": email, "password": password})
        except Exception as e:
            print(f"Daftar juga gagal: {e}")
            sys.exit(1)
        try:
            auth_resp = client.auth.sign_in_with_password({"email": email, "password": password})
        except Exception as e:
            print(
                f"Akun dibuat tapi belum bisa sign in ({e}).\n"
                "Kemungkinan besar 'Confirm email' masih aktif di project Supabase - "
                "cek inbox untuk link konfirmasi, atau matikan sementara di "
                "Authentication -> Providers -> Email -> Confirm email, lalu ulangi skrip ini."
            )
            sys.exit(1)

    user = auth_resp.user
    print(f"\nBerhasil masuk sebagai {user.email} (user id: {user.id})")

    print("\n=== Cek baris pengguna (harus otomatis ada dari trigger) ===")
    resp = client.table("pengguna").select("*").eq("id", user.id).execute()
    if not resp.data:
        print(
            "  [GAGAL] Tidak ada baris di tabel pengguna untuk user ini - cek apakah "
            "trigger on_auth_user_created di sql/schema.sql sudah dijalankan."
        )
        sys.exit(1)
    profil = resp.data[0]
    print(f"  [OK] role = '{profil['role']}', prodi_id = {profil['prodi_id']}")

    print("\n=== Cek bisa baca data master (setelah login) ===")
    for table in ("prodi", "mata_kuliah", "cpl"):
        try:
            resp = client.table(table).select("*").limit(5).execute()
            print(f"  [OK] '{table}': {len(resp.data)} baris terbaca (contoh, maks 5)")
        except Exception as e:
            print(f"  [GAGAL] '{table}': {e}")

    print(
        "\nSelesai. Kalau semua di atas [OK] dan bagian anon di awal memang kosong/ditolak, "
        "Fase 2 (Auth + RLS dasar) sudah berfungsi dengan benar."
    )


if __name__ == "__main__":
    main()