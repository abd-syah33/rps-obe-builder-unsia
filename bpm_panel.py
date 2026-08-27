# -*- coding: utf-8 -*-
"""Panel BPM (Biro Penjaminan Mutu) - validasi TAHAP KEDUA setelah Kaprodi
menyetujui (status 'disetujui' -> 'divalidasi'). Cakupan SE-INSTITUSI (semua
Prodi, tidak dibatasi seperti Kaprodi) - lihat policy RLS "bpm baca rps
antrian & riwayat" di sql/schema.sql.

Kalau BPM menolak, RPS LANGSUNG kembali ke Dosen (status 'ditolak') - bukan
ke Kaprodi dulu. Saat Dosen mengajukan ulang, otomatis masuk antrian Kaprodi
lagi dari awal (lihat catatan di ajukan_rps() pada sql/schema.sql)."""

import streamlit as st

from rps_store import list_bpm_queue, validasi_bpm_rps, tolak_bpm_rps


def render_bpm_panel(client, pengguna):
    st.title("✅ Panel BPM · RPS Builder")
    st.caption(
        "Validasi RPS yang sudah disetujui Kaprodi, dari SEMUA Program Studi. "
        "RPS baru muncul di menu \"RPS Tervalidasi\" (bisa dilihat semua Dosen) "
        "setelah lolos validasi di sini."
    )

    rows = list_bpm_queue(client)
    if not rows:
        st.info("Tidak ada RPS yang sedang menunggu validasi BPM saat ini.")
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
            st.caption(
                f"Koordinator: {nama_dosen} · disetujui Kaprodi "
                f"{row.get('diproses_pada', '-')}"
            )

            catatan = st.text_area(
                "Catatan (wajib diisi kalau menolak, opsional kalau memvalidasi)",
                key=f"catatan_bpm_{row['id']}", height=70,
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Validasi", key=f"validasi_{row['id']}", use_container_width=True, type="primary"):
                    try:
                        validasi_bpm_rps(client, row["id"], catatan.strip() or None)
                        st.success("RPS divalidasi - sekarang final dan muncul di RPS Tervalidasi.")
                        list_bpm_queue.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal memvalidasi: {e}")
            with col2:
                if st.button("↩️ Tolak", key=f"tolak_bpm_{row['id']}", use_container_width=True):
                    if not catatan.strip():
                        st.warning("Isi catatan alasan penolakan dulu (kolom di atas).")
                    else:
                        try:
                            tolak_bpm_rps(client, row["id"], catatan.strip())
                            st.success("RPS ditolak, langsung kembali ke Dosen untuk direvisi.")
                            list_bpm_queue.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal menolak: {e}")