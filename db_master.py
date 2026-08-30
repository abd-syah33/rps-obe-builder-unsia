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

import re

import pandas as pd
import streamlit as st

MK_DISPLAY_COLUMNS = ["Nama Mata Kuliah", "Kode MK", "SKS", "Semester", "Rumpun MK"]
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


@st.cache_data(ttl=30)
def get_tahun_kurikulum_terbaru(_client, prodi_id):
    """Tahun Kurikulum TERBARU yang BENAR-BENAR sudah ada Mata Kuliahnya di
    Prodi ini - beda dari sekadar "opsi terakhir di list_tahun_kurikulum()",
    yang bisa memuat tahun rencana dari DEFAULT_TAHUN_OPTIONS yang belum ada
    isinya sama sekali (mis. tahun kurikulum baru yang baru mau disiapkan,
    sementara operasionalnya masih di tahun sebelumnya). Dipakai sebagai
    default otomatis di selector Tahun Kurikulum & Statistik, supaya tidak
    salah kira "tahun terbaru di daftar pilihan" = "tahun yang aktif
    dipakai sekarang". None kalau Prodi ini belum punya Mata Kuliah sama
    sekali (fallback ke opsi terakhir di list_tahun_kurikulum() dipakai
    pemanggil kalau ini None)."""
    resp = _client.table("mata_kuliah").select("tahun_kurikulum").eq("prodi_id", prodi_id).execute()
    tahun_list = [r["tahun_kurikulum"] for r in (resp.data or []) if r.get("tahun_kurikulum") is not None]
    return max(tahun_list) if tahun_list else None


def index_tahun_default(tahun_options, tahun_terbaru):
    """Hitung index untuk default selectbox Tahun Kurikulum - pakai
    tahun_terbaru (dari get_tahun_kurikulum_terbaru) kalau ada dan
    tercantum di opsi, fallback ke opsi TERAKHIR (perilaku lama) kalau
    tidak (mis. Prodi belum punya Mata Kuliah sama sekali)."""
    if tahun_terbaru is not None and tahun_terbaru in tahun_options:
        return tahun_options.index(tahun_terbaru)
    return len(tahun_options) - 1


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
            "id, nama_mk, kode_mk, sks, semester, rumpun_mk, "
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


