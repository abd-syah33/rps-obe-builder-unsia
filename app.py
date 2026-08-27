# -*- coding: utf-8 -*-
"""
Aplikasi Input RPS (Rencana Pembelajaran Semester) untuk UNSIA

Cara menjalankan:
    pip install -r requirements.txt
    streamlit run app.py

Struktur data master:
    data/<Nama Prodi>.xlsx   -> setiap file mewakili 1 Program Studi
        sheet 'Mata Kuliah'  -> kolom: No, Nama Mata Kuliah, Kode MK, SKS, Semester, Rumpun MK
        sheet 'CPL'          -> kolom: Kode CPL, Deskripsi CPL

Catatan teknis (widget perlu 2x klik):
    Semua widget interaktif diberi `key=` yang STABIL selama Mata Kuliah yang sama
    dipilih (di-scope lewat helper `mk_key()`), dan berubah otomatis saat pindah MK.
    Ini mencegah Streamlit membuat ulang identitas widget di setiap rerun (penyebab
    umum gejala "perlu klik 2x"), sekaligus mencegah nilai lama "bocor" saat pindah MK.
"""

import io
import glob
import os
import json
import hashlib
from datetime import datetime

import pandas as pd
import streamlit as st
import openpyxl
from openpyxl import Workbook

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from pdf_export import with_code
from docx_export import BOBOT_KATEGORI
from auth import require_login, get_client
from db_master import (
    list_prodi_db, get_prodi_id, load_master_db, list_tahun_kurikulum,
    get_kaprodi_nama, get_bpm_nama,
)
from admin_panel import render_admin_panel
from kaprodi_panel import render_kaprodi_panel
from bpm_panel import render_bpm_panel
from rps_store import load_rps, save_rps, ajukan_rps, tarik_pengajuan_rps
from rps_saya import render_rps_saya
from rps_browse import render_rps_tervalidasi

# --------------------------------------------------------------------------
# Konstanta
# --------------------------------------------------------------------------
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DEFAULT_GEMINI_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "gemini_default.txt")


def load_default_gemini_config():
    """Baca config/gemini_default.txt -> {'api_key': ..., 'model': ...}, dengan
    fallback ke st.secrets (fitur "Secrets" Streamlit Community Cloud) kalau
    file lokal tidak ada/kosong - config/gemini_default.txt sengaja di-gitignore
    jadi tidak akan ada sama sekali di server Cloud. Format di Secrets:

        GEMINI_API_KEY = "xxxx"
        GEMINI_MODEL = "gemini-2.0-flash"
    """
    result = {"api_key": "", "model": "gemini-2.0-flash"}
    if os.path.exists(DEFAULT_GEMINI_CONFIG_PATH):
        try:
            with open(DEFAULT_GEMINI_CONFIG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip()
                    if key == "GEMINI_API_KEY" and value:
                        result["api_key"] = value
                    elif key == "GEMINI_MODEL" and value:
                        result["model"] = value
        except Exception:
            pass

    if not result["api_key"]:
        try:
            if st.secrets.get("GEMINI_API_KEY"):
                result["api_key"] = st.secrets["GEMINI_API_KEY"]
            if st.secrets.get("GEMINI_MODEL"):
                result["model"] = st.secrets["GEMINI_MODEL"]
        except Exception:
            pass
    return result


PEJABAT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "pejabat.txt")


def load_pejabat_config():
    """Baca config/pejabat.txt -> {'kabiro': ..., 'kaprodi': {nama_prodi: nama_kaprodi}},
    dengan fallback ke st.secrets (Streamlit Community Cloud) kalau file lokal
    tidak ada/kosong. Format di Secrets (perhatikan [KAPRODI] sebagai tabel
    TOML, beda dari KABIRO_PENJAMINAN_MUTU yang baris biasa):

        KABIRO_PENJAMINAN_MUTU = "Dr. Nama Kabiro"

        [KAPRODI]
        "Informatika PJJ S1" = "Dr. Nama Kaprodi"
    """
    result = {"kabiro": "", "kaprodi": {}}
    if os.path.exists(PEJABAT_CONFIG_PATH):
        try:
            with open(PEJABAT_CONFIG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip()
                    if key == "KABIRO_PENJAMINAN_MUTU" and value:
                        result["kabiro"] = value
                    elif key.startswith("KAPRODI_") and value:
                        nama_prodi = key[len("KAPRODI_"):]
                        result["kaprodi"][nama_prodi] = value
        except Exception:
            pass

    if not result["kabiro"] and not result["kaprodi"]:
        try:
            if st.secrets.get("KABIRO_PENJAMINAN_MUTU"):
                result["kabiro"] = st.secrets["KABIRO_PENJAMINAN_MUTU"]
            if "KAPRODI" in st.secrets:
                result["kaprodi"] = dict(st.secrets["KAPRODI"])
        except Exception:
            pass
    return result

BLOOM_LEVELS = ["C1", "C2", "C3", "C4", "C5", "C6"]
METODE_OPTIONS = ["SGD", "RPS", "DL", "SDL", "CoL", "CbL", "CtL", "PjBL", "PBL", "BL"]
BENTUK_OPTIONS = ["EL-1", "EL-2", "EL-3", "EL-4", "EL-5", "EL-6", "EL-7", "EL-8", "EL-9"]

BLOOM_INFO = {
    "C1": "Remembering", "C2": "Understanding", "C3": "Applying",
    "C4": "Analyzing", "C5": "Evaluating", "C6": "Creating",
}
METODE_INFO = {
    "SGD": "Small Group Discussion", "RPS": "Role-Play & Simulation",
    "DL": "Discovery Learning", "SDL": "Self-Directed Learning",
    "CoL": "Cooperative Learning", "CbL": "Collaborative Learning",
    "CtL": "Contextual Learning", "PjBL": "Project Based Learning",
    "PBL": "Problem Based Learning & Inquiry", "BL": "Blended Learning",
}
BENTUK_INFO = {
    "EL-1": "Video E-Learning", "EL-2": "Discussion at Forum",
    "EL-3": "Video Conference atau Webinar (Web Seminar)",
    "EL-4": "E-simulation using software (Virtual Lab)",
    "EL-5": "E-learning Link (journal online, library online, digital learning dari URL/HTTP)",
    "EL-6": "Vlog Presentation", "EL-7": "Writing Paper on-line",
    "EL-8": "Virtual Lab", "EL-9": "AI Learning Mode",
}


def info_tooltip(info_dict):
    return "  \n".join(f"**{k}**: {v}" for k, v in info_dict.items())


N_CPL_WAJIB = 5
N_MINGGU = 16
KATEGORI_PENILAIAN = ["Interaksi", "UTS", "Tugas", "UAS"]
HEADER_BLUE = "#92CDDC"  # warna header tabel utama, sesuai template resmi terbaru

st.set_page_config(page_title="RPS Builder · UNSIA", layout="wide")

# --------------------------------------------------------------------------
# Fase 2: gerbang login - hentikan halaman kalau belum masuk.
# Penyesuaian: Admin/Kaprodi TIDAK dikunci eksklusif ke panel masing-masing -
# semua peran tetap bisa mengisi RPS sendiri (kepemilikan RPS berbasis akun,
# bukan role). Menu di bawah menampilkan opsi tambahan sesuai role.
# --------------------------------------------------------------------------
pengguna = require_login()
client = get_client()


# --------------------------------------------------------------------------
# Asisten AI (Google Gemini, opsional) - menyarankan draf isi 1 pertemuan
# --------------------------------------------------------------------------
def get_ai_suggestion(nama_mk, deskripsi_mk, cpmk_desc, sub_cpmk_desc, minggu, api_key, model_name="gemini-2.0-flash"):
    client = genai.Client(api_key=api_key)
    prompt = f"""Anda membantu dosen menyusun RPS (Rencana Pembelajaran Semester) untuk mata kuliah "{nama_mk}".

Deskripsi mata kuliah ini secara keseluruhan: {deskripsi_mk or "(belum diisi)"}

Konteks pertemuan minggu ke-{minggu} dari 16 minggu perkuliahan:
- CPMK terkait: {cpmk_desc or "(belum diisi)"}
- Sub-CPMK (jika sudah diisi dosen): {sub_cpmk_desc or "(belum diisi)"}

Gunakan deskripsi mata kuliah, CPMK, DAN Sub-CPMK di atas sebagai konteks utama supaya saran
yang diberikan relevan dan konsisten dengan arah keseluruhan mata kuliah, bukan generik.

Sarankan draf singkat, konkret, dan realistis untuk SATU pertemuan ini saja (bukan seluruh semester),
dalam Bahasa Indonesia:
- materi: poin-poin utama materi pembelajaran minggu ini (boleh berupa daftar singkat)
- bentuk_asesmen: bentuk asesmen penilaian yang sesuai untuk pertemuan ini (mis. kuis, tugas individu, presentasi)
- indikator: indikator penilaian yang terukur
- bloom: 1-2 level Bloom's Taxonomy yang paling sesuai dengan kedalaman pertemuan ini
- bentuk: 1-2 bentuk pembelajaran online yang paling sesuai dengan materi/asesmen yang disarankan"""

    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "object",
            "properties": {
                "materi": {"type": "string"},
                "bentuk_asesmen": {"type": "string"},
                "indikator": {"type": "string"},
                "bloom": {"type": "array", "items": {"type": "string", "enum": BLOOM_LEVELS}},
                "bentuk": {"type": "array", "items": {"type": "string", "enum": BENTUK_OPTIONS}},
            },
            "required": ["materi", "bentuk_asesmen", "indikator", "bloom", "bentuk"],
        },
    )
    response = client.models.generate_content(model=model_name, contents=prompt, config=config)
    return json.loads(response.text)



