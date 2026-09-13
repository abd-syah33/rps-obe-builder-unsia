# -*- coding: utf-8 -*-
"""
Admin: lihat isi RPS siapa pun (lintas Prodi/Dosen) dan kunci/buka akses
edit RPS tertentu secara sepihak - lihat set_kunci_admin() di
sql/schema.sql & pengecekan dikunci_admin tambahan di app.py (bisa_edit,
auto_save_fragment, simpan_progres_button). Terpisah dari alur
persetujuan normal (Kaprodi/BPM) - murni alat bantu Admin untuk kasus
khusus, berlaku APA PUN status RPS-nya saat ini.
"""

import streamlit as st

from db_master import load_master_db
from rps_store import list_semua_rps_admin, set_kunci_admin
from rps_preview import render_rps_preview
from stats_ui import _nama_koordinator, _peta_nama_pengguna, _peta_nama_whitelist

STATUS_LABEL_RINGKAS = {
    None: "\u2b1c Belum Diisi",
    "draft": "\U0001F4DD Draft",
    "diajukan": "\U0001F4E4 Diajukan",
    "disetujui": "\u2705 Disetujui",
    "ditolak": "\u21A9\uFE0F Ditolak",
    "divalidasi": "\u2705 Final",
}


def render_kelola_rps_dosen(client, prodi_rows):
    st.caption(
        "Lihat isi RPS siapa pun dan kunci akses edit Dosen ke RPS tertentu kalau perlu "
        "(mis. sedang ditelusuri masalahnya) - berlaku APA PUN status RPS-nya saat ini, "
        "terpisah dari alur persetujuan Kaprodi/BPM yang biasa."
    )

    nama_prodi_opsi = ["Semua Program Studi"] + sorted({p["nama"] for p in prodi_rows})
    prodi_pilih = st.selectbox("Program Studi", nama_prodi_opsi, key="admin_kelola_rps_prodi")
    prodi_id_pilih = None
    if prodi_pilih != "Semua Program Studi":
        prodi_id_pilih = next((p["id"] for p in prodi_rows if p["nama"] == prodi_pilih), None)

    rows = list_semua_rps_admin(client, prodi_id_pilih)
    if not rows:
        st.info("Belum ada Mata Kuliah di sini.")
        return

    peta_pengguna = _peta_nama_pengguna(client)
    peta_whitelist = _peta_nama_whitelist(client)
    for r in rows:
        r["nama_koordinator"] = _nama_koordinator(r, peta_pengguna, peta_whitelist) or "(belum ada koordinator)"

    col_cari, col_status = st.columns([2, 1.3])
    with col_cari:
        cari = st.text_input(
            "\U0001F50D Cari (Kode/Nama Mata Kuliah/Dosen)", key="admin_kelola_rps_cari",
        ).strip().lower()
    with col_status:
        opsi_status = ["Semua"] + list(dict.fromkeys(STATUS_LABEL_RINGKAS.values()))
        status_pilih = st.selectbox("Filter Status", opsi_status, key="admin_kelola_rps_status")

    if cari:
        rows = [
            r for r in rows
            if cari in r["kode_mk"].lower() or cari in r["nama_mk"].lower()
            or cari in r["nama_koordinator"].lower()
        ]
    if status_pilih != "Semua":
        rows = [
            r for r in rows
            if STATUS_LABEL_RINGKAS.get((r["rps"] or {}).get("status")) == status_pilih
        ]

    st.caption(f"Menampilkan {len(rows)} Mata Kuliah.")
    if not rows:
        st.caption("Tidak ada yang cocok dengan pencarian/filter ini.")

    for r in rows:
        rps_row = r["rps"]
        label_status = STATUS_LABEL_RINGKAS.get(rps_row["status"] if rps_row else None, "-")
        with st.container(border=True):
            st.markdown(f"**{r['nama_mk']}** ({r['kode_mk']}) \u00B7 {r['prodi_nama']} \u00B7 Kurikulum {r['tahun_kurikulum']}")
            st.caption(f"Koordinator: {r['nama_koordinator']} \u00B7 Status: {label_status}")

            if not rps_row:
                st.caption("Belum ada RPS untuk Mata Kuliah ini - tidak ada yang bisa dilihat/dikunci.")
                continue

            with st.expander("\U0001F441\uFE0F Lihat Detail Pengisian RPS"):
                _, cpl_df = load_master_db(client, r["prodi_id"], r["tahun_kurikulum"])
                render_rps_preview(rps_row.get("data"), cpl_df)

            col_kunci, col_info = st.columns([1, 3])
            with col_kunci:
                if rps_row.get("dikunci_admin"):
                    if st.button("\U0001F513 Buka Akses Edit", key=f"buka_kunci_{rps_row['id']}", use_container_width=True):
                        try:
                            set_kunci_admin(client, rps_row["id"], False)
                            st.success("Akses edit dibuka kembali untuk Dosen.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal membuka akses: {e}")
                else:
                    if st.button("\U0001F512 Kunci Akses Edit", key=f"kunci_{rps_row['id']}", use_container_width=True):
                        try:
                            set_kunci_admin(client, rps_row["id"], True)
                            st.success("Akses edit RPS ini dikunci - Dosen tidak bisa mengedit sampai dibuka lagi.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal mengunci akses: {e}")
            with col_info:
                if rps_row.get("dikunci_admin"):
                    st.caption("\U0001F512 Sedang dikunci - Dosen tidak bisa mengedit RPS ini sama sekali.")