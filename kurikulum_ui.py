# -*- coding: utf-8 -*-
"""
UI bersama untuk edit Mata Kuliah & CPL, dipakai baik oleh admin_panel.py
(bisa pilih Prodi mana saja) maupun kaprodi_panel.py (dikunci ke Prodi yang
diampu sendiri) - supaya logikanya tidak ditulis dua kali.
"""

import streamlit as st

from db_master import load_master_db, save_cpl_df, save_mata_kuliah_df


def render_mk_editor(client, prodi_id, tahun_kurikulum):
    st.caption(
        "Dobel klik sel untuk edit. Tambah baris lewat tombol **+** di pojok kiri "
        "bawah tabel. **Kode MK harus unik per Tahun Kurikulum** (boleh sama dengan "
        "tahun kurikulum lain - itu dianggap versi revisi Mata Kuliah yang sama; "
        "Mata Kuliah Umum yang dipakai lintas Prodi sudah dipindah ke Prodi "
        "\"Mata Kuliah Umum\" tersendiri) - kalau Kode MK diubah, itu akan tersimpan "
        "sebagai baris baru (bukan mengganti yang lama). Koordinator per Mata "
        "Kuliah diatur di bagian terpisah, bukan di sini."
    )
    mk_df, _ = load_master_db(client, prodi_id, tahun_kurikulum)
    edited_mk = st.data_editor(
        mk_df.drop(columns=["id", "koordinator_user_id"]),
        num_rows="dynamic",
        use_container_width=True,
        key=f"mk_editor_{prodi_id}_{tahun_kurikulum}",
    )
    if st.button("💾 Simpan Perubahan Mata Kuliah", key=f"save_mk_btn_{prodi_id}_{tahun_kurikulum}"):
        try:
            n = save_mata_kuliah_df(client, prodi_id, tahun_kurikulum, edited_mk)
            st.success(f"{n} baris Mata Kuliah disimpan.")
            load_master_db.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Gagal menyimpan: {e}")


def render_cpl_editor(client, prodi_id, tahun_kurikulum):
    st.caption(
        "Dobel klik sel untuk edit. Tambah baris lewat tombol **+** di pojok kiri "
        "bawah tabel. **Kode CPL harus unik** dalam satu Prodi + Tahun Kurikulum "
        "(mis. S1, P2, KU3, KK1)."
    )
    _, cpl_df = load_master_db(client, prodi_id, tahun_kurikulum)
    edited_cpl = st.data_editor(
        cpl_df.drop(columns=["id"]),
        num_rows="dynamic",
        use_container_width=True,
        key=f"cpl_editor_{prodi_id}_{tahun_kurikulum}",
    )
    if st.button("💾 Simpan Perubahan CPL", key=f"save_cpl_btn_{prodi_id}_{tahun_kurikulum}"):
        try:
            n = save_cpl_df(client, prodi_id, tahun_kurikulum, edited_cpl)
            st.success(f"{n} baris CPL disimpan.")
            load_master_db.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Gagal menyimpan: {e}")