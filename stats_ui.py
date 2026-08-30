# -*- coding: utf-8 -*-
"""
Statistik pengisian RPS - dipakai di 4 tempat berbeda dengan cakupan
berbeda-beda, semuanya lewat modul ini supaya logikanya tidak ditulis ulang:

- Dosen (RPS Saya): ringkasan status RPS-nya sendiri, dari data yang SUDAH
  diambil rps_saya.py lewat list_my_rps() - TIDAK query ulang ke database.
- Kaprodi (tab Statistik): breakdown per Dosen dalam SATU Prodi + peringatan
  Mata Kuliah yang belum punya koordinator sama sekali.
- BPM & Admin (tab/bagian Statistik): ringkasan se-institusi + tabel per
  Program Studi, lalu pilih satu Prodi lewat dropdown untuk lihat breakdown
  per Dosen (komponen yang SAMA dengan milik Kaprodi, dipanggil untuk Prodi
  manapun yang dipilih).

Kategori status SENGAJA dibuat lengkap (6, termasuk "Belum Diisi" untuk Mata
Kuliah yang belum punya RPS SAMA SEKALI) - data mentahnya diambil mulai dari
tabel mata_kuliah (bukan dari tabel rps), supaya Mata Kuliah yang belum
pernah disentuh tetap ikut terhitung, bukan hilang dari statistik.
"""

from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

STATUS_URUTAN = ["belum", "draft", "diajukan", "disetujui", "ditolak", "divalidasi"]
STATUS_LABEL = {
    "belum": "\u2b1c Belum Diisi",
    "draft": "\U0001F4DD Draft",
    "diajukan": "\U0001F4E4 Diajukan",
    "disetujui": "\u2705 Disetujui",
    "ditolak": "\u21A9\uFE0F Ditolak",
    "divalidasi": "\U0001F4D7 Final",
}
STATUS_WARNA = {
    "belum": "#9CA3AF",       # abu-abu
    "draft": "#93C5FD",       # biru muda
    "diajukan": "#2563EB",    # biru
    "disetujui": "#4ADE80",   # hijau
    "ditolak": "#EF4444",     # merah
    "divalidasi": "#15803D",  # hijau tua
}


def _status_dari_rps_list(rps_list):
    """rps_list adalah list embed dari PostgREST (0 atau 1 elemen, karena RPS
    unik per Mata Kuliah) - kembalikan kode status, "belum" kalau list
    kosong (Mata Kuliah ini belum punya RPS sama sekali)."""
    if not rps_list:
        return "belum"
    return rps_list[0].get("status") or "draft"


STATUS_LABEL_URUT = [STATUS_LABEL[k] for k in STATUS_URUTAN]
STATUS_WARNA_URUT = [STATUS_WARNA[k] for k in STATUS_URUTAN]


def _hitung_per_kategori(daftar_status):
    """daftar_status: list kode status mentah -> dict {kode: jumlah}, urut
    sesuai STATUS_URUTAN, termasuk kategori yang jumlahnya 0 (supaya tabel/
    chart tetap punya kolom yang sama setiap saat, tidak "loncat-loncat")."""
    c = Counter(daftar_status)
    return {k: c.get(k, 0) for k in STATUS_URUTAN}


def _chart_status_tunggal(hitung):
    """Bar chart satu seri (dipakai render_ringkasan_metrik) - urutan
    kategori DIPAKSA mengikuti STATUS_URUTAN (alur SOP: Belum Diisi ->
    Draft -> Diajukan -> Disetujui -> Ditolak -> Final). PENTING dibuat
    lewat Altair (bukan st.bar_chart polos) karena st.bar_chart otomatis
    mengurutkan kategori secara ALFABETIS (ikut karakter emoji di depan
    tiap label, bikin urutannya kelihatan acak) dan tidak punya opsi untuk
    memaksa urutan sendiri."""
    df = pd.DataFrame({
        "Status": STATUS_LABEL_URUT,
        "Jumlah": [hitung[k] for k in STATUS_URUTAN],
    })
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("Status:N", sort=STATUS_LABEL_URUT, title=None),
            y=alt.Y("Jumlah:Q"),
            color=alt.Color(
                "Status:N",
                sort=STATUS_LABEL_URUT,
                scale=alt.Scale(domain=STATUS_LABEL_URUT, range=STATUS_WARNA_URUT),
                legend=None,
            ),
            tooltip=["Status", "Jumlah"],
        )
    )
    st.altair_chart(chart, use_container_width=True)


