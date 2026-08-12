# RPS Builder - Prototype Streamlit

Aplikasi input RPS (Rencana Pembelajaran Semester) untuk Dosen UNSIA.
Alur: pilih Program Studi → pilih Mata Kuliah → pilih 5 CPL → isi CPMK, Sub-CPMK
per pertemuan, 16 pertemuan, referensi, komponen penilaian → ekspor ke **Word (.docx)** & PDF
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

Aplikasi bisa memakai Google Gemini untuk menyarankan draf materi/tugas/Bloom/Bentuk
Pembelajaran Online per pertemuan.

- **Pakai API key sendiri**: pilih "API Key Sendiri" di sidebar aplikasi, tempel API key
  di situ (hanya dipakai untuk sesi berjalan, tidak disimpan ke mana pun).
- **Sediakan API key default untuk semua Dosen** (opsional): salin
  `config/gemini_default.txt.example` menjadi `config/gemini_default.txt`, lalu isi
  `GEMINI_API_KEY=` dengan key asli. File `gemini_default.txt` (bukan yang `.example`)
  sudah masuk `.gitignore`, **tidak akan ikut ter-commit ke git**, supaya key tidak
  bocor kalau repo di-push ke GitHub (apalagi kalau publik).

## Mengisi nama pejabat untuk blok validasi (opsional, otomatis)

Beberapa nama di blok tanda tangan bisa terisi otomatis (tetap bisa diedit manual di
tab "Pratinjau & Ekspor"):

- **Dosen Koordinator** & **Koordinator Mata Kuliah**: otomatis dari kolom
  `Dosen Pengembang` di file data master Mata Kuliah (`data/<Prodi>.xlsx`).
- **Ketua Prodi** & **Kepala Biro Penjaminan Mutu**: otomatis dari `config/pejabat.txt`.
  Salin `config/pejabat.txt.example` menjadi `config/pejabat.txt`, lalu isi:
  - `KABIRO_PENJAMINAN_MUTU=`: satu nama untuk seluruh Prodi/universitas
  - `KAPRODI_<Nama Prodi>=`: satu baris per Prodi (nama setelah `KAPRODI_` harus
    persis sama dengan nama file di folder `data/`, tanpa `.xlsx`)

  File `pejabat.txt` (bukan `.example`) juga sudah masuk `.gitignore`.

## Cara deploy gratis ke internet (Streamlit Community Cloud)

Kalau ingin dipakai tanpa install apa pun di komputer (mis. diakses Dosen lain lewat link):

1. Push folder ini ke GitHub (lihat bagian "Push ke GitHub" di bawah).
2. Buka [share.streamlit.io](https://share.streamlit.io) → login dengan akun GitHub.
3. Klik **New app** → pilih repository tadi → `app.py` sebagai entry point → Deploy.
4. Setelah beberapa menit, akan muncul link publik (mis. `namaapp.streamlit.app`) yang bisa
   dibagikan ke Dosen lain.
5. Kalau memakai API key default / nama pejabat default: **jangan** andalkan file
   `config/gemini_default.txt` atau `config/pejabat.txt` di Streamlit Cloud (tidak ikut
   ter-push). Pindahkan isinya ke menu **App settings → Secrets** di dashboard Streamlit
   Cloud sebagai gantinya.

Catatan: di versi gratis, siapa pun yang punya link bisa mengakses & mengisi form (belum ada
login/pembatasan akses per Dosen). Untuk kebutuhan itu, perlu penambahan modul autentikasi
terpisah (mis. `streamlit-authenticator`); bisa dibahas lebih lanjut kalau sudah sampai tahap itu.

## Push ke GitHub

Kalau repository di GitHub belum pernah dibuat sama sekali:
```bash
cd rps_streamlit
git init
git add .
git commit -m "Initial commit: RPS Builder"
git branch -M main
git remote add origin https://github.com/<username>/<nama-repo>.git
git push -u origin main
```

Kalau repository sudah ada (mis. sudah pernah Bapak push sebelumnya) dan ini hanya
update file-file baru:
```bash
cd rps_streamlit
git add .
git commit -m "Update: DOCX export, asisten AI diperluas, auto-isi nama pejabat"
git push origin main
```

## Menambah Program Studi baru

Data master ada di folder `data/`. Setiap file `.xlsx` = 1 Program Studi, nama file = nama
Prodi yang akan tampil di aplikasi.

Format wajib di setiap file:
- Sheet **`Mata Kuliah`** dengan kolom: `No`, `Nama Mata Kuliah`, `Kode MK`, `SKS`, `Semester`,
  `Ranah Topik`, `Dosen Pengembang`
- Sheet **`CPL`** dengan kolom: `Kode CPL`, `Deskripsi CPL`

Untuk menambah Prodi baru: salin format ini ke file baru, mis. `data/Sistem Informasi PJJ S1.xlsx`,
lalu restart aplikasi (`streamlit run app.py` ulang); Prodi baru akan otomatis muncul di dropdown,
tidak perlu ubah kode `app.py` sama sekali. Jangan lupa tambahkan juga baris
`KAPRODI_Sistem Informasi PJJ S1=...` di `config/pejabat.txt` kalau mau nama Kaprodi-nya
ikut terisi otomatis.

## Menyimpan progres

Karena Streamlit tidak menyimpan data secara permanen antar sesi, gunakan tombol
**"Unduh Progres (.xlsx)"** di sidebar untuk menyimpan pekerjaan yang sedang berjalan, dan
**"Muat Progres (.xlsx)"** untuk melanjutkannya lain waktu. Formatnya Excel biasa, bisa
dibuka & diperiksa manual kalau perlu. (Ini terpisah dari hasil akhir RPS yang diekspor
dalam format Word/PDF.)

## Struktur file

```
app.py                             -> aplikasi utama (UI, alur input, ekspor Word, asisten AI)
pdf_export.py                      -> modul khusus pembuatan PDF (pakai reportlab)
docx_export.py                     -> modul khusus pembuatan Word/.docx (pakai python-docx)
requirements.txt                   -> daftar library yang dibutuhkan
assets/logo_unsia.png              -> logo untuk header PDF/Word
config/gemini_default.txt.example  -> template API key default (aman di-commit)
config/gemini_default.txt          -> API key default asli (gitignored, dibuat sendiri secara lokal)
config/pejabat.txt.example         -> template nama Kaprodi/Biro PJM (aman di-commit)
config/pejabat.txt                 -> nama asli (gitignored, dibuat sendiri secara lokal)
data/
  Informatika PJJ S1.xlsx          -> contoh data master (56 Mata Kuliah, 26 CPL)
```

## Batasan versi prototipe ini

- Belum ada login/multi-user, cocok dipakai 1 Dosen per sesi browser
- Data tidak tersimpan otomatis di server, pakai fitur Simpan/Muat Progres di atas
- Layout PDF/Word sudah mengikuti struktur RPS resmi UNSIA (termasuk Catatan, Rubrik
  Penilaian, dan blok validasi), tapi blok tanda tangan belum memakai QR code asli;
  nama diisi otomatis/manual, ruang kosong untuk tanda tangan fisik

