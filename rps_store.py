# -*- coding: utf-8 -*-
"""
Fase 4: baca/tulis dokumen RPS ke tabel `rps` di Supabase - menggantikan
mekanisme "Unduh/Muat Progres (.xlsx)" manual dengan penyimpanan otomatis ke
database (tidak hilang kalau browser ditutup).

Satu baris `rps` = satu dokumen (kombinasi mata_kuliah_id + dosen_user_id,
dijaga unik lewat index `ux_rps_mata_kuliah_dosen` di sql/schema.sql bagian
FASE 4). Kolom `data` (JSONB) berisi persis isi session_state yang dulu
diserialisasi ke Excel - lihat state_to_rps_data()/apply_rps_data_to_state()
di app.py untuk konversi ke/dari bentuk ini.
"""

import streamlit as st

from cache_scope import cache_scope


def load_rps(client, mata_kuliah_id):
    """Satu Mata Kuliah = satu dokumen RPS (dimiliki siapa pun yang SAAT INI
    jadi koordinatornya - lihat mata_kuliah.koordinator_user_id). Kembalikan
    None kalau belum pernah diisi sama sekali."""
    resp = (
        client.table("rps")
        .select(
            "id, data, status, catatan_kaprodi, catatan_bpm, diajukan_pada, "
            "diproses_pada, diproses_pada_bpm, created_at, updated_at, dikunci_admin"
        )
        .eq("mata_kuliah_id", mata_kuliah_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def save_rps(client, mata_kuliah_id, dosen_user_id, data):
    """Simpan (insert kalau baru, update kalau sudah ada) isi RPS. `status`
    SENGAJA tidak disertakan di payload supaya tidak ikut ter-timpa balik ke
    default saat menyimpan draft biasa - perubahan status (mis. "diajukan")
    ditangani terpisah lewat rps_store.ajukan_rps() dkk. `dosen_user_id`
    dicatat sebagai siapa yang terakhir menyimpan (dijamin = koordinator saat
    ini oleh RLS - lihat sql/schema.sql). Upsert berdasarkan mata_kuliah_id
    SAJA (satu Mata Kuliah = satu RPS, siapa pun koordinatornya)."""
    payload = {
        "mata_kuliah_id": mata_kuliah_id,
        "dosen_user_id": dosen_user_id,
        "data": data,
    }
    resp = client.table("rps").upsert(payload, on_conflict="mata_kuliah_id").execute()
    return resp.data[0] if resp.data else None


@st.cache_data(ttl=15)
def list_my_rps(_client, user_id):
    """Semua Mata Kuliah yang koordinatornya SAAT INI adalah user ini, beserta
    RPS-nya kalau sudah pernah diisi (kalau belum, "rps" akan kosong - tetap
    ditampilkan supaya Dosen tahu Mata Kuliah mana yang perlu diisi). Berbasis
    penugasan koordinator saat ini, BUKAN riwayat siapa yang pernah mengisi -
    kalau koordinator diganti, Mata Kuliah itu otomatis hilang dari daftar
    koordinator lama dan muncul di koordinator baru."""
    resp = (
        _client.table("mata_kuliah")
        .select("id, nama_mk, kode_mk, tahun_kurikulum, prodi(nama), rps(id, status, updated_at, catatan_kaprodi)")
        .eq("koordinator_user_id", user_id)
        .execute()
    )
    return resp.data or []


def load_riwayat(client, rps_id, limit=10):
    return _load_riwayat_cached(client, cache_scope(), rps_id, limit)


@st.cache_data(ttl=15)
def _load_riwayat_cached(_client, scope, rps_id, limit):
    """Daftar snapshot riwayat perubahan untuk satu RPS (dari tabel
    rps_riwayat, diisi otomatis lewat trigger - lihat sql/schema.sql FASE 4)."""
    resp = (
        _client.table("rps_riwayat")
        .select("id, status, diubah_pada")
        .eq("rps_id", rps_id)
        .order("diubah_pada", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


# --------------------------------------------------------------------------
# Fase 5: transisi status (Dosen: ajukan/tarik; Kaprodi/Admin: setujui/tolak).
# Semua lewat fungsi database (RPC) SECURITY DEFINER di sql/schema.sql, BUKAN
# update langsung ke tabel rps - otorisasi & validasi dilakukan di sana.
# --------------------------------------------------------------------------
def ajukan_rps(client, rps_id):
    client.rpc("ajukan_rps", {"target_rps_id": rps_id}).execute()


def tarik_pengajuan_rps(client, rps_id):
    client.rpc("tarik_pengajuan_rps", {"target_rps_id": rps_id}).execute()


def setujui_rps(client, rps_id, catatan=None):
    client.rpc("setujui_rps", {"target_rps_id": rps_id, "catatan": catatan}).execute()


def tolak_rps(client, rps_id, catatan):
    client.rpc("tolak_rps", {"target_rps_id": rps_id, "catatan": catatan}).execute()


def list_diajukan(client):
    return _list_diajukan_cached(client, cache_scope())


@st.cache_data(ttl=15)
def _list_diajukan_cached(_client, scope):
    """RPS berstatus 'diajukan' yang boleh dilihat pengguna yang login saat
    ini - RLS otomatis membatasi ke RPS di prodi yang diampu untuk Kaprodi,
    atau semua untuk Admin (lihat policy "kaprodi & admin baca rps"). Nama
    Dosen diambil dari isi dokumen RPS-nya sendiri (info_umum), bukan dari
    tabel pengguna - lebih sederhana & tidak perlu izin baca lintas-akun."""
    resp = (
        _client.table("rps")
        .select("id, status, updated_at, data, mata_kuliah(nama_mk, kode_mk, tahun_kurikulum, prodi_id, prodi(nama))")
        .eq("status", "diajukan")
        .order("updated_at")
        .execute()
    )
    return resp.data or []


@st.cache_data(ttl=30)
def list_divalidasi(_client):
    """RPS berstatus 'divalidasi' (lolos Kaprodi DAN BPM - final) - RLS
    mengizinkan SEMUA Dosen yang login membacanya (transparansi kurikulum).
    Draft/diajukan/disetujui(menunggu BPM)/ditolak tetap privat. Lihat policy
    "semua dosen baca rps divalidasi" di sql/schema.sql."""
    resp = (
        _client.table("rps")
        .select(
            "id, status, updated_at, diajukan_pada, diproses_pada, diproses_pada_bpm, data, "
            "mata_kuliah(nama_mk, kode_mk, tahun_kurikulum, sks, semester, prodi_id, prodi(nama))"
        )
        .eq("status", "divalidasi")
        .order("updated_at", desc=True)
        .execute()
    )
    return resp.data or []


# --------------------------------------------------------------------------
# Penyesuaian: Role BPM - validasi tahap kedua setelah Kaprodi menyetujui,
# se-institusi (semua Prodi, tidak dibatasi seperti Kaprodi).
# --------------------------------------------------------------------------
def list_bpm_queue(client):
    return _list_bpm_queue_cached(client, cache_scope())


@st.cache_data(ttl=15)
def _list_bpm_queue_cached(_client, scope):
    """RPS berstatus 'disetujui' (menunggu validasi BPM) - RLS otomatis
    membatasi ke akun ber-role bpm saja (lihat policy "bpm baca rps antrian
    & riwayat"), TANPA filter Prodi (BPM se-institusi)."""
    resp = (
        _client.table("rps")
        .select("id, status, updated_at, diproses_pada, data, mata_kuliah(nama_mk, kode_mk, tahun_kurikulum, prodi_id, prodi(nama))")
        .eq("status", "disetujui")
        .order("diproses_pada")
        .execute()
    )
    return resp.data or []


def segarkan_cache_rps():
    """Buang semua cache daftar/statistik RPS setelah ada perubahan status
    (ajukan, tarik, setujui, tolak, validasi, buka kembali), supaya Dosen,
    Kaprodi, BPM, dan Admin langsung melihat keadaan terbaru, tidak menunggu
    TTL habis. Dipanggil dari tombol-tombol transisi status."""
    from stats_ui import get_rps_progress_raw  # impor lokal: hindari impor melingkar
    for fn in (list_my_rps, _load_riwayat_cached, _list_diajukan_cached,
               list_divalidasi, _list_bpm_queue_cached, get_rps_progress_raw):
        fn.clear()


def validasi_bpm_rps(client, rps_id, catatan=None):
    client.rpc("validasi_bpm_rps", {"target_rps_id": rps_id, "catatan": catatan}).execute()


def tolak_bpm_rps(client, rps_id, catatan):
    client.rpc("tolak_bpm_rps", {"target_rps_id": rps_id, "catatan": catatan}).execute()


def list_divalidasi_by_prodi(client, prodi_id):
    """RPS berstatus 'divalidasi' KHUSUS untuk satu Prodi - dipakai Kaprodi
    di panelnya sendiri untuk skenario "buka kembali untuk revisi" (beda
    dari list_divalidasi() di atas yang untuk halaman "RPS Tervalidasi"
    lintas-Prodi buat semua Dosen)."""
    resp = (
        client.table("rps")
        .select("id, status, diproses_pada_bpm, data, mata_kuliah!inner(nama_mk, kode_mk, tahun_kurikulum, prodi_id)")
        .eq("status", "divalidasi")
        .eq("mata_kuliah.prodi_id", prodi_id)
        .order("diproses_pada_bpm", desc=True)
        .execute()
    )
    return resp.data or []


def buka_kembali_rps(client, rps_id, catatan=None):
    """Kembalikan RPS yang sudah divalidasi ke status draft untuk direvisi -
    lihat buka_kembali_rps() di sql/schema.sql untuk aturan wewenang &
    field apa saja yang ikut dikosongkan."""
    client.rpc("buka_kembali_rps", {"target_rps_id": rps_id, "catatan": catatan}).execute()


def list_semua_rps_admin(client, prodi_id=None):
    """Semua Mata Kuliah + RPS-nya (kalau ada) untuk Admin melihat &
    mengelola akses edit LINTAS SEMUA DOSEN - prodi_id=None berarti semua
    Prodi sekaligus. Mata Kuliah yang belum ada RPS-nya tetap disertakan
    (dengan rps=None) supaya "belum diisi" juga kelihatan, bukan cuma yang
    sudah ada isinya."""
    query = client.table("mata_kuliah").select(
        "id, kode_mk, nama_mk, tahun_kurikulum, prodi_id, koordinator_user_id, koordinator_nip, "
        "prodi(nama), rps(id, status, data, dikunci_admin, updated_at)"
    )
    if prodi_id:
        query = query.eq("prodi_id", prodi_id)
    resp = query.execute()
    hasil = []
    for r in (resp.data or []):
        rps_list = r.get("rps") or []
        rps_row = rps_list[0] if isinstance(rps_list, list) and rps_list else (
            rps_list if not isinstance(rps_list, list) else None
        )
        hasil.append({
            "mata_kuliah_id": r["id"], "kode_mk": r["kode_mk"], "nama_mk": r["nama_mk"],
            "tahun_kurikulum": r.get("tahun_kurikulum"), "prodi_id": r.get("prodi_id"),
            "prodi_nama": (r.get("prodi") or {}).get("nama", "-"),
            "koordinator_user_id": r.get("koordinator_user_id"),
            "koordinator_nip": r.get("koordinator_nip"),
            "rps": rps_row,
        })
    return hasil


def set_kunci_admin(client, rps_id, kunci):
    """Kunci (kunci=True) atau buka (kunci=False) akses edit satu RPS -
    lihat set_kunci_admin() di sql/schema.sql. Berlaku APA PUN status
    RPS-nya saat ini."""
    client.rpc("set_kunci_admin", {"target_rps_id": rps_id, "kunci": kunci}).execute()

# Kompatibilitas: pemanggil lama memakai list_diajukan.clear() / list_bpm_queue.clear().
list_diajukan.clear = _list_diajukan_cached.clear
list_bpm_queue.clear = _list_bpm_queue_cached.clear
load_riwayat.clear = _load_riwayat_cached.clear
