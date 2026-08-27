# -*- coding: utf-8 -*-
"""
Fase 3: baca/tulis data master (Prodi, Mata Kuliah, CPL) dari Supabase,
menggantikan file Excel di folder data/ sebagai sumber data yang dipakai
aplikasi saat berjalan (file Excel-nya sendiri tetap ada di data/, cuma
tidak lagi dibaca langsung oleh app.py - lihat scripts/migrate_excel_to_db.py
untuk migrasi satu kali dari Excel ke tabel-tabel ini).

Nama kolom DataFrame yang dikembalikan SENGAJA dibuat identik dengan versi
Excel lama (mis. "Nama Mata Kuliah", "Kode MK", "Kode CPL", dst.) supaya
app.py, docx_export.py, dan pdf_export.py yang mengandalkan nama kolom itu
tidak perlu diubah sama sekali.
"""

import re

import pandas as pd
import streamlit as st

MK_DISPLAY_COLUMNS = ["Nama Mata Kuliah", "Kode MK", "SKS", "Semester", "Rumpun MK", "Dosen Pengembang"]
CPL_DISPLAY_COLUMNS = ["Kode CPL", "Deskripsi CPL"]

# Tahun kurikulum yang SELALU ditawarkan di dropdown, walau belum ada Mata
# Kuliah yang memakainya - supaya Admin/Kaprodi bisa mulai isi kurikulum baru
# dari kosong. Daftar aktual di dropdown = ini digabung dengan tahun yang
# sudah benar-benar ada di database (lihat list_tahun_kurikulum()).
DEFAULT_TAHUN_OPTIONS = [2021, 2026]


# --------------------------------------------------------------------------
# Baca (dipakai semua peran - Dosen pilih Prodi/MK/CPL, Admin lihat isi tabel)
# --------------------------------------------------------------------------
@st.cache_data(ttl=60)
def list_prodi_db(_client):
    """Kembalikan list of {"id": ..., "nama": ...}, terurut nama. `_client`
    diberi underscore di depan supaya Streamlit tidak mencoba meng-hash-nya
    (objek client tidak stabil untuk di-hash) - lihat dokumentasi st.cache_data.
    """
    resp = _client.table("prodi").select("id, nama").order("nama").execute()
    return resp.data or []


def get_prodi_id(prodi_rows, nama):
    for p in prodi_rows:
        if p["nama"] == nama:
            return p["id"]
    return None


@st.cache_data(ttl=60)
def list_tahun_kurikulum(_client, prodi_id):
    """Daftar Tahun Kurikulum untuk dropdown - gabungan DEFAULT_TAHUN_OPTIONS
    dengan tahun yang benar-benar sudah ada Mata Kuliah/CPL-nya di Prodi ini,
    supaya tahun baru yang belum ada isinya sama sekali tetap muncul sebagai
    pilihan (buat mulai isi dari kosong)."""
    mk_resp = _client.table("mata_kuliah").select("tahun_kurikulum").eq("prodi_id", prodi_id).execute()
    tahun_ada = {r["tahun_kurikulum"] for r in (mk_resp.data or [])}
    return sorted(tahun_ada | set(DEFAULT_TAHUN_OPTIONS))


def _sort_cpl(cpl_df):
    """Urutkan CPL secara alami (S1..S10, P1..P3, KU1..KU9, KK1..KK4),
    bukan alfabetis (yang akan salah urut S10 sebelum S2)."""
    if cpl_df.empty:
        return cpl_df

    prefix_order = {"S": 0, "P": 1, "KU": 2, "KK": 3}

    def sort_key(kode):
        m = re.match(r"([A-Za-z]+)(\d+)", str(kode))
        if not m:
            return (99, str(kode), 0)
        prefix, num = m.group(1), int(m.group(2))
        return (prefix_order.get(prefix, 99), prefix, num)

    return cpl_df.sort_values(by="Kode CPL", key=lambda col: col.map(sort_key)).reset_index(drop=True)


