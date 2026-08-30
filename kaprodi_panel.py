# -*- coding: utf-8 -*-
"""Fase 5: panel Kaprodi - tinjau & setujui/tolak RPS yang diajukan Dosen di
Program Studi yang diampu."""

import streamlit as st

from db_master import get_tahun_kurikulum_terbaru, index_tahun_default, list_tahun_kurikulum, load_master_db
from rps_store import (
    buka_kembali_rps,
    list_diajukan,
    list_divalidasi_by_prodi,
    setujui_rps,
    tolak_rps,
)
from koordinator_ui import render_koordinator_tab
from kurikulum_ui import render_mk_editor, render_cpl_editor
from rps_preview import render_rps_preview
from stats_ui import render_statistik_kaprodi


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
        index=index_tahun_default(tahun_options, get_tahun_kurikulum_terbaru(client, prodi_id)),
        key=f"kaprodi_tahun_sel_{prodi_id}",
    )

    tab_stats, tab_review, tab_revisi, tab_mk, tab_koor, tab_cpl = st.tabs(
        ["📊 Statistik", "✅ Review RPS", "🔓 Buka Kembali RPS Final", "📚 Mata Kuliah", "🎓 Koordinator", "🎯 CPL"]
    )

    with tab_stats:
        render_statistik_kaprodi(client, prodi_id)

    with tab_review:
        render_review_rps(client)

    with tab_revisi:
        render_buka_kembali(client, prodi_id)

    with tab_mk:
        render_mk_editor(client, prodi_id, tahun_sel)

    with tab_koor:
        render_koordinator_tab(client, prodi_id, tahun_sel)

    with tab_cpl:
        render_cpl_editor(client, prodi_id, tahun_sel)


def render_review_rps(client):
    pesan_review = st.session_state.pop("_pesan_review_rps", None)
    if pesan_review:
        st.success(pesan_review)

    rows = list_diajukan(client)
    if not rows:
        st.info("Tidak ada RPS yang sedang menunggu persetujuan saat ini.")
        return

    entri = []
    for row in rows:
        mk = row.get("mata_kuliah") or {}
        prodi = mk.get("prodi") or {}
        info_umum = (row.get("data") or {}).get("info_umum") or {}
        nama_dosen = info_umum.get("dosen_koordinator") or "-"
        entri.append({
            "row": row, "mk": mk, "prodi": prodi, "nama_dosen": nama_dosen,
            "nama_mk": mk.get("nama_mk", "-"), "kode_mk": mk.get("kode_mk", "-"),
            "updated_at": row.get("updated_at") or "",
        })

    c1, c2 = st.columns([2, 1])
    with c1:
        cari = st.text_input(
            "🔍 Cari (Nama/Kode MK atau nama Dosen)", key="kaprodi_review_cari",
        ).strip().lower()
    with c2:
        urutan = st.selectbox(
            "Urutkan", ["Terlama menunggu", "Terbaru menunggu", "Nama MK (A-Z)"],
            key="kaprodi_review_urutan",
        )

    if cari:
        entri = [
            e for e in entri
            if cari in e["nama_mk"].lower() or cari in e["kode_mk"].lower()
            or cari in e["nama_dosen"].lower()
        ]

    if urutan == "Terlama menunggu":
        entri.sort(key=lambda e: e["updated_at"])
    elif urutan == "Terbaru menunggu":
        entri.sort(key=lambda e: e["updated_at"], reverse=True)
    else:
        entri.sort(key=lambda e: e["nama_mk"])

    if not entri:
        st.info("Tidak ada RPS yang cocok dengan pencarian di atas.")
        return

    st.caption(f"Menampilkan {len(entri)} dari {len(rows)} RPS yang menunggu.")

    for e in entri:
        row, mk, prodi, nama_dosen = e["row"], e["mk"], e["prodi"], e["nama_dosen"]

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
            with st.expander("\U0001F441\uFE0F Lihat Detail Pengisian RPS"):
                _, cpl_df = load_master_db(client, mk.get("prodi_id"), mk.get("tahun_kurikulum"))
                render_rps_preview(row.get("data"), cpl_df)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Setujui", key=f"setuju_{row['id']}", use_container_width=True, type="primary"):
                    try:
                        setujui_rps(client, row["id"], catatan.strip() or None)
                        st.session_state["_pesan_review_rps"] = "RPS disetujui - lanjut ke tahap validasi BPM."
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
                            st.session_state["_pesan_review_rps"] = "RPS ditolak, catatan tersimpan untuk Dosen."
                            list_diajukan.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal menolak: {e}")