# --------------------------------------------------------------------------
# Data master
# --------------------------------------------------------------------------
# Fase 3: dipindah ke db_master.py (baca dari tabel Supabase, bukan file
# Excel di folder data/ lagi). Lihat list_prodi_db() & load_master_db() yang
# di-import di atas. File Excel di data/ tetap ada sebagai sumber untuk
# scripts/migrate_excel_to_db.py, tapi tidak lagi dibaca langsung di sini.

# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
def default_pertemuan():
    pertemuan = {
        m: {
            "sub_cpmk_desc": "", "cpmk_ref": None, "bloom": [], "materi": "",
            "metode": [], "bentuk": [], "bentuk_asesmen": "", "indikator": "",
        } for m in range(1, N_MINGGU + 1)
    }
    # Minggu 8 & 16 di template baru sekarang punya barisnya sendiri (tidak lagi
    # dilompati/digabung seperti template lama) - auto-isi teks starting default,
    # tetap bisa diedit/dihapus dosen kalau mau isi lain.
    pertemuan[8]["sub_cpmk_desc"] = "Ujian Tengah Semester (UTS)"
    pertemuan[16]["sub_cpmk_desc"] = "Ujian Akhir Semester (UAS)"
    return pertemuan


def init_state():
    defaults = {
        "prodi_sel": None,
        "tahun_sel": None,
        "mk_sel": None,
        "cpl_selected": [],
        "info_umum": {
            # dosen_pengampu SENGAJA tidak lagi diisi manual di sini - dokumen final
            # yang diunduh (dari halaman RPS Tervalidasi) selalu memakai nama akun
            # yang sedang mengunduh, bukan nilai tersimpan. Kuncinya tetap ada di
            # dict ini untuk kompatibilitas mundur data lama, tapi tidak ada widget
            # untuk mengeditnya lagi.
            "dosen_koordinator": "", "dosen_pengampu": "", "deskripsi_mk": "",
            "rumpun_mk": "",
            "nama_kaprodi": "", "nama_koordinator": "", "nama_penyusun": "",
            "nama_biro_pjm": "", "tanggal_dokumen": "",
            "level_ai": "", "deskripsi_ai": "",
        },
        "cpmk_data": {i: {"cpl_kode": None, "deskripsi": ""} for i in range(1, 6)},
        "pertemuan_data": default_pertemuan(),
        # dict persen per kategori per CPMK (bukan checklist lagi) - tiap
        # kategori (kolom) totalnya harus PAS sama dengan bobot kategori itu,
        # dijumlah dari 5 CPMK (lihat get_komponen_issues() & tab_nilai).
        "komponen_data": {i: {kat: 0 for kat in KATEGORI_PENILAIAN} for i in range(1, 6)},
        "referensi_data": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_rps_state():
    """Reset semua isian RPS (dipanggil saat ganti Mata Kuliah)."""
    keys = ["cpl_selected", "info_umum", "cpmk_data", "pertemuan_data",
            "komponen_data", "referensi_data"]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]
    init_state()


# --------------------------------------------------------------------------
# Konversi Pertemuan <-> DataFrame (dipakai untuk template impor/ekspor progres)
# --------------------------------------------------------------------------
def pertemuan_to_df(pertemuan_data):
    rows = []
    for m in range(1, N_MINGGU + 1):
        p = pertemuan_data[m]
        rows.append({
            "Minggu": m,
            "Sub-CPMK": p.get("sub_cpmk_desc", ""),
            "CPMK Ref": p.get("cpmk_ref") or "-",
            "Bloom": ", ".join(p.get("bloom", [])),
            "Indikator": p.get("indikator", ""),
            "Bentuk Asesmen": p.get("bentuk_asesmen", ""),
            "Metode": ", ".join(p.get("metode", [])),
            "Bentuk Online": ", ".join(p.get("bentuk", [])),
            "Materi": p.get("materi", ""),
        })
    return pd.DataFrame(rows)


def df_to_pertemuan(df):
    data = {}
    for _, row in df.iterrows():
        if pd.isna(row["Minggu"]):
            continue  # lewati baris kosong (mis. sisa baris terpakai dari Excel)
        m = int(row["Minggu"])
        cpmk_ref = row["CPMK Ref"]
        data[m] = {
            "sub_cpmk_desc": row["Sub-CPMK"] or "",
            "cpmk_ref": None if cpmk_ref in ("-", None, "") else cpmk_ref,
            "bloom": [x.strip() for x in str(row["Bloom"] or "").split(",") if x.strip()],
            "indikator": row["Indikator"] or "",
            "bentuk_asesmen": row["Bentuk Asesmen"] or "",
            "metode": [x.strip() for x in str(row["Metode"] or "").split(",") if x.strip()],
            "bentuk": [x.strip() for x in str(row["Bentuk Online"] or "").split(",") if x.strip()],
            "materi": row["Materi"] or "",
        }
    # pastikan minggu 1-16 selalu ada meski file yang diimpor tidak lengkap
    for m in range(1, N_MINGGU + 1):
        if m not in data:
            data[m] = default_pertemuan()[m]
    return data


# --------------------------------------------------------------------------
# Konversi session_state <-> kolom `data` (JSONB) di tabel `rps` - Fase 4.
# Dipakai untuk simpan/muat ke database, menggantikan Unduh/Muat Progres Excel
# sebagai mekanisme utama (Excel tetap ada sebagai cadangan opsional).
# --------------------------------------------------------------------------
def state_to_rps_data():
    return {
        "cpl_selected": st.session_state.cpl_selected,
        "info_umum": st.session_state.info_umum,
        "cpmk_data": {str(k): v for k, v in st.session_state.cpmk_data.items()},
        "pertemuan_data": {str(k): v for k, v in st.session_state.pertemuan_data.items()},
        "komponen_data": {str(k): v for k, v in st.session_state.komponen_data.items()},
        "referensi_data": st.session_state.referensi_data,
    }


def _normalize_komponen_row(value):
    """Normalisasi satu baris komponen_data ke format TERBARU (dict persen per
    kategori, mis. {"UTS": 20}). Format lama (checklist/list, atau nilai
    tunggal/string dari sebelum itu) TIDAK membawa info persentase sama
    sekali, jadi RPS lama otomatis di-reset ke 0 untuk tab Komponen Penilaian
    ini saja - Dosen perlu mengisi ulang pembagian persentasenya (isi CPMK &
    bagian lain RPS TIDAK terpengaruh/tidak hilang).

    Kategori "Kehadiran dan Sikap" berganti nama jadi "Interaksi" - kalau
    data lama masih pakai nama lama, petakan ke nama baru DULU supaya
    nilainya (persentase yang sudah diisi) tidak ikut hilang seperti
    perubahan struktur lain di atas - ini murni rename, bukan perubahan
    makna, jadi datanya tetap valid untuk dibawa.
    """
    if isinstance(value, dict):
        migrated = dict(value)
        if "Kehadiran dan Sikap" in migrated and "Interaksi" not in migrated:
            migrated["Interaksi"] = migrated.pop("Kehadiran dan Sikap")
        return {kat: int(migrated.get(kat) or 0) for kat in KATEGORI_PENILAIAN}
    return {kat: 0 for kat in KATEGORI_PENILAIAN}


