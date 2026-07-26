# RPS Builder — Prototype Streamlit

Aplikasi input RPS (Rencana Pembelajaran Semester) untuk Dosen UNSIA.
Alur: pilih Program Studi → pilih Mata Kuliah → pilih 5 CPL → isi CPMK, Sub-CPMK
per pertemuan, 16 pertemuan, referensi, komponen penilaian → ekspor ke Excel & PDF
(format mengikuti layout RPS resmi UNSIA, lengkap dengan Catatan, Rubrik Penilaian,
dan blok validasi).

## Cara menjalankan di komputer sendiri

1. Pastikan Python 3.9+ sudah terpasang.
2. Buka terminal di folder ini, lalu jalankan:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

3. Browser akan terbuka otomatis ke `http://localhost:8501`. Kalau tidak, buka manual.
4. Untuk berhenti: tekan `Ctrl+C` di terminal.

## Menyiapkan Asisten AI (opsional)

Aplikasi bisa memakai Google Gemini untuk menyarankan draf materi/tugas per pertemuan.

- **Pakai API key sendiri**: pilih "API Key Sendiri" di sidebar aplikasi, tempel API key
  di situ (hanya dipakai untuk sesi berjalan, tidak disimpan ke mana pun).
- **Sediakan API key default untuk semua Dosen** (opsional): salin
  `config/gemini_default.txt.example` menjadi `config/gemini_default.txt`, lalu isi
  `GEMINI_API_KEY=` dengan key asli. File `gemini_default.txt` (bukan yang `.example`)
  sudah masuk `.gitignore` — **tidak akan ikut ter-commit ke git**, supaya key tidak
  bocor kalau repo di-push ke GitHub (apalagi kalau publik).

## Cara deploy gratis ke internet (Streamlit Community Cloud)

Kalau ingin dipakai tanpa install apa pun di komputer (mis. diakses Dosen lain lewat link):

1. Push folder ini ke GitHub (lihat bagian "Push ke GitHub" di bawah).
2. Buka [share.streamlit.io](https://share.streamlit.io) → login dengan akun GitHub.
3. Klik **New app** → pilih repository tadi → `app.py` sebagai entry point → Deploy.
4. Setelah beberapa menit, akan muncul link publik (mis. `namaapp.streamlit.app`) yang bisa
   dibagikan ke Dosen lain.
5. Kalau memakai API key default: **jangan** andalkan `config/gemini_default.txt` di
   Streamlit Cloud (file itu tidak ikut ter-push). Pindahkan isinya ke menu
   **App settings → Secrets** di dashboard Streamlit Cloud sebagai gantinya.

Catatan: di versi gratis, siapa pun yang punya link bisa mengakses & mengisi form (belum ada
login/pembatasan akses per Dosen). Untuk kebutuhan itu, perlu penambahan modul autentikasi
terpisah (mis. `streamlit-authenticator`) — bisa dibahas lebih lanjut kalau sudah sampai tahap itu.

## Push ke GitHub

```bash
cd rps_streamlit
git init
git add .
git commit -m "Initial commit: RPS Builder"
git branch -M main
git remote add origin https://github.com/<username>/<nama-repo>.git
git push -u origin main
```

Ganti `<username>` dan `<nama-repo>` sesuai punya Bapak. Kalau repository di GitHub belum
dibuat, buat dulu lewat github.com → **New repository** (boleh kosong, tanpa README/gitignore
bawaan GitHub supaya tidak bentrok saat push pertama).

## Menambah Program Studi baru

Data master ada di folder `data/`. Setiap file `.xlsx` = 1 Program Studi, nama file = nama
Prodi yang akan tampil di aplikasi.

Format wajib di setiap file:
- Sheet **`Mata Kuliah`** dengan kolom: `No`, `Nama Mata Kuliah`, `Kode MK`, `SKS`, `Semester`,
  `Ranah Topik`, `Dosen Pengembang`
- Sheet **`CPL`** dengan kolom: `Kode CPL`, `Deskripsi CPL`

Untuk menambah Prodi baru: salin format ini ke file baru, mis. `data/Sistem Informasi PJJ S1.xlsx`,
lalu restart aplikasi (`streamlit run app.py` ulang) — Prodi baru akan otomatis muncul di dropdown,
tidak perlu ubah kode `app.py` sama sekali.

## Menyimpan progres

Karena Streamlit tidak menyimpan data secara permanen antar sesi, gunakan tombol
**"Unduh Progres (.xlsx)"** di sidebar untuk menyimpan pekerjaan yang sedang berjalan, dan
**"Muat Progres (.xlsx)"** untuk melanjutkannya lain waktu. Formatnya Excel biasa — bisa
dibuka & diperiksa manual kalau perlu.

## Struktur file

```
app.py                          -> aplikasi utama (UI, alur input, ekspor Excel, asisten AI)
pdf_export.py                   -> modul khusus pembuatan PDF (pakai reportlab)
requirements.txt                -> daftar library yang dibutuhkan
assets/logo_unsia.png           -> logo untuk header PDF
config/gemini_default.txt.example -> template API key default (aman di-commit)
config/gemini_default.txt       -> API key default asli (gitignored, dibuat sendiri secara lokal)
data/
  Informatika PJJ S1.xlsx       -> contoh data master (56 Mata Kuliah, 26 CPL)
```

## Batasan versi prototipe ini

- Belum ada login/multi-user — cocok dipakai 1 Dosen per sesi browser
- Data tidak tersimpan otomatis di server — pakai fitur Simpan/Muat Progres di atas
- Layout PDF/Excel sudah mengikuti struktur RPS resmi UNSIA (termasuk Catatan, Rubrik
  Penilaian, dan blok validasi), tapi blok tanda tangan belum memakai QR code asli —
  nama diisi manual, ruang kosong untuk tanda tangan fisik

