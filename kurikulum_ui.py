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
        "bawah tabel, atau hapus baris lewat ikon tempat sampah di sebelah kiri "
        "baris (baris yang dihapus di sini akan BENAR-BENAR terhapus dari "
        "database setelah disimpan - kecuali Mata Kuliah itu sudah pernah "
        "dipakai mengisi RPS, yang otomatis DITOLAK sistem demi keamanan data). "
        "**Kode MK harus unik per Tahun Kurikulum** (boleh sama dengan tahun "
        "kurikulum lain - itu dianggap versi revisi Mata Kuliah yang sama; "
        "Mata Kuliah Umum yang dipakai lintas Prodi sudah dipindah ke Prodi "
        "\"Mata Kuliah Umum\" tersendiri). Koordinator per Mata Kuliah diatur "
        "di bagian terpisah, bukan di sini."
    )
    mk_df, _ = load_master_db(client, prodi_id, tahun_kurikulum)
    mk_df_tampil = mk_df.drop(columns=["id", "koordinator_user_id", "koordinator_nip"])
    edited_mk = st.data_editor(
        mk_df_tampil,
        num_rows="dynamic",
        use_container_width=True,
        key=f"mk_editor_{prodi_id}_{tahun_kurikulum}",
    )
    if st.button("💾 Simpan Perubahan Mata Kuliah", key=f"save_mk_btn_{prodi_id}_{tahun_kurikulum}"):
        try:
            n, gagal_hapus = save_mata_kuliah_df(client, prodi_id, tahun_kurikulum, edited_mk, mk_df_tampil)
            st.success(f"{n} baris Mata Kuliah disimpan.")
            if gagal_hapus:
                st.warning(
                    "Mata Kuliah berikut TIDAK bisa dihapus karena sudah pernah dipakai "
                    "mengisi RPS (Kode MK): " + ", ".join(sorted(gagal_hapus))
                )
            load_master_db.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Gagal menyimpan: {e}")


def render_cpl_editor(client, prodi_id, tahun_kurikulum):
    st.caption(
        "Dobel klik sel untuk edit. Tambah baris lewat tombol **+** di pojok kiri "
        "bawah tabel, atau hapus baris lewat ikon tempat sampah di sebelah kiri "
        "baris (baris yang dihapus di sini akan BENAR-BENAR terhapus dari "
        "database setelah disimpan - kecuali kode CPL itu sudah dirujuk sebagai "
        "CPMK di RPS manapun, yang otomatis DITOLAK sistem demi keamanan data). "
        "**Kode CPL harus unik** dalam satu Prodi + Tahun Kurikulum (mis. S1, "
        "P2, KU3, KK1)."
    )
    _, cpl_df = load_master_db(client, prodi_id, tahun_kurikulum)
    cpl_df_tampil = cpl_df.drop(columns=["id"])
    edited_cpl = st.data_editor(
        cpl_df_tampil,
        num_rows="dynamic",
        use_container_width=True,
        key=f"cpl_editor_{prodi_id}_{tahun_kurikulum}",
    )
    if st.button("💾 Simpan Perubahan CPL", key=f"save_cpl_btn_{prodi_id}_{tahun_kurikulum}"):
        try:
            n, terpakai = save_cpl_df(client, prodi_id, tahun_kurikulum, edited_cpl, cpl_df_tampil)
            st.success(f"{n} baris CPL disimpan.")
            if terpakai:
                st.warning(
                    "CPL berikut TIDAK bisa dihapus karena masih dirujuk sebagai CPMK "
                    "di RPS manapun (Kode CPL): " + ", ".join(terpakai)
                )
            load_master_db.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Gagal menyimpan: {e}")