def _clean_long_text(value):
    """Bersihkan teks panjang yang sering ditempel dari Word/PDF (mis.
    Deskripsi CPL) dari spasi berantakan - BUKAN cuma strip() ujungnya
    (yang cuma bersihkan spasi di awal/akhir, bukan yang di tengah):
    - Spasi tak-putus (non-breaking space \\xa0) & varian spasi unicode lain
      (sering ikut kepaste dari Word/PDF, terlihat sama seperti spasi biasa
      tapi bikin pencarian/penataan teks jadi aneh) - diseragamkan jadi
      spasi biasa.
    - Spasi/tab berulang di tengah kalimat - dirapikan jadi satu spasi.
    - Baris kosong berulang (lebih dari satu) - dirapikan jadi maksimal
      satu baris kosong, dan spasi nempel di awal/akhir tiap baris dibuang.

    MEMPERTAHANKAN baris baru tunggal (dianggap paragraf yang disengaja) -
    untuk field yang seharusnya SATU kalimat utuh tanpa baris baru sama
    sekali (Deskripsi CPL/CPMK/MK, Referensi), pakai _clean_single_line_text
    di bawah, bukan fungsi ini.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value)
    text = re.sub(r"[\u00a0\u2000-\u200b\u202f\u205f\u3000]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_single_line_text(value):
    """Sama seperti _clean_long_text, TAPI baris baru di dalam teks JUGA
    digabung jadi satu spasi - dipakai KHUSUS untuk field yang memang
    seharusnya SATU kalimat/paragraf utuh tanpa baris baru sama sekali
    (Deskripsi CPL, Deskripsi CPMK, Deskripsi Mata Kuliah, Referensi).

    Kasus yang ditangani: teks yang ditempel dari PDF sering ikut membawa
    baris baru di SETIAP baris hasil word-wrap PDF aslinya (bukan baris
    baru yang disengaja penulisnya) - satu kalimat utuh jadi terpecah jadi
    beberapa baris pendek di tengah kalimat. _clean_long_text SENGAJA tidak
    menangani ini karena field lain (mis. Materi Pembelajaran di tabel 16
    Pertemuan) memang boleh berisi beberapa baris/poin terpisah - jangan
    pakai fungsi ini untuk field semacam itu.
    """
    text = _clean_long_text(value)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _clean_int(value):
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    return int(value)


def save_mata_kuliah_df(client, prodi_id, tahun_kurikulum, edited_df, original_df):
    """Upsert semua baris di edited_df (hasil st.data_editor) ke tabel
    mata_kuliah, untuk satu prodi_id + tahun_kurikulum tertentu. Baris dengan
    "Nama Mata Kuliah" kosong dilewati (baris kosong sisa dari data_editor).
    Upsert dicocokkan lewat (kode_mk, tahun_kurikulum) - Kode MK unik PER
    TAHUN KURIKULUM (Mata Kuliah Umum lintas Prodi sudah dikonsolidasi ke
    Prodi "Mata Kuliah Umum" tersendiri, lihat sql/migrate_mata_kuliah_umum.sql).

    Penyesuaian: baris yang ADA di original_df (state SEBELUM diedit) tapi
    SUDAH TIDAK ADA lagi di edited_df (dihapus lewat tombol hapus baris di
    data_editor) sekarang BENAR-BENAR dihapus dari database lewat RPC
    hapus_mata_kuliah_aman() - sebelumnya dilewati diam-diam (baris itu
    muncul lagi setelah reload, membingungkan). RPC ini membedakan RPS
    berstatus draft (ikut terhapus otomatis, karena belum pernah dilihat
    siapa pun selain koordinatornya sendiri) dari RPS yang sudah
    diajukan/disetujui/divalidasi/ditolak (MENOLAK penghapusan MK-nya,
    supaya jejak resmi tidak hilang) - error penolakan itu ditangkap di sini
    dan nama Kode MK-nya dikembalikan lewat `gagal_hapus` supaya pemanggil
    bisa kasih tahu Admin/Kaprodi.

    Efek samping dari logika di atas: KALAU Kode MK diubah di editor (bukan
    dihapus), kode LAMA-nya kini otomatis ikut coba dihapus (karena sudah
    tidak ada di edited_df) - kalau kode lama itu TERNYATA belum dipakai di
    RPS manapun (atau cuma draft), hasilnya baris lama betulan hilang
    (diganti baris baru, bukan lagi menyisakan duplikat seperti
    sebelumnya); kalau sudah diajukan/diproses, penghapusannya otomatis
    gagal (masuk daftar gagal_hapus) dan baris lama tetap ada berdampingan
    dengan baris baru - sama seperti perilaku lama.
    """
    kode_mk_tersisa = {
        _clean_str(row.get("Kode MK")) for _, row in edited_df.iterrows()
        if _clean_str(row.get("Kode MK"))
    }
    kode_mk_lama = {
        _clean_str(row.get("Kode MK")) for _, row in original_df.iterrows()
        if _clean_str(row.get("Kode MK"))
    }
    kode_mk_dihapus = kode_mk_lama - kode_mk_tersisa

    gagal_hapus = []
    for kode_mk_hapus in kode_mk_dihapus:
        try:
            client.rpc("hapus_mata_kuliah_aman", {
                "target_prodi_id": prodi_id,
                "target_tahun_kurikulum": tahun_kurikulum,
                "target_kode_mk": kode_mk_hapus,
            }).execute()
        except Exception:
            gagal_hapus.append(kode_mk_hapus)

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
        }
        client.table("mata_kuliah").upsert(payload, on_conflict="kode_mk,tahun_kurikulum").execute()
        saved += 1
    return saved, gagal_hapus


def _cpl_kode_terpakai_di_rps(client, prodi_id, tahun_kurikulum, kode_cpl_set):
    """Dari kode_cpl_set, kembalikan kode mana saja yang MASIH dirujuk sebagai
    CPL suatu CPMK di RPS manapun untuk Prodi+Tahun Kurikulum ini. Dicek
    manual (bukan lewat foreign key database) karena rujukan CPMK->CPL cuma
    berupa teks kode di dalam kolom JSONB rps.data, bukan foreign key
    sungguhan - jadi database TIDAK bisa mencegah sendiri penghapusan CPL
    yang masih dipakai."""
    if not kode_cpl_set:
        return set()
    mk_resp = (
        client.table("mata_kuliah")
        .select("id")
        .eq("prodi_id", prodi_id)
        .eq("tahun_kurikulum", tahun_kurikulum)
        .execute()
    )
    mk_ids = [m["id"] for m in (mk_resp.data or [])]
    if not mk_ids:
        return set()
    rps_resp = client.table("rps").select("data").in_("mata_kuliah_id", mk_ids).execute()
    terpakai = set()
    for r in (rps_resp.data or []):
        cpmk_data = (r.get("data") or {}).get("cpmk_data") or {}
        for c in cpmk_data.values():
            kode = (c or {}).get("cpl_kode")
            if kode in kode_cpl_set:
                terpakai.add(kode)
    return terpakai


def save_cpl_df(client, prodi_id, tahun_kurikulum, edited_df, original_df):
    """Sama seperti save_mata_kuliah_df, untuk tabel cpl. Cocokkan lewat
    (prodi_id, kode_cpl, tahun_kurikulum) - ubah Kode CPL = baris baru
    (kecuali kode lamanya ternyata aman dihapus - lihat catatan efek samping
    di save_mata_kuliah_df, berlaku sama di sini).

    Penyesuaian: baris yang dihapus dari editor sekarang BENAR-BENAR dihapus
    dari database - TAPI hanya kalau kode CPL itu tidak sedang dirujuk CPMK
    di RPS manapun (dicek lewat _cpl_kode_terpakai_di_rps, karena tidak ada
    foreign key database yang otomatis mencegah ini seperti pada Mata
    Kuliah). Kode yang gagal dihapus karena masih dipakai dikembalikan lewat
    `terpakai` supaya pemanggil bisa kasih tahu Admin.
    """
    kode_tersisa = {
        _clean_str(row.get("Kode CPL")) for _, row in edited_df.iterrows()
        if _clean_str(row.get("Kode CPL"))
    }
    kode_lama = {
        _clean_str(row.get("Kode CPL")) for _, row in original_df.iterrows()
        if _clean_str(row.get("Kode CPL"))
    }
    kode_dihapus = kode_lama - kode_tersisa

    terpakai = _cpl_kode_terpakai_di_rps(client, prodi_id, tahun_kurikulum, kode_dihapus)
    boleh_dihapus = kode_dihapus - terpakai
    for kode in boleh_dihapus:
        client.table("cpl").delete().eq("prodi_id", prodi_id).eq(
            "tahun_kurikulum", tahun_kurikulum
        ).eq("kode_cpl", kode).execute()

    saved = 0
    for _, row in edited_df.iterrows():
        kode_cpl = _clean_str(row.get("Kode CPL"))
        if not kode_cpl:
            continue
        payload = {
            "prodi_id": prodi_id,
            "tahun_kurikulum": tahun_kurikulum,
            "kode_cpl": kode_cpl,
            "deskripsi": _clean_single_line_text(row.get("Deskripsi CPL")),
        }
        client.table("cpl").upsert(payload, on_conflict="prodi_id,kode_cpl,tahun_kurikulum").execute()
        saved += 1
    return saved, sorted(terpakai)


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
    resp = client.table("pengguna").select(
        "id, email, nama, nip, role, prodi_id, pejabat_utama"
    ).order("email").execute()
    return resp.data or []


def update_pengguna(client, user_id, role, prodi_id, nama=None, nip=None):
    payload = {"role": role, "prodi_id": prodi_id}
    if nama is not None:
        payload["nama"] = nama
    if nip is not None:
        payload["nip"] = nip
    client.table("pengguna").update(payload).eq("id", user_id).execute()


def set_pejabat_utama(client, user_id):
    """Tetapkan satu akun Kaprodi/BPM sebagai "pejabat resmi" - yang namanya
    dipakai otomatis di dokumen RPS (Nama Ketua Prodi / Nama Ka. BPM) kalau
    ada LEBIH DARI SATU akun dengan role yang sama. Lihat set_pejabat_utama()
    di sql/schema.sql untuk logika lengkapnya (termasuk melepas status ini
    dari akun lain dengan role - dan untuk Kaprodi, Prodi - yang sama)."""
    client.rpc("set_pejabat_utama", {"target_user_id": user_id}).execute()


def sinkronkan_nama_pejabat(client):
    """Timpa nama_kaprodi/nama_biro_pjm di SEMUA baris rps yang sudah ada
    dengan nilai TERKINI - lihat sinkronkan_nama_pejabat() di sql/schema.sql.
    Mengembalikan jumlah baris rps yang disentuh."""
    resp = client.rpc("sinkronkan_nama_pejabat").execute()
    return resp.data


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


def save_whitelist_df(client, edited_df, prodi_rows, original_df):
    """Upsert baris whitelist (NIP, Nama, Prodi Homebase) dari st.data_editor.
    Baris dengan NIP/Nama kosong dilewati. Prodi Homebase diketik sebagai NAMA
    (dicocokkan ke prodi_id lewat nama, tidak case-sensitive) supaya gampang
    ditempel dari Excel - nama Prodi yang tidak dikenali dilewati KHUSUS kolom
    itu (NIP+Nama tetap tersimpan), dikembalikan di `tidak_dikenali`.

    Penyesuaian: baris yang dihapus dari editor sekarang BENAR-BENAR dihapus
    dari database (sebelumnya dilewati diam-diam, baris muncul lagi setelah
    reload). Aman tanpa pengecekan tambahan - tidak ada tabel lain yang
    berelasi ke whitelist_pendaftaran lewat foreign key (baris ini cuma
    dibaca SEKALI oleh trigger saat Dosen Daftar, bukan rujukan hidup
    seterusnya) - menghapusnya tidak memengaruhi akun yang sudah aktif.
    """
    nama_ke_id = {p["nama"].strip().lower(): p["id"] for p in prodi_rows}

    nip_tersisa = {
        _clean_str(row.get("NIP")) for _, row in edited_df.iterrows()
        if _clean_str(row.get("NIP"))
    }
    nip_lama = {
        _clean_str(row.get("NIP")) for _, row in original_df.iterrows()
        if _clean_str(row.get("NIP"))
    }
    for nip_hapus in (nip_lama - nip_tersisa):
        client.table("whitelist_pendaftaran").delete().eq("nip", nip_hapus).execute()

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