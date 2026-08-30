# -*- coding: utf-8 -*-
"""
Penyesuaian: UI penetapan Koordinator Mata Kuliah - dipakai bersama oleh
admin_panel.py (tab "🎓 Koordinator") dan kaprodi_panel.py, supaya logikanya
tidak ditulis dua kali.

Hanya Dosen yang ditetapkan sebagai koordinator suatu Mata Kuliah yang boleh
mengisi/mengubah RPS-nya - lihat sql/schema.sql bagian "Koordinator Mata
Kuliah" untuk aturan aksesnya di level database.
"""

import pandas as pd
import streamlit as st

from db_master import list_dosen, list_whitelist_menunggu, load_master_db, set_koordinator_mk

BELUM_DITETAPKAN = "(belum ditetapkan)"


def render_koordinator_tab(client, prodi_id, tahun_kurikulum):
    pesan_koor = st.session_state.pop(f"_pesan_koor_{prodi_id}_{tahun_kurikulum}", None)
    if pesan_koor:
        st.success(pesan_koor)
    st.caption(
        "Tetapkan satu Dosen sebagai koordinator per Mata Kuliah - HANYA Dosen yang "
        "ditetapkan di sini yang bisa mengisi RPS untuk Mata Kuliah tsb. Mata Kuliah "
        "yang belum ditetapkan koordinatornya terkunci untuk semua Dosen. Dosen yang "
        "belum sempat Daftar akun juga bisa dipilih (dari daftar pra-pendaftaran) - "
        "penugasannya otomatis tersambung begitu mereka Daftar."
    )

    mk_df, _ = load_master_db(client, prodi_id, tahun_kurikulum)
    if mk_df.empty:
        st.info(f"Belum ada Mata Kuliah di Prodi ini untuk kurikulum {tahun_kurikulum}.")
        return

    col_cari, col_urut, col_filter = st.columns([2, 1.3, 1.5])
    with col_cari:
        cari = st.text_input(
            "\U0001F50D Cari (Kode/Nama Mata Kuliah)",
            key=f"koor_cari_{prodi_id}_{tahun_kurikulum}",
        ).strip().lower()
    with col_urut:
        urutan = st.selectbox(
            "Urutkan", ["Semester", "Kode MK (A-Z)", "Nama MK (A-Z)"],
            key=f"koor_urut_{prodi_id}_{tahun_kurikulum}",
        )
    with col_filter:
        hanya_kosong = st.checkbox(
            "Hanya tanpa koordinator", key=f"koor_hanya_kosong_{prodi_id}_{tahun_kurikulum}",
        )

    mk_tampil = mk_df
    if cari:
        mk_tampil = mk_tampil[
            mk_tampil["Kode MK"].astype(str).str.lower().str.contains(cari)
            | mk_tampil["Nama Mata Kuliah"].astype(str).str.lower().str.contains(cari)
        ]
    if hanya_kosong:
        mk_tampil = mk_tampil[mk_tampil["koordinator_user_id"].isna() & mk_tampil["koordinator_nip"].isna()]
    if urutan == "Kode MK (A-Z)":
        mk_tampil = mk_tampil.sort_values("Kode MK")
    elif urutan == "Nama MK (A-Z)":
        mk_tampil = mk_tampil.sort_values("Nama Mata Kuliah")
    else:
        mk_tampil = mk_tampil.sort_values("Semester")

    st.caption(f"Menampilkan {len(mk_tampil)} dari {len(mk_df)} Mata Kuliah.")
    if mk_tampil.empty:
        st.caption("Tidak ada Mata Kuliah yang cocok dengan pencarian/filter ini.")

    dosen_rows = list_dosen(client)
    label_by_id = {d["id"]: (d.get("nama") or d["email"]) for d in dosen_rows}
    id_by_label = {v: k for k, v in label_by_id.items()}

    menunggu_rows = list_whitelist_menunggu(client)
    label_by_nip = {w["nip"]: f"{w['nama']} (NIP {w['nip']}, belum Daftar)" for w in menunggu_rows}
    nip_by_label = {v: k for k, v in label_by_nip.items()}

    dosen_options = [BELUM_DITETAPKAN] + list(id_by_label.keys()) + list(label_by_nip.values())

    for _, mk in mk_tampil.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                st.markdown(f"**{mk['Kode MK']}** · {mk['Nama Mata Kuliah']}")
            with col2:
                # Catatan: nilai kosong dari kolom Pandas yang bercampur
                # string (UUID/NIP) dan None akan otomatis menjadi NaN
                # (float) - bukan None - dan bool(NaN) adalah True di
                # Python. Pakai pd.notna() supaya baris kosong tidak
                # dianggap "ada isinya".
                koor_id = mk.get("koordinator_user_id")
                koor_nip = mk.get("koordinator_nip")
                if pd.notna(koor_id):
                    current_label = label_by_id.get(koor_id, BELUM_DITETAPKAN)
                elif pd.notna(koor_nip):
                    current_label = label_by_nip.get(koor_nip, f"(NIP {koor_nip}, belum Daftar)")
                else:
                    current_label = BELUM_DITETAPKAN
                pilihan = st.selectbox(
                    "Koordinator", dosen_options,
                    index=dosen_options.index(current_label) if current_label in dosen_options else 0,
                    key=f"koor_{mk['id']}", label_visibility="collapsed",
                )
            with col3:
                st.write("")
                if st.button("💾", key=f"save_koor_{mk['id']}", help="Simpan koordinator"):
                    try:
                        if pilihan in id_by_label:
                            set_koordinator_mk(client, mk["id"], koordinator_id=id_by_label[pilihan])
                        elif pilihan in nip_by_label:
                            set_koordinator_mk(client, mk["id"], koordinator_nip=nip_by_label[pilihan])
                        else:
                            set_koordinator_mk(client, mk["id"])
                        st.session_state[f"_pesan_koor_{prodi_id}_{tahun_kurikulum}"] = "Koordinator diperbarui."
                        load_master_db.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal memperbarui: {e}")