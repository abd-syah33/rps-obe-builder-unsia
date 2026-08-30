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

import pandas as pd
import streamlit as st

from db_master import (
    get_prodi_id,
    get_tahun_kurikulum_terbaru,
    index_tahun_default,
    insert_prodi,
    list_prodi_db,
    list_pengguna,
    list_tahun_kurikulum,
    list_whitelist_all,
    save_pengguna_df,
    save_whitelist_df,
    set_pejabat_utama,
    sinkronkan_nama_pejabat,
)
from koordinator_ui import render_koordinator_tab
from kurikulum_ui import render_mk_editor, render_cpl_editor
from stats_ui import render_statistik_institusi


def render_stats(client):
    with st.expander("📊 Statistik RPS", expanded=True):
        render_statistik_institusi(client, list_prodi_db(client))


def render_admin_panel(client):
    st.title("⚙️ Panel Admin · RPS Builder")
    st.caption("Kelola data master Program Studi, Mata Kuliah, CPL, dan pantau progres pengisian RPS.")

    render_stats(client)
    st.divider()

    with st.expander("➕ Tambah Program Studi baru"):
        pesan_prodi = st.session_state.pop("_pesan_prodi_baru", None)
        if pesan_prodi:
            st.success(pesan_prodi)
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
                    st.session_state["_pesan_prodi_baru"] = f"Program Studi '{nama_prodi_baru}' berhasil ditambahkan."
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
        index=index_tahun_default(tahun_options, get_tahun_kurikulum_terbaru(client, prodi_id)),
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
        pesan_pengguna = st.session_state.pop("_pesan_pengguna", None)
        if pesan_pengguna:
            if pesan_pengguna.get("sukses"):
                st.success(pesan_pengguna["sukses"])
            for w in pesan_pengguna.get("peringatan") or []:
                st.warning(w)
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
            df_pengguna_full = pd.DataFrame(
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
            cari_pengguna = st.text_input(
                "🔍 Cari (Nama, Email, atau NIP)", key="cari_pengguna",
            ).strip().lower()
            if cari_pengguna:
                mask = (
                    df_pengguna_full["Nama"].str.lower().str.contains(cari_pengguna, na=False)
                    | df_pengguna_full["Email"].str.lower().str.contains(cari_pengguna, na=False)
                    | df_pengguna_full["NIP"].str.lower().str.contains(cari_pengguna, na=False)
                )
                df_pengguna = df_pengguna_full[mask].reset_index(drop=True)
            else:
                df_pengguna = df_pengguna_full
            st.caption(f"Menampilkan {len(df_pengguna)} dari {len(df_pengguna_full)} pengguna. (Klik header kolom untuk mengurutkan.)")
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
                    peringatan_pengguna = []
                    if tidak_dikenali:
                        daftar = ", ".join(f"{email} ('{nama}')" for email, nama in tidak_dikenali)
                        peringatan_pengguna.append(
                            f"Nama Prodi tidak dikenali (Prodi Homebase TIDAK diubah untuk "
                            f"baris ini, field lain tetap tersimpan): {daftar}"
                        )
                    st.session_state["_pesan_pengguna"] = {
                        "sukses": f"{n} akun diperbarui.", "peringatan": peringatan_pengguna,
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")

        st.divider()
        st.markdown("#### \U0001F396\uFE0F Tetapkan Pejabat Resmi (Kaprodi & BPM)")
        pesan_pejabat = st.session_state.pop("_pesan_pejabat_utama", None)
        if pesan_pejabat:
            st.success(pesan_pejabat)
        st.caption(
            "Kalau ada LEBIH DARI SATU akun dengan role yang sama (mis. 2 akun ber-role "
            "BPM), field \"Nama Ketua Prodi\"/\"Nama Ka. BPM\" yang otomatis terisi saat "
            "Dosen mengisi RPS bisa salah ambil orang - tanpa ini, sistem cuma menebak "
            "sembarang salah satu. Tetapkan di sini siapa yang resmi."
        )
        kandidat_pejabat = [p for p in pengguna_rows if p.get("role") in ("kaprodi", "bpm")]
        if not kandidat_pejabat:
            st.caption("Belum ada akun dengan role Kaprodi atau BPM.")
        else:
            label_by_id_pejabat = {}
            for p in kandidat_pejabat:
                if p.get("role") == "kaprodi":
                    cakupan = prodi_nama_by_id.get(p.get("prodi_id"), "(Prodi belum diatur)")
                else:
                    cakupan = "se-institusi"
                tanda = " \u2B50 resmi saat ini" if p.get("pejabat_utama") else ""
                label = f"{p.get('nama') or p.get('email')} \u2014 {p.get('role').upper()} ({cakupan}){tanda}"
                label_by_id_pejabat[label] = p["id"]
            col_pilih, col_tombol = st.columns([3, 1])
            with col_pilih:
                pilihan_pejabat = st.selectbox(
                    "Pilih akun", list(label_by_id_pejabat.keys()), key="pejabat_utama_pilihan",
                    label_visibility="collapsed",
                )
            with col_tombol:
                if st.button("Jadikan Resmi", key="set_pejabat_utama_btn", use_container_width=True):
                    try:
                        set_pejabat_utama(client, label_by_id_pejabat[pilihan_pejabat])
                        st.session_state["_pesan_pejabat_utama"] = "Berhasil ditetapkan sebagai pejabat resmi."
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal menetapkan: {e}")

        st.caption(
            "Menetapkan pejabat resmi di atas TIDAK otomatis mengubah RPS yang sudah "
            "ada - nama Kaprodi/BPM yang tersimpan di tiap RPS \"membeku\" sejak RPS "
            "itu dibuat. Dokumen FINAL (RPS Tervalidasi) selalu memakai nama terkini "
            "secara otomatis, tapi tampilan info umum di RPS yang belum final (draft/"
            "diajukan/dst.) serta cadangan lokal yang diunduh masih memakai nilai "
            "lama sampai disinkronkan manual lewat tombol ini."
        )
        if st.button("🔄 Sinkronkan Nama Pejabat ke Semua RPS", key="sinkron_pejabat_btn"):
            try:
                jumlah = sinkronkan_nama_pejabat(client)
                st.session_state["_pesan_pejabat_utama"] = (
                    f"Berhasil disinkronkan - {jumlah} RPS diperbarui ke nama pejabat terkini."
                )
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyinkronkan: {e}")

    with tab_whitelist:
        pesan_whitelist = st.session_state.pop("_pesan_whitelist", None)
        if pesan_whitelist:
            if pesan_whitelist.get("sukses"):
                st.success(pesan_whitelist["sukses"])
            for w in pesan_whitelist.get("peringatan") or []:
                st.warning(w)
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
        df_whitelist_full = pd.DataFrame(
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
        cari_whitelist = st.text_input(
            "🔍 Cari (NIP atau Nama)", key="cari_whitelist",
        ).strip().lower()
        if cari_whitelist:
            mask = (
                df_whitelist_full["Nama"].str.lower().str.contains(cari_whitelist, na=False)
                | df_whitelist_full["NIP"].str.lower().str.contains(cari_whitelist, na=False)
            )
            # Penyesuaian: df_whitelist (versi TERSARING ini) dipakai baik untuk
            # ditampilkan MAUPUN sebagai "original_df" saat menyimpan di bawah -
            # SENGAJA, supaya baris yang sedang disembunyikan oleh pencarian ini
            # tidak ikut dibandingkan sama sekali (dan karenanya tidak pernah
            # salah dianggap "dihapus" oleh save_whitelist_df hanya karena tidak
            # sedang tampil).
            df_whitelist = df_whitelist_full[mask].reset_index(drop=True)
        else:
            df_whitelist = df_whitelist_full
        st.caption(f"Menampilkan {len(df_whitelist)} dari {len(df_whitelist_full)} baris. (Klik header kolom untuk mengurutkan.)")
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
                peringatan_whitelist = []
                if tidak_dikenali:
                    daftar = ", ".join(f"NIP {nip} ('{nama}')" for nip, nama in tidak_dikenali)
                    peringatan_whitelist.append(
                        f"Nama Prodi tidak dikenali (Prodi Homebase TIDAK diisi untuk "
                        f"baris ini, NIP+Nama tetap tersimpan): {daftar}"
                    )
                st.session_state["_pesan_whitelist"] = {
                    "sukses": f"{n} baris disimpan.", "peringatan": peringatan_whitelist,
                }
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")