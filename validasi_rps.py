# -*- coding: utf-8 -*-
"""Aturan kelengkapan RPS yang tidak bergantung pada Streamlit, supaya bisa
diuji langsung (lihat tests/test_validasi_rps.py).

Penggunaan AI (Paket Perbaikan 1, BUG-01): Level Penggunaan AI dan Deskripsi
Penggunaan AI WAJIB diisi sebelum RPS diajukan ke Kaprodi. Aturan yang sama
dijaga di database oleh trigger trg_rps_cek_penggunaan_ai
(sql/paket-perbaikan-1b-wajib-ai.sql); kalau angka/pilihan di sini diubah,
ubah juga di file SQL itu.
"""

LEVEL_AI_PILIHAN = ["Tanpa AI", "Assisted AI", "Free AI"]
MIN_DESKRIPSI_AI = 20


def _rapikan(teks):
    """Buang spasi di tepi dan ringkas spasi/baris baru berulang jadi satu
    spasi, sama seperti regexp_replace(btrim(..), '\\s+', ' ') di SQL."""
    return " ".join(str(teks or "").split())


def masalah_penggunaan_ai(info_umum):
    """Daftar kekurangan isian Penggunaan AI (list kosong = sudah lengkap).
    info_umum: dict info_umum RPS (boleh None)."""
    info_umum = info_umum or {}
    masalah = []
    if (info_umum.get("level_ai") or "").strip() not in LEVEL_AI_PILIHAN:
        masalah.append("Level Penggunaan AI belum dipilih")
    panjang = len(_rapikan(info_umum.get("deskripsi_ai")))
    if panjang == 0:
        masalah.append("Deskripsi Penggunaan AI belum diisi")
    elif panjang < MIN_DESKRIPSI_AI:
        masalah.append(
            f"Deskripsi Penggunaan AI terlalu singkat ({panjang} karakter, minimal {MIN_DESKRIPSI_AI})"
        )
    return masalah
