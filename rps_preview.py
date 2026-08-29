# -*- coding: utf-8 -*-
"""
Pratinjau isi RPS (read-only) - dipakai bersama oleh kaprodi_panel.py (tab
"Review RPS") dan bpm_panel.py, supaya Kaprodi/BPM bisa membaca seluruh
isian RPS sebelum menyetujui/menolak, tanpa perlu berpindah halaman atau
mengunduh dokumennya dulu. Murni tampilan - tidak ada widget untuk mengedit.
"""

import pandas as pd
import streamlit as st

KATEGORI_PENILAIAN = ["Interaksi", "UTS", "Tugas", "UAS"]
BOBOT_KATEGORI = {"Interaksi": 30, "UTS": 20, "Tugas": 20, "UAS": 30}


def _get(d, key_int):
    """Ambil field dari dict yang key-nya bisa berupa int (saat masih di
    session_state sebelum disimpan) ATAU string (sesudah disimpan sebagai
    JSONB - JSON tidak punya key integer, semua jadi teks "1", "2", dst)."""
    if d is None:
        return {}
    return d.get(str(key_int)) or d.get(key_int) or {}


def render_rps_preview(data, cpl_df):
    """Tampilkan seluruh isian RPS (kolom `data` dari tabel rps) secara
    read-only. Panggil ini di dalam st.expander milik pemanggil."""
    data = data or {}
    info_umum = data.get("info_umum") or {}
    cpmk_data = data.get("cpmk_data") or {}
    pertemuan_data = data.get("pertemuan_data") or {}
    komponen_data = data.get("komponen_data") or {}
    referensi_data = data.get("referensi_data") or []

    st.markdown("**Deskripsi Mata Kuliah**")
    st.write(info_umum.get("deskripsi_mk") or "*(belum diisi)*")

    st.markdown("**CPL & CPMK**")
    rows_cpmk = []
    for i in range(1, 6):
        c = _get(cpmk_data, i)
        kode = c.get("cpl_kode") or "-"
        desk_cpl = "-"
        if cpl_df is not None and not cpl_df.empty and "Kode CPL" in cpl_df.columns:
            cocok = cpl_df.loc[cpl_df["Kode CPL"] == kode, "Deskripsi CPL"]
            if len(cocok):
                desk_cpl = cocok.values[0]
        rows_cpmk.append({
            "CPMK": f"CPMK-{i}", "Kode CPL": kode,
            "Deskripsi CPL": desk_cpl, "Deskripsi CPMK": c.get("deskripsi") or "-",
        })
    st.dataframe(pd.DataFrame(rows_cpmk), use_container_width=True, hide_index=True)

    st.markdown("**16 Pertemuan**")
    rows_pertemuan = []
    for m in range(1, 17):
        p = _get(pertemuan_data, m)
        rows_pertemuan.append({
            "Minggu": m,
            "Sub-CPMK": p.get("sub_cpmk_desc") or "-",
            "Bahan Kajian / Materi": p.get("materi") or "-",
            "Bentuk Pembelajaran": ", ".join(p.get("bentuk") or []) or "-",
            "Bentuk Asesmen": p.get("bentuk_asesmen") or "-",
        })
    st.dataframe(pd.DataFrame(rows_pertemuan), use_container_width=True, hide_index=True, height=380)

    st.markdown("**Daftar Pustaka**")
    st.caption(f"Level Penggunaan AI: **{info_umum.get('level_ai') or '(belum dipilih)'}**")
    if info_umum.get("deskripsi_ai"):
        st.caption(info_umum["deskripsi_ai"])
    if referensi_data:
        for i, r in enumerate(referensi_data, start=1):
            st.write(f"{i}. {r.get('sitasi', '-')}")
    else:
        st.write("*(belum ada referensi)*")

    st.markdown("**Komponen Penilaian**")
    rows_nilai = []
    totals = {k: 0 for k in KATEGORI_PENILAIAN}
    for i in range(1, 6):
        k = _get(komponen_data, i)
        row = {"CPMK": f"CPMK-{i}"}
        for kat in KATEGORI_PENILAIAN:
            val = k.get(kat, 0) or 0
            row[kat] = val
            totals[kat] += val
        rows_nilai.append(row)
    st.dataframe(pd.DataFrame(rows_nilai), use_container_width=True, hide_index=True)
    st.caption(" · ".join(
        f"{kat}: {totals[kat]}% (target {BOBOT_KATEGORI[kat]}%)" +
        (" \u2705" if totals[kat] == BOBOT_KATEGORI[kat] else " \u26A0\uFE0F")
        for kat in KATEGORI_PENILAIAN
    ))