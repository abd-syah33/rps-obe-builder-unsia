# RPS Builder - Prototype Streamlit

Aplikasi input RPS (Rencana Pembelajaran Semester) untuk Dosen UNSIA.
Alur: pilih Program Studi → pilih Mata Kuliah → pilih 5 CPL → isi CPMK, Sub-CPMK
per pertemuan, 16 pertemuan, Daftar Pustaka, Komponen Penilaian → ekspor ke
**Word (.docx)** & PDF.

Hasil Word dibuat dengan **mengisi langsung file template resmi UNSIA**
(`assets/rps_template.docx`), bukan membangun ulang tabel dari kode - jadi warna,
font, border, dan tata letaknya dijamin sama persis dengan format resmi, karena
memang file yang sama, hanya diisi teksnya. PDF dibuat dengan mengonversi Word
yang sudah terisi itu (lewat LibreOffice), supaya Word dan PDF selalu identik.

## Cara menjalankan di komputer sendiri

1. Pastikan Python 3.9+ sudah terpasang.
2. Buka terminal di folder ini, lalu jalankan:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

3. Browser akan terbuka otomatis ke `http://localhost:8501`. Kalau tidak, buka manual.
4. Untuk berhenti: tekan `Ctrl+C` di terminal.

## Menyiapkan LibreOffice (dibutuhkan untuk unduh PDF)

Word (.docx) bisa langsung diunduh tanpa syarat tambahan. Untuk **PDF**, aplikasi
mengonversi file Word yang sudah terisi lewat LibreOffice, supaya PDF-nya dijamin
identik dengan Word-nya (bukan dibuat lewat jalur kode terpisah yang bisa melenceng).

