# -*- coding: utf-8 -*-
"""Halaman "RPS Tervalidasi" - transparansi kurikulum: semua Dosen yang login
bisa MELIHAT & MENGUNDUH (bukan mengedit) RPS yang sudah lolos KEDUA tahap
validasi (Kaprodi menyetujui, LALU BPM memvalidasi), lintas Prodi. Akses
dijamin lewat policy RLS "semua dosen baca rps divalidasi" di sql/schema.sql
- hanya status='divalidasi' yang terbuka; draft/diajukan/disetujui (baru
lolos Kaprodi, masih menunggu BPM)/ditolak tetap privat.

Dokumen Word/PDF dibangun ULANG dari kolom `data` yang tersimpan (bukan dari
session_state - RPS ini bukan milik/sedang diedit oleh yang membuka halaman
ini), lewat pipeline export yang SAMA dengan tab Pratinjau & Ekspor di app.py.

Penyesuaian (template RPS baru): "Dosen Pengampu" & "Tanggal Penyusunan" di
dokumen yang diunduh dari sini SENGAJA dihitung ulang di sini juga (bukan
dipakai apa adanya dari data tersimpan) - persis prinsip yang sama dengan tab
Pratinjau & Ekspor: Dosen Pengampu = akun yang SEDANG mengunduh, Tanggal
Penyusunan = tanggal RPS ini diajukan (diajukan_pada), bukan tanggal proses."""

from datetime import datetime

import streamlit as st

from rps_store import list_divalidasi
from db_master import load_master_db
from docx_export import build_docx, build_pdf_via_libreoffice, find_soffice, BOBOT_KATEGORI


def _format_tanggal_indonesia(iso_str):
    """Duplikat kecil dari app.py punya nama sama - sengaja tidak diimpor dari
    app.py supaya rps_browse.py tidak circular-import ke app.py (app.py sendiri
    yang meng-import render_rps_tervalidasi dari modul ini)."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
    except ValueError:
        return None
    bulan = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    return f"{dt.day} {bulan[dt.month - 1]} {dt.year}"


def _data_to_export_args(data, tanggal_tampil, dosen_pengampu_tampil):
    info_umum = dict(data.get("info_umum") or {})
    info_umum["tanggal_dokumen"] = tanggal_tampil
    info_umum["dosen_pengampu"] = dosen_pengampu_tampil
    return {
        "info_umum": info_umum,
        "cpmk_data": {int(k): v for k, v in (data.get("cpmk_data") or {}).items()},
        "pertemuan_data": {int(k): v for k, v in (data.get("pertemuan_data") or {}).items()},
        "referensi_data": data.get("referensi_data") or [],
        "komponen_data": {int(k): v for k, v in (data.get("komponen_data") or {}).items()},
    }


def render_rps_tervalidasi(client, pengguna):
    st.title("📚 RPS Tervalidasi")
    st.caption(
        "RPS yang sudah lolos Kaprodi DAN BPM (final) - bisa dilihat & diunduh "
        "semua Dosen, tidak bisa diedit di sini."
    )

    rows = list_divalidasi(client)
    if not rows:
        st.info("Belum ada RPS yang tervalidasi (lolos Kaprodi & BPM) sejauh ini.")
        return

    prodi_list = sorted({
        ((r.get("mata_kuliah") or {}).get("prodi") or {}).get("nama", "-") for r in rows
    })
    prodi_filter = st.selectbox("Filter Program Studi", ["Semua"] + prodi_list, key="filter_prodi_tervalidasi")
    if prodi_filter != "Semua":
        rows = [
            r for r in rows
            if ((r.get("mata_kuliah") or {}).get("prodi") or {}).get("nama") == prodi_filter
        ]

    for row in rows:
        mk = row.get("mata_kuliah") or {}
        prodi = mk.get("prodi") or {}
        nama_mk = mk.get("nama_mk", "-")
        kode_mk = mk.get("kode_mk", "-")
        tahun_kurikulum = mk.get("tahun_kurikulum", "-")

        with st.container(border=True):
            st.markdown(f"**{nama_mk}** ({kode_mk}) · Kurikulum {tahun_kurikulum} · {prodi.get('nama', '-')}")
            st.caption(f"Tervalidasi {row.get('diproses_pada_bpm') or row.get('updated_at', '-')}")

            siapkan_key = f"_siapkan_{row['id']}"
            if st.button("📄 Siapkan Unduhan", key=f"btn_siapkan_{row['id']}"):
                st.session_state[siapkan_key] = True

            if st.session_state.get(siapkan_key):
                mk_row = {
                    "Nama Mata Kuliah": nama_mk,
                    "Kode MK": kode_mk,
                    "SKS": mk.get("sks"),
                    "Semester": mk.get("semester"),
                }
                _, cpl_df = load_master_db(client, mk.get("prodi_id"), tahun_kurikulum)
                tanggal_tampil = _format_tanggal_indonesia(row.get("diajukan_pada")) or "(belum diajukan)"
                dosen_pengampu_tampil = pengguna.get("nama") or pengguna.get("email")
                export_args = _data_to_export_args(row.get("data") or {}, tanggal_tampil, dosen_pengampu_tampil)

                docx_buf = build_docx(
                    prodi=prodi.get("nama", "-"), mk_row=mk_row, cpl_df=cpl_df,
                    bobot_kategori=BOBOT_KATEGORI, **export_args,
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "⬇️ Unduh Word (.docx)", data=docx_buf,
                        file_name=f"RPS_{kode_mk}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_docx_{row['id']}",
                    )
                with col2:
                    if find_soffice() is None:
                        st.caption("PDF butuh LibreOffice terpasang di komputer ini.")
                    else:
                        docx_buf.seek(0)
                        pdf_buf = build_pdf_via_libreoffice(docx_buf)
                        if pdf_buf is not None:
                            st.download_button(
                                "⬇️ Unduh PDF", data=pdf_buf,
                                file_name=f"RPS_{kode_mk}.pdf",
                                mime="application/pdf",
                                key=f"dl_pdf_{row['id']}",
                            )
                        else:
                            st.caption("Gagal membuat PDF - coba lagi, atau unduh Word saja.")