def _chart_status_berkelompok(df, kolom_kategori):
    """Bar chart berkelompok per kategori (Program Studi/Dosen) - satu
    kelompok bar per Prodi/Dosen, isinya 6 batang status berdampingan,
    urutannya DIPAKSA mengikuti STATUS_URUTAN (sama alasannya seperti
    _chart_status_tunggal di atas)."""
    df_long = df.melt(
        id_vars=[kolom_kategori], value_vars=STATUS_LABEL_URUT,
        var_name="Status", value_name="Jumlah",
    )
    chart = (
        alt.Chart(df_long)
        .mark_bar()
        .encode(
            x=alt.X(f"{kolom_kategori}:N", title=None),
            xOffset=alt.XOffset("Status:N", sort=STATUS_LABEL_URUT),
            y=alt.Y("Jumlah:Q"),
            color=alt.Color(
                "Status:N",
                sort=STATUS_LABEL_URUT,
                scale=alt.Scale(domain=STATUS_LABEL_URUT, range=STATUS_WARNA_URUT),
            ),
            tooltip=[kolom_kategori, "Status", "Jumlah"],
        )
    )
    st.altair_chart(chart, use_container_width=True)


@st.cache_data(ttl=30)
def get_rps_progress_raw(_client, prodi_id=None):
    """Data mentah utk statistik: satu baris per Mata Kuliah, digabung ke
    status RPS-nya (kalau ada) dan info koordinator MENTAH (id/nip - belum
    di-resolve ke nama, lihat _nama_koordinator). prodi_id=None berarti
    SEMUA Program Studi (dipakai BPM/Admin); diisi untuk satu Prodi saja
    (dipakai Kaprodi).

    HANYA menyertakan Mata Kuliah dari Tahun Kurikulum TERBARU yang benar-
    benar sudah ada datanya di masing-masing Prodi (lihat
    get_tahun_kurikulum_terbaru di db_master.py) - supaya kurikulum lama
    yang sudah tidak relevan (mis. 2021) tidak ikut mencampuri statistik
    kurikulum yang sedang berjalan (mis. 2026). Tiap Prodi dihitung
    tahun terbarunya SENDIRI-SENDIRI (bukan satu potongan tahun untuk
    semua Prodi), karena Prodi yang belum pindah kurikulum baru tidak
    boleh ikut kepotong datanya."""
    query = _client.table("mata_kuliah").select(
        "kode_mk, nama_mk, prodi_id, tahun_kurikulum, koordinator_user_id, koordinator_nip, "
        "prodi(nama), rps(status)"
    )
    if prodi_id:
        query = query.eq("prodi_id", prodi_id)
    resp = query.execute()
    semua_baris = []
    for r in (resp.data or []):
        semua_baris.append({
            "kode_mk": r["kode_mk"], "nama_mk": r["nama_mk"],
            "prodi_nama": (r.get("prodi") or {}).get("nama", "-"),
            "tahun_kurikulum": r.get("tahun_kurikulum"),
            "koordinator_user_id": r.get("koordinator_user_id"),
            "koordinator_nip": r.get("koordinator_nip"),
            "status": _status_dari_rps_list(r.get("rps") or []),
        })

    tahun_terbaru_per_prodi = {}
    for r in semua_baris:
        p, t = r["prodi_nama"], r["tahun_kurikulum"]
        if t is not None and (p not in tahun_terbaru_per_prodi or t > tahun_terbaru_per_prodi[p]):
            tahun_terbaru_per_prodi[p] = t

    return [
        r for r in semua_baris
        if r["tahun_kurikulum"] == tahun_terbaru_per_prodi.get(r["prodi_nama"])
    ]


@st.cache_data(ttl=30)
def _peta_nama_pengguna(_client):
    resp = _client.table("pengguna").select("id, nama, email").execute()
    return {p["id"]: (p.get("nama") or p.get("email") or "-") for p in (resp.data or [])}