@st.cache_data(ttl=60)
def load_master_db(_client, prodi_id, tahun_kurikulum):
    """Kembalikan (mk_df, cpl_df) untuk satu prodi_id + tahun_kurikulum.
    Kolom identik dengan versi Excel lama (plus "id" dan "koordinator_user_id"
    tambahan untuk keperluan admin/kaprodi)."""
    mk_resp = (
        _client.table("mata_kuliah")
        .select(
            "id, nama_mk, kode_mk, sks, semester, rumpun_mk, dosen_pengembang, "
            "koordinator_user_id, koordinator_nip"
        )
        .eq("prodi_id", prodi_id)
        .eq("tahun_kurikulum", tahun_kurikulum)
        .order("kode_mk")
        .execute()
    )
    mk_rows = mk_resp.data or []
    mk_df = pd.DataFrame(
        [
            {
                "id": r["id"],
                "koordinator_user_id": r.get("koordinator_user_id"),
                "koordinator_nip": r.get("koordinator_nip"),
                "Nama Mata Kuliah": r["nama_mk"],
                "Kode MK": r["kode_mk"],
                "SKS": r.get("sks"),
                "Semester": r.get("semester"),
                "Rumpun MK": r.get("rumpun_mk") or "-",
                "Dosen Pengembang": r.get("dosen_pengembang") or "",
            }
            for r in mk_rows
        ],
        columns=["id", "koordinator_user_id", "koordinator_nip"] + MK_DISPLAY_COLUMNS,
    )

    cpl_resp = (
        _client.table("cpl")
        .select("id, kode_cpl, deskripsi")
        .eq("prodi_id", prodi_id)
        .eq("tahun_kurikulum", tahun_kurikulum)
        .execute()
    )
    cpl_rows = cpl_resp.data or []
    cpl_df = pd.DataFrame(
        [{"id": r["id"], "Kode CPL": r["kode_cpl"], "Deskripsi CPL": r["deskripsi"]} for r in cpl_rows],
        columns=["id"] + CPL_DISPLAY_COLUMNS,
    )
    cpl_df = _sort_cpl(cpl_df)

    return mk_df, cpl_df


# --------------------------------------------------------------------------
# Tulis (dipakai panel Admin - lihat admin_panel.py). Butuh policy RLS
# "admin tambah/ubah ..." di sql/schema.sql (bagian FASE 3) supaya berhasil.
# --------------------------------------------------------------------------
def insert_prodi(client, nama):
    resp = client.table("prodi").insert({"nama": nama.strip()}).execute()
    return resp.data[0] if resp.data else None


