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

    # Siapkan field tampilan sekali di awal, dipakai bareng untuk cari/filter/sortir
    # dan render kartu di bawah - supaya tidak dihitung ulang dua kali per baris.
    entri = []
    for row in rows:
        mk = row.get("mata_kuliah") or {}
        prodi = mk.get("prodi") or {}
        info_umum = (row.get("data") or {}).get("info_umum") or {}
        nama_dosen = info_umum.get("dosen_koordinator") or info_umum.get("nama_koordinator") or "-"
        entri.append({
            "row": row, "mk": mk, "prodi": prodi, "nama_dosen": nama_dosen,
            "nama_mk": mk.get("nama_mk", "-"), "kode_mk": mk.get("kode_mk", "-"),
            "nama_prodi": prodi.get("nama", "-"),
            "diproses_pada": row.get("diproses_pada") or "",
        })

    prodi_list = sorted({e["nama_prodi"] for e in entri})
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        cari = st.text_input(
            "🔍 Cari (Nama/Kode MK atau nama Koordinator)", key="bpm_cari",
        ).strip().lower()
    with c2:
        prodi_filter = st.selectbox("Filter Prodi", ["Semua"] + prodi_list, key="bpm_filter_prodi")
    with c3:
        urutan = st.selectbox(
            "Urutkan", ["Terlama menunggu", "Terbaru menunggu", "Nama MK (A-Z)"],
            key="bpm_urutan",
        )

    if cari:
        entri = [
            e for e in entri
            if cari in e["nama_mk"].lower() or cari in e["kode_mk"].lower()
            or cari in e["nama_dosen"].lower()
        ]
    if prodi_filter != "Semua":
        entri = [e for e in entri if e["nama_prodi"] == prodi_filter]

    if urutan == "Terlama menunggu":
        entri.sort(key=lambda e: e["diproses_pada"])
    elif urutan == "Terbaru menunggu":
        entri.sort(key=lambda e: e["diproses_pada"], reverse=True)
    else:
        entri.sort(key=lambda e: e["nama_mk"])

    if not entri:
        st.info("Tidak ada RPS yang cocok dengan pencarian/filter di atas.")
        return

    st.caption(f"Menampilkan {len(entri)} dari {len(rows)} RPS dalam antrian.")

    for e in entri:
        row, mk, prodi, nama_dosen = e["row"], e["mk"], e["prodi"], e["nama_dosen"]

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