# -*- coding: utf-8 -*-
"""
Fase 3: panel admin sederhana untuk kelola data master (Prodi, Mata Kuliah,
CPL) langsung dari aplikasi - menggantikan edit file Excel manual.

Fase 5: ditambah dashboard statistik RPS & tab kelola peran pengguna
(assign Kaprodi ke Prodi yang diampu).

Penyesuaian: hapus baris data master (Mata Kuliah/CPL/Whitelist/Pengguna)
lewat editor sekarang BENAR-BENAR menghapus dari database (lihat
save_mata_kuliah_df, save_cpl_df, save_whitelist_df di db_master.py) -
sebelumnya cuma dilewati diam-diam saat disimpan (baris "terhapus" itu
muncul lagi setelah reload, membingungkan). Pengecekan "dipakai di RPS mana
saja" yang tadinya ditunda kini sudah diterapkan: Mata Kuliah dilindungi
langsung oleh database (foreign key), CPL dicek manual (rujukan CPMK->CPL
cuma teks di JSONB, bukan foreign key sungguhan) - keduanya menolak
penghapusan (bukan diam-diam gagal) kalau masih dipakai. Tab Pengguna tetap
TIDAK punya opsi hapus baris sama sekali (num_rows="fixed") - itu memang
disengaja, akun cuma boleh dihapus lewat Supabase Dashboard (lihat
auth.py) supaya auth.users ikut terhapus, bukan cuma baris di tabel
pengguna.
"""

from collections import Counter

import pandas as pd
import streamlit as st

from db_master import (
    get_prodi_id,
    insert_prodi,
    list_prodi_db,
    list_pengguna,
    list_tahun_kurikulum,
    list_whitelist_all,
    save_pengguna_df,
    save_whitelist_df,
)
from rps_store import get_rps_stats
from koordinator_ui import render_koordinator_tab
from kurikulum_ui import render_mk_editor, render_cpl_editor


def render_stats(client):
    with st.expander("📊 Statistik RPS", expanded=True):
        stats_rows = get_rps_stats(client)
        if not stats_rows:
            st.caption("Belum ada RPS yang tersimpan sama sekali.")
            return

        status_count = Counter(r.get("status", "draft") for r in stats_rows)
        labels = [
            ("draft", "📝 Draft"), ("diajukan", "📤 Diajukan"),
            ("disetujui", "✅ Disetujui"), ("ditolak", "↩️ Ditolak"),
        ]
        cols = st.columns(4)
        for col, (key, label) in zip(cols, labels):
            col.metric(label, status_count.get(key, 0))

        prodi_count = Counter()
        for r in stats_rows:
            mk = r.get("mata_kuliah") or {}
            nama_prodi = (mk.get("prodi") or {}).get("nama", "-")
            prodi_count[nama_prodi] += 1
        df_prodi = pd.DataFrame(sorted(prodi_count.items()), columns=["Program Studi", "Jumlah RPS"])
        st.dataframe(df_prodi, use_container_width=True, hide_index=True)