def _clean_str(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _clean_int(value):
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    return int(value)


def save_mata_kuliah_df(client, prodi_id, tahun_kurikulum, edited_df):
    """Upsert semua baris di edited_df (hasil st.data_editor) ke tabel
    mata_kuliah, untuk satu prodi_id + tahun_kurikulum tertentu. Baris dengan
    "Nama Mata Kuliah" kosong dilewati (baris kosong sisa dari data_editor).
    Upsert dicocokkan lewat (kode_mk, tahun_kurikulum) - Kode MK unik PER
    TAHUN KURIKULUM (Mata Kuliah Umum lintas Prodi sudah dikonsolidasi ke
    Prodi "Mata Kuliah Umum" tersendiri, lihat sql/migrate_mata_kuliah_umum.sql).
    KALAU Kode MK diubah di editor, itu akan membuat baris BARU, bukan
    mengganti baris lama (batasan yang disengaja, supaya tidak perlu logika
    diff yang rumit). Hapus baris lama manual lewat SQL Editor kalau memang
    perlu mengubah Kode MK.
    """
    saved = 0
    for _, row in edited_df.iterrows():
        nama = _clean_str(row.get("Nama Mata Kuliah"))
        kode_mk = _clean_str(row.get("Kode MK"))
        if not nama or not kode_mk:
            continue
        payload = {
            "prodi_id": prodi_id,
            "tahun_kurikulum": tahun_kurikulum,
            "nama_mk": nama,
            "kode_mk": kode_mk,
            "sks": _clean_int(row.get("SKS")),
            "semester": _clean_int(row.get("Semester")),
            "rumpun_mk": _clean_str(row.get("Rumpun MK")),
            "dosen_pengembang": _clean_str(row.get("Dosen Pengembang")),
        }
        client.table("mata_kuliah").upsert(payload, on_conflict="kode_mk,tahun_kurikulum").execute()
        saved += 1
    return saved


def save_cpl_df(client, prodi_id, tahun_kurikulum, edited_df):
    """Sama seperti save_mata_kuliah_df, untuk tabel cpl. Cocokkan lewat
    (prodi_id, kode_cpl, tahun_kurikulum) - ubah Kode CPL = baris baru,
    bukan mengganti."""
    saved = 0
    for _, row in edited_df.iterrows():
        kode_cpl = _clean_str(row.get("Kode CPL"))
        if not kode_cpl:
            continue
        payload = {
            "prodi_id": prodi_id,
            "tahun_kurikulum": tahun_kurikulum,
            "kode_cpl": kode_cpl,
            "deskripsi": _clean_str(row.get("Deskripsi CPL")),
        }
        client.table("cpl").upsert(payload, on_conflict="prodi_id,kode_cpl,tahun_kurikulum").execute()
        saved += 1
    return saved


# --------------------------------------------------------------------------
# Penyesuaian: Dosen BIASA (bukan admin/kaprodi) perlu tahu nama Kaprodi
# Prodi-nya & nama BPM untuk auto-isi RPS - tapi policy RLS pengguna saat ini
# cuma izinkan baca profil SENDIRI (+ admin/kaprodi baca semua). Dosen biasa
# TIDAK match salah satu dari itu untuk baris milik ORANG LAIN, jadi query
# select biasa ke tabel pengguna akan pulang kosong. Lewat RPC khusus
# (SECURITY DEFINER, cakupan dipersempit HANYA nama+email) di sql/schema.sql.
# --------------------------------------------------------------------------
def get_kaprodi_nama(client, prodi_id):
    """Nama Kaprodi terdaftar untuk satu Prodi. None kalau belum ada yang
    ditetapkan sebagai Kaprodi Prodi ini (atau prodi_id kosong)."""
    if not prodi_id:
        return None
    try:
        resp = client.rpc("get_pejabat_prodi", {"target_prodi_id": prodi_id}).execute()
        rows = resp.data or []
        if rows:
            return rows[0].get("kaprodi_nama") or rows[0].get("kaprodi_email")
    except Exception:
        pass
    return None


def get_bpm_nama(client):
    """Nama BPM terdaftar (se-institusi). None kalau belum ada akun ber-role bpm."""
    try:
        resp = client.rpc("get_pejabat_bpm").execute()
        rows = resp.data or []
        if rows:
            return rows[0].get("bpm_nama") or rows[0].get("bpm_email")
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------
# Kelola pengguna (Panel Admin) - butuh policy "hanya admin bisa update
# pengguna" dari Fase 2 (sudah ada, tidak perlu policy baru).
#
# Penyesuaian: NIP & Prodi Homebase sekarang atribut permanen SEMUA pengguna
# (bukan cuma Kaprodi/whitelist) - lihat catatan lengkap di sql/schema.sql.
# --------------------------------------------------------------------------
def list_pengguna(client):
    resp = client.table("pengguna").select("id, email, nama, nip, role, prodi_id").order("email").execute()
    return resp.data or []


def update_pengguna(client, user_id, role, prodi_id, nama=None, nip=None):
    payload = {"role": role, "prodi_id": prodi_id}
    if nama is not None:
        payload["nama"] = nama
    if nip is not None:
        payload["nip"] = nip
    client.table("pengguna").update(payload).eq("id", user_id).execute()


def save_pengguna_df(client, edited_df, prodi_rows, id_by_email):
    """Simpan perubahan massal dari tabel Kelola Pengguna (bisa ditempel dari
    Excel). Kolom "Prodi Homebase" diketik sebagai NAMA Prodi (bukan dropdown -
    supaya gampang ditempel banyak baris sekaligus), dicocokkan ke prodi_id
    lewat nama (tidak case-sensitive). Baris dengan nama Prodi yang tidak
    dikenali akan dilewati KHUSUS kolom itu (field lain tetap tersimpan),
    namanya dikembalikan di `tidak_dikenali` supaya bisa diberi tahu ke Admin.
    Kolom Email tidak diubah - itu cuma dipakai untuk mencari akun mana yang
    dimaksud, bukan untuk diedit di sini."""
    nama_ke_id = {p["nama"].strip().lower(): p["id"] for p in prodi_rows}
    tidak_dikenali = []
    saved = 0
    for _, row in edited_df.iterrows():
        email = _clean_str(row.get("Email"))
        user_id = id_by_email.get(email)
        if not user_id:
            continue
        prodi_input = _clean_str(row.get("Prodi Homebase"))
        prodi_id = None
        if prodi_input:
            prodi_id = nama_ke_id.get(prodi_input.lower())
            if prodi_id is None:
                tidak_dikenali.append((email, prodi_input))
        update_pengguna(
            client, user_id,
            role=_clean_str(row.get("Role")) or "dosen",
            prodi_id=prodi_id,
            nama=_clean_str(row.get("Nama")) or None,
            nip=_clean_str(row.get("NIP")) or None,
        )
        saved += 1
    return saved, tidak_dikenali


# --------------------------------------------------------------------------
# Penyesuaian: Koordinator Mata Kuliah - Kaprodi/Admin menetapkan satu Dosen
# per Mata Kuliah yang jadi satu-satunya yang boleh mengisi RPS-nya.
# --------------------------------------------------------------------------
def list_dosen(client):
    """Semua akun terdaftar (dipakai untuk memilih siapa jadi koordinator -
    TIDAK dibatasi role='dosen' karena Kaprodi/Admin bisa juga mengajar)."""
    resp = client.table("pengguna").select("id, email, nama").order("email").execute()
    return resp.data or []


def set_koordinator_mk(client, mk_id, koordinator_id=None, koordinator_nip=None):
    """Isi SALAH SATU: koordinator_id (akun yang sudah terdaftar) atau
    koordinator_nip (NIP yang belum py akun - staging, lihat
    list_whitelist_menunggu()). Keduanya None berarti dikosongkan."""
    client.rpc(
        "set_koordinator_mk",
        {"target_mk_id": mk_id, "koordinator_id": koordinator_id, "koordinator_nip_baru": koordinator_nip},
    ).execute()


# --------------------------------------------------------------------------
# Penyesuaian: Pra-pendaftaran Dosen (whitelist NIP + Prodi Homebase) -
# persiapan sebelum demo/pelatihan, supaya Dosen bisa langsung jadi
# koordinator & sudah punya Prodi Homebase begitu Daftar.
# --------------------------------------------------------------------------
def list_whitelist_all(client):
    """Semua baris whitelist, dilengkapi status sudah Daftar atau belum
    (dicek silang ke pengguna.nip) dan nama Prodi Homebase-nya."""
    wl_resp = client.table("whitelist_pendaftaran").select("nip, nama, prodi_id").order("nama").execute()
    wl_rows = wl_resp.data or []
    pengguna_resp = client.table("pengguna").select("nip").execute()
    nip_terdaftar = {p["nip"] for p in (pengguna_resp.data or []) if p.get("nip")}
    prodi_rows = list_prodi_db(client)
    prodi_nama_by_id = {p["id"]: p["nama"] for p in prodi_rows}
    return [
        {
            "nip": w["nip"],
            "nama": w["nama"],
            "prodi_id": w.get("prodi_id"),
            "prodi_nama": prodi_nama_by_id.get(w.get("prodi_id"), ""),
            "sudah_daftar": w["nip"] in nip_terdaftar,
        }
        for w in wl_rows
    ]


def list_whitelist_menunggu(client):
    """Whitelist yang NIP-nya BELUM dipakai Daftar - dipakai sebagai pilihan
    koordinator untuk orang yang belum punya akun sama sekali."""
    return [w for w in list_whitelist_all(client) if not w["sudah_daftar"]]


def save_whitelist_df(client, edited_df, prodi_rows):
    """Upsert baris whitelist (NIP, Nama, Prodi Homebase) dari st.data_editor.
    Baris dengan NIP/Nama kosong dilewati. Prodi Homebase diketik sebagai NAMA
    (dicocokkan ke prodi_id lewat nama, tidak case-sensitive) supaya gampang
    ditempel dari Excel - nama Prodi yang tidak dikenali dilewati KHUSUS kolom
    itu (NIP+Nama tetap tersimpan), dikembalikan di `tidak_dikenali`."""
    nama_ke_id = {p["nama"].strip().lower(): p["id"] for p in prodi_rows}
    tidak_dikenali = []
    saved = 0
    for _, row in edited_df.iterrows():
        nip = _clean_str(row.get("NIP"))
        nama = _clean_str(row.get("Nama"))
        if not nip or not nama:
            continue
        prodi_input = _clean_str(row.get("Prodi Homebase"))
        prodi_id = None
        if prodi_input:
            prodi_id = nama_ke_id.get(prodi_input.lower())
            if prodi_id is None:
                tidak_dikenali.append((nip, prodi_input))
        client.table("whitelist_pendaftaran").upsert(
            {"nip": nip, "nama": nama, "prodi_id": prodi_id}, on_conflict="nip",
        ).execute()
        saved += 1
    return saved, tidak_dikenali