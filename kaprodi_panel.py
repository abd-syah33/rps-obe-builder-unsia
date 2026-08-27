# -*- coding: utf-8 -*-
"""Fase 5: panel Kaprodi - tinjau & setujui/tolak RPS yang diajukan Dosen di
Program Studi yang diampu."""

import streamlit as st

from db_master import list_tahun_kurikulum
from rps_store import list_diajukan, setujui_rps, tolak_rps
from koordinator_ui import render_koordinator_tab
from kurikulum_ui import render_mk_editor, render_cpl_editor


def render_kaprodi_panel(client, pengguna):
    st.title("✅ Panel Kaprodi · RPS Builder")
    st.caption("Tinjau RPS yang diajukan, kelola kurikulum, dan tetapkan koordinator di Program Studi Anda.")

    if not pengguna.get("prodi_id"):
        st.warning(
            "Akun Anda belum ditetapkan mengampu Program Studi mana pun. "
            "Hubungi Admin untuk mengatur ini lewat Panel Admin -> tab Pengguna."
        )
        return

    prodi_id = pengguna["prodi_id"]
    tahun_options = list_tahun_kurikulum(client, prodi_id)
    tahun_sel = st.selectbox(
        "Tahun Kurikulum", tahun_options,
        index=len(tahun_options) - 1,  # default ke tahun terbaru
        key=f"kaprodi_tahun_sel_{prodi_id}",
    )

    tab_review, tab_mk, tab_koor, tab_cpl = st.tabs(
        ["✅ Review RPS", "📚 Mata Kuliah", "🎓 Koordinator", "🎯 CPL"]
    )

    with tab_review:
        render_review_rps(client)

    with tab_mk:
        render_mk_editor(client, prodi_id, tahun_sel)

    with tab_koor:
        render_koordinator_tab(client, prodi_id, tahun_sel)

    with tab_cpl:
        render_cpl_editor(client, prodi_id, tahun_sel)


def render_review_rps(client):
    rows = list_diajukan(client)
    if not rows:
        st.info("Tidak ada RPS yang sedang menunggu persetujuan saat ini.")
        return

    for row in rows:
        mk = row.get("mata_kuliah") or {}
        prodi = mk.get("prodi") or {}
        info_umum = (row.get("data") or {}).get("info_umum") or {}
        nama_dosen = info_umum.get("dosen_koordinator") or info_umum.get("nama_koordinator") or "-"

        with st.container(border=True):
            st.markdown(
                f"**{mk.get('nama_mk', '-')}** ({mk.get('kode_mk', '-')}) · "
                f"Kurikulum {mk.get('tahun_kurikulum', '-')} · {prodi.get('nama', '-')}"
            )
            st.caption(f"Dosen: {nama_dosen} · diajukan {row.get('updated_at', '-')}")

            catatan = st.text_area(
                "Catatan (wajib diisi kalau menolak, opsional kalau menyetujui)",
                key=f"catatan_{row['id']}", height=70,
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Setujui", key=f"setuju_{row['id']}", use_container_width=True, type="primary"):
                    try:
                        setujui_rps(client, row["id"], catatan.strip() or None)
                        st.success("RPS disetujui - lanjut ke tahap validasi BPM.")
                        list_diajukan.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal menyetujui: {e}")
            with col2:
                if st.button("↩️ Tolak", key=f"tolak_{row['id']}", use_container_width=True):
                    if not catatan.strip():
                        st.warning("Isi catatan alasan penolakan dulu (kolom di atas).")
                    else:
                        try:
                            tolak_rps(client, row["id"], catatan.strip())
                            st.success("RPS ditolak, catatan tersimpan untuk Dosen.")
                            list_diajukan.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal menolak: {e}")