1. Unduh gratis dari [libreoffice.org/download](https://www.libreoffice.org/download/download/)
2. Install seperti biasa (Next-Next-Finish, pengaturan default sudah cukup)
3. Restart komputer setelah install, supaya bisa terbaca aplikasi lain
4. Cek berhasil dengan buka Command Prompt/PowerShell, ketik `soffice --version`

Kalau LibreOffice belum terpasang, aplikasi tetap berjalan normal - hanya tombol
"Unduh PDF" yang akan menampilkan pesan pengingat untuk memasangnya dulu.

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

Beberapa nama bisa terisi otomatis (tetap bisa diedit manual di tab "Info Umum" /
"Pratinjau & Ekspor"):

- **Dosen Pengembang RPS** & **Koordinator Mata Kuliah**: otomatis dari kolom
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
6. Supaya tombol "Unduh PDF" berfungsi di Streamlit Cloud, tambahkan file `packages.txt`
   (isi satu baris: `libreoffice`) di folder ini sebelum push - Streamlit Cloud akan
   otomatis memasang LibreOffice di servernya lewat file itu.

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
app.py                             -> aplikasi utama (UI, alur input, asisten AI)
docx_export.py                     -> mengisi assets/rps_template.docx & konversi ke PDF lewat LibreOffice
pdf_export.py                      -> fungsi bantu bersama (QR code, format kode CPL/CPMK)
requirements.txt                   -> daftar library Python yang dibutuhkan
packages.txt                       -> system package untuk Streamlit Cloud (LibreOffice)
assets/rps_template.docx           -> TEMPLATE RESMI UNSIA asli - sumber format Word & PDF, jangan diubah manual
assets/logo_unsia.png              -> logo cadangan (tidak dipakai saat ini - logo asli sudah ada di dalam template)
config/gemini_default.txt.example  -> template API key default (aman di-commit)
config/gemini_default.txt          -> API key default asli (gitignored, dibuat sendiri secara lokal)
config/pejabat.txt.example         -> template nama Kaprodi/Biro PJM (aman di-commit)
config/pejabat.txt                 -> nama asli (gitignored, dibuat sendiri secara lokal)
data/
  Informatika PJJ S1.xlsx          -> contoh data master (56 Mata Kuliah, 26 CPL)
```

**Kalau format resmi UNSIA berubah lagi di kemudian hari**: cukup ganti isi
`assets/rps_template.docx` dengan versi terbaru (jaga nama file & struktur tabelnya
tetap sama), tidak perlu bongkar kode `docx_export.py` dari awal - asalkan posisi
baris/kolom yang diisi (identitas, CPL, CPMK, 16 pertemuan) tidak berubah drastis.
Kalau strukturnya berubah signifikan, kirim saja file barunya untuk dipetakan ulang.

## Batasan versi prototipe ini

- Belum ada login/multi-user, cocok dipakai 1 Dosen per sesi browser
- Data tidak tersimpan otomatis di server, pakai fitur Simpan/Muat Progres di atas
- Unduh PDF butuh LibreOffice terpasang (lihat bagian di atas). Word (.docx) selalu
  bisa diunduh tanpa syarat tambahan
- Word/PDF dibuat dengan mengisi `assets/rps_template.docx` langsung, sehingga
  strukturnya sama persis dengan template resmi - termasuk detail yang mungkin
  terlihat seperti "kekurangan" di template aslinya tapi sengaja tidak diubah,
  misalnya: tabel 16 Pertemuan di file resmi tidak punya baris khusus untuk minggu
  ke-8 (langsung loncat dari minggu 7 ke minggu 9), meski teks lain menyebut UTS
  dilaksanakan di minggu ke-8. Ini bukan bug aplikasi - itu memang begitu di file
  resminya, dan sengaja tidak "diperbaiki" supaya formatnya tidak berubah dari yang
  Bapak unggah. Kalau Bapak mau baris minggu 8 ditambahkan, tinggal minta
- Kolom Kriteria Penilaian, Referensi, dan Bobot per pertemuan yang ada di versi
  sebelumnya sudah dihapus dari form input karena tidak ada di template resmi ini
- Tiap kolom tanda tangan sudah punya QR code berisi teks info dokumen (ID MK, nama
  penanda tangan, tanggal) yang langsung terbaca saat di-scan. QR ini sifatnya
  informasional saja, bukan tanda tangan digital/verifikasi keaslian dokumen (tidak
  ada enkripsi di baliknya). Bagian ini tidak ada di template resmi, ditambahkan di
  akhir dokumen sebagai tambahan sesuai permintaan

## Status pengembangan: menuju multi-user dengan database (Supabase)

Aplikasi ini sedang dikembangkan bertahap dari prototipe single-user (session
Streamlit + file Excel) menuju aplikasi multi-user dengan database sungguhan.
Rencana lengkap ada di `RPS_Builder_Rencana_Pengembangan.md`.

**Fase 1 - Fondasi (sudah dikerjakan di sini):**
- `sql/schema.sql` - skema database (tabel `prodi`, `mata_kuliah`, `cpl`, `rps`)
- `config/supabase.txt.example` - template kredensial (salin jadi `config/supabase.txt`, isi, jangan commit)
- `supabase_config.py` - helper baca kredensial dari `config/supabase.txt`
- `scripts/test_supabase_connection.py` - verifikasi project & skema sudah siap

Cara menjalankan Fase 1:
1. Buat project gratis di [supabase.com](https://supabase.com)
2. Buka **SQL Editor** di dashboard project, jalankan seluruh isi `sql/schema.sql`
3. Salin `config/supabase.txt.example` -> `config/supabase.txt`, isi `SUPABASE_URL`
   dan `SUPABASE_ANON_KEY` dari **Project Settings -> Data API**
4. `pip install supabase`, lalu `python scripts/test_supabase_connection.py` untuk
   memastikan semua tabel sudah bisa diakses

Login/peran (Dosen/Kaprodi/Admin), migrasi data Excel ke tabel, dan penyimpanan
RPS otomatis ke database (menggantikan tombol Unduh/Muat Progres) menyusul di
Fase 2-4.

**Fase 2 - Login & Peran (sudah dikerjakan di sini):**
- `auth.py` - form Masuk/Daftar, gerbang login, badge peran + tombol Logout di sidebar
- `sql/schema.sql` bagian "FASE 2" - tabel `pengguna`, trigger auto-provision role
  `dosen` saat Daftar, RLS aktif di semua tabel
- `scripts/test_fase2_auth.py` - verifikasi login, role, dan RLS bekerja

Setelah Daftar lewat aplikasi, jadikan akun pertama sebagai admin lewat SQL Editor:
```sql
update public.pengguna set role = 'admin' where email = 'email_anda@...';
```

**Fase 3 - Migrasi Data Master (sudah dikerjakan di sini):**
- `db_master.py` - baca/tulis Prodi, Mata Kuliah, CPL dari Supabase (menggantikan
  file Excel di `data/` sebagai sumber yang dipakai aplikasi saat berjalan)
- `admin_panel.py` - Panel Admin sederhana di dalam aplikasi: tambah Prodi, edit
  tabel Mata Kuliah & CPL langsung (lewat `st.data_editor`, tambah baris = tombol **+**)
- `scripts/migrate_excel_to_db.py` - migrasi sekali jalan dari `data/*.xlsx` ke tabel
  database (aman dijalankan berulang, upsert berdasarkan Kode MK/Kode CPL)

Cara menjalankan Fase 3:
1. Jalankan `python scripts/migrate_excel_to_db.py` untuk memindahkan data Excel
   yang sudah ada ke database (butuh `SUPABASE_SERVICE_ROLE_KEY` di `config/supabase.txt`)
2. Login sebagai admin di aplikasi -> otomatis diarahkan ke Panel Admin untuk
   tambah/edit data master selanjutnya
3. Login sebagai Dosen -> dropdown Program Studi/Mata Kuliah/CPL di sidebar
   sekarang datanya dari database, bukan file Excel lagi

Catatan: Panel Admin sengaja hanya mendukung tambah & edit, belum hapus baris -
kalau perlu menghapus atau mengubah Kode MK/Kode CPL yang sudah ada, lakukan
lewat SQL Editor Supabase untuk saat ini.

**Fase 4 - Migrasi Penyimpanan RPS (sudah dikerjakan di sini):**
- `rps_store.py` - simpan/muat dokumen RPS ke/dari tabel `rps` (satu baris per
  kombinasi Dosen + Mata Kuliah, dijaga unik lewat index database)
- `rps_saya.py` - halaman **📋 RPS Saya**: daftar semua RPS milik Dosen yang
  login, dengan status dan riwayat perubahan
- `sql/schema.sql` bagian "FASE 4" - index unik untuk simpan, tabel
  `rps_riwayat` + trigger otomatis (snapshot tiap simpan, tanpa kode tambahan
  di aplikasi), RLS-nya
- `app.py` - tombol **💾 Simpan ke Database** jadi mekanisme utama (Excel
  jadi cadangan opsional di dalam expander); RPS otomatis dimuat ulang saat
  membuka kembali Mata Kuliah yang sama

Cara menjalankan Fase 4:
1. Jalankan lagi seluruh isi `sql/schema.sql` di SQL Editor (ada tambahan
   "FASE 4" di akhir - aman, tidak mengganggu data yang sudah ada)
2. Login sebagai Dosen, isi RPS seperti biasa, klik **💾 Simpan ke Database**
   di sidebar - coba tutup browser & buka lagi, isian akan otomatis termuat
   kembali saat memilih Mata Kuliah yang sama
3. Cek menu **📋 RPS Saya** di bagian atas halaman untuk melihat daftar RPS
   yang sudah tersimpan beserta status dan riwayat perubahannya

Approval Kaprodi (ubah status diajukan -> disetujui/ditolak) menyusul di
Fase 5, belum ada di versi ini - status RPS baru saja untuk sekarang.

**Fase 5 - Approval & Dashboard (sudah dikerjakan di sini):**
- `kaprodi_panel.py` - Panel Kaprodi: tinjau RPS berstatus "Diajukan" di Prodi
  yang diampu, Setujui atau Tolak (wajib isi catatan kalau menolak)
- `admin_panel.py` - tambah dashboard statistik RPS (jumlah per status, per
  Prodi) dan tab **👥 Pengguna** untuk assign role Kaprodi ke Prodi yang diampu
- `app.py` - tombol **📤 Ajukan ke Kaprodi** & **↩️ Tarik Pengajuan** di sidebar;
  isian RPS otomatis terkunci (tidak bisa "Simpan ke Database" lagi) selama
  berstatus Diajukan/Disetujui, sampai ditarik atau ditolak
- `sql/schema.sql` bagian "FASE 5" - kolom `catatan_kaprodi`/`diproses_oleh`/
  `diproses_pada`, dan 4 fungsi database (`ajukan_rps`, `tarik_pengajuan_rps`,
  `setujui_rps`, `tolak_rps`) yang memvalidasi otorisasinya sendiri, dipanggil
  lewat `client.rpc(...)` - bukan update tabel `rps` langsung

Cara menjalankan Fase 5:
1. Jalankan lagi seluruh isi `sql/schema.sql` di SQL Editor (ada tambahan
   "FASE 5" di akhir - aman, tidak mengganggu data yang sudah ada)
2. Login sebagai admin -> tab **👥 Pengguna** -> jadikan satu akun sebagai
   **Kaprodi** dan pilih Prodi yang diampu
3. Login sebagai Dosen, simpan sebuah RPS, klik **📤 Ajukan ke Kaprodi**
4. Login sebagai Kaprodi (akun yang tadi di-set) -> RPS itu akan muncul di
   Panel Kaprodi untuk disetujui/ditolak

Dengan ini, seluruh rencana pengembangan (Fase 1-5) sudah selesai
diimplementasikan.

## Penyesuaian pasca-Fase 5

Tiga penyesuaian berdasarkan pemakaian nyata:

**1. Profil nama bisa diedit** - setiap user bisa isi/ubah nama sendiri lewat
"✏️ Ubah Nama" di sidebar. Admin bisa edit nama siapa saja lewat tab Pengguna.

**2. Satu akun bisa jadi Kaprodi sekaligus Dosen** - menu sekarang gabungan:
Kaprodi/Admin tetap dapat "✏️ Isi RPS" & "📋 RPS Saya" yang sama seperti Dosen
biasa, PLUS menu tambahan untuk panel masing-masing. Kepemilikan RPS memang
sudah berbasis akun/penugasan sejak awal, bukan berbasis role, jadi ini murni
perbaikan tampilan (menu tidak lagi mengunci eksklusif ke satu panel).

**3. Koordinator Mata Kuliah - RPS jadi milik Mata Kuliah, bukan milik Dosen:**
- `mata_kuliah.koordinator_user_id` - Kaprodi (di prodinya) atau Admin
  menetapkan SATU Dosen sebagai koordinator per Mata Kuliah, lewat tab
  **🎓 Koordinator** (Panel Admin) atau bagian sejenis di Panel Kaprodi
- Mata Kuliah TANPA koordinator otomatis **terkunci** - tidak muncul di
  dropdown "Isi RPS" siapa pun sampai ditetapkan
- Satu Mata Kuliah = satu dokumen RPS (bukan lagi satu per Dosen). Kalau
  koordinator diganti, RPS yang sudah ada otomatis "pindah" ke koordinator
  baru - karena hak edit dicek dari `koordinator_user_id` saat itu juga,
  bukan dari siapa yang dulu membuat baris RPS-nya
- **Transparansi**: RPS berstatus **Disetujui** boleh dilihat & diunduh
  SEMUA Dosen (menu baru **📚 RPS Disetujui**), lintas Prodi. Draft/diajukan/
  ditolak tetap privat (hanya koordinator/Kaprodi/Admin yang bersangkutan)

**PENTING - migrasi ini mengunci ulang semua Mata Kuliah yang sudah ada:**
setelah menjalankan skema terbaru, SEMUA Mata Kuliah yang sudah ada akan
kehilangan akses Dosen (koordinator belum ditetapkan) sampai Kaprodi/Admin
menetapkan koordinatornya lewat tab **🎓 Koordinator**. Ini konsekuensi yang
disengaja (bukan bug) - sesuai keputusan bahwa Mata Kuliah tanpa koordinator
harus terkunci total.

Sebelum menjalankan bagian skema ini, WAJIB jalankan dulu query pengecekan
data ganda (ada di komentar paling atas bagian ini di `sql/schema.sql`) -
kalau ada Mata Kuliah yang sudah kadung punya RPS dari lebih dari satu Dosen
(dari sebelum aturan koordinator ini berlaku), unique index barunya akan
gagal dibuat sampai duplikatnya diberesi manual dulu.

## Penyesuaian lanjutan: Kaprodi kelola kurikulum, Kode MK unik se-institusi

- **Kaprodi bisa ikut mengedit kurikulum** (Mata Kuliah & CPL) di Prodi yang
  diampu sendiri, lewat Panel Kaprodi (tab "📚 Mata Kuliah" & "🎯 CPL") - fitur
  yang sama seperti Panel Admin, cuma dikunci ke satu Prodi. Logikanya
  ditaruh di `kurikulum_ui.py` supaya dipakai bersama Admin & Kaprodi, tidak
  ditulis dua kali.
- **Kolom `no_urut`** ("No" di Excel lama) **dihapus** - urutan Mata Kuliah
  sekarang selalu berdasarkan Kode MK, dan dropdown "Isi RPS" menampilkan
  format "Kode - Nama" (Kode MK didahulukan).
- **Kode MK sekarang unik SE-INSTITUSI.** Riwayat keputusan: sempat dicoba
  unik se-institusi -> ternyata bentrok dengan Mata Kuliah Umum yang memang
  sengaja dipakai lintas Prodi (mis. Pancasila, Bahasa Indonesia) -> sempat
  dibalik ke unik per Prodi -> solusi final: **Mata Kuliah Umum dikonsolidasi
  ke satu Prodi baru "Mata Kuliah Umum"** (`sql/migrate_mata_kuliah_umum.sql`,
  migrasi sekali jalan) - dengan begitu Kode MK bisa unik se-institusi lagi
  TANPA kehilangan data. Koordinator & RPS untuk Mata Kuliah Umum dikelola di
  bawah Prodi baru ini, oleh siapa pun yang ditetapkan sebagai Kaprodi-nya
  (ditetapkan manual lewat Panel Admin -> tab Pengguna, belum otomatis).

**Urutan menjalankan (PENTING, harus berurutan):**
1. `sql/migrate_mata_kuliah_umum.sql` - migrasi sekali jalan, konsolidasi
   Mata Kuliah Umum ke Prodi baru
2. `sql/schema.sql` (seluruh isinya) - baru setelah migrasi di atas berhasil,
   supaya index unik se-institusi tidak gagal dibuat

## Kurikulum ganda (2021 & 2026 berdampingan) - Opsi A, SUDAH dikerjakan

Sebelumnya ditahan karena kompleksitasnya, sekarang sudah diimplementasikan
(Opsi A dari dua opsi yang dibahas sebelumnya): setiap Mata Kuliah & CPL
sekarang punya kolom `tahun_kurikulum`. Data yang sudah ada di database
otomatis dianggap kurikulum **2021** (backfill otomatis saat `sql/schema.sql`
dijalankan).

- **Kode MK unik per (Kode MK, Tahun Kurikulum)** - bukan lagi unik mutlak
  se-institusi. Kode yang sama BOLEH dipakai lagi di tahun kurikulum lain -
  dianggap versi revisi Mata Kuliah tsb, baris database yang sepenuhnya
  terpisah (bisa beda SKS/semester/koordinator/RPS).
- **CPL unik per (Prodi, Kode CPL, Tahun Kurikulum)**.
- **UI**: dropdown "Isi RPS" di sidebar sekarang punya selector **Tahun
  Kurikulum** (setelah Program Studi, sebelum Mata Kuliah). Panel Admin &
  Kaprodi juga dapat selector yang sama, berlaku untuk tab Mata Kuliah,
  Koordinator, dan CPL sekaligus.
- **`scripts/migrate_excel_to_db.py`** sekarang menerima `--tahun` (default
  2021) dan `--data-dir`, jadi bisa dipakai lagi nanti untuk mengimpor Excel
  kurikulum 2026 begitu datanya siap:
  ```
  python scripts/migrate_excel_to_db.py --tahun 2026 --data-dir data_2026
  ```
- Tahun yang selalu ditawarkan di dropdown (walau belum ada isinya sama
  sekali): 2021 dan 2026 (`DEFAULT_TAHUN_OPTIONS` di `db_master.py` - tambah
  baris di situ kalau nanti perlu tahun lain, mis. 2031).

## Catatan lain

- **Kaprodi Prodi "Mata Kuliah Umum"** belum ditetapkan - ditentukan
  kemudian oleh Bapak Abdullah, lewat Panel Admin -> tab Pengguna kapan pun
  siap.
- **Kaprodi memang diperbolehkan menyetujui RPS miliknya sendiri** (kalau dia
  juga koordinator suatu Mata Kuliah) - dikonfirmasi ini perilaku yang
  diinginkan, tidak ada pembatasan tambahan yang diterapkan.

## Pra-pendaftaran Dosen (whitelist NIP) - persiapan sebelum demo

Supaya puluhan Dosen bisa langsung praktek sebagai koordinator saat demo,
tanpa Admin harus menetapkan ulang satu-satu setelah semua orang Daftar:

- **Panel Admin -> tab "📋 Pra-daftar"**: input NIP + Nama semua Dosen yang
  akan demo (bisa tempel langsung dari Excel dua kolom). Kolom Status
  menunjukkan siapa yang sudah Daftar dan siapa yang masih menunggu.
- **Tab "🎓 Koordinator"** (Admin & Kaprodi) sekarang juga menawarkan Dosen
  yang **belum py akun** (dari daftar pra-pendaftaran) sebagai pilihan
  koordinator, ditandai "(NIP ..., belum Daftar)".
- **Form Daftar** sekarang wajib isi **NIP**. Kalau NIP tidak ada di daftar
  pra-pendaftaran, Daftar ditolak dengan pesan jelas. Kalau cocok, nama
  otomatis terisi dari data pra-pendaftaran, DAN semua Mata Kuliah yang
  sudah ditetapkan koordinatornya atas nama NIP itu otomatis "tersambung" ke
  akun barunya - tidak perlu Admin menetapkan ulang.

**Cara pakai untuk persiapan demo:**
1. Sebelum hari-H: isi tab "📋 Pra-daftar" dengan NIP+Nama semua peserta
2. Tetapkan koordinator per Mata Kuliah lewat tab "🎓 Koordinator" - pilih
   dari daftar "(NIP ..., belum Daftar)" untuk yang belum py akun
3. Saat demo: setiap orang Daftar dengan NIP masing-masing - otomatis
   langsung jadi koordinator Mata Kuliah yang sudah ditetapkan, siap praktek

## Update Template RPS (menyesuaikan `assets/rps_template.docx` versi baru)

Template resmi UNSIA diperbarui, dengan beberapa perubahan struktur dan alur:

- **Mata Kuliah Syarat & Prasyarat dihapus** - field `mk_prasyarat`/
  `prasyarat_untuk_mk` sudah tidak ada di form maupun dokumen.
- **QR pindah ke awal dokumen** - QR Koordinator & QR Kaprodi sekarang ada di
  blok identitas Mata Kuliah (dekat baris Kode/Rumpun/SKS), BUKAN lagi di
  blok "Validasi Dokumen" terpisah di akhir dokumen (blok itu, beserta fungsi
  `append_signature_block()`, sudah dihapus total dari `docx_export.py` -
  template resmi sekarang sudah punya tempatnya sendiri).
- **Tanggal Penyusunan otomatis** - mengikuti kapan RPS **diajukan** ke
  Kaprodi (kolom baru `rps.diajukan_pada`, diisi `ajukan_rps()`, dikosongkan
  `tarik_pengajuan_rps()`). Kalau RPS belum pernah diajukan, tampil
  "(belum diajukan)". Tidak bisa diedit manual lagi.
- **Dosen Pengampu di dokumen = akun yang sedang mengunduh** - dihitung
  ulang setiap kali dokumen di-generate (di tab Pratinjau & Ekspor, maupun
  saat mengunduh dari menu "RPS Disetujui"), TIDAK disimpan permanen di data
  RPS. Field manual "Dosen Pengampu" di tab Info Umum sudah dihapus.
- **Mapping CPMK ke Komponen Penilaian jadi checklist** - `komponen_data`
  sekarang berisi LIST kategori per CPMK (satu CPMK boleh masuk lebih dari
  satu kategori), bukan satu nilai tunggal lagi. RPS lama yang tersimpan
  dengan format nilai tunggal otomatis dibungkus jadi list saat dibuka
  (kompatibel mundur, tidak ada data yang hilang).
- **Baris "Bobot Nilai" baru** - persentase komponen penilaian sekarang ikut
  tercetak ke dokumen (template lama tidak punya baris ini sama sekali).
- **Minggu 8 (UTS) & 16 (UAS)** - template baru tidak lagi melompati minggu
  8. Kedua minggu ini auto-terisi teks starting default ("Ujian Tengah
  Semester (UTS)"/"Ujian Akhir Semester (UAS)") di `default_pertemuan()`,
  boleh diedit/ditambah cakupan materinya, dan ditandai badge 🔴 di form
  supaya jelas beda dari minggu reguler.

**Sudah diuji**: dokumen contoh sudah di-generate & dirender ke gambar untuk
diperiksa langsung - semua bagian di atas tampil benar, tidak ada blok sisa
di akhir dokumen, dan seluruh isi lain (tabel referensi EL, rubrik
penilaian, dsb.) tidak berubah sama sekali dari template asli.


## NIP & Prodi Homebase jadi atribut permanen semua pengguna

Sebelumnya NIP cuma dipakai untuk validasi whitelist saat Daftar, dan
`prodi_id` cuma dipakai untuk Kaprodi ("prodi yang diampu"). Sekarang:

- **Setiap pengguna** (Dosen, Kaprodi, Admin) bisa punya **NIP** (unik kalau
  diisi) dan **Prodi Homebase** - dikelola lewat Panel Admin -> tab
  **"👥 Pengguna"**, sekarang berbentuk tabel yang **bisa ditempel dari Excel**
  (klik sel "Nama" paling atas, lalu Ctrl+V), bukan lagi satu-per-satu.
- **Untuk Dosen**, Prodi Homebase MURNI jadi Prodi default yang tampil duluan
  di menu "Isi RPS" saat login - **tidak membatasi** akses. Dosen tetap bebas
  memilih Prodi lain, dan tetap bisa jadi koordinator/mengisi RPS di Prodi
  mana pun yang ditetapkan Kaprodi/Admin.
- **Untuk Kaprodi**, kolom yang sama masih berfungsi sebagai "Prodi yang
  diampu" (batasan wewenang, RLS `is_kaprodi_of()`) - tidak ada perubahan
  perilaku di sisi ini.
- **Tab "📋 Pra-daftar"** sekarang juga punya kolom **Prodi Homebase** (diisi
  sebagai nama Prodi, mis. "Informatika PJJ S1") - begitu orang dengan NIP
  yang cocok Daftar, Nama DAN Prodi Homebase-nya otomatis tersalin ke akun
  barunya sekaligus (lewat trigger `handle_new_user()`).
- Nama Prodi yang salah ketik/tidak dikenali TIDAK menggagalkan penyimpanan
  baris lainnya - cuma kolom Prodi Homebase baris itu yang dilewati, dengan
  peringatan jelas menyebutkan baris mana yang bermasalah.

**Bulk data secara umum**: semua tabel kelola data di Panel Admin/Kaprodi
(Mata Kuliah, CPL, Pengguna, Pra-daftar) memakai `st.data_editor` yang
mendukung tempel langsung dari Excel - klik sel pertama tujuan, Ctrl+V,
asal jumlah & urutan kolom yang ditempel cocok dengan kolom di tabel.

## Lupa Password (aktif) & Login Persisten (dibatalkan)

**Lupa Password** - SUDAH BERHASIL diuji langsung oleh pengguna. Pakai kode
6 digit lewat email (BUKAN link) - supaya tidak perlu menangani redirect/
URL-fragment dari email link yang secara teknis sulit ditangkap balik oleh
aplikasi Streamlit. Alurnya: masuk email di tab "Lupa Password" -> terima
kode 6 digit -> masukkan kode + password baru -> otomatis Masuk.

**WAJIB langkah manual satu kali di Supabase Dashboard supaya kode 6 digit
benar-benar terkirim** (tidak bisa dikerjakan lewat kode):
1. Buka **Authentication -> Emails -> SMTP Settings**, aktifkan Custom SMTP
   (mis. pakai Gmail: Host `smtp.gmail.com`, Port `587`, Username = email
   Gmail, Password = App Password 16 karakter dari Google Account -> Security
   -> App Passwords, butuh 2-Step Verification aktif dulu). **Di tier gratis
   Supabase, body email TIDAK BISA diedit tanpa SMTP kustom ini.**
2. Setelah SMTP aktif, buka **Authentication -> Emails -> Templates -> Reset
   Password**, tambahkan `{{ .Token }}` di badan email, mis.:
   ```html
   <h2>Reset Password - RPS Builder</h2>
   <p>Kode reset password Anda: <strong>{{ .Token }}</strong></p>
   <p>Masukkan kode ini di aplikasi untuk membuat password baru. Berlaku
   sementara - kalau tidak diminta, abaikan email ini.</p>
   ```
3. Simpan template.

**Login Persisten (~30 menit) - DIBATALKAN**, tidak jadi dipakai. Sempat
dicoba lewat cookie browser (`extra-streamlit-components`), tapi ditemukan
race condition nyata: `cookies.delete()` di komponen itu perlu round-trip
Python <-> JS browser untuk benar-benar menghapus cookie, sementara alur
Logout langsung memanggil `st.rerun()` setelahnya - rerun bisa terjadi
SEBELUM penghapusan itu sempat sampai ke browser, sehingga Logout kelihatan
berhasil sesaat lalu sesi lama "hidup lagi" dari cookie yang ternyata belum
terhapus. Ditemukan lewat pengujian nyata pengguna, dianggap tidak layak
diandalkan untuk sesuatu sesensitif Logout (terutama risiko di komputer
bersama), sehingga DIBATALKAN sepenuhnya (bukan ditambal) - `auth.py`
kembali ke `session_state` biasa yang sudah teruji stabil sepanjang proyek
ini (login bertahan selama tab browser terbuka, refresh = perlu Masuk lagi).
Dependency `extra-streamlit-components` sudah dilepas dari `requirements.txt`.

Tanpa langkah ini, email akan terkirim tapi TIDAK berisi kode 6 digit yang
dibutuhkan form "Reset Password" di aplikasi.

## Mapping CPMK ke Komponen Penilaian: dari checklist jadi persentase

Perubahan lanjutan dari model checklist sebelumnya - sekarang tiap CPMK diisi
**persentase kontribusinya** ke tiap komponen, bukan cuma tanda centang:

- **Bobot komponen diperbaiki**: Kehadiran dan Sikap **30%** (sebelumnya 10%),
  UTS **20%** (sebelumnya 30%), Tugas **20%** (sebelumnya 30%), UAS tetap
  **30%**. Total tetap 100%. Lihat `BOBOT_KATEGORI` di `docx_export.py`.
- **UI baru** (tab "Komponen Penilaian"): untuk tiap komponen, ada 5 kotak
  angka (satu per CPMK) - total kelimanya HARUS PAS sama dengan bobot
  komponen itu, ada indikator live (✅ pas / ⚠️ kurang / ❌ kelebihan).
- **Validasi sebelum Ajukan**: tombol "📤 Ajukan ke Kaprodi" akan menolak
  (dengan pesan jelas kategori mana yang belum pas) kalau ada komponen yang
  totalnya belum tepat - "Simpan ke Database" biasa tetap bisa dipakai kapan
  saja meski belum pas (buat nyimpan progres yang belum selesai).
- **Dokumen Word**: sel mapping sekarang menampilkan angka persentase
  (mis. "15%"), bukan tanda centang lagi. Sel dengan 0% dikosongkan (tidak
  tercetak "0%").
- **Kompatibilitas mundur**: RPS lama (format checklist ataupun format nilai
  tunggal dari sebelumnya) otomatis di-reset ke 0% di tab ini SAJA saat
  dibuka lagi - format lama tidak membawa info persentase sama sekali,
  jadi tidak ada "tebakan" yang bisa dilakukan otomatis. Bagian RPS lainnya
  (CPMK, CPL, 16 Pertemuan, dst.) TIDAK terpengaruh/tidak hilang.

**Sudah diuji**: dokumen contoh sudah di-generate & diperiksa - kolom
persentase per CPMK dan baris Bobot Nilai tampil benar sesuai bobot baru.