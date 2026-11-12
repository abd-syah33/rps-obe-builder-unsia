"""Uji layanan ekspor v2 (container rps-ekspor) terhadap docx_export.py v1.
Jalankan dari akar repo dengan venv berisi python-docx/pandas/reportlab/qrcode."""
import concurrent.futures as cf, io, json, os, sys, time, urllib.request, zipfile
sys.path.insert(0, os.getcwd())
import pandas as pd
from docx_export import BOBOT_KATEGORI, build_docx

URL, TOKEN = sys.argv[1], sys.argv[2]
teks = "Mahasiswa mampu menganalisis dan menerapkan konsep secara sistematis. " * 3
cpl = [{"kode": k, "deskripsi": teks} for k in ["S8", "P1", "P3", "KU5", "KK2"]]
data = {
    "prodi": "Informatika PJJ S1",
    "mk": {"Nama Mata Kuliah": "Pengantar Data Science", "Kode MK": "260402220", "SKS": 3, "Semester": 4},
    "cpl": cpl,
    "info_umum": {"tanggal_dokumen": "12 November 2026", "rumpun_mk": "Data Science", "dosen_pengampu": "Dosen A",
                  "deskripsi_mk": teks, "tanggal_disetujui": "13 November 2026", "tanggal_divalidasi": "14 November 2026",
                  "dosen_koordinator": "Dosen A", "nama_kaprodi": "Kaprodi", "nama_biro_pjm": "BPM",
                  "level_ai": "Assisted AI", "deskripsi_ai": teks},
    "cpmk_data": {str(i): {"cpl_kode": cpl[i - 1]["kode"], "deskripsi": teks} for i in range(1, 6)},
    "pertemuan_data": {str(m): {"sub_cpmk_desc": teks, "cpmk_ref": ["CPMK-1"], "bloom": ["C3"], "materi": teks,
                                "metode": ["SGD"], "bentuk": ["EL-1"], "bentuk_asesmen": "Kuis", "indikator": teks}
                       for m in range(1, 17)},
    "referensi_data": [{"sitasi": "Penulis (2024). Judul. Penerbit."}],
    "komponen_data": {str(i): {k: (v if i == 1 else 0) for k, v in BOBOT_KATEGORI.items()} for i in range(1, 6)},
}


def kirim(jalur, token=TOKEN, isi=data):
    req = urllib.request.Request(URL + jalur, data=json.dumps(isi).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def isi_dokumen(b):
    return zipfile.ZipFile(io.BytesIO(b)).read("word/document.xml")


lulus = []
def cek(nama, ok):
    lulus.append(ok); print(("LULUS " if ok else "GAGAL ") + nama)

st, b = kirim("/docx", token="salah")
cek("UAT-26 tanpa token yang benar ditolak 401", st == 401)

t = time.time(); st, b2 = kirim("/docx"); dt = time.time() - t
v1 = build_docx(prodi=data["prodi"], mk_row=data["mk"],
                cpl_df=pd.DataFrame({"Kode CPL": [c["kode"] for c in cpl], "Deskripsi CPL": [c["deskripsi"] for c in cpl]}),
                info_umum=data["info_umum"], cpmk_data={int(k): v for k, v in data["cpmk_data"].items()},
                pertemuan_data={int(k): v for k, v in data["pertemuan_data"].items()}, referensi_data=data["referensi_data"],
                komponen_data={int(k): v for k, v in data["komponen_data"].items()}, bobot_kategori=BOBOT_KATEGORI).getvalue()
cek(f"FR-E04 Word v2 identik dengan v1 (isi dokumen) [{dt:.2f} dtk]", st == 200 and isi_dokumen(b2) == isi_dokumen(v1))

t = time.time(); st, p = kirim("/pdf"); dt = time.time() - t
cek(f"PDF pertama jadi [{dt:.1f} dtk, {len(p)//1024} KB]", st == 200 and p[:4] == b"%PDF")
t = time.time(); st, p2 = kirim("/pdf"); dt2 = time.time() - t
cek(f"PDF kedua dari cache [{dt2:.2f} dtk]", st == 200 and p2 == p and dt2 < 1)

def pdf_beda(i):
    d = json.loads(json.dumps(data)); d["info_umum"]["dosen_pengampu"] = f"Dosen {i}"
    t = time.time(); s, x = kirim("/pdf", isi=d); return s, time.time() - t
t = time.time()
with cf.ThreadPoolExecutor(5) as ex:
    hasil = list(ex.map(pdf_beda, range(5)))
cek(f"UAT-25 5 PDF berbeda bersamaan semua selesai [total {time.time()-t:.1f} dtk, terlama {max(h[1] for h in hasil):.1f} dtk]",
    all(s == 200 for s, _ in hasil))
print(f"{sum(lulus)}/{len(lulus)} lulus")
