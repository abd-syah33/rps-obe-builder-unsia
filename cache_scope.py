# -*- coding: utf-8 -*-
"""
Kunci cache per pengguna untuk fungsi baca yang hasilnya dipengaruhi RLS.

Masalah yang diperbaiki: st.cache_data dipakai BERSAMA oleh semua sesi
(semua pengguna yang sedang membuka aplikasi). Argumen berawalan underscore
(mis. `_client`) TIDAK ikut jadi kunci cache. Akibatnya fungsi seperti
get_rps_progress_raw(_client, prodi_id=None) menghasilkan kunci yang SAMA
untuk BPM dan Admin, padahal RLS memberi mereka data yang berbeda (BPM hanya
boleh membaca RPS berstatus disetujui/divalidasi, Admin membaca semua).
Siapa pun yang memuat duluan dalam jendela TTL "menang", dan pengguna lain
melihat hasil milik orang itu: angka statistik BPM berubah-ubah, dan daftar
antrian Kaprodi satu Prodi bisa sempat terlihat oleh Kaprodi Prodi lain.

Solusinya: fungsi yang hasilnya bergantung pada siapa yang login menerima
argumen `scope` (id + peran + prodi pengguna) sebagai bagian dari kunci cache.
"""

import streamlit as st

_KEY = "_cache_scope"


def set_cache_scope(pengguna):
    """Dipanggil sekali per rerun dari auth.require_login() setelah profil
    pengguna berhasil dimuat. Peran & prodi ikut dimasukkan supaya perubahan
    peran oleh Admin langsung memakai cache baru, tanpa menunggu TTL."""
    st.session_state[_KEY] = f"{pengguna['id']}|{pengguna.get('role')}|{pengguna.get('prodi_id')}"


def cache_scope():
    return st.session_state.get(_KEY, "anonim")
