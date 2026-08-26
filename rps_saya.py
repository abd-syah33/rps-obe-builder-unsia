# -*- coding: utf-8 -*-
"""Halaman "RPS Saya" - daftar Mata Kuliah yang dikoordinatori user yang
login saat ini, beserta status pengisian RPS-nya.

Penyesuaian: berbasis penugasan koordinator SAAT INI (mata_kuliah.
koordinator_user_id), bukan lagi riwayat "siapa yang pernah mengisi" - kalau
koordinator sebuah Mata Kuliah diganti, Mata Kuliah itu otomatis pindah dari
daftar koordinator lama ke koordinator baru."""

import streamlit as st

from rps_store import list_my_rps, load_riwayat

STATUS_LABEL = {
    "draft": "📝 Draft",
    "diajukan": "📤 Diajukan",
    "disetujui": "✅ Disetujui",
    "ditolak": "↩️ Ditolak",
}


def render_rps_saya(client, pengguna):
    st.title("📋 RPS Saya")
    st.caption("Mata Kuliah yang Anda koordinatori, beserta status pengisian RPS-nya.")

    rows = list_my_rps(client, pengguna["id"])
    if not rows:
        st.info(
            "Anda belum ditetapkan sebagai koordinator Mata Kuliah manapun. "
            "Hubungi Kaprodi/Admin Program Studi terkait."
        )
        return

    for mk in rows:
        prodi = mk.get("prodi") or {}
        nama_mk = mk.get("nama_mk", "-")
        kode_mk = mk.get("kode_mk", "-")
        tahun_kurikulum = mk.get("tahun_kurikulum", "-")

        rps_list = mk.get("rps") or []
        rps_row = rps_list[0] if rps_list else None
        status = rps_row.get("status", "draft") if rps_row else None

        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{nama_mk}** ({kode_mk}) · Kurikulum {tahun_kurikulum}")
                if rps_row:
                    st.caption(
                        f"{prodi.get('nama', '-')} · {STATUS_LABEL.get(status, status)} · "
                        f"terakhir diubah {rps_row.get('updated_at', '-')}"
                    )
                else:
                    st.caption(f"{prodi.get('nama', '-')} · ⬜ Belum diisi")
            with col2:
                if st.button("Buka ✏️", key=f"buka_{mk['id']}", use_container_width=True):
                    # Set key WIDGET selectbox-nya langsung (bukan variabel pelacak
                    # prodi_sel/mk_sel) - supaya di render berikutnya nilainya
                    # dianggap "berubah" dan logika muat-ulang RPS di app.py
                    # otomatis jalan. Untuk pindah TAB menu, tidak bisa langsung
                    # set session_state["menu_utama"] di sini karena widget itu
                    # sudah diinstansiasi lebih dulu di app.py pada render ini -
                    # dipakai flag "_jump_to_isi_rps" yang dibaca app.py SEBELUM
                    # widget menu_utama dirender di rerun berikutnya.
                    st.session_state["prodi_selectbox"] = prodi.get("nama")
                    st.session_state["tahun_selectbox"] = tahun_kurikulum
                    st.session_state["mk_selectbox"] = nama_mk
                    st.session_state["_jump_to_isi_rps"] = True
                    st.rerun()

            if rps_row and status == "ditolak" and rps_row.get("catatan_kaprodi"):
                st.warning(f"**Catatan Kaprodi:** {rps_row['catatan_kaprodi']}")

            if rps_row:
                riwayat = load_riwayat(client, rps_row["id"], limit=5)
                if len(riwayat) > 1:
                    with st.expander(f"🕒 Riwayat perubahan ({len(riwayat)} tersimpan terakhir)"):
                        for r in riwayat:
                            st.caption(f"{r['diubah_pada']} · {STATUS_LABEL.get(r['status'], r['status'])}")