def get_komponen_issues():
    """Daftar kategori yang totalnya (dijumlah dari 5 CPMK) belum PAS sama
    dengan bobot kategori itu. List kosong = semua sudah benar."""
    issues = []
    for kategori in KATEGORI_PENILAIAN:
        target = BOBOT_KATEGORI.get(kategori, 0)
        total = sum(
            (st.session_state.komponen_data.get(i) or {}).get(kategori, 0)
            for i in range(1, 6)
        )
        if total != target:
            issues.append(f"{kategori}: total {total}% (seharusnya {target}%)")
    return issues


def _hash_rps_data(data):
    """Hash konten RPS (urutan key konsisten) - dipakai auto-save (dan tombol
    manual) untuk tahu "sudah tersimpan persis seperti ini sebelumnya atau
    belum" - supaya auto-save tidak menyimpan (dan mencatat baris riwayat
    baru) berulang-ulang padahal tidak ada perubahan apa pun sejak terakhir
    disimpan."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def simpan_progres_button(key_suffix, primary=False, label="💾 Simpan Progres ke Database"):
    """Tombol Simpan yang SAMA dipakai ulang di sidebar DAN di bagian atas
    tiap tab (Info Umum, CPL&CPMK, 16 Pertemuan, dst.) - supaya tidak perlu
    scroll balik ke sidebar tiap kali mau menyimpan, terutama di tab yang
    isinya panjang (mis. 16 Pertemuan). key_suffix WAJIB beda-beda di tiap
    lokasi supaya tidak duplicate-key error. Otomatis disembunyikan kalau
    status RPS sedang tidak bisa diedit (diajukan/disetujui/divalidasi).
    Membaca client/mk_row/pengguna dari scope global - sama seperti pola
    get_komponen_issues() di atas terhadap session_state."""
    status_saat_ini = st.session_state.get("_rps_status") or "draft"
    if status_saat_ini not in ("draft", "ditolak"):
        return
    if st.button(label, key=f"save_progres_{key_suffix}",
                 type="primary" if primary else "secondary", use_container_width=True):
        try:
            data = state_to_rps_data()
            saved = save_rps(client, mk_row["id"], pengguna["id"], data)
            st.session_state["_rps_id"] = saved["id"]
            st.session_state["_rps_status"] = saved["status"]
            st.session_state["_rps_last_saved_hash"] = _hash_rps_data(data)
            st.success("✅ Progres tersimpan.")
        except Exception as e:
            st.error(f"Gagal menyimpan: {e}")


@st.fragment(run_every=60)
def auto_save_fragment():
    """Auto-save berkala (~60 detik) selagi Dosen mengisi RPS - lapisan
    TAMBAHAN di atas tombol Simpan manual (simpan_progres_button), supaya
    progres tidak hilang total kalau tidak sengaja refresh sebelum sempat
    klik Simpan sendiri.

    CATATAN JUJUR: @st.fragment(run_every=...) adalah fitur BAWAAN Streamlit
    (bukan library pihak ketiga seperti komponen cookie yang pernah dicoba
    dan dibatalkan sebelumnya) - tapi belum pernah dipakai di proyek ini,
    jadi tetap perlu diuji nyata: buka salah satu RPS, tunggu >=60 detik
    sambil isi sesuatu, lihat apakah caption "Auto-save terakhir" di sidebar
    ikut berubah tanpa perlu klik apa pun. Butuh Streamlit >=1.37 (lihat
    requirements.txt) - kalau versi lebih lama, decorator ini akan error saat
    aplikasi dijalankan, bukan gagal diam-diam.

    Membaca client/mk_row/pengguna dari scope global (sama seperti
    simpan_progres_button) - TIDAK dipanggil sebelum mk_row ada (dipanggil
    setelah blok sidebar "Isi Mata Kuliah" selesai, lihat titik panggilnya).

    Sengaja TIDAK menyimpan kalau:
    - status sedang tidak bisa diedit (diajukan/disetujui/divalidasi) - sama
      seperti syarat simpan_progres_button, supaya tidak mencoba menyimpan
      sesuatu yang memang akan ditolak RLS database
    - isi RPS PERSIS SAMA dengan penyimpanan terakhir (dicek lewat hash) -
      supaya tidak membuat baris riwayat perubahan baru terus-menerus tanpa
      perubahan berarti (tabel rps_riwayat dicatat otomatis oleh trigger
      database tiap kali baris rps di-update, lihat sql/schema.sql)
    Gagal auto-save (mis. sedang tidak ada koneksi internet sesaat) SENGAJA
    didiamkan tanpa munculkan error - supaya tidak mengganggu Dosen yang
    sedang fokus mengetik dengan popup setiap menit.
    """
    status_saat_ini = st.session_state.get("_rps_status") or "draft"
    if status_saat_ini not in ("draft", "ditolak"):
        return
    data = state_to_rps_data()
    current_hash = _hash_rps_data(data)
    if current_hash == st.session_state.get("_rps_last_saved_hash"):
        return
    try:
        saved = save_rps(client, mk_row["id"], pengguna["id"], data)
        st.session_state["_rps_id"] = saved["id"]
        st.session_state["_rps_status"] = saved["status"]
        st.session_state["_rps_last_saved_hash"] = current_hash
        st.session_state["_rps_last_autosave_at"] = datetime.now().strftime("%H:%M:%S")
    except Exception:
        pass


def apply_rps_data_to_state(data):
    """Timpa session_state RPS yang aktif dengan isi `data` (dari kolom JSONB
    rps.data). Dipanggil setelah reset_rps_state()+auto-isi, jadi field yang
    memang tersimpan di `data` akan menang dibanding nilai auto-isi default."""
    st.session_state.cpl_selected = data.get("cpl_selected") or []

    info = dict(st.session_state.info_umum)
    info.update(data.get("info_umum") or {})
    st.session_state.info_umum = info

    cpmk = {i: {"cpl_kode": None, "deskripsi": ""} for i in range(1, 6)}
    for k, v in (data.get("cpmk_data") or {}).items():
        cpmk[int(k)] = v
    st.session_state.cpmk_data = cpmk

    pertemuan = default_pertemuan()
    for k, v in (data.get("pertemuan_data") or {}).items():
        pertemuan[int(k)] = v
    st.session_state.pertemuan_data = pertemuan

    komponen = {i: {kat: 0 for kat in KATEGORI_PENILAIAN} for i in range(1, 6)}
    for k, v in (data.get("komponen_data") or {}).items():
        komponen[int(k)] = _normalize_komponen_row(v)
    st.session_state.komponen_data = komponen

    st.session_state.referensi_data = data.get("referensi_data") or []


# --------------------------------------------------------------------------
# Simpan / muat progres, format Excel (bukan JSON, supaya bisa dibuka & dicek
# manual oleh dosen di Excel biasa)
# --------------------------------------------------------------------------
def serialize_progress_excel(mk_row):
    wb = Workbook()

    ws_meta = wb.active
    ws_meta.title = "Meta"
    ws_meta.append(["Key", "Value"])
    ws_meta.append(["prodi_sel", st.session_state.prodi_sel])
    ws_meta.append(["mk_sel", st.session_state.mk_sel])
    info = st.session_state.info_umum
    for key in ("dosen_koordinator", "dosen_pengampu", "deskripsi_mk",
                "rumpun_mk", "nama_kaprodi", "nama_koordinator", "nama_penyusun",
                "nama_biro_pjm", "tanggal_dokumen", "level_ai", "deskripsi_ai"):
        ws_meta.append([key, info.get(key, "")])

    ws_cpl = wb.create_sheet("CPL_Selected")
    ws_cpl.append(["Kode CPL"])
    for k in st.session_state.cpl_selected:
        ws_cpl.append([k])

    ws_cpmk = wb.create_sheet("CPMK")
    ws_cpmk.append(["No", "Kode CPL", "Deskripsi"])
    for i in range(1, 6):
        c = st.session_state.cpmk_data[i]
        ws_cpmk.append([i, c["cpl_kode"], c["deskripsi"]])

    ws_komp = wb.create_sheet("Komponen")
    ws_komp.append(["CPMK"] + KATEGORI_PENILAIAN)
    for i in range(1, 6):
        row_persen = st.session_state.komponen_data.get(i) or {}
        ws_komp.append([f"CPMK-{i}"] + [row_persen.get(kat, 0) for kat in KATEGORI_PENILAIAN])

    ws_ref = wb.create_sheet("Referensi")
    ws_ref.append(["No", "Sitasi"])
    for i, ref in enumerate(st.session_state.referensi_data, start=1):
        ws_ref.append([i, ref["sitasi"]])

    ws_prt = wb.create_sheet("Pertemuan")
    df = pertemuan_to_df(st.session_state.pertemuan_data)
    ws_prt.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws_prt.append(list(row))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def load_progress_excel(uploaded_file):
    wb = openpyxl.load_workbook(uploaded_file, data_only=True)

    if "Meta" in wb.sheetnames:
        ws = wb["Meta"]
        meta = {row[0]: row[1] for row in ws.iter_rows(min_row=2, values_only=True) if row[0]}
        st.session_state.prodi_sel = meta.get("prodi_sel")
        st.session_state.mk_sel = meta.get("mk_sel")
        # Perbarui info_umum field-per-field (bukan mengganti seluruh dict), supaya field
        # yang belum ada di file progres lama (mis. ditambahkan di versi aplikasi yang lebih
        # baru) tidak sampai hilang dan menyebabkan KeyError di tempat lain.
        for key in ("dosen_koordinator", "dosen_pengampu", "deskripsi_mk",
                    "rumpun_mk", "nama_kaprodi", "nama_koordinator", "nama_penyusun",
                    "nama_biro_pjm", "tanggal_dokumen", "level_ai", "deskripsi_ai"):
            st.session_state.info_umum[key] = meta.get(key) or st.session_state.info_umum.get(key, "")

    if "CPL_Selected" in wb.sheetnames:
        ws = wb["CPL_Selected"]
        st.session_state.cpl_selected = [
            row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row[0]
        ]

    if "CPMK" in wb.sheetnames:
        ws = wb["CPMK"]
        cpmk_data = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            no, cpl_kode, desk = row[0], row[1], row[2]
            if no:
                cpmk_data[int(no)] = {"cpl_kode": cpl_kode, "deskripsi": desk or ""}
        if cpmk_data:
            st.session_state.cpmk_data = cpmk_data

    if "Komponen" in wb.sheetnames:
        ws = wb["Komponen"]
        komponen_data = {}
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=1):
            komponen_data[i] = {
                kat: int(row[j + 1] or 0) if j + 1 < len(row) else 0
                for j, kat in enumerate(KATEGORI_PENILAIAN)
            }
        if komponen_data:
            st.session_state.komponen_data = komponen_data

    if "Referensi" in wb.sheetnames:
        ws = wb["Referensi"]
        st.session_state.referensi_data = [
            {"sitasi": row[1]} for row in ws.iter_rows(min_row=2, values_only=True) if row[1]
        ]

    if "Pertemuan" in wb.sheetnames:
        ws = wb["Pertemuan"]
        values = list(ws.iter_rows(min_row=1, values_only=True))
        if values:
            cols = values[0]
            df = pd.DataFrame(values[1:], columns=cols)
            st.session_state.pertemuan_data = df_to_pertemuan(df)



# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
init_state()

st.title("📘 RPS Builder")
st.caption("Universitas Siber Asia")

# Penyesuaian: menu dasar sama untuk semua orang (Isi RPS, RPS Saya, RPS
# Disetujui - RPS tetap milik Mata Kuliah/koordinatornya, bukan tergantung
# role), Kaprodi/Admin cuma dapat TAMBAHAN opsi menu untuk panel masing-
# masing. Ini supaya Kaprodi yang juga mengajar (jadi koordinator Mata
# Kuliahnya sendiri) tetap bisa mengisi RPS-nya sendiri, bukan terkunci
# hanya ke panel Kaprodi.
menu_options = ["✏️ Isi RPS", "📋 RPS Saya", "📚 RPS Tervalidasi"]
if pengguna["role"] == "kaprodi":
    menu_options.append("✅ Review Kaprodi")
elif pengguna["role"] == "admin":
    menu_options.append("⚙️ Panel Admin")
elif pengguna["role"] == "bpm":
    menu_options.append("✅ Validasi BPM")

# Fase 4: kalau tombol "Buka" di halaman RPS Saya baru saja diklik, paksa
# menu balik ke "Isi RPS". HARUS dicek di sini, SEBELUM widget menu_utama
# di bawah diinstansiasi - session_state sebuah widget tidak boleh diubah
# lagi setelah widget-nya sendiri sempat dirender di run yang sama.
if st.session_state.pop("_jump_to_isi_rps", False):
    st.session_state["menu_utama"] = "✏️ Isi RPS"

menu = st.radio(
    "Menu", menu_options, horizontal=True,
    key="menu_utama", label_visibility="collapsed",
)
if menu == "📋 RPS Saya":
    render_rps_saya(client, pengguna)
    st.stop()
elif menu == "📚 RPS Tervalidasi":
    render_rps_tervalidasi(client, pengguna)
    st.stop()
elif menu == "✅ Review Kaprodi":
    render_kaprodi_panel(client, pengguna)
    st.stop()
elif menu == "⚙️ Panel Admin":
    render_admin_panel(client)
    st.stop()
elif menu == "✅ Validasi BPM":
    render_bpm_panel(client, pengguna)
    st.stop()

with st.sidebar:
    st.header("Pilih Mata Kuliah")

    prodi_rows = list_prodi_db(client)
    prodi_options = [p["nama"] for p in prodi_rows]
    if not prodi_options:
        st.error(
            "Belum ada data Prodi di database. Minta Admin menjalankan migrasi "
            "(scripts/migrate_excel_to_db.py) atau menambah Prodi lewat Panel Admin."
        )
        st.stop()

    # Penyesuaian: default Prodi yang tampil pertama kali = Prodi Homebase akun
    # yang login (kalau ada) - MURNI titik awal yang nyaman, sama sekali tidak
    # membatasi; begitu dipilih, prodi_sel tersimpan di session_state dan
    # penggantian manual berikutnya (baris "if prodi_sel != ..." di bawah) yang
    # menentukan, bukan homebase ini lagi.
    homebase_nama = next(
        (p["nama"] for p in prodi_rows if p["id"] == pengguna.get("prodi_id")), None
    )
    if st.session_state.prodi_sel in prodi_options:
        default_index = prodi_options.index(st.session_state.prodi_sel)
    elif homebase_nama in prodi_options:
        default_index = prodi_options.index(homebase_nama)
    else:
        default_index = 0

    prodi_sel = st.selectbox(
        "Program Studi", prodi_options,
        index=default_index,
        key="prodi_selectbox",
    )
    if prodi_sel != st.session_state.prodi_sel:
        st.session_state.prodi_sel = prodi_sel
        st.session_state.mk_sel = None

    prodi_id = get_prodi_id(prodi_rows, prodi_sel)

    # Penyesuaian: kurikulum ganda - satu Prodi bisa punya beberapa Tahun
    # Kurikulum berdampingan (mis. 2021 & 2026), masing-masing Mata Kuliahnya
    # terpisah sepenuhnya (baris database berbeda, koordinator bisa berbeda).
    tahun_options = list_tahun_kurikulum(client, prodi_id)
    tahun_sel = st.selectbox(
        "Tahun Kurikulum", tahun_options,
        index=tahun_options.index(st.session_state.tahun_sel) if st.session_state.tahun_sel in tahun_options else len(tahun_options) - 1,
        key="tahun_selectbox",
    )
    if tahun_sel != st.session_state.tahun_sel:
        st.session_state.tahun_sel = tahun_sel
        st.session_state.mk_sel = None

    mk_df_semua, cpl_df = load_master_db(client, prodi_id, tahun_sel)
    # Penyesuaian: hanya Mata Kuliah yang koordinatornya = Anda yang boleh
    # diisi - Mata Kuliah tanpa koordinator, atau koordinatornya orang lain,
    # tidak muncul di dropdown ini sama sekali (dikunci di level akses).
    mk_df = mk_df_semua[mk_df_semua["koordinator_user_id"] == pengguna["id"]].reset_index(drop=True)
    mk_options = mk_df["Nama Mata Kuliah"].tolist()
    if not mk_options:
        st.warning(
            f"Anda belum ditetapkan sebagai koordinator Mata Kuliah manapun di Prodi "
            f"'{prodi_sel}' untuk kurikulum {tahun_sel}. Hubungi Kaprodi/Admin Prodi ini "
            "untuk ditetapkan sebagai koordinator suatu Mata Kuliah dulu, atau coba "
            "pilih Tahun Kurikulum lain."
        )
        st.stop()
    # Label tampilan "Kode - Nama" (Kode MK didahulukan) - HANYA untuk tampilan,
    # value yang dipakai untuk pencocokan/session_state tetap Nama Mata Kuliah
    # seperti sebelumnya, supaya tidak perlu ubah logika di tempat lain.
    label_mk = {
        row["Nama Mata Kuliah"]: f"{row['Kode MK']} - {row['Nama Mata Kuliah']}"
        for _, row in mk_df.iterrows()
    }
    mk_sel_name = st.selectbox(
        "Mata Kuliah", mk_options,
        index=mk_options.index(st.session_state.mk_sel) if st.session_state.mk_sel in mk_options else 0,
        format_func=lambda nama: label_mk.get(nama, nama),
        key="mk_selectbox",
    )

    if mk_sel_name != st.session_state.mk_sel:
        new_mk_row = mk_df[mk_df["Nama Mata Kuliah"] == mk_sel_name].iloc[0]
        raw_rumpun = new_mk_row.get("Rumpun MK", "")
        rumpun_mk_val = "" if pd.isna(raw_rumpun) or raw_rumpun == "-" else str(raw_rumpun).strip()

        reset_rps_state()
        st.session_state.prodi_sel = prodi_sel
        st.session_state.mk_sel = mk_sel_name

        # Penyesuaian: Dosen Pengembang RPS (Koordinator), Nama Kaprodi, dan
        # Nama Ka. BPM TIDAK LAGI diketik manual atau diambil dari file
        # config/pejabat.txt - sekarang ditarik LANGSUNG dari database:
        # koordinator = akun yang sedang login (cuma koordinator MK ini yang
        # bisa sampai ke titik ini, dijamin RLS), Kaprodi & BPM lewat RPC
        # get_kaprodi_nama()/get_bpm_nama() (lihat db_master.py). Kalau belum
        # ada yang ditetapkan sebagai Kaprodi/BPM di database, jatuh ke
        # config/pejabat.txt dulu sebagai fallback masa transisi, baru kosong
        # kalau itu juga tidak ada.
        nama_saya = pengguna.get("nama") or pengguna.get("email") or ""
        st.session_state.info_umum["dosen_koordinator"] = nama_saya
        st.session_state.info_umum["nama_koordinator"] = nama_saya

        pejabat_cfg = load_pejabat_config()
        nama_kaprodi_db = get_kaprodi_nama(client, prodi_id)
        st.session_state.info_umum["nama_kaprodi"] = nama_kaprodi_db or pejabat_cfg["kaprodi"].get(prodi_sel, "")
        nama_bpm_db = get_bpm_nama(client)
        st.session_state.info_umum["nama_biro_pjm"] = nama_bpm_db or pejabat_cfg["kabiro"]

        st.session_state.info_umum["rumpun_mk"] = rumpun_mk_val

        # Fase 4: kalau RPS untuk Mata Kuliah ini sudah pernah disimpan
        # sebelumnya (oleh Dosen yang sama), muat isinya - menang dibanding
        # auto-isi default di atas.
        existing = load_rps(client, new_mk_row["id"])
        if existing:
            apply_rps_data_to_state(existing["data"])
            st.session_state["_rps_id"] = existing["id"]
            st.session_state["_rps_status"] = existing["status"]
            st.session_state["_rps_catatan"] = existing.get("catatan_kaprodi")
            st.session_state["_rps_catatan_bpm"] = existing.get("catatan_bpm")
            st.session_state["_rps_diajukan_pada"] = existing.get("diajukan_pada")
        else:
            st.session_state["_rps_id"] = None
            st.session_state["_rps_status"] = None
            st.session_state["_rps_catatan"] = None
            st.session_state["_rps_catatan_bpm"] = None
            st.session_state["_rps_diajukan_pada"] = None

        st.rerun()

    mk_row = mk_df[mk_df["Nama Mata Kuliah"] == mk_sel_name].iloc[0]
    st.markdown(f"""
    **Kode MK:** {mk_row['Kode MK']}
    **SKS:** {mk_row['SKS']} · **Semester:** {mk_row['Semester']}
    """)

    st.divider()
    st.subheader("💾 Simpan RPS")
    status_saat_ini = st.session_state.get("_rps_status") or "draft"
    status_label = {
        "draft": "📝 Draft", "diajukan": "📤 Diajukan (menunggu Kaprodi)",
        "disetujui": "✅ Disetujui Kaprodi (menunggu BPM)",
        "ditolak": "↩️ Ditolak", "divalidasi": "✅ Tervalidasi (Final)",
    }
    bisa_edit = status_saat_ini in ("draft", "ditolak")

    if st.session_state.get("_rps_id"):
        st.caption(f"Status: {status_label.get(status_saat_ini, status_saat_ini)} · tersimpan di database")
    else:
        st.caption("Belum pernah disimpan ke database untuk Mata Kuliah ini.")

    if st.session_state.get("_rps_last_autosave_at"):
        st.caption(f"🔄 Auto-save terakhir: {st.session_state['_rps_last_autosave_at']}")

    # Catatan penolakan bisa dari Kaprodi ATAU BPM (ditolak di tahap mana pun
    # sama-sama balik ke status 'ditolak') - tampilkan yang mana pun terisi.
    if status_saat_ini == "ditolak":
        if st.session_state.get("_rps_catatan_bpm"):
            st.warning(f"**Catatan BPM (ditolak):** {st.session_state['_rps_catatan_bpm']}")
        elif st.session_state.get("_rps_catatan"):
            st.warning(f"**Catatan Kaprodi (ditolak):** {st.session_state['_rps_catatan']}")

    if bisa_edit:
        simpan_progres_button("sidebar", primary=True, label="💾 Simpan ke Database")

        if st.session_state.get("_rps_id"):
            st.caption("➡️ Untuk mengajukan RPS ini ke Kaprodi, buka tab **Preview dan Ajukan**.")
    else:
        st.info(
            f"RPS berstatus **{status_label.get(status_saat_ini, status_saat_ini)}** - "
            "isian dikunci, tidak bisa disimpan ulang."
        )
        if status_saat_ini == "diajukan":
            st.caption("Menunggu review Kaprodi.")
            if st.button("↩️ Tarik Pengajuan", key="tarik_btn", use_container_width=True):
                try:
                    tarik_pengajuan_rps(client, st.session_state["_rps_id"])
                    st.session_state["_rps_status"] = "draft"
                    st.session_state["_rps_diajukan_pada"] = None
                    st.success("Pengajuan ditarik, kembali ke status Draft dan bisa diedit lagi.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menarik pengajuan: {e}")

    with st.expander("📦 Cadangan lokal (opsional, format Excel)"):
        st.caption(
            "Simpan ke Database di atas sudah jadi penyimpanan utama - bagian "
            "ini murni opsional untuk cadangan pribadi, atau mengimpor progres "
            "lama dari sebelum fitur database ini ada."
        )
        st.download_button(
            "Unduh Cadangan (.xlsx)", data=serialize_progress_excel(mk_row),
            file_name=f"progres_{mk_row['Kode MK']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_progress_btn",
        )
        up = st.file_uploader("Impor dari Cadangan Lama (.xlsx)", type=["xlsx"], key="progress_uploader")
        if up is not None:
            file_fingerprint = f"{up.name}_{up.size}"
            if st.session_state.get("_last_loaded_progress_file") != file_fingerprint:
                try:
                    load_progress_excel(up)
                    st.session_state["_last_loaded_progress_file"] = file_fingerprint
                    st.success("Progres dimuat. Jangan lupa klik 'Simpan ke Database' di atas untuk menyimpannya permanen.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal memuat progres: {type(e).__name__}: {e}")
                    st.caption(
                        "Pastikan file yang diunggah adalah hasil tombol 'Unduh Cadangan (.xlsx)' "
                        "dari aplikasi ini (bukan file Excel lain, dan bukan hasil ekspor RPS)."
                    )

    st.divider()
    st.subheader("🤖 Asisten AI (Gemini)")
    if not GENAI_AVAILABLE:
        st.caption(
            "Paket `google-genai` belum terpasang. Jalankan `pip install google-genai` "
            "(sudah ada di requirements.txt), lalu restart aplikasi."
        )
    else:
        default_cfg = load_default_gemini_config()
        has_default = bool(default_cfg["api_key"])

        source_options = (["Default (disediakan Prodi)"] if has_default else []) + ["API Key Sendiri"]
        source = st.radio("Sumber API Key", source_options, key="gemini_key_source")

        if source == "Default (disediakan Prodi)":
            st.caption(f"Memakai API key default yang disediakan. Model: `{default_cfg['model']}`")
            st.session_state["gemini_api_key_effective"] = default_cfg["api_key"]
            st.session_state["gemini_model_effective"] = default_cfg["model"]
        else:
            st.caption(
                "Kunci API hanya dipakai untuk sesi ini, tidak disimpan permanen ke mana pun."
            )
            st.text_input("Google Gemini API Key", type="password", key="gemini_api_key")
            st.text_input(
                "Model Gemini", value="gemini-2.0-flash", key="gemini_model_name",
                help=(
                    "Ganti kalau muncul error kuota (429 RESOURCE_EXHAUSTED) untuk model ini, "
                    "coba model lain, mis. 'gemini-2.5-flash-lite', 'gemini-1.5-flash', dsb. "
                    "Ketersediaan kuota gratis per model bisa berbeda-beda dan berubah dari waktu ke waktu."
                ),
            )
            st.session_state["gemini_api_key_effective"] = st.session_state.get("gemini_api_key", "")
            st.session_state["gemini_model_effective"] = st.session_state.get("gemini_model_name") or "gemini-2.0-flash"

        if not has_default:
            st.caption(
                "Belum ada API key default. Admin bisa isi `config/gemini_default.txt` untuk "
                "menyediakan API key bersama sebagai opsi tambahan bagi semua Dosen."
            )

# Opsi B: auto-save berkala (~60 detik) - dipanggil di SINI (bukan di dalam
# "with st.sidebar:" di atas) karena tidak perlu render UI apa pun sendiri,
# murni tugas latar belakang. Ditaruh setelah blok sidebar selesai supaya
# mk_row (dibutuhkan fungsinya) sudah pasti ada.
auto_save_fragment()


def mk_key(suffix):
    """Bikin widget key yang unik & stabil per Mata Kuliah aktif.

    Kunci tetap SAMA selama MK yang sama masih dipilih (mencegah Streamlit
    membuat ulang identitas widget setiap rerun -> penyebab gejala 'klik 2x'),
    tapi otomatis BEDA saat pindah MK (mencegah nilai lama nyangkut/bocor)."""
    return f"{st.session_state.mk_sel}__{suffix}"


tab_info, tab_cpl, tab_pertemuan, tab_ref, tab_nilai, tab_export = st.tabs(
    ["Info Umum", "CPL & CPMK", "16 Pertemuan", "Daftar Pustaka", "Komponen Penilaian", "Preview dan Ajukan"]
)

# --- Tab: Info Umum ---
with tab_info:
    simpan_progres_button("info_umum")
    st.divider()
    st.subheader("Informasi Umum RPS")
    info = st.session_state.info_umum
    st.text_input(
        "Dosen Pengembang RPS (Koordinator)", info["dosen_koordinator"], disabled=True,
        key=mk_key("dosen_koordinator_display"),
        help="Otomatis diisi nama akun Anda sendiri (koordinator Mata Kuliah ini), tidak bisa diedit manual.",
    )
    st.caption(
        "ℹ️ Field **Dosen Pengampu** di dokumen final otomatis diisi nama akun yang "
        "mengunduhnya dari halaman RPS Tervalidasi, tidak lagi diisi manual di sini."
    )
    info["deskripsi_mk"] = st.text_area(
        "Deskripsi Mata Kuliah", info["deskripsi_mk"], key=mk_key("deskripsi_mk"),
    )

    st.divider()
    st.subheader("Rumpun Mata Kuliah")
    st.text_input(
        "Rumpun MK (RMK)", info["rumpun_mk"], disabled=True, key=mk_key("rumpun_mk_display"),
        help="Otomatis diisi dari data master Mata Kuliah (kolom Rumpun MK) - hubungi Admin/Kaprodi kalau perlu diperbaiki.",
    )

    st.divider()
    st.subheader("Ketua Prodi")
    st.text_input(
        "Nama Ketua Prodi", info["nama_kaprodi"], disabled=True, key=mk_key("nama_kaprodi_display"),
        help="Otomatis diisi dari akun yang terdaftar sebagai Kaprodi Prodi ini. Muncul di QR Kaprodi pada dokumen.",
    )
    if not info["nama_kaprodi"]:
        st.caption("⚠️ Belum ada akun Kaprodi terdaftar untuk Prodi ini - hubungi Admin.")

    st.divider()
    st.subheader("Ka. Biro Penjaminan Mutu (BPM)")
    st.text_input(
        "Nama Ka. Biro Penjaminan Mutu", info["nama_biro_pjm"], disabled=True, key=mk_key("nama_biro_pjm_display"),
        help="Otomatis diisi dari akun yang terdaftar sebagai BPM. Muncul di QR BPM pada dokumen.",
    )
    if not info["nama_biro_pjm"]:
        st.caption("⚠️ Belum ada akun BPM terdaftar - hubungi Admin.")

# --- Tab: CPL & CPMK ---
with tab_cpl:
    simpan_progres_button("cpl_cpmk")
    st.divider()
    st.subheader("Pilih CPL Mata Kuliah")
    st.caption(f"Wajib memilih tepat {N_CPL_WAJIB} CPL untuk mata kuliah ini.")
    cpl_all = cpl_df["Kode CPL"].tolist()
    cpl_label = {row["Kode CPL"]: f"{row['Kode CPL']}: {row['Deskripsi CPL'][:70]}…"
                 for _, row in cpl_df.iterrows()}
    selected = st.multiselect(
        "CPL", cpl_all, default=st.session_state.cpl_selected,
        format_func=lambda k: cpl_label[k],
        key=mk_key("cpl_multiselect"),
        help=(
            "Urutan CPL yang dipilih menentukan pemetaan ke CPMK: CPL pertama yang dicentang "
            "otomatis jadi rujukan CPMK-1, kedua jadi CPMK-2, dst. Untuk mengubah pemetaan, "
            "hapus semua lalu pilih ulang sesuai urutan yang diinginkan."
        ),
    )
    st.session_state.cpl_selected = selected

    if len(selected) != N_CPL_WAJIB:
        st.warning(f"Sudah dipilih {len(selected)} dari {N_CPL_WAJIB} CPL yang diwajibkan.")
    else:
        st.success(f"{N_CPL_WAJIB} CPL sudah lengkap.")

        st.divider()
        st.subheader("CPMK")
        st.caption(
            "CPL untuk tiap CPMK ditentukan otomatis dari urutan CPL yang dipilih di atas "
            "(CPL ke-1 → CPMK-1, CPL ke-2 → CPMK-2, dst.), dosen tinggal isi deskripsinya. "
            "Kode CPL otomatis ditambahkan dalam kurung di akhir deskripsi CPMK pada hasil ekspor."
        )
        for i in range(1, 6):
            st.session_state.cpmk_data[i]["cpl_kode"] = selected[i - 1]
            cpl_kode_i = selected[i - 1]
            cpl_desk_i = cpl_df.loc[cpl_df["Kode CPL"] == cpl_kode_i, "Deskripsi CPL"]
            st.caption(f"📖 **{cpl_kode_i}**: {cpl_desk_i.values[0] if len(cpl_desk_i) else '-'}")
            st.session_state.cpmk_data[i]["deskripsi"] = st.text_area(
                f"Deskripsi CPMK-{i}  (rujukan: {cpl_kode_i})",
                st.session_state.cpmk_data[i]["deskripsi"],
                key=mk_key(f"cpmk_desk_{i}"), height=70,
            )
        st.success("5 CPL sudah otomatis terpetakan satu-satu ke CPMK-1 s/d CPMK-5, tanpa duplikasi.")

# --- Tab: 16 Pertemuan (accordion per minggu + opsi impor tabel) ---
with tab_pertemuan:
    simpan_progres_button("pertemuan_atas")
    st.divider()
    st.subheader("Rincian 16 Pertemuan")

    with st.expander("📥 Impor dari Tabel (opsional): isi banyak minggu sekaligus"):
        st.caption(
            "Unduh templatnya, isi di Excel (lebih leluasa untuk isi banyak baris sekaligus), "
            "lalu unggah kembali untuk mengisi otomatis ke-16 pertemuan. Kolom **CPMK Ref** diisi "
            "'CPMK-1' s/d 'CPMK-5' (atau '-' untuk UTS/UAS); kolom Bloom/Metode/Bentuk Online "
            "dipisah koma kalau lebih dari satu."
        )
        template_buf = io.BytesIO()
        pertemuan_to_df(default_pertemuan()).to_excel(template_buf, index=False)
        template_buf.seek(0)
        c1, c2 = st.columns(2)
        c1.download_button(
            "Unduh Template Kosong (.xlsx)", data=template_buf,
            file_name="template_16_pertemuan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=mk_key("download_template_pertemuan"),
        )
        upfile = c2.file_uploader("Unggah Tabel Terisi", type=["xlsx", "csv"], key=mk_key("pertemuan_import"))
        if upfile is not None:
            try:
                imported_df = pd.read_csv(upfile) if upfile.name.endswith(".csv") else pd.read_excel(upfile)
                st.session_state.pertemuan_data = df_to_pertemuan(imported_df)
                st.success("Berhasil mengimpor data 16 pertemuan.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal mengimpor: {e}")

    st.caption(
        "Sub-CPMK diisi langsung per minggu, sertakan CPMK mana yang dirujuk lewat **CPMK Ref** "
        "(kode CPMK otomatis ditambahkan dalam kurung di akhir kalimat Sub-CPMK pada hasil ekspor)."
    )
    cpmk_ref_options = ["-"] + [f"CPMK-{i}" for i in range(1, 6)]
    for m in range(1, N_MINGGU + 1):
        p = st.session_state.pertemuan_data[m]
        is_ujian = m in (8, 16)
        label = f"Minggu {m}" + (" 🔴 UTS" if m == 8 else " 🔴 UAS" if m == 16 else "")
        preview = p["sub_cpmk_desc"] or p["materi"] or "belum diisi"
        with st.expander(f"{label}: {preview[:60]}{'…' if len(preview) > 60 else ''}"):
            if is_ujian:
                st.warning(
                    f"Minggu ujian ({'UTS' if m == 8 else 'UAS'}) - field Sub-CPMK sudah "
                    "diisi teks standar, boleh diedit/ditambah cakupan materinya."
                )
            current_ref = p["cpmk_ref"] or "-"
            ref_choice = st.selectbox(
                "CPMK Ref", cpmk_ref_options,
                index=cpmk_ref_options.index(current_ref) if current_ref in cpmk_ref_options else 0,
                key=mk_key(f"prt_cpmkref_{m}"),
            )
            p["cpmk_ref"] = None if ref_choice == "-" else ref_choice
            if p["cpmk_ref"]:
                idx_cpmk_disp = int(p["cpmk_ref"].split("-")[1])
                cpmk_desc_disp = st.session_state.cpmk_data[idx_cpmk_disp]["deskripsi"]
                st.caption(f"📖 **{p['cpmk_ref']}**: {cpmk_desc_disp or '(belum diisi)'}")

            p["sub_cpmk_desc"] = st.text_area("Sub-CPMK", p["sub_cpmk_desc"], key=mk_key(f"prt_sub_{m}"), height=70)

            if GENAI_AVAILABLE:
                if st.button("✨ Sarankan dengan AI", key=mk_key(f"ai_btn_{m}")):
                    api_key = st.session_state.get("gemini_api_key_effective")
                    if not api_key:
                        st.warning("Isi dulu Google Gemini API Key di sidebar (atau pilih sumber Default kalau tersedia).")
                    else:
                        with st.spinner("Meminta saran dari AI..."):
                            try:
                                cpmk_desc = ""
                                if p["cpmk_ref"]:
                                    idx_cpmk = int(p["cpmk_ref"].split("-")[1])
                                    cpmk_desc = st.session_state.cpmk_data[idx_cpmk]["deskripsi"]
                                model_name = st.session_state.get("gemini_model_effective") or "gemini-2.0-flash"
                                suggestion = get_ai_suggestion(
                                    mk_row["Nama Mata Kuliah"], st.session_state.info_umum.get("deskripsi_mk", ""),
                                    cpmk_desc, p["sub_cpmk_desc"], m, api_key,
                                    model_name=model_name,
                                )
                                st.session_state[mk_key(f"ai_suggestion_{m}")] = suggestion
                            except Exception as e:
                                msg = str(e)
                                if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                                    st.error(
                                        "Kuota Gemini untuk model ini habis/nol pada paket akun Bapak "
                                        f"(model: `{model_name}`). Ini bukan error dari aplikasi, melainkan "
                                        "dari sisi akun Google. Coba salah satu:\n\n"
                                        "1. Ganti **Model Gemini** di sidebar ke model lain (mis. "
                                        "`gemini-2.5-flash-lite` atau `gemini-1.5-flash`), kuota gratis "
                                        "per model berbeda-beda.\n"
                                        "2. Aktifkan billing (pay-as-you-go) di [Google AI Studio]"
                                        "(https://aistudio.google.com), biaya pemakaian ringan seperti ini "
                                        "biasanya sangat kecil.\n"
                                        "3. Tunggu beberapa saat lalu coba lagi (kuota harian/menit bisa reset)."
                                    )
                                else:
                                    st.error(f"Gagal meminta saran AI: {e}")

                suggestion = st.session_state.get(mk_key(f"ai_suggestion_{m}"))
                if suggestion:
                    st.info(
                        "**Saran AI** (tinjau dulu, belum diterapkan ke field di bawah):\n\n"
                        f"**Materi:** {suggestion.get('materi', '-')}\n\n"
                        f"**Bentuk Asesmen:** {suggestion.get('bentuk_asesmen', '-')}\n\n"
                        f"**Indikator:** {suggestion.get('indikator', '-')}\n\n"
                        f"**Bloom:** {', '.join(suggestion.get('bloom', [])) or '-'}\n\n"
                        f"**Bentuk Online:** {', '.join(suggestion.get('bentuk', [])) or '-'}"
                    )
                    ca, cb = st.columns(2)
                    if ca.button("✅ Terapkan Saran", key=mk_key(f"ai_apply_{m}")):
                        new_materi = suggestion.get("materi", p["materi"])
                        new_bentuk_asesmen = suggestion.get("bentuk_asesmen", p["bentuk_asesmen"])
                        new_indikator = suggestion.get("indikator", p["indikator"])
                        new_bloom = [b for b in suggestion.get("bloom", []) if b in BLOOM_LEVELS] or p["bloom"]
                        new_bentuk = [b for b in suggestion.get("bentuk", []) if b in BENTUK_OPTIONS] or p["bentuk"]
                        # Tulis ke data kita sendiri...
                        p["materi"] = new_materi
                        p["bentuk_asesmen"] = new_bentuk_asesmen
                        p["indikator"] = new_indikator
                        p["bloom"] = new_bloom
                        p["bentuk"] = new_bentuk
                        # ...DAN ke key widget-nya langsung: widget dengan `key` tetap akan
                        # selalu memakai nilai dari session_state[key], bukan argumen `value=`
                        # yang kita berikan, begitu key tersebut pernah dibuat. Tanpa baris ini
                        # perubahan tidak akan pernah muncul di kotak teksnya.
                        st.session_state[mk_key(f"prt_materi_{m}")] = new_materi
                        st.session_state[mk_key(f"prt_bentuk_asesmen_{m}")] = new_bentuk_asesmen
                        st.session_state[mk_key(f"prt_indikator_{m}")] = new_indikator
                        st.session_state[mk_key(f"prt_bloom_{m}")] = new_bloom
                        st.session_state[mk_key(f"prt_bentuk_{m}")] = new_bentuk
                        del st.session_state[mk_key(f"ai_suggestion_{m}")]
                        st.rerun()
                    if cb.button("✖ Abaikan", key=mk_key(f"ai_dismiss_{m}")):
                        del st.session_state[mk_key(f"ai_suggestion_{m}")]
                        st.rerun()

            p["bloom"] = st.multiselect(
                "Bloom's Taxonomy Level", BLOOM_LEVELS, default=p["bloom"], key=mk_key(f"prt_bloom_{m}"),
                help=info_tooltip(BLOOM_INFO),
            )
            p["materi"] = st.text_area("Materi Pembelajaran", p["materi"], key=mk_key(f"prt_materi_{m}"))
            c3, c4 = st.columns(2)
            p["metode"] = c3.multiselect(
                "Metode Pembelajaran", METODE_OPTIONS, default=p["metode"], key=mk_key(f"prt_metode_{m}"),
                help=info_tooltip(METODE_INFO),
            )
            p["bentuk"] = c4.multiselect(
                "Bentuk Pembelajaran Online", BENTUK_OPTIONS, default=p["bentuk"], key=mk_key(f"prt_bentuk_{m}"),
                help=info_tooltip(BENTUK_INFO),
            )
            c5, c6 = st.columns(2)
            p["bentuk_asesmen"] = c5.text_area(
                "Bentuk Asesmen Penilaian", p["bentuk_asesmen"], key=mk_key(f"prt_bentuk_asesmen_{m}"),
                help="Mis. kuis pilihan ganda, tugas individu, presentasi kelompok.",
            )
            p["indikator"] = c6.text_area("Indikator Penilaian", p["indikator"], key=mk_key(f"prt_indikator_{m}"))

    st.divider()
    simpan_progres_button("pertemuan_bawah", primary=True)

# --- Tab: Daftar Pustaka ---
with tab_ref:
    simpan_progres_button("daftar_pustaka")
    st.divider()
    st.subheader("Level Penggunaan AI")
    st.caption("Opsional, boleh dikosongkan - tidak menghalangi pengajuan ke Kaprodi.")
    info = st.session_state.info_umum
    pilihan_ai = ["(belum dipilih)", "Tanpa AI", "Assisted AI", "Free AI"]
    current_ai = info.get("level_ai") or "(belum dipilih)"
    level_ai_pilih = st.selectbox(
        "Level Penggunaan AI", pilihan_ai,
        index=pilihan_ai.index(current_ai) if current_ai in pilihan_ai else 0,
        key=mk_key("level_ai"),
    )
    info["level_ai"] = "" if level_ai_pilih == "(belum dipilih)" else level_ai_pilih
    info["deskripsi_ai"] = st.text_area(
        "Deskripsi Penggunaan AI", info.get("deskripsi_ai", ""), key=mk_key("deskripsi_ai"),
        help="Jelaskan bagaimana/di bagian mana AI dipakai (atau kenapa tidak dipakai) dalam penyusunan RPS/pembelajaran ini.",
    )

    st.divider()
    st.subheader("Daftar Pustaka")
    st.caption("Tautan materi/buku jika tersedia online.")
    for idx, ref in enumerate(st.session_state.referensi_data):
        c1, c2 = st.columns([6, 1])
        ref["sitasi"] = c1.text_input(f"Pustaka #{idx + 1}", ref["sitasi"], key=mk_key(f"ref_{idx}"))
        if c2.button("Hapus", key=mk_key(f"ref_del_{idx}")):
            st.session_state.referensi_data.pop(idx)
            st.rerun()
    if st.button("➕ Tambah Pustaka", key=mk_key("tambah_referensi")):
        st.session_state.referensi_data.append({"sitasi": ""})
        st.rerun()

# --- Tab: Komponen Penilaian (bagi persentase tiap kategori ke 5 CPMK) ---
with tab_nilai:
    simpan_progres_button("komponen_nilai")
    st.divider()
    st.subheader("Komponen Penilaian")
    st.caption(
        "Untuk tiap komponen, bagi persentase bobotnya ke CPMK yang dinilai lewat "
        "komponen tsb. **Total tiap komponen (dijumlah dari 5 CPMK) harus PAS sama "
        "dengan bobotnya** - tidak boleh lebih atau kurang. CPMK yang tidak dinilai "
        "lewat komponen tertentu, biarkan 0."
    )

    for kategori in KATEGORI_PENILAIAN:
        target = BOBOT_KATEGORI.get(kategori, 0)
        st.markdown(f"**{kategori}** — bobot total {target}%")
        cols = st.columns(5)
        total_kategori = 0
        for i in range(1, 6):
            row = st.session_state.komponen_data.setdefault(i, {kat: 0 for kat in KATEGORI_PENILAIAN})
            with cols[i - 1]:
                nilai = st.number_input(
                    f"CPMK-{i}", min_value=0, max_value=100, value=int(row.get(kategori, 0)),
                    step=5, key=mk_key(f"komp_{kategori}_{i}"),
                )
            row[kategori] = nilai
            total_kategori += nilai

        selisih = target - total_kategori
        if selisih == 0:
            st.success(f"Total: {total_kategori}% dari {target}% ✅")
        elif selisih > 0:
            st.warning(f"Total: {total_kategori}% dari {target}% (kurang {selisih}%)")
        else:
            st.error(f"Total: {total_kategori}% dari {target}% (kelebihan {abs(selisih)}%)")
        st.divider()

    st.markdown("**Bobot Komponen Penilaian (baku):**")
    cols = st.columns(4)
    for idx, (k, v) in enumerate(BOBOT_KATEGORI.items()):
        cols[idx].metric(k, f"{v}%")

# --- Tab: Preview dan Ajukan ---
with tab_export:
    st.subheader("Preview")
    ready = len(st.session_state.cpl_selected) == N_CPL_WAJIB
    if not ready:
        st.info("Lengkapi pemilihan 5 CPL di tab 'CPL & CPMK' terlebih dahulu untuk mengaktifkan pengajuan.")
    else:
        st.markdown(f"### {mk_row['Nama Mata Kuliah']} ({mk_row['Kode MK']})")
        st.write(f"**Prodi:** {st.session_state.prodi_sel} · **SKS:** {mk_row['SKS']} · **Semester:** {mk_row['Semester']}")
        st.dataframe(pd.DataFrame([
            {"CPMK": f"CPMK-{i}",
             "Deskripsi (dengan kode CPL)": with_code(
                 st.session_state.cpmk_data[i]["deskripsi"], st.session_state.cpmk_data[i]["cpl_kode"])[:100]}
            for i in range(1, 6)
        ]), use_container_width=True, hide_index=True)

        st.caption(
            "ℹ️ Dokumen Word/PDF resminya baru bisa diunduh setelah RPS ini divalidasi "
            "BPM, dari halaman **RPS Tervalidasi**. Preview di atas hanya untuk "
            "memeriksa data sebelum diajukan."
        )

        st.divider()
        st.subheader("Ajukan ke Kaprodi")

        if not bisa_edit:
            st.info(
                f"RPS ini berstatus **{status_label.get(status_saat_ini, status_saat_ini)}** - "
                "sudah diajukan/diproses, tidak perlu diajukan ulang."
            )
        elif not st.session_state.get("_rps_id"):
            st.info("Simpan RPS ke database terlebih dahulu (tombol di sidebar) sebelum bisa diajukan.")
        elif st.session_state.get("_confirm_ajukan"):
            st.warning(
                "⚠️ **Pastikan kembali sebelum mengajukan:** cek semua isian (Info Umum, "
                "CPL & CPMK, 16 Pertemuan, Daftar Pustaka, Komponen Penilaian) sudah benar "
                "dan lengkap. Setelah diajukan, RPS akan **terkunci** dan tidak bisa diedit "
                "lagi sampai Kaprodi selesai mereview."
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    "✅ Ya, Ajukan Sekarang", key="konfirmasi_ajukan_btn",
                    use_container_width=True, type="primary",
                ):
                    issues = get_komponen_issues()
                    if issues:
                        st.error(
                            "Belum bisa diajukan - persentase Komponen Penilaian belum pas "
                            "(cek tab 'Komponen Penilaian'):\n"
                            + "\n".join(f"- {msg}" for msg in issues)
                        )
                    else:
                        try:
                            ajukan_rps(client, st.session_state["_rps_id"])
                            st.session_state["_rps_status"] = "diajukan"
                            st.session_state["_rps_catatan"] = None
                            st.session_state["_rps_catatan_bpm"] = None
                            st.session_state["_rps_diajukan_pada"] = datetime.now().isoformat()
                            st.session_state["_confirm_ajukan"] = False
                            st.success("RPS diajukan ke Kaprodi untuk direview.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal mengajukan: {e}")
            with c2:
                if st.button("❌ Batal", key="batal_ajukan_btn", use_container_width=True):
                    st.session_state["_confirm_ajukan"] = False
                    st.rerun()
        else:
            if st.button(
                "📤 Ajukan ke Kaprodi", key="ajukan_btn",
                use_container_width=True, type="primary",
            ):
                st.session_state["_confirm_ajukan"] = True
                st.rerun()