@st.cache_data(ttl=30)
def _peta_nama_whitelist(_client):
    resp = _client.table("whitelist_pendaftaran").select("nip, nama").execute()
    return {w["nip"]: w["nama"] for w in (resp.data or [])}


def _nama_koordinator(row, peta_pengguna, peta_whitelist):
    """Nama tampilan koordinator Mata Kuliah ini - lewat akun aktif kalau
    ada (koordinator_user_id), lewat data pra-daftar kalau belum bikin akun
    (koordinator_nip), atau None kalau Mata Kuliah ini SAMA SEKALI belum
    punya koordinator yang ditetapkan."""
    if row.get("koordinator_user_id"):
        return peta_pengguna.get(row["koordinator_user_id"], "(akun tidak dikenali)")
    if row.get("koordinator_nip"):
        return peta_whitelist.get(row["koordinator_nip"], f"NIP {row['koordinator_nip']} (belum daftar akun)")
    return None


def render_ringkasan_metrik(daftar_status, tampilkan_chart=True):
    """Baris kartu metrik (Total + 6 kategori) + bar chart untuk satu set
    status - dipakai di keempat tempat (Dosen/Kaprodi/BPM/Admin)."""
    hitung = _hitung_per_kategori(daftar_status)
    total = sum(hitung.values())
    cols = st.columns(len(STATUS_URUTAN) + 1)
    cols[0].metric("Total", total)
    for col, key in zip(cols[1:], STATUS_URUTAN):
        col.metric(STATUS_LABEL[key], hitung[key])
    if tampilkan_chart and total > 0:
        _chart_status_tunggal(hitung)


def render_tabel_per_prodi(rows, tampilkan_chart=True):
    """Tabel Program Studi x kategori status, + bar chart per Prodi -
    dipakai BPM/Admin (ringkasan se-institusi). Kolom "Tahun Kurikulum"
    menampilkan tahun TERBARU yang dipakai untuk Prodi itu (bisa beda-beda
    antar Prodi, kalau ada yang belum pindah ke kurikulum terbaru)."""
    per_prodi = {}
    tahun_per_prodi = {}
    for r in rows:
        per_prodi.setdefault(r["prodi_nama"], []).append(r["status"])
        tahun_per_prodi[r["prodi_nama"]] = r["tahun_kurikulum"]

    data_tabel = []
    for prodi_nama in sorted(per_prodi.keys()):
        hitung = _hitung_per_kategori(per_prodi[prodi_nama])
        baris = {
            "Program Studi": prodi_nama,
            "Tahun Kurikulum": tahun_per_prodi[prodi_nama],
            "Total": sum(hitung.values()),
        }
        for k in STATUS_URUTAN:
            baris[STATUS_LABEL[k]] = hitung[k]
        data_tabel.append(baris)
    df = pd.DataFrame(data_tabel)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if tampilkan_chart and not df.empty:
        _chart_status_berkelompok(df, "Program Studi")


def render_tabel_per_dosen(client, rows, tampilkan_peringatan_koordinator=True, tampilkan_chart=True):
    """Tabel Dosen x kategori status UNTUK SATU PRODI (rows sudah difilter
    ke satu Prodi oleh pemanggil) + peringatan Mata Kuliah tanpa koordinator
    sama sekali - dipakai Kaprodi (Prodi sendiri) dan BPM/Admin (Prodi yang
    dipilih lewat dropdown)."""
    peta_pengguna = _peta_nama_pengguna(client)
    peta_whitelist = _peta_nama_whitelist(client)

    per_dosen = {}
    tanpa_koordinator = []
    for r in rows:
        nama_koor = _nama_koordinator(r, peta_pengguna, peta_whitelist)
        if nama_koor is None:
            tanpa_koordinator.append(f"{r['kode_mk']} - {r['nama_mk']}")
            continue
        per_dosen.setdefault(nama_koor, []).append(r["status"])

    if not per_dosen:
        st.caption("Belum ada Mata Kuliah dengan koordinator di Prodi ini.")
    else:
        data_tabel = []
        for nama_dosen in sorted(per_dosen.keys()):
            hitung = _hitung_per_kategori(per_dosen[nama_dosen])
            baris = {"Dosen": nama_dosen, "MK Diampu": sum(hitung.values())}
            for k in STATUS_URUTAN:
                baris[STATUS_LABEL[k]] = hitung[k]
            data_tabel.append(baris)
        df = pd.DataFrame(data_tabel)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if tampilkan_chart and not df.empty:
            _chart_status_berkelompok(df, "Dosen")

    if tampilkan_peringatan_koordinator and tanpa_koordinator:
        st.warning(
            f"\u26A0\uFE0F {len(tanpa_koordinator)} Mata Kuliah belum punya Koordinator:\n\n"
            + "\n".join(f"- {m}" for m in sorted(tanpa_koordinator))
        )