def render_buka_kembali(client, prodi_id):
    pesan_buka = st.session_state.pop("_pesan_buka_kembali", None)
    if pesan_buka:
        st.success(pesan_buka)
    st.caption(
        "Buka kembali RPS yang sudah FINAL (divalidasi BPM) untuk direvisi - dipakai "
        "kalau ada kesalahan yang baru ketahuan setelah RPS resmi berlaku. Isi "
        "dokumennya tetap seperti versi final terakhir, koordinator tinggal edit dari "
        "situ. RPS ini akan **hilang sementara dari halaman \"RPS Tervalidasi\"** "
        "sampai diajukan dan lolos Kaprodi + BPM lagi dari awal - bukan langsung "
        "final lagi begitu selesai direvisi."
    )
    rows = list_divalidasi_by_prodi(client, prodi_id)
    if not rows:
        st.info("Tidak ada RPS yang sudah final (divalidasi) di Prodi ini untuk kurikulum manapun.")
        return

    cari = st.text_input(
        "🔍 Cari (Nama/Kode Mata Kuliah)", key="kaprodi_revisi_cari",
    ).strip().lower()
    if cari:
        rows = [
            r for r in rows
            if cari in (r.get("mata_kuliah") or {}).get("nama_mk", "").lower()
            or cari in str((r.get("mata_kuliah") or {}).get("kode_mk", "")).lower()
        ]
    if not rows:
        st.info("Tidak ada RPS final yang cocok dengan pencarian ini.")
        return

    for row in rows:
        mk = row.get("mata_kuliah") or {}
        with st.container(border=True):
            st.markdown(
                f"**{mk.get('nama_mk', '-')}** ({mk.get('kode_mk', '-')}) · "
                f"Kurikulum {mk.get('tahun_kurikulum', '-')}"
            )
            st.caption(f"Divalidasi BPM: {row.get('diproses_pada_bpm', '-')}")

            konfirmasi_key = f"konfirmasi_buka_{row['id']}"
            catatan_key = f"catatan_buka_{row['id']}"

            if st.session_state.get(konfirmasi_key):
                st.warning(
                    "⚠️ RPS ini akan kembali ke status **Draft** dan langsung hilang dari "
                    "\"RPS Tervalidasi\" sampai diajukan & divalidasi ulang dari awal. "
                    "Yakin lanjutkan?"
                )
                catatan_alasan = st.text_area(
                    "Alasan dibuka kembali (akan terlihat oleh Dosen koordinator)",
                    key=catatan_key, height=70,
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        "✅ Ya, Buka untuk Revisi", key=f"ya_buka_{row['id']}",
                        use_container_width=True, type="primary",
                    ):
                        try:
                            buka_kembali_rps(client, row["id"], catatan_alasan.strip() or None)
                            st.session_state["_pesan_buka_kembali"] = (
                                "RPS dibuka kembali - sekarang berstatus Draft dan bisa diedit koordinatornya."
                            )
                            st.session_state[konfirmasi_key] = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal membuka kembali: {e}")
                with c2:
                    if st.button("❌ Batal", key=f"batal_buka_{row['id']}", use_container_width=True):
                        st.session_state[konfirmasi_key] = False
                        st.rerun()
            else:
                if st.button(
                    "🔓 Buka Kembali untuk Revisi", key=f"buka_{row['id']}",
                    use_container_width=True,
                ):
                    st.session_state[konfirmasi_key] = True
                    st.rerun()