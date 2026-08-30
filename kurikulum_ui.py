# -*- coding: utf-8 -*-
"""
UI bersama untuk edit Mata Kuliah & CPL, dipakai baik oleh admin_panel.py
(bisa pilih Prodi mana saja) maupun kaprodi_panel.py (dikunci ke Prodi yang
diampu sendiri) - supaya logikanya tidak ditulis dua kali.
"""

import pandas as pd
import streamlit as st

from db_master import load_master_db, save_cpl_df, save_mata_kuliah_df


def _tampilkan_pesan_pending(state_key):
    """Tampilkan (lalu hapus) pesan sukses/peringatan yang disimpan SEBELUM
    st.rerun() terakhir. Perlu ditaruh terpisah dari titik st.success/
    st.warning aslinya karena st.rerun() yang dipanggil di run YANG SAMA
    langsung memotong render sebelum pesan itu sempat kelihatan - jadi
    pesannya lewat session_state dulu, dan baru betul-betul ditampilkan di
    render BERIKUTNYA (giliran ini), sampai pengguna sungguh membacanya."""
    pesan = st.session_state.pop(state_key, None)
    if pesan:
        if pesan.get("sukses"):
            st.success(pesan["sukses"])
        for w in pesan.get("peringatan") or []:
            st.warning(w)


def render_mk_editor(client, prodi_id, tahun_kurikulum):
    st.caption(
        "Dobel klik sel untuk edit. Tambah baris lewat tombol **+** di pojok kiri "
        "bawah tabel, atau hapus baris lewat ikon tempat sampah di sebelah kiri "
        "baris (baris yang dihapus di sini akan BENAR-BENAR terhapus dari "
        "database setelah disimpan - draft RPS yang belum diajukan ikut terhapus "
        "otomatis, tapi kalau Mata Kuliah itu sudah pernah DIAJUKAN/diproses "
        "penghapusannya otomatis DITOLAK sistem demi menjaga jejak resmi). "
        "**Kode MK harus unik per Tahun Kurikulum** (boleh sama dengan tahun "
        "kurikulum lain - itu dianggap versi revisi Mata Kuliah yang sama; "
        "Mata Kuliah Umum yang dipakai lintas Prodi sudah dipindah ke Prodi "
        "\"Mata Kuliah Umum\" tersendiri). Koordinator per Mata Kuliah diatur "
        "di bagian terpisah, bukan di sini."
    )
    state_key = f"_pesan_mk_{prodi_id}_{tahun_kurikulum}"
    _tampilkan_pesan_pending(state_key)

    mk_df, _ = load_master_db(client, prodi_id, tahun_kurikulum)
    mk_df_tampil = mk_df.drop(columns=["id", "koordinator_user_id", "koordinator_nip"])

    col_cari, col_urut = st.columns([2, 1.3])
    with col_cari:
        cari = st.text_input(
            "\U0001F50D Cari (Kode/Nama Mata Kuliah)", key=f"mk_cari_{prodi_id}_{tahun_kurikulum}",
        ).strip().lower()
    with col_urut:
        urutan = st.selectbox(
            "Urutkan", ["Semester", "Kode MK (A-Z)", "Nama MK (A-Z)"],
            key=f"mk_urut_{prodi_id}_{tahun_kurikulum}",
        )

    if cari:
        mask = (
            mk_df_tampil["Kode MK"].astype(str).str.lower().str.contains(cari)
            | mk_df_tampil["Nama Mata Kuliah"].astype(str).str.lower().str.contains(cari)
        )
    else:
        mask = pd.Series(True, index=mk_df_tampil.index)

    df_terfilter = mk_df_tampil[mask]
    if urutan == "Kode MK (A-Z)":
        df_terfilter = df_terfilter.sort_values("Kode MK")
    elif urutan == "Nama MK (A-Z)":
        df_terfilter = df_terfilter.sort_values("Nama Mata Kuliah")
    else:
        df_terfilter = df_terfilter.sort_values("Semester")

    if cari:
        st.caption(f"Menampilkan {len(df_terfilter)} dari {len(mk_df_tampil)} Mata Kuliah yang cocok pencarian.")
        st.caption(
            "\u26A0\uFE0F Simpan dulu perubahan sebelum mengubah kata kunci pencarian - "
            "mengubah pencarian akan me-reset tabel ke data tersimpan terakhir."
        )

    # Key widget SENGAJA ikut berubah kalau kata kunci pencarian/urutan
    # berubah - supaya st.data_editor selalu dianggap widget yang benar-benar
    # BARU saat filter berubah (bukan "widget lama, data baru" yang berisiko
    # menampilkan data basi - gotcha yang sama seperti dibahas di app.py
    # bagian sinkronkan_widget_pertemuan()). Konsekuensinya: perubahan yang
    # BELUM disimpan hilang kalau pencarian/urutan diubah - lihat peringatan
    # di atas.
    editor_key = f"mk_editor_{prodi_id}_{tahun_kurikulum}_{cari}_{urutan}"
    edited_terfilter = st.data_editor(
        df_terfilter,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=editor_key,
    )
    if st.button("💾 Simpan Perubahan Mata Kuliah", key=f"save_mk_btn_{prodi_id}_{tahun_kurikulum}"):
        try:
            # Baris yang sedang DISEMBUNYIKAN pencarian (tidak match "mask")
            # digabung APA ADANYA (tidak disentuh) bersama hasil edit pada
            # baris yang SEDANG ditampilkan - supaya baris yang cuma
            # "tersembunyi karena difilter" TIDAK ikut dianggap "dihapus
            # pengguna" oleh save_mata_kuliah_df (yang mendeteksi hapus lewat
            # selisih Kode MK antara edited_df vs original_df).
            edited_mk = pd.concat([mk_df_tampil[~mask], edited_terfilter], ignore_index=True)
            n, gagal_hapus = save_mata_kuliah_df(client, prodi_id, tahun_kurikulum, edited_mk, mk_df_tampil)
            peringatan = []
            if gagal_hapus:
                peringatan.append(
                    "Mata Kuliah berikut TIDAK bisa dihapus karena sudah pernah DIAJUKAN "
                    "atau diproses (draft murni yang belum diajukan aman dihapus otomatis) "
                    "(Kode MK): " + ", ".join(sorted(gagal_hapus))
                )
            st.session_state[state_key] = {
                "sukses": f"{n} baris Mata Kuliah disimpan.", "peringatan": peringatan,
            }
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
    state_key = f"_pesan_cpl_{prodi_id}_{tahun_kurikulum}"
    _tampilkan_pesan_pending(state_key)

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
            peringatan = []
            if terpakai:
                peringatan.append(
                    "CPL berikut TIDAK bisa dihapus karena masih dirujuk sebagai CPMK "
                    "di RPS manapun (Kode CPL): " + ", ".join(terpakai)
                )
            st.session_state[state_key] = {
                "sukses": f"{n} baris CPL disimpan.", "peringatan": peringatan,
            }
            load_master_db.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Gagal menyimpan: {e}")