def render_statistik_dosen(rows_mk_saya):
    """Dipanggil dari rps_saya.py - rows_mk_saya adalah hasil list_my_rps()
    yang SUDAH diambil pemanggil (tidak query ulang ke database di sini)."""
    daftar_status = [_status_dari_rps_list(mk.get("rps") or []) for mk in rows_mk_saya]
    st.markdown("#### \U0001F4CA Ringkasan Status")
    render_ringkasan_metrik(daftar_status, tampilkan_chart=False)

    per_prodi = Counter()
    for mk in rows_mk_saya:
        per_prodi[(mk.get("prodi") or {}).get("nama", "-")] += 1
    if len(per_prodi) > 1:
        st.markdown("###### Per Program Studi")
        df_prodi = pd.DataFrame(sorted(per_prodi.items()), columns=["Program Studi", "Jumlah RPS"])
        st.dataframe(df_prodi, use_container_width=True, hide_index=True)


def render_statistik_kaprodi(client, prodi_id):
    """Dipanggil dari kaprodi_panel.py - statistik KHUSUS satu Program Studi
    (milik Kaprodi yang login), termasuk peringatan koordinator kosong."""
    rows = get_rps_progress_raw(client, prodi_id)
    if not rows:
        st.info("Belum ada Mata Kuliah di Program Studi ini.")
        return
    tahun_aktif = rows[0]["tahun_kurikulum"]
    st.caption(f"Menampilkan Tahun Kurikulum {tahun_aktif} (terbaru) - kurikulum lama tidak disertakan.")
    st.markdown("#### \U0001F4CA Ringkasan Program Studi")
    render_ringkasan_metrik([r["status"] for r in rows], tampilkan_chart=False)
    st.markdown("#### \U0001F464 Per Dosen")
    render_tabel_per_dosen(client, rows, tampilkan_peringatan_koordinator=True, tampilkan_chart=False)


def render_statistik_institusi(client, prodi_rows):
    """Dipanggil dari bpm_panel.py & admin_panel.py - statistik SELURUH
    institusi, plus dropdown untuk lihat breakdown per Dosen di satu Prodi
    tertentu. prodi_rows: list dict {id, nama} (hasil list_prodi_db())."""
    rows = get_rps_progress_raw(client, prodi_id=None)
    if not rows:
        st.caption("Belum ada Mata Kuliah yang tersimpan sama sekali.")
        return

    st.caption(
        "Menampilkan Tahun Kurikulum TERBARU untuk masing-masing Program Studi "
        "(lihat kolom \"Tahun Kurikulum\" di tabel) - kurikulum lama yang sudah "
        "tidak relevan tidak disertakan."
    )
    st.markdown("#### \U0001F4CA Ringkasan Seluruh Institusi")
    render_ringkasan_metrik([r["status"] for r in rows])

    st.markdown("#### \U0001F3EB Per Program Studi")
    render_tabel_per_prodi(rows)

    st.markdown("#### \U0001F464 Per Dosen")
    nama_prodi_opsi = sorted({p["nama"] for p in prodi_rows})
    if not nama_prodi_opsi:
        return
    prodi_pilih = st.selectbox("Pilih Program Studi", nama_prodi_opsi, key="stats_institusi_prodi_pilih")
    rows_prodi = [r for r in rows if r["prodi_nama"] == prodi_pilih]
    render_tabel_per_dosen(client, rows_prodi, tampilkan_peringatan_koordinator=True)