def render_admin_panel(client):
    st.title("⚙️ Panel Admin · RPS Builder")
    st.caption("Kelola data master Program Studi, Mata Kuliah, CPL, dan pantau progres pengisian RPS.")

    render_stats(client)
    st.divider()

    with st.expander("➕ Tambah Program Studi baru"):
        with st.form("form_prodi_baru"):
            nama_prodi_baru = st.text_input(
                "Nama Program Studi",
                help="Bebas, tapi disarankan konsisten dengan penamaan yang sudah ada "
                     "(mis. 'Informatika PJJ S1').",
            )
            submit_prodi = st.form_submit_button("Simpan Program Studi")
        if submit_prodi:
            if not nama_prodi_baru.strip():
                st.warning("Nama Program Studi tidak boleh kosong.")
            else:
                try:
                    insert_prodi(client, nama_prodi_baru)
                    st.success(f"Program Studi '{nama_prodi_baru}' berhasil ditambahkan.")
                    list_prodi_db.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menambah Program Studi: {e}")

    st.divider()

    prodi_rows = list_prodi_db(client)
    if not prodi_rows:
        st.info(
            "Belum ada Program Studi di database. Tambahkan lewat form di atas, atau "
            "jalankan `python scripts/migrate_excel_to_db.py` kalau datanya masih ada "
            "di file Excel lama (folder data/)."
        )
        return

    prodi_options = [p["nama"] for p in prodi_rows]
    prodi_sel = st.selectbox("Pilih Program Studi untuk dikelola", prodi_options, key="admin_prodi_sel")
    prodi_id = get_prodi_id(prodi_rows, prodi_sel)

    tahun_options = list_tahun_kurikulum(client, prodi_id)
    tahun_sel = st.selectbox(
        "Tahun Kurikulum", tahun_options,
        index=len(tahun_options) - 1,  # default ke tahun terbaru
        key=f"admin_tahun_sel_{prodi_id}",
    )

    tab_mk, tab_koor, tab_cpl, tab_pengguna, tab_whitelist = st.tabs(
        ["📚 Mata Kuliah", "🎓 Koordinator", "🎯 CPL", "👥 Pengguna", "📋 Pra-daftar"]
    )

    with tab_mk:
        render_mk_editor(client, prodi_id, tahun_sel)

    with tab_koor:
        render_koordinator_tab(client, prodi_id, tahun_sel)

    with tab_cpl:
        render_cpl_editor(client, prodi_id, tahun_sel)

    with tab_pengguna:
        st.caption(
            "Ubah Nama, NIP, Role, dan Prodi Homebase siapa pun yang sudah pernah "
            "Daftar - tabel ini bisa ditempel langsung dari Excel (klik sel **Nama** "
            "paling atas dulu, baru tempel). Kolom **Email** tidak bisa diubah (cuma "
            "penanda akun mana yang dimaksud). **Prodi Homebase** ditulis sebagai "
            "nama Prodi (mis. 'Informatika PJJ S1') - berlaku untuk semua peran, "
            "tapi untuk Dosen sifatnya cuma Prodi default saat login, TIDAK "
            "membatasi - Dosen tetap bebas mengisi RPS/jadi koordinator di Prodi lain. "
            "Untuk Kaprodi, ini juga menentukan Prodi yang diampu (batasan wewenang)."
        )
        pengguna_rows = list_pengguna(client)
        if not pengguna_rows:
            st.info("Belum ada yang Daftar lewat aplikasi.")
        else:
            prodi_nama_by_id = {p["id"]: p["nama"] for p in prodi_rows}
            id_by_email = {p["email"]: p["id"] for p in pengguna_rows}
            df_pengguna = pd.DataFrame(
                [
                    {
                        "Email": p.get("email", "-"),
                        "Nama": p.get("nama") or "",
                        "NIP": p.get("nip") or "",
                        "Role": p.get("role") or "dosen",
                        "Prodi Homebase": prodi_nama_by_id.get(p.get("prodi_id"), ""),
                    }
                    for p in pengguna_rows
                ],
                columns=["Email", "Nama", "NIP", "Role", "Prodi Homebase"],
            )
            edited_pengguna = st.data_editor(
                df_pengguna,
                num_rows="fixed",
                use_container_width=True,
                disabled=["Email"],
                column_config={
                    "Role": st.column_config.SelectboxColumn(options=["dosen", "kaprodi", "admin", "bpm"]),
                },
                key="pengguna_editor",
            )
            if st.button("💾 Simpan Perubahan Pengguna", key="save_pengguna_btn"):
                try:
                    n, tidak_dikenali = save_pengguna_df(client, edited_pengguna, prodi_rows, id_by_email)
                    st.success(f"{n} akun diperbarui.")
                    if tidak_dikenali:
                        daftar = ", ".join(f"{email} ('{nama}')" for email, nama in tidak_dikenali)
                        st.warning(
                            f"Nama Prodi tidak dikenali (Prodi Homebase TIDAK diubah untuk "
                            f"baris ini, field lain tetap tersimpan): {daftar}"
                        )
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")

    with tab_whitelist:
        st.caption(
            "Daftarkan NIP, Nama, dan Prodi Homebase Dosen SEBELUM mereka Daftar "
            "akun sendiri - berguna buat persiapan sebelum demo/pelatihan. Saat "
            "Daftar, NIP yang dimasukkan harus cocok dengan salah satu baris di "
            "sini, dan Nama + Prodi Homebase otomatis terisi dari daftar ini. Bisa "
            "juga langsung dipakai buat menetapkan koordinator Mata Kuliah (tab "
            "Koordinator) sebelum orangnya sempat Daftar - begitu Daftar, "
            "penugasannya otomatis tersambung. Hapus baris lewat ikon tempat "
            "sampah kalau memang salah input atau batal - baris yang dihapus di "
            "sini BENAR-BENAR terhapus dari database, tidak memengaruhi akun "
            "yang sudah aktif kalau orangnya sudah keburu Daftar.\n\n"
            "**Prodi Homebase** ditulis sebagai nama Prodi (mis. 'Informatika PJJ "
            "S1'), boleh dikosongkan kalau belum tahu.\n\n"
            "Tips: siapkan tiga kolom (NIP, Nama, Prodi Homebase) di Excel, salin, "
            "lalu tempel langsung ke tabel di bawah (klik sel NIP paling atas dulu)."
        )
        whitelist_rows = list_whitelist_all(client)
        df_whitelist = pd.DataFrame(
            [
                {
                    "NIP": w["nip"],
                    "Nama": w["nama"],
                    "Prodi Homebase": w.get("prodi_nama") or "",
                    "Status": "✅ Sudah Daftar" if w["sudah_daftar"] else "⏳ Menunggu",
                }
                for w in whitelist_rows
            ],
            columns=["NIP", "Nama", "Prodi Homebase", "Status"],
        )
        edited_whitelist = st.data_editor(
            df_whitelist,
            num_rows="dynamic",
            use_container_width=True,
            disabled=["Status"],
            key="whitelist_editor",
        )
        if st.button("💾 Simpan Daftar Pra-pendaftaran", key="save_whitelist_btn"):
            try:
                n, tidak_dikenali = save_whitelist_df(client, edited_whitelist, prodi_rows, df_whitelist)
                st.success(f"{n} baris disimpan.")
                if tidak_dikenali:
                    daftar = ", ".join(f"NIP {nip} ('{nama}')" for nip, nama in tidak_dikenali)
                    st.warning(
                        f"Nama Prodi tidak dikenali (Prodi Homebase TIDAK diisi untuk "
                        f"baris ini, NIP+Nama tetap tersimpan): {daftar}"
                    )
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")