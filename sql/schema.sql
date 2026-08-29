-- =============================================================================
-- RPS Builder - Skema Database Supabase (Fase 1: Fondasi)
-- =============================================================================
-- Cara pakai:
--   1. Buat project baru di supabase.com (lihat langkah-langkah di chat).
--   2. Buka Project -> SQL Editor -> New query.
--   3. Salin-tempel SELURUH isi file ini, lalu klik "Run".
--   4. Aman dijalankan berulang kali (semua "create ... if not exists").
--
-- Cakupan Fase 1 (sesuai RPS_Builder_Rencana_Pengembangan.md):
--   - Tabel data master relasional: prodi, mata_kuliah, cpl
--   - Tabel dokumen RPS (rps) dengan isian per-pertemuan/CPMK/dst disimpan
--     sebagai satu kolom JSONB, karena selalu dibaca/ditulis sebagai satu
--     kesatuan per submission, bukan di-query per baris pertemuan.
--   - BELUM mencakup: Supabase Auth, peran (Dosen/Kaprodi/Admin), Row Level
--     Security aktif, migrasi data Excel -> tabel (menyusul di Fase 2 & 3).
-- =============================================================================

create extension if not exists pgcrypto;  -- untuk gen_random_uuid()


-- -----------------------------------------------------------------------------
-- 1. prodi
-- -----------------------------------------------------------------------------
-- Satu baris = satu Program Studi. `nama` SENGAJA dibuat sama persis dengan
-- nama file Excel data/<Nama Prodi>.xlsx yang sudah ada sekarang (mis.
-- "Informatika PJJ S1"), supaya skrip migrasi Fase 3 tinggal mencocokkan nama
-- file ke baris ini tanpa perlu tabel mapping tambahan.
create table if not exists public.prodi (
    id          uuid primary key default gen_random_uuid(),
    nama        text not null unique,
    created_at  timestamptz not null default now()
);

comment on table public.prodi is
    'Program Studi. nama harus sama persis dengan nama file data/<Nama Prodi>.xlsx.';


-- -----------------------------------------------------------------------------
-- 2. mata_kuliah
-- -----------------------------------------------------------------------------
-- Satu baris = satu baris di sheet "Mata Kuliah" pada Excel data master.
create table if not exists public.mata_kuliah (
    id                uuid primary key default gen_random_uuid(),
    prodi_id          uuid not null references public.prodi(id) on delete cascade,
    no_urut           integer,        -- kolom "No" asli di Excel, hanya untuk urutan tampilan
    nama_mk           text not null,
    kode_mk           text not null,  -- disimpan sebagai text (bukan angka) agar aman
                                       -- kalau suatu saat format kode berubah (huruf/leading zero)
    sks               integer,
    semester          integer,
    ranah_topik       text,
    dosen_pengembang  text,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),
    unique (prodi_id, kode_mk)
);

comment on table public.mata_kuliah is
    'Data master Mata Kuliah per Prodi, dari sheet "Mata Kuliah" di Excel.';


-- -----------------------------------------------------------------------------
-- 3. cpl
-- -----------------------------------------------------------------------------
-- Satu baris = satu baris di sheet "CPL" pada Excel data master.
create table if not exists public.cpl (
    id          uuid primary key default gen_random_uuid(),
    prodi_id    uuid not null references public.prodi(id) on delete cascade,
    kode_cpl    text not null,        -- mis. 'S1', 'P1', 'KU1', 'KK1'
    deskripsi   text not null default '',
    created_at  timestamptz not null default now(),
    unique (prodi_id, kode_cpl)
);

comment on table public.cpl is
    'Data master CPL (Capaian Pembelajaran Lulusan) per Prodi, dari sheet "CPL".';


-- -----------------------------------------------------------------------------
-- 4. rps  (dokumen RPS - inti aplikasi)
-- -----------------------------------------------------------------------------
-- Satu baris = satu dokumen RPS (hasil isian penuh 1 Mata Kuliah oleh 1 Dosen).
-- Kolom `data` (JSONB) menampung SEMUA isian yang di app.py saat ini hidup di
-- st.session_state, yaitu:
--   {
--     "info_umum":      {...11 field spt sekarang: dosen_koordinator, dosen_pengampu,
--                         deskripsi_mk, rumpun_mk, mk_prasyarat, prasyarat_untuk_mk,
--                         nama_kaprodi, nama_koordinator, nama_penyusun,
--                         nama_biro_pjm, tanggal_dokumen},
--     "cpl_selected":   ["S1", "P2", "KU1", "KU5", "KK2"],   -- 5 kode CPL terpilih
--     "cpmk_data":      {"1": {"cpl_kode": "S1", "deskripsi": "..."}, ..., "5": {...}},
--     "pertemuan_data": {"1": {...9 field spt sekarang}, ..., "16": {...}},
--     "komponen_data":  {"1": "UTS", "2": "Tugas", ...},
--     "referensi_data": [{"sitasi": "..."}, ...]
--   }
-- Field-field ini TIDAK dipecah jadi kolom/tabel terpisah karena selalu
-- dibaca & ditulis sebagai satu kesatuan per RPS (bukan di-query per minggu
-- atau per CPMK secara terpisah) - lihat diskusi arsitektur di dokumen rencana.
create table if not exists public.rps (
    id               uuid primary key default gen_random_uuid(),
    mata_kuliah_id   uuid not null references public.mata_kuliah(id) on delete restrict,
    dosen_user_id    uuid references auth.users(id) on delete set null,
    status           text not null default 'draft'
                          check (status in ('draft', 'diajukan', 'disetujui', 'ditolak')),
    data             jsonb not null default '{}'::jsonb,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

comment on table public.rps is
    'Satu baris = satu dokumen RPS lengkap. Isian per-CPMK/per-pertemuan/dst disimpan di kolom data (JSONB).';
comment on column public.rps.dosen_user_id is
    'Pemilik RPS. NULLABLE di Fase 1 karena belum ada Supabase Auth. Diisi & di-enforce lewat RLS mulai Fase 2.';
comment on column public.rps.status is
    'draft = masih diisi dosen; diajukan = menunggu approval Kaprodi; disetujui/ditolak = hasil approval (dipakai mulai Fase 5).';


-- -----------------------------------------------------------------------------
-- Trigger: auto-update kolom updated_at
-- -----------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_mata_kuliah_updated_at on public.mata_kuliah;
create trigger trg_mata_kuliah_updated_at
    before update on public.mata_kuliah
    for each row execute function public.set_updated_at();

drop trigger if exists trg_rps_updated_at on public.rps;
create trigger trg_rps_updated_at
    before update on public.rps
    for each row execute function public.set_updated_at();


-- -----------------------------------------------------------------------------
-- Index
-- -----------------------------------------------------------------------------
create index if not exists idx_mata_kuliah_prodi   on public.mata_kuliah (prodi_id);
create index if not exists idx_cpl_prodi            on public.cpl (prodi_id);
create index if not exists idx_rps_mata_kuliah      on public.rps (mata_kuliah_id);
create index if not exists idx_rps_dosen            on public.rps (dosen_user_id);
create index if not exists idx_rps_data_gin         on public.rps using gin (data);

-- Satu Dosen cuma boleh punya SATU dokumen RPS per Mata Kuliah (dipakai
-- Fase 4 untuk upsert lewat on_conflict="mata_kuliah_id,dosen_user_id" -
-- lihat rps_store.py). Index unik (bukan constraint biasa) supaya bisa
-- "create ... if not exists", aman dijalankan berulang.
create unique index if not exists ux_rps_mata_kuliah_dosen
    on public.rps (mata_kuliah_id, dosen_user_id);


-- =============================================================================
-- FASE 2: Login & Peran (pengguna, trigger auto-provision, RLS + policy)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 5. pengguna
-- -----------------------------------------------------------------------------
-- Profil & peran tiap orang yang login. `id` SAMA dengan auth.users.id (baris
-- ini otomatis dibuat lewat trigger di bawah setiap kali ada user baru daftar).
create table if not exists public.pengguna (
    id          uuid primary key references auth.users(id) on delete cascade,
    email       text,
    nama        text,
    role        text not null default 'dosen' check (role in ('dosen', 'kaprodi', 'admin')),
    prodi_id    uuid references public.prodi(id) on delete set null,
    created_at  timestamptz not null default now()
);

comment on table public.pengguna is
    'Profil & peran tiap user login. id = auth.users.id. role default "dosen" saat pertama daftar; admin mengubah lewat SQL Editor (Fase 2) atau panel admin (Fase 3).';
comment on column public.pengguna.prodi_id is
    'Wajib diisi untuk role kaprodi (menentukan prodi yang diampu, dipakai policy RLS di bawah). Tidak dipakai untuk admin (akses semua prodi) atau dosen (RPS dosen tidak dibatasi 1 prodi).';


-- -----------------------------------------------------------------------------
-- Trigger: auto-provision baris pengguna setiap kali ada user baru di
-- auth.users (habis Daftar dari form Streamlit). Role default 'dosen' -
-- naikkan ke 'kaprodi'/'admin' manual lewat SQL Editor untuk saat ini:
--   update public.pengguna set role = 'admin' where email = 'email_anda@...';
-- -----------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.pengguna (id, email)
    values (new.id, new.email)
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();


-- -----------------------------------------------------------------------------
-- Helper function SECURITY DEFINER untuk policy RLS di bawah.
--
-- KENAPA PERLU: policy pada tabel pengguna butuh cek "apakah user ini admin?",
-- yang secara alami berarti membaca ulang tabel pengguna itu sendiri. Kalau
-- dicek langsung lewat "exists (select ... from public.pengguna ...)" di
-- dalam policy pengguna, Postgres akan menerapkan RLS pengguna LAGI ke
-- subquery itu, yang berarti mengevaluasi policy yang sama lagi, dst -
-- menghasilkan error "infinite recursion detected in policy". Fungsi
-- SECURITY DEFINER di bawah berjalan dengan hak akses pemilik fungsi
-- (postgres, yang bypass RLS) sehingga baca tabel pengguna DI DALAM fungsi
-- ini tidak memicu RLS lagi - memutus rantai rekursinya.
-- -----------------------------------------------------------------------------
create or replace function public.is_admin()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
    select exists (
        select 1 from public.pengguna where id = auth.uid() and role = 'admin'
    );
$$;

create or replace function public.is_kaprodi_of(target_prodi_id uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
    select exists (
        select 1 from public.pengguna
        where id = auth.uid() and role = 'kaprodi' and prodi_id = target_prodi_id
    );
$$;


-- -----------------------------------------------------------------------------
-- Row Level Security - diaktifkan sekarang bahwa Auth sudah tersambung
-- -----------------------------------------------------------------------------
alter table public.prodi        enable row level security;
alter table public.mata_kuliah  enable row level security;
alter table public.cpl          enable row level security;
alter table public.rps          enable row level security;
alter table public.pengguna     enable row level security;

-- prodi/mata_kuliah/cpl: siapa pun yang sudah login boleh BACA (dipakai untuk
-- dropdown Prodi/Mata Kuliah/CPL di app). Tambah/ubah data master masih lewat
-- SQL Editor/dashboard sampai ada panel admin di Fase 3 - makanya belum ada
-- policy insert/update/delete untuk role manapun di ketiga tabel ini.
drop policy if exists "authenticated bisa baca prodi" on public.prodi;
create policy "authenticated bisa baca prodi" on public.prodi
    for select to authenticated using (true);

drop policy if exists "authenticated bisa baca mata_kuliah" on public.mata_kuliah;
create policy "authenticated bisa baca mata_kuliah" on public.mata_kuliah
    for select to authenticated using (true);

drop policy if exists "authenticated bisa baca cpl" on public.cpl;
create policy "authenticated bisa baca cpl" on public.cpl
    for select to authenticated using (true);

-- pengguna: tiap user boleh baca profil sendiri (buat tahu role sendiri saat
-- login); admin boleh baca semua (dipakai panel admin di Fase 3)
drop policy if exists "baca profil sendiri, admin baca semua" on public.pengguna;
create policy "baca profil sendiri, admin baca semua" on public.pengguna
    for select to authenticated
    using (
        id = auth.uid()
        or public.is_admin()
    );

-- hanya admin yang boleh mengubah role/prodi_id siapa pun - SENGAJA dosen
-- tidak bisa update baris sendiri sama sekali, supaya tidak bisa menaikkan
-- role-nya sendiri lewat request langsung ke API
drop policy if exists "hanya admin bisa update pengguna" on public.pengguna;
create policy "hanya admin bisa update pengguna" on public.pengguna
    for update to authenticated
    using (public.is_admin())
    with check (public.is_admin());

-- rps: dosen boleh baca/tambah/ubah RPS miliknya sendiri saja (dosen_user_id
-- harus = dirinya). TIDAK ada policy delete sama sekali (baik untuk dosen
-- maupun kaprodi/admin) - dokumen RPS tidak boleh terhapus lewat aplikasi;
-- kalau suatu saat memang perlu, tambahkan policy delete secara sadar nanti.
drop policy if exists "dosen baca rps sendiri" on public.rps;
create policy "dosen baca rps sendiri" on public.rps
    for select to authenticated using (dosen_user_id = auth.uid());

drop policy if exists "dosen insert rps sendiri" on public.rps;
create policy "dosen insert rps sendiri" on public.rps
    for insert to authenticated with check (dosen_user_id = auth.uid());

drop policy if exists "dosen update rps sendiri" on public.rps;
create policy "dosen update rps sendiri" on public.rps
    for update to authenticated
    using (dosen_user_id = auth.uid())
    with check (dosen_user_id = auth.uid());

-- kaprodi & admin boleh BACA (belum tulis - approve/tolak baru di Fase 5) RPS
-- di luar miliknya sendiri: kaprodi dibatasi ke RPS di prodi yang diampu saja,
-- admin boleh baca semua
drop policy if exists "kaprodi & admin baca rps" on public.rps;
create policy "kaprodi & admin baca rps" on public.rps
    for select to authenticated
    using (
        public.is_admin()
        or exists (
            select 1 from public.mata_kuliah mk
            where mk.id = rps.mata_kuliah_id and public.is_kaprodi_of(mk.prodi_id)
        )
    );


-- =============================================================================
-- FASE 3: Admin bisa tambah/ubah data master lewat Panel Admin di aplikasi
-- =============================================================================
-- Sebelum ini, prodi/mata_kuliah/cpl cuma punya policy SELECT (dari Fase 2) -
-- data master hanya bisa ditulis lewat SQL Editor atau skrip migrasi
-- (service_role key). Policy di bawah membuka jalur tulis untuk role admin
-- lewat aplikasi (admin_panel.py), pakai token login-nya sendiri (anon key +
-- JWT), BUKAN service_role key.
drop policy if exists "admin insert prodi" on public.prodi;
create policy "admin insert prodi" on public.prodi
    for insert to authenticated with check (public.is_admin());

drop policy if exists "admin update prodi" on public.prodi;
create policy "admin update prodi" on public.prodi
    for update to authenticated using (public.is_admin()) with check (public.is_admin());

drop policy if exists "admin insert mata_kuliah" on public.mata_kuliah;
create policy "admin insert mata_kuliah" on public.mata_kuliah
    for insert to authenticated with check (public.is_admin());

drop policy if exists "admin update mata_kuliah" on public.mata_kuliah;
create policy "admin update mata_kuliah" on public.mata_kuliah
    for update to authenticated using (public.is_admin()) with check (public.is_admin());

drop policy if exists "admin insert cpl" on public.cpl;
create policy "admin insert cpl" on public.cpl
    for insert to authenticated with check (public.is_admin());

drop policy if exists "admin update cpl" on public.cpl;
create policy "admin update cpl" on public.cpl
    for update to authenticated using (public.is_admin()) with check (public.is_admin());

-- Penyesuaian: policy delete DITAMBAHKAN (sebelumnya sengaja tidak ada sama
-- sekali - lihat riwayat di admin_panel.py) - kini hapus data master lewat
-- aplikasi (bukan cuma SQL Editor manual) sudah didukung, dengan penjagaan
-- referensi diterapkan di level lain: rps.mata_kuliah_id "on delete restrict"
-- (database) untuk Mata Kuliah, dan pengecekan manual rujukan CPMK->CPL
-- (aplikasi, lihat save_cpl_df di db_master.py) untuk CPL - keduanya
-- MENOLAK penghapusan (bukan diam-diam gagal) kalau masih dipakai di RPS.
drop policy if exists "admin delete mata_kuliah" on public.mata_kuliah;
create policy "admin delete mata_kuliah" on public.mata_kuliah
    for delete to authenticated using (public.is_admin());

drop policy if exists "kaprodi delete mata_kuliah" on public.mata_kuliah;
create policy "kaprodi delete mata_kuliah" on public.mata_kuliah
    for delete to authenticated using (public.is_kaprodi_of(prodi_id));

drop policy if exists "admin delete cpl" on public.cpl;
create policy "admin delete cpl" on public.cpl
    for delete to authenticated using (public.is_admin());

drop policy if exists "kaprodi delete cpl" on public.cpl;
create policy "kaprodi delete cpl" on public.cpl
    for delete to authenticated using (public.is_kaprodi_of(prodi_id));


-- =============================================================================
-- FASE 4: Riwayat versi RPS (otomatis, tanpa kode tambahan di aplikasi)
-- =============================================================================
-- Setiap kali baris `rps` dibuat/diubah (lewat "Simpan ke Database" di
-- app.py), trigger di bawah otomatis menyimpan SALINAN datanya ke
-- rps_riwayat. Ini murni manfaat dari struktur database dibanding file Excel
-- lama - tidak perlu kode tambahan di app.py untuk mencatatnya.
create table if not exists public.rps_riwayat (
    id           uuid primary key default gen_random_uuid(),
    rps_id       uuid not null references public.rps(id) on delete cascade,
    data         jsonb not null,
    status       text not null,
    diubah_oleh  uuid references auth.users(id) on delete set null,
    diubah_pada  timestamptz not null default now()
);

comment on table public.rps_riwayat is
    'Snapshot otomatis tiap kali baris rps dibuat/diubah - riwayat versi, diisi lewat trigger, bukan oleh aplikasi.';

create index if not exists idx_rps_riwayat_rps on public.rps_riwayat (rps_id, diubah_pada desc);

create or replace function public.log_rps_riwayat()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.rps_riwayat (rps_id, data, status, diubah_oleh)
    values (new.id, new.data, new.status, auth.uid());
    return new;
end;
$$;

drop trigger if exists trg_rps_riwayat on public.rps;
create trigger trg_rps_riwayat
    after insert or update on public.rps
    for each row execute function public.log_rps_riwayat();

alter table public.rps_riwayat enable row level security;

-- Baca riwayat: pemilik RPS-nya sendiri, Kaprodi (RPS di prodi yang diampu),
-- atau Admin. Sengaja TIDAK ada policy insert/update/delete sama sekali -
-- baris di tabel ini HANYA boleh masuk lewat trigger (SECURITY DEFINER,
-- bypass RLS), bukan langsung dari client manapun.
drop policy if exists "baca riwayat rps sendiri, kaprodi, admin" on public.rps_riwayat;
create policy "baca riwayat rps sendiri, kaprodi, admin" on public.rps_riwayat
    for select to authenticated
    using (
        exists (
            select 1 from public.rps r
            where r.id = rps_riwayat.rps_id and r.dosen_user_id = auth.uid()
        )
        or public.is_admin()
        or exists (
            select 1 from public.rps r
            join public.mata_kuliah mk on mk.id = r.mata_kuliah_id
            where r.id = rps_riwayat.rps_id and public.is_kaprodi_of(mk.prodi_id)
        )
    );


-- =============================================================================
-- FASE 5: Approval Kaprodi (setujui/tolak RPS yang diajukan)
-- =============================================================================
alter table public.rps add column if not exists catatan_kaprodi text;
alter table public.rps add column if not exists diproses_oleh uuid references auth.users(id) on delete set null;
alter table public.rps add column if not exists diproses_pada timestamptz;

comment on column public.rps.catatan_kaprodi is
    'Catatan Kaprodi saat menyetujui/menolak - wajib diisi kalau menolak, opsional kalau menyetujui.';
comment on column public.rps.diproses_oleh is
    'Kaprodi/Admin yang terakhir memproses (menyetujui/menolak) RPS ini.';
comment on column public.rps.diproses_pada is
    'Waktu terakhir diproses (disetujui/ditolak).';

-- Dosen cuma boleh menyimpan ulang (tombol "Simpan ke Database") saat status
-- draft atau ditolak - dikunci begitu status diajukan/disetujui, supaya isi
-- RPS tidak berubah diam-diam selagi/setelah direview Kaprodi. (Menggantikan
-- policy dengan nama sama dari Fase 2.)
drop policy if exists "dosen update rps sendiri" on public.rps;
create policy "dosen update rps sendiri" on public.rps
    for update to authenticated
    using (dosen_user_id = auth.uid() and status in ('draft', 'ditolak'))
    with check (dosen_user_id = auth.uid() and status in ('draft', 'ditolak'));

-- -----------------------------------------------------------------------------
-- Fungsi aksi (SECURITY DEFINER) untuk transisi status. Dipakai lewat
-- client.rpc(...) di rps_store.py, BUKAN update tabel rps langsung - supaya
-- kaprodi/dosen tidak perlu (dan tidak diberi) akses UPDATE penuh ke tabel
-- rps hanya untuk mengubah status; otorisasi divalidasi di dalam tiap fungsi.
-- -----------------------------------------------------------------------------
create or replace function public.ajukan_rps(target_rps_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    update public.rps
    set status = 'diajukan', catatan_kaprodi = null, diproses_oleh = null, diproses_pada = null
    where id = target_rps_id and dosen_user_id = auth.uid() and status in ('draft', 'ditolak');

    if not found then
        raise exception 'RPS tidak ditemukan, bukan milik Anda, atau statusnya tidak bisa diajukan.';
    end if;
end;
$$;

create or replace function public.tarik_pengajuan_rps(target_rps_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    update public.rps
    set status = 'draft'
    where id = target_rps_id and dosen_user_id = auth.uid() and status = 'diajukan';

    if not found then
        raise exception 'RPS tidak ditemukan, bukan milik Anda, atau statusnya bukan "diajukan".';
    end if;
end;
$$;

create or replace function public.setujui_rps(target_rps_id uuid, catatan text default null)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
    v_prodi_id uuid;
begin
    select mk.prodi_id into v_prodi_id
    from public.rps r
    join public.mata_kuliah mk on mk.id = r.mata_kuliah_id
    where r.id = target_rps_id;

    if v_prodi_id is null then
        raise exception 'RPS tidak ditemukan.';
    end if;

    if not (public.is_admin() or public.is_kaprodi_of(v_prodi_id)) then
        raise exception 'Anda tidak berwenang menyetujui RPS ini.';
    end if;

    update public.rps
    set status = 'disetujui', catatan_kaprodi = catatan, diproses_oleh = auth.uid(), diproses_pada = now()
    where id = target_rps_id and status = 'diajukan';

    if not found then
        raise exception 'RPS sudah tidak berstatus "diajukan" (mungkin sudah diproses pihak lain).';
    end if;
end;
$$;

create or replace function public.tolak_rps(target_rps_id uuid, catatan text)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
    v_prodi_id uuid;
begin
    if catatan is null or btrim(catatan) = '' then
        raise exception 'Catatan alasan penolakan wajib diisi.';
    end if;

    select mk.prodi_id into v_prodi_id
    from public.rps r
    join public.mata_kuliah mk on mk.id = r.mata_kuliah_id
    where r.id = target_rps_id;

    if v_prodi_id is null then
        raise exception 'RPS tidak ditemukan.';
    end if;

    if not (public.is_admin() or public.is_kaprodi_of(v_prodi_id)) then
        raise exception 'Anda tidak berwenang menolak RPS ini.';
    end if;

    update public.rps
    set status = 'ditolak', catatan_kaprodi = catatan, diproses_oleh = auth.uid(), diproses_pada = now()
    where id = target_rps_id and status = 'diajukan';

    if not found then
        raise exception 'RPS sudah tidak berstatus "diajukan" (mungkin sudah diproses pihak lain).';
    end if;
end;
$$;

grant execute on function public.ajukan_rps(uuid) to authenticated;
grant execute on function public.tarik_pengajuan_rps(uuid) to authenticated;
grant execute on function public.setujui_rps(uuid, text) to authenticated;
grant execute on function public.tolak_rps(uuid, text) to authenticated;


-- =============================================================================
-- PENYESUAIAN: user bisa mengubah nama profil sendiri
-- =============================================================================
-- Trigger auto-provision (Fase 2) cuma mengisi email, tidak pernah mengisi
-- nama - jadi kolom pengguna.nama selalu kosong sampai diisi manual. Policy
-- "hanya admin bisa update pengguna" (Fase 2) sengaja tidak mengizinkan user
-- meng-update baris sendiri sama sekali (supaya tidak bisa menaikkan role
-- sendiri), jadi fungsi khusus di bawah ini dibuat SECURITY DEFINER supaya
-- user bisa ubah nama sendiri TANPA lewat jalur yang bisa dipakai mengubah
-- role/prodi_id.
create or replace function public.update_nama_saya(nama_baru text)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    update public.pengguna set nama = nama_baru where id = auth.uid();
end;
$$;

grant execute on function public.update_nama_saya(text) to authenticated;


-- =============================================================================
-- PENYESUAIAN: Koordinator Mata Kuliah - RPS jadi "milik" Mata Kuliah, bukan
-- milik Dosen. Hanya Dosen yang ditetapkan sebagai koordinator suatu Mata
-- Kuliah (oleh Kaprodi/Admin) yang boleh mengisi/mengubah RPS-nya. Mata
-- Kuliah TANPA koordinator otomatis terkunci untuk semua Dosen. Kalau
-- koordinator diganti, RPS yang sudah ada otomatis "pindah" ke koordinator
-- baru (karena hak edit dicek dari koordinator_user_id saat itu juga, bukan
-- dari siapa yang membuat baris rps-nya).
--
-- >>> PENTING - JALANKAN DULU SEBELUM BAGIAN INI, DI SQL EDITOR TERPISAH:
--
--     select mata_kuliah_id, count(*) from public.rps
--     group by mata_kuliah_id having count(*) > 1;
--
-- Kalau query itu mengembalikan baris (artinya ada Mata Kuliah yang kadung
-- punya lebih dari satu RPS dari beberapa Dosen berbeda, dari sebelum aturan
-- ini berlaku), unique index di bagian ini (ux_rps_mata_kuliah) akan GAGAL
-- dibuat. Putuskan dulu mana yang mau dipertahankan per Mata Kuliah yang
-- bentrok (lihat kolom updated_at/status buat bantu memutuskan), baru hapus
-- baris yang tidak dipakai secara manual lewat SQL Editor, baru kemudian
-- jalankan bagian ini. Kalau query di atas kosong, langsung aman lanjut.
-- =============================================================================

alter table public.mata_kuliah add column if not exists koordinator_user_id uuid references auth.users(id) on delete set null;

comment on column public.mata_kuliah.koordinator_user_id is
    'Dosen yang ditetapkan Kaprodi/Admin sebagai koordinator - HANYA dia yang boleh mengisi/mengubah RPS Mata Kuliah ini. NULL = belum ditetapkan, terkunci untuk semua Dosen.';

-- Ganti unique index lama (per Mata Kuliah + Dosen) jadi per Mata Kuliah saja
-- - satu Mata Kuliah = satu dokumen RPS, siapa pun koordinatornya saat ini.
drop index if exists ux_rps_mata_kuliah_dosen;
create unique index if not exists ux_rps_mata_kuliah on public.rps (mata_kuliah_id);

-- Helper: apakah pemanggil ber-role kaprodi (di prodi manapun) - dipakai utk
-- izin baca daftar pengguna (perlu buat pilih siapa jadi koordinator).
create or replace function public.is_kaprodi()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
    select exists (select 1 from public.pengguna where id = auth.uid() and role = 'kaprodi');
$$;

-- Perluas policy baca tabel pengguna (dari Fase 2): Kaprodi juga boleh baca
-- semua baris (perlu buat memilih Dosen mana yang ditetapkan jadi koordinator
-- Mata Kuliah - lihat set_koordinator_mk()). Menggantikan policy nama sama.
drop policy if exists "baca profil sendiri, admin baca semua" on public.pengguna;
drop policy if exists "baca profil sendiri, admin & kaprodi baca semua" on public.pengguna;
create policy "baca profil sendiri, admin & kaprodi baca semua" on public.pengguna
    for select to authenticated
    using (
        id = auth.uid()
        or public.is_admin()
        or public.is_kaprodi()
    );

-- Fungsi: Kaprodi (di prodinya sendiri) atau Admin menetapkan/mengubah
-- koordinator Mata Kuliah. koordinator_id = null artinya dikosongkan lagi
-- (dikunci untuk semua Dosen).
create or replace function public.set_koordinator_mk(target_mk_id uuid, koordinator_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
    v_prodi_id uuid;
begin
    select prodi_id into v_prodi_id from public.mata_kuliah where id = target_mk_id;
    if v_prodi_id is null then
        raise exception 'Mata Kuliah tidak ditemukan.';
    end if;

    if not (public.is_admin() or public.is_kaprodi_of(v_prodi_id)) then
        raise exception 'Anda tidak berwenang menetapkan koordinator untuk Mata Kuliah ini.';
    end if;

    if koordinator_id is not null and not exists (select 1 from public.pengguna where id = koordinator_id) then
        raise exception 'Akun Dosen tidak ditemukan.';
    end if;

    update public.mata_kuliah set koordinator_user_id = koordinator_id where id = target_mk_id;
end;
$$;

grant execute on function public.set_koordinator_mk(uuid, uuid) to authenticated;

-- Ganti policy insert/update rps (dari Fase 2/5): sekarang berbasis
-- "apakah saya koordinator Mata Kuliah ini SEKARANG", bukan lagi berdasarkan
-- dosen_user_id yang tersimpan di baris rps - ini yang membuat RPS otomatis
-- "berpindah" ke koordinator baru saat diganti.
drop policy if exists "dosen insert rps sendiri" on public.rps;
drop policy if exists "koordinator insert rps" on public.rps;
create policy "koordinator insert rps" on public.rps
    for insert to authenticated
    with check (
        exists (
            select 1 from public.mata_kuliah mk
            where mk.id = rps.mata_kuliah_id and mk.koordinator_user_id = auth.uid()
        )
    );

drop policy if exists "dosen update rps sendiri" on public.rps;
drop policy if exists "koordinator update rps" on public.rps;
create policy "koordinator update rps" on public.rps
    for update to authenticated
    using (
        status in ('draft', 'ditolak')
        and exists (
            select 1 from public.mata_kuliah mk
            where mk.id = rps.mata_kuliah_id and mk.koordinator_user_id = auth.uid()
        )
    )
    with check (
        status in ('draft', 'ditolak')
        and exists (
            select 1 from public.mata_kuliah mk
            where mk.id = rps.mata_kuliah_id and mk.koordinator_user_id = auth.uid()
        )
    );

drop policy if exists "dosen baca rps sendiri" on public.rps;
drop policy if exists "koordinator baca rps mata kuliahnya" on public.rps;
create policy "koordinator baca rps mata kuliahnya" on public.rps
    for select to authenticated
    using (
        exists (
            select 1 from public.mata_kuliah mk
            where mk.id = rps.mata_kuliah_id and mk.koordinator_user_id = auth.uid()
        )
    );

-- BARU: transparansi - RPS yang sudah DISETUJUI boleh dibaca (& diunduh)
-- SEMUA Dosen yang login, bukan cuma koordinator/kaprodi/admin. Draft/
-- diajukan/ditolak tetap privat (tidak kena policy ini).
drop policy if exists "semua dosen baca rps disetujui" on public.rps;
create policy "semua dosen baca rps disetujui" on public.rps
    for select to authenticated
    using (status = 'disetujui');

-- ajukan_rps()/tarik_pengajuan_rps() (Fase 5) perlu diganti juga - dulu
-- mengecek dosen_user_id = auth.uid(), sekarang harus mengecek "saya
-- koordinator Mata Kuliah ini" supaya konsisten dengan aturan baru.
create or replace function public.ajukan_rps(target_rps_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    update public.rps r
    set status = 'diajukan', catatan_kaprodi = null, diproses_oleh = null, diproses_pada = null
    from public.mata_kuliah mk
    where r.id = target_rps_id
      and mk.id = r.mata_kuliah_id
      and mk.koordinator_user_id = auth.uid()
      and r.status in ('draft', 'ditolak');

    if not found then
        raise exception 'RPS tidak ditemukan, Anda bukan koordinatornya, atau statusnya tidak bisa diajukan.';
    end if;
end;
$$;

create or replace function public.tarik_pengajuan_rps(target_rps_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    update public.rps r
    set status = 'draft'
    from public.mata_kuliah mk
    where r.id = target_rps_id
      and mk.id = r.mata_kuliah_id
      and mk.koordinator_user_id = auth.uid()
      and r.status = 'diajukan';

    if not found then
        raise exception 'RPS tidak ditemukan, Anda bukan koordinatornya, atau statusnya bukan "diajukan".';
    end if;
end;
$$;


-- =============================================================================
-- PENYESUAIAN: hapus no_urut, Kaprodi bisa ikut mengedit kurikulum (Mata
-- Kuliah & CPL) di prodinya sendiri, Kode MK unik se-institusi
-- =============================================================================
-- RIWAYAT KEPUTUSAN (untuk konteks kalau baca ulang nanti):
--   1. Awalnya dicoba Kode MK unik SE-INSTITUSI
--   2. Ternyata ada Mata Kuliah Umum yang SENGAJA dipakai lintas Prodi dengan
--      Kode MK sama (mis. Pancasila, Bahasa Indonesia) -> sempat dibalik ke
--      unik PER PRODI
--   3. Solusi final: Mata Kuliah Umum dikonsolidasi ke SATU Prodi baru
--      "Mata Kuliah Umum" (lewat sql/migrate_mata_kuliah_umum.sql) - dengan
--      begitu Kode MK unik SE-INSTITUSI bisa diterapkan lagi TANPA kehilangan
--      data, karena tidak ada lagi Kode MK yang benar-benar bentrok.
--
-- >>> WAJIB jalankan sql/migrate_mata_kuliah_umum.sql DULU (satu kali,
-- terpisah) SEBELUM bagian ini - kalau belum, index di bawah akan GAGAL
-- dibuat selama masih ada Kode MK yang bentrok lintas Prodi.
-- =============================================================================

drop index if exists ux_mata_kuliah_prodi_kode;
alter table public.mata_kuliah drop constraint if exists mata_kuliah_prodi_id_kode_mk_key;
create unique index if not exists ux_mata_kuliah_kode_mk on public.mata_kuliah (kode_mk);

-- no_urut tidak dipakai lagi - urutan Mata Kuliah sekarang selalu berdasarkan
-- Kode MK (kolom utama/leading identifier), bukan urutan manual lagi
alter table public.mata_kuliah drop column if exists no_urut;

-- Kaprodi (di Prodi yang diampu) sekarang juga boleh tambah/ubah Mata Kuliah
-- & CPL, sama seperti Admin (sebelumnya cuma bisa baca & atur koordinator)
drop policy if exists "kaprodi insert mata_kuliah" on public.mata_kuliah;
create policy "kaprodi insert mata_kuliah" on public.mata_kuliah
    for insert to authenticated with check (public.is_kaprodi_of(prodi_id));

drop policy if exists "kaprodi update mata_kuliah" on public.mata_kuliah;
create policy "kaprodi update mata_kuliah" on public.mata_kuliah
    for update to authenticated
    using (public.is_kaprodi_of(prodi_id))
    with check (public.is_kaprodi_of(prodi_id));

drop policy if exists "kaprodi insert cpl" on public.cpl;
create policy "kaprodi insert cpl" on public.cpl
    for insert to authenticated with check (public.is_kaprodi_of(prodi_id));

drop policy if exists "kaprodi update cpl" on public.cpl;
create policy "kaprodi update cpl" on public.cpl
    for update to authenticated
    using (public.is_kaprodi_of(prodi_id))
    with check (public.is_kaprodi_of(prodi_id));


-- =============================================================================
-- PENYESUAIAN: Kurikulum ganda (tahun_kurikulum) - satu Prodi bisa punya
-- beberapa "edisi" kurikulum berdampingan (mis. 2021 & 2026), masing-masing
-- dengan Mata Kuliah & CPL sendiri (baris database terpisah sepenuhnya -
-- Kode MK yang sama boleh dipakai lagi di tahun kurikulum lain, dianggap
-- versi revisi Mata Kuliah tsb). Data yang sudah ada di database dianggap
-- kurikulum 2021 (di-backfill otomatis oleh bagian ini).
-- =============================================================================

alter table public.mata_kuliah add column if not exists tahun_kurikulum integer;
alter table public.cpl add column if not exists tahun_kurikulum integer;

-- Backfill data lama (yang belum punya tahun_kurikulum) sebagai kurikulum 2021
update public.mata_kuliah set tahun_kurikulum = 2021 where tahun_kurikulum is null;
update public.cpl set tahun_kurikulum = 2021 where tahun_kurikulum is null;

alter table public.mata_kuliah alter column tahun_kurikulum set not null;
alter table public.cpl alter column tahun_kurikulum set not null;

comment on column public.mata_kuliah.tahun_kurikulum is
    'Tahun/edisi kurikulum (mis. 2021, 2026). Kode MK yang sama boleh dipakai lagi di tahun kurikulum berbeda - dianggap versi revisi Mata Kuliah tsb, bukan bentrok.';
comment on column public.cpl.tahun_kurikulum is
    'Tahun/edisi kurikulum - CPL bisa berbeda antar edisi kurikulum dalam satu Prodi.';

-- Kode MK unik per (Kode MK, Tahun Kurikulum) - bukan lagi unik mutlak
-- se-institusi sepanjang masa
drop index if exists ux_mata_kuliah_kode_mk;
create unique index if not exists ux_mata_kuliah_kode_tahun on public.mata_kuliah (kode_mk, tahun_kurikulum);

-- CPL unik per (Prodi, Kode CPL, Tahun Kurikulum)
alter table public.cpl drop constraint if exists cpl_prodi_id_kode_cpl_key;
drop index if exists ux_cpl_prodi_kode_tahun;
create unique index if not exists ux_cpl_prodi_kode_tahun on public.cpl (prodi_id, kode_cpl, tahun_kurikulum);


-- =============================================================================
-- PENYESUAIAN: Pra-pendaftaran Dosen (whitelist NIP) - Admin bisa daftarkan
-- NIP+Nama Dosen SEBELUM orangnya benar-benar Daftar akun, dan bahkan
-- menetapkan mereka sebagai koordinator Mata Kuliah lebih dulu (mis. buat
-- persiapan sebelum demo/pelatihan). Saat Dosen benar-benar Daftar dengan
-- NIP yang cocok, semuanya otomatis "tersambung" ke akun barunya.
-- =============================================================================

create table if not exists public.whitelist_pendaftaran (
    nip         text primary key,
    nama        text not null,
    created_at  timestamptz not null default now()
);

comment on table public.whitelist_pendaftaran is
    'Daftar NIP+Nama yang di-pra-daftar Admin SEBELUM orangnya benar-benar Daftar akun - dipakai untuk validasi NIP saat Daftar (lihat cek_nip_terdaftar()) dan penetapan koordinator lebih dulu (lihat mata_kuliah.koordinator_nip).';

alter table public.whitelist_pendaftaran enable row level security;

drop policy if exists "admin kelola whitelist" on public.whitelist_pendaftaran;
create policy "admin kelola whitelist" on public.whitelist_pendaftaran
    for all to authenticated
    using (public.is_admin())
    with check (public.is_admin());

drop policy if exists "kaprodi baca whitelist" on public.whitelist_pendaftaran;
create policy "kaprodi baca whitelist" on public.whitelist_pendaftaran
    for select to authenticated
    using (public.is_kaprodi());

-- Kolom NIP di pengguna (diisi otomatis dari whitelist saat Daftar, kalau
-- NIP-nya cocok) dan koordinator_nip di mata_kuliah (staging koordinator
-- untuk NIP yang belum py akun - dikosongkan otomatis begitu orangnya Daftar
-- dan koordinator_user_id terisi).
alter table public.pengguna add column if not exists nip text;
alter table public.mata_kuliah add column if not exists koordinator_nip text;

comment on column public.pengguna.nip is
    'NIP, otomatis terisi dari whitelist_pendaftaran saat Daftar kalau NIP yang diinput cocok.';
comment on column public.mata_kuliah.koordinator_nip is
    'NIP calon koordinator yang BELUM py akun (staging, dipakai bareng koordinator_user_id) - begitu orang dengan NIP ini Daftar, trigger otomatis mengisi koordinator_user_id dan mengosongkan kolom ini.';

-- Fungsi cek NIP (dipanggil dari form Daftar, SEBELUM login - makanya perlu
-- bisa dipanggil oleh role anon). Mengembalikan nama yang terdaftar kalau
-- NIP cocok, atau null kalau tidak ditemukan - form Daftar pakai ini untuk
-- menolak pendaftaran dengan NIP yang tidak dikenal.
create or replace function public.cek_nip_terdaftar(nip_input text)
returns text
language sql
security definer
set search_path = public
stable
as $$
    select nama from public.whitelist_pendaftaran where nip = nip_input limit 1;
$$;

grant execute on function public.cek_nip_terdaftar(text) to anon, authenticated;

-- Trigger auto-provision (dari Fase 2) diperluas: kalau user baru Daftar
-- dengan NIP yang cocok di whitelist, otomatis (1) isi nama & nip di
-- pengguna, dan (2) sambungkan ke Mata Kuliah manapun yang sudah ditetapkan
-- atas nama NIP itu (koordinator_nip -> koordinator_user_id).
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
    v_nip text;
    v_nama_whitelist text;
begin
    v_nip := new.raw_user_meta_data->>'nip';

    if v_nip is not null then
        select nama into v_nama_whitelist from public.whitelist_pendaftaran where nip = v_nip limit 1;
    end if;

    insert into public.pengguna (id, email, nip, nama)
    values (new.id, new.email, v_nip, v_nama_whitelist)
    on conflict (id) do nothing;

    if v_nip is not null then
        update public.mata_kuliah
        set koordinator_user_id = new.id, koordinator_nip = null
        where koordinator_nip = v_nip;
    end if;

    return new;
end;
$$;

-- Ganti fungsi set_koordinator_mk (dari penyesuaian sebelumnya): sekarang
-- bisa menetapkan koordinator lewat akun yang SUDAH terdaftar (koordinator_id)
-- ATAU lewat NIP yang BELUM py akun (koordinator_nip_baru) - salah satu saja
-- yang diisi, sisanya null. Signature-nya berubah (tambah 1 parameter) -
-- Postgres menganggap signature berbeda sebagai fungsi TERPISAH (bukan
-- "replace"), jadi versi lama (2 parameter) harus di-drop dulu secara
-- eksplisit supaya tidak ada dua versi nyangkut bersamaan.
drop function if exists public.set_koordinator_mk(uuid, uuid);

-- Penyesuaian: koordinator_nip sekarang TETAP terisi meskipun akun sudah
-- terdaftar (koordinator_id) - diambil dari pengguna.nip milik akun
-- tersebut, bukan dikosongkan lagi. NIP jadi identitas yang melekat pada
-- dosen (berguna untuk laporan), bukan cuma placeholder staging.
create or replace function public.set_koordinator_mk(
    target_mk_id uuid,
    koordinator_id uuid default null,
    koordinator_nip_baru text default null
)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
    v_prodi_id uuid;
    v_nip text;
begin
    select prodi_id into v_prodi_id from public.mata_kuliah where id = target_mk_id;
    if v_prodi_id is null then
        raise exception 'Mata Kuliah tidak ditemukan.';
    end if;

    if not (public.is_admin() or public.is_kaprodi_of(v_prodi_id)) then
        raise exception 'Anda tidak berwenang menetapkan koordinator untuk Mata Kuliah ini.';
    end if;

    if koordinator_id is not null then
        select nip into v_nip from public.pengguna where id = koordinator_id;
        if not found then
            raise exception 'Akun Dosen tidak ditemukan.';
        end if;
    end if;

    update public.mata_kuliah
    set koordinator_user_id = koordinator_id,
        koordinator_nip = case when koordinator_id is not null then v_nip else koordinator_nip_baru end
    where id = target_mk_id;
end;
$$;

grant execute on function public.set_koordinator_mk(uuid, uuid, text) to authenticated;


-- =============================================================================
-- PENYESUAIAN: Template RPS baru - tanggal dokumen otomatis = tanggal pengajuan
-- =============================================================================
-- Sebelumnya "Tanggal Dokumen" diisi manual oleh Dosen. Sekarang otomatis
-- mengikuti kapan RPS diajukan ke Kaprodi - butuh kolom tersendiri (diproses_pada
-- yang sudah ada itu untuk waktu Kaprodi memutuskan, BUKAN waktu Dosen mengajukan).

alter table public.rps add column if not exists diajukan_pada timestamptz;

comment on column public.rps.diajukan_pada is
    'Waktu RPS ini TERAKHIR diajukan ke Kaprodi (diisi ajukan_rps(), dikosongkan tarik_pengajuan_rps()). Dipakai sebagai "Tanggal Penyusunan" otomatis di dokumen Word/PDF - lihat app.py.';

-- Ganti ajukan_rps()/tarik_pengajuan_rps() (dari penyesuaian Koordinator Mata
-- Kuliah) supaya juga mengisi/mengosongkan diajukan_pada.
create or replace function public.ajukan_rps(target_rps_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    update public.rps r
    set status = 'diajukan', catatan_kaprodi = null, diproses_oleh = null,
        diproses_pada = null, diajukan_pada = now()
    from public.mata_kuliah mk
    where r.id = target_rps_id
      and mk.id = r.mata_kuliah_id
      and mk.koordinator_user_id = auth.uid()
      and r.status in ('draft', 'ditolak');

    if not found then
        raise exception 'RPS tidak ditemukan, Anda bukan koordinatornya, atau statusnya tidak bisa diajukan.';
    end if;
end;
$$;

create or replace function public.tarik_pengajuan_rps(target_rps_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    update public.rps r
    set status = 'draft', diajukan_pada = null
    from public.mata_kuliah mk
    where r.id = target_rps_id
      and mk.id = r.mata_kuliah_id
      and mk.koordinator_user_id = auth.uid()
      and r.status = 'diajukan';

    if not found then
        raise exception 'RPS tidak ditemukan, Anda bukan koordinatornya, atau statusnya bukan "diajukan".';
    end if;
end;
$$;


-- =============================================================================
-- PENYESUAIAN: NIP & Prodi Homebase jadi atribut permanen SEMUA pengguna
-- (sebelumnya NIP cuma dipakai buat validasi whitelist saat Daftar, prodi_id
-- cuma dipakai untuk Kaprodi/"prodi yang diampu"). Sekarang Dosen juga
-- diharapkan punya NIP + Prodi Homebase - TAPI prodi_id untuk Dosen SENGAJA
-- TIDAK membatasi akses (beda dari Kaprodi, yang prodi_id-nya memang jadi
-- batas wewenang lewat is_kaprodi_of()) - murni Prodi default yang muncul
-- duluan saat login, Dosen tetap bebas isi RPS/jadi koordinator di Prodi lain.
-- =============================================================================

-- NIP unik KALAU DIISI (partial unique index - baris dengan nip masih null
-- tidak dianggap bentrok satu sama lain, jadi aman utk akun lama yg belum
-- diisi NIP-nya)
create unique index if not exists ux_pengguna_nip on public.pengguna (nip) where nip is not null;

-- whitelist_pendaftaran juga dapat kolom Prodi Homebase, supaya bisa
-- ditetapkan di depan sebelum orangnya sempat Daftar (sama seperti Nama)
alter table public.whitelist_pendaftaran add column if not exists prodi_id uuid references public.prodi(id) on delete set null;

comment on column public.whitelist_pendaftaran.prodi_id is
    'Prodi Homebase yang otomatis tersalin ke pengguna.prodi_id saat orang dengan NIP ini Daftar.';

-- handle_new_user() diperluas lagi: salin juga Prodi Homebase dari whitelist
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
    v_nip text;
    v_nama_whitelist text;
    v_prodi_id_whitelist uuid;
begin
    v_nip := new.raw_user_meta_data->>'nip';

    if v_nip is not null then
        select nama, prodi_id into v_nama_whitelist, v_prodi_id_whitelist
        from public.whitelist_pendaftaran where nip = v_nip limit 1;
    end if;

    insert into public.pengguna (id, email, nip, nama, prodi_id)
    values (new.id, new.email, v_nip, v_nama_whitelist, v_prodi_id_whitelist)
    on conflict (id) do nothing;

    if v_nip is not null then
        update public.mata_kuliah
        set koordinator_user_id = new.id, koordinator_nip = null
        where koordinator_nip = v_nip;
    end if;

    return new;
end;
$$;


-- =============================================================================
-- PENYESUAIAN: Role BPM (Biro Penjaminan Mutu) - validasi tahap KEDUA setelah
-- Kaprodi menyetujui. Alur baru:
--   draft -> diajukan -> disetujui (Kaprodi, MENUNGGU BPM) -> divalidasi (BPM, FINAL)
-- Ditolak di tahap MANA PUN (Kaprodi atau BPM) -> balik ke 'ditolak', LANGSUNG
-- ke Dosen untuk revisi (bukan ke Kaprodi dulu) - sesuai keputusan.
-- BPM cakupannya SE-INSTITUSI (semua Prodi), seperti Admin - bukan per-Prodi
-- seperti Kaprodi.
--
-- CATATAN MIGRASI: RPS yang SUDAH berstatus 'disetujui' dari SEBELUM fitur
-- ini ada TIDAK diubah statusnya oleh bagian ini - otomatis masuk antrian
-- BPM (dianggap "menunggu validasi", bukan langsung final). Tidak ada
-- migrasi data yang perlu dijalankan terpisah untuk ini.
-- =============================================================================

-- Tambah 'bpm' ke peran yang diizinkan
alter table public.pengguna drop constraint if exists pengguna_role_check;
alter table public.pengguna add constraint pengguna_role_check
    check (role in ('dosen', 'kaprodi', 'admin', 'bpm'));

-- Tambah 'divalidasi' ke status RPS yang diizinkan
alter table public.rps drop constraint if exists rps_status_check;
alter table public.rps add constraint rps_status_check
    check (status in ('draft', 'diajukan', 'disetujui', 'ditolak', 'divalidasi'));

-- Kolom pencatatan aksi BPM, terpisah dari kolom Kaprodi yang sudah ada
-- (catatan_kaprodi/diproses_oleh/diproses_pada) - supaya jelas siapa
-- mencatat apa di tiap tahap.
alter table public.rps add column if not exists catatan_bpm text;
alter table public.rps add column if not exists diproses_oleh_bpm uuid references auth.users(id) on delete set null;
alter table public.rps add column if not exists diproses_pada_bpm timestamptz;

comment on column public.rps.catatan_bpm is
    'Catatan BPM saat memvalidasi/menolak - wajib diisi kalau menolak, opsional kalau memvalidasi.';
comment on column public.rps.diproses_oleh_bpm is
    'Akun BPM yang terakhir memproses (memvalidasi/menolak) RPS ini.';
comment on column public.rps.diproses_pada_bpm is
    'Waktu terakhir diproses BPM (divalidasi/ditolak).';

-- Helper: apakah pemanggil ber-role bpm (se-institusi, tidak terikat Prodi
-- manapun - beda dari is_kaprodi_of() yang perlu parameter prodi_id).
create or replace function public.is_bpm()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
    select exists (select 1 from public.pengguna where id = auth.uid() and role = 'bpm');
$$;

-- BPM boleh baca RPS yang menunggu validasinya (disetujui) ATAU yang sudah
-- pernah divalidasi (untuk referensi/riwayat) - se-institusi, semua Prodi.
drop policy if exists "bpm baca rps antrian & riwayat" on public.rps;
create policy "bpm baca rps antrian & riwayat" on public.rps
    for select to authenticated
    using (public.is_bpm() and status in ('disetujui', 'divalidasi'));

-- Transparansi (dulu "semua dosen baca rps disetujui") sekarang mensyaratkan
-- status divalidasi (lolos KEDUANYA - Kaprodi & BPM), bukan cuma disetujui
-- Kaprodi lagi - sesuai keputusan.
drop policy if exists "semua dosen baca rps disetujui" on public.rps;
drop policy if exists "semua dosen baca rps divalidasi" on public.rps;
create policy "semua dosen baca rps divalidasi" on public.rps
    for select to authenticated
    using (status = 'divalidasi');

-- Fungsi aksi BPM (SECURITY DEFINER, pola sama seperti setujui_rps/tolak_rps
-- Kaprodi) - hanya berlaku dari status 'disetujui', BUKAN update tabel rps
-- langsung, supaya BPM tidak perlu akses UPDATE penuh ke tabel rps.
create or replace function public.validasi_bpm_rps(target_rps_id uuid, catatan text default null)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    if not public.is_bpm() then
        raise exception 'Anda tidak berwenang memvalidasi RPS ini.';
    end if;

    update public.rps
    set status = 'divalidasi', catatan_bpm = catatan, diproses_oleh_bpm = auth.uid(), diproses_pada_bpm = now()
    where id = target_rps_id and status = 'disetujui';

    if not found then
        raise exception 'RPS sudah tidak berstatus "disetujui" (mungkin sudah diproses pihak lain).';
    end if;
end;
$$;

create or replace function public.tolak_bpm_rps(target_rps_id uuid, catatan text)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    if not public.is_bpm() then
        raise exception 'Anda tidak berwenang menolak RPS ini.';
    end if;

    if catatan is null or btrim(catatan) = '' then
        raise exception 'Catatan alasan penolakan wajib diisi.';
    end if;

    update public.rps
    set status = 'ditolak', catatan_bpm = catatan, diproses_oleh_bpm = auth.uid(), diproses_pada_bpm = now()
    where id = target_rps_id and status = 'disetujui';

    if not found then
        raise exception 'RPS sudah tidak berstatus "disetujui" (mungkin sudah diproses pihak lain).';
    end if;
end;
$$;

grant execute on function public.validasi_bpm_rps(uuid, text) to authenticated;
grant execute on function public.tolak_bpm_rps(uuid, text) to authenticated;


-- Ganti ajukan_rps() sekali lagi - sekarang juga membersihkan kolom BPM
-- (catatan_bpm dkk) saat re-submit, supaya catatan penolakan lama (dari
-- Kaprodi ATAU BPM) tidak nyangkut ke siklus review berikutnya. Perilaku
-- routing-nya SENGAJA tidak berubah: ajukan_rps() SELALU set status jadi
-- 'diajukan' (antrian Kaprodi) apa pun status sebelumnya (ditolak Kaprodi
-- ATAU ditolak BPM) - ini yang membuat "ajukan ulang ke Kaprodi dari awal"
-- otomatis berlaku tanpa logika tambahan.
create or replace function public.ajukan_rps(target_rps_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
    update public.rps r
    set status = 'diajukan',
        catatan_kaprodi = null, diproses_oleh = null, diproses_pada = null,
        catatan_bpm = null, diproses_oleh_bpm = null, diproses_pada_bpm = null,
        diajukan_pada = now()
    from public.mata_kuliah mk
    where r.id = target_rps_id
      and mk.id = r.mata_kuliah_id
      and mk.koordinator_user_id = auth.uid()
      and r.status in ('draft', 'ditolak');

    if not found then
        raise exception 'RPS tidak ditemukan, Anda bukan koordinatornya, atau statusnya tidak bisa diajukan.';
    end if;
end;
$$;


-- =============================================================================
-- PENYESUAIAN: Nama Koordinator/Kaprodi/BPM & Rumpun MK ditarik OTOMATIS dari
-- database (bukan diketik manual/dari config/pejabat.txt lagi) saat mengisi RPS.
-- =============================================================================

-- Ganti nama kolom "ranah_topik" jadi "rumpun_mk" - konsep yang sama, cuma
-- istilahnya disamakan dengan yang dipakai di form/dokumen RPS. Tidak perlu
-- migrasi data terpisah - RENAME COLUMN otomatis mempertahankan isi. Dibungkus
-- pengecekan supaya aman dijalankan ulang (kolom "ranah_topik" sudah tidak
-- ada lagi setelah rename pertama - tanpa pengecekan ini, ALTER akan gagal
-- kalau seluruh file ini dijalankan ulang, melanggar pola idempotent yang
-- dipegang di seluruh file ini).
do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'mata_kuliah' and column_name = 'ranah_topik'
    ) then
        alter table public.mata_kuliah rename column ranah_topik to rumpun_mk;
    end if;
end $$;

-- RPC khusus untuk Dosen BIASA (bukan admin/kaprodi) bisa tahu nama Kaprodi
-- Prodi-nya & nama BPM, TANPA perlu akses baca penuh ke tabel pengguna orang
-- lain (policy pengguna saat ini cuma izinkan baca profil sendiri + admin/
-- kaprodi baca semua - Dosen biasa TIDAK match salah satu dari itu untuk
-- baris milik orang lain). SECURITY DEFINER supaya bisa baca lintas baris,
-- tapi cakupannya SENGAJA dipersempit HANYA nama+email, bukan seluruh kolom.
create or replace function public.get_pejabat_prodi(target_prodi_id uuid)
returns table(kaprodi_nama text, kaprodi_email text)
language sql
security definer
set search_path = public
stable
as $$
    select nama, email from public.pengguna
    where role = 'kaprodi' and prodi_id = target_prodi_id
    limit 1;
$$;

create or replace function public.get_pejabat_bpm()
returns table(bpm_nama text, bpm_email text)
language sql
security definer
set search_path = public
stable
as $$
    select nama, email from public.pengguna
    where role = 'bpm'
    limit 1;
$$;

grant execute on function public.get_pejabat_prodi(uuid) to authenticated;
grant execute on function public.get_pejabat_bpm() to authenticated;

-- =============================================================================
-- PENYESUAIAN: Hapus kolom dosen_pengembang (mata_kuliah) - peninggalan
-- impor Excel lama, sudah tidak dipakai di alur RPS manapun (field "Dosen
-- Pengembang RPS (Koordinator)" di form RPS diambil dari sistem koordinator,
-- bukan dari kolom ini). Aman dijalankan berkali-kali.
-- =============================================================================
alter table public.mata_kuliah drop column if exists dosen_pengembang;

-- =============================================================================
-- PENYESUAIAN: Kolom pejabat_utama + cara menetapkannya secara eksplisit -
-- sebelum ini, get_pejabat_prodi()/get_pejabat_bpm() pakai "limit 1" TANPA
-- "order by" sama sekali. Kalau ada LEBIH DARI SATU akun dengan role yang
-- sama (mis. 2 akun ber-role bpm), Postgres mengembalikan salah satu secara
-- SEMBARANG (tidak konsisten, tidak bisa dipilih) - itulah sebabnya nama
-- yang muncul di RPS kadang bukan yang dimaksud. Sekarang Admin bisa
-- menetapkan secara eksplisit siapa yang "resmi" lewat set_pejabat_utama().
-- =============================================================================
alter table public.pengguna add column if not exists pejabat_utama boolean not null default false;

create or replace function public.set_pejabat_utama(target_user_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
    v_role text;
    v_prodi_id uuid;
begin
    if not public.is_admin() then
        raise exception 'Hanya Admin yang boleh menetapkan pejabat resmi.';
    end if;

    select role, prodi_id into v_role, v_prodi_id from public.pengguna where id = target_user_id;
    if v_role is null then
        raise exception 'Akun tidak ditemukan.';
    end if;
    if v_role not in ('kaprodi', 'bpm') then
        raise exception 'Hanya akun ber-role Kaprodi atau BPM yang bisa ditetapkan sebagai pejabat resmi.';
    end if;

    -- Lepas status pejabat_utama dari akun LAIN dengan role sama - untuk
    -- Kaprodi, dibatasi ke Prodi yang sama juga (tiap Prodi punya Kaprodi
    -- resminya sendiri-sendiri, bukan cuma satu se-institusi seperti BPM).
    if v_role = 'kaprodi' then
        update public.pengguna set pejabat_utama = false
        where role = 'kaprodi' and prodi_id = v_prodi_id and id <> target_user_id;
    else
        update public.pengguna set pejabat_utama = false
        where role = 'bpm' and id <> target_user_id;
    end if;

    update public.pengguna set pejabat_utama = true where id = target_user_id;
end;
$$;

grant execute on function public.set_pejabat_utama(uuid) to authenticated;

-- Urutan baru: pejabat_utama = true diprioritaskan, baru fallback ke akun
-- terlama (created_at) kalau belum ada yang ditetapkan sama sekali - supaya
-- tetap ada hasil (bukan kosong) bahkan sebelum Admin sempat menetapkan.
create or replace function public.get_pejabat_prodi(target_prodi_id uuid)
returns table(kaprodi_nama text, kaprodi_email text)
language sql
security definer
set search_path = public
stable
as $$
    select nama, email from public.pengguna
    where role = 'kaprodi' and prodi_id = target_prodi_id
    order by pejabat_utama desc, created_at asc
    limit 1;
$$;

create or replace function public.get_pejabat_bpm()
returns table(bpm_nama text, bpm_email text)
language sql
security definer
set search_path = public
stable
as $$
    select nama, email from public.pengguna
    where role = 'bpm'
    order by pejabat_utama desc, created_at asc
    limit 1;
$$;

grant execute on function public.get_pejabat_prodi(uuid) to authenticated;
grant execute on function public.get_pejabat_bpm() to authenticated;

-- =============================================================================
-- PENYESUAIAN: Hapus Mata Kuliah yang lebih pintar - sebelum ini,
-- "on delete restrict" di rps.mata_kuliah_id menolak SEMUA penghapusan kalau
-- ada RPS apa pun yang menyinggung Mata Kuliah itu, TERMASUK RPS yang masih
-- berstatus draft (belum pernah diajukan/dilihat siapa pun selain
-- koordinatornya sendiri). Ini kadang bikin Mata Kuliah yang salah input
-- tidak bisa dihapus, padahal drafnya sendiri aman untuk ikut terhapus.
-- Sekarang: draft ikut terhapus otomatis bersama Mata Kuliah-nya, tapi RPS
-- yang SUDAH diajukan/disetujui/divalidasi/ditolak tetap melindungi Mata
-- Kuliah dari penghapusan seperti sebelumnya (ada jejak/riwayat resmi).
-- =============================================================================
create or replace function public.hapus_mata_kuliah_aman(
    target_prodi_id uuid, target_tahun_kurikulum integer, target_kode_mk text
)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
    v_mk_id uuid;
    v_ada_non_draft boolean;
begin
    if not (public.is_admin() or public.is_kaprodi_of(target_prodi_id)) then
        raise exception 'Anda tidak berwenang menghapus Mata Kuliah ini.';
    end if;

    select id into v_mk_id from public.mata_kuliah
    where prodi_id = target_prodi_id
      and tahun_kurikulum = target_tahun_kurikulum
      and kode_mk = target_kode_mk;

    if v_mk_id is null then
        return; -- sudah tidak ada (atau tidak cocok) - anggap aman, tidak perlu error
    end if;

    select exists(
        select 1 from public.rps where mata_kuliah_id = v_mk_id and status <> 'draft'
    ) into v_ada_non_draft;

    if v_ada_non_draft then
        raise exception 'Mata Kuliah ini sudah pernah diajukan/disetujui/divalidasi - tidak bisa dihapus.';
    end if;

    -- Aman: satu-satunya RPS yang mungkin masih menyinggung Mata Kuliah ini
    -- (kalau ada) berstatus draft murni - hapus dulu, baru Mata Kuliahnya.
    delete from public.rps where mata_kuliah_id = v_mk_id and status = 'draft';
    delete from public.mata_kuliah where id = v_mk_id;
end;
$$;

grant execute on function public.hapus_mata_kuliah_aman(uuid, integer, text) to authenticated;

-- =============================================================================
-- PENYESUAIAN: Kaprodi bisa membuka kembali RPS yang SUDAH divalidasi BPM,
-- untuk skenario revisi (mis. ada kesalahan yang baru ketahuan setelah
-- final). RPS kembali ke status draft (isi dokumennya TETAP seperti versi
-- tervalidasi terakhir, koordinator tinggal edit dari situ) dan otomatis
-- HILANG dari "RPS Tervalidasi" sampai diajukan & divalidasi ulang dari
-- awal (Kaprodi -> BPM, bukan cuma re-approve sepihak). Alasan pembukaan
-- disimpan di catatan_kaprodi supaya koordinator tahu kenapa - lihat
-- app.py bagian tampilan sidebar untuk cara catatan ini ditampilkan ke
-- Dosen (dibedakan dari catatan penolakan biasa).
-- =============================================================================
create or replace function public.buka_kembali_rps(target_rps_id uuid, catatan text default null)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
    v_prodi_id uuid;
begin
    select mk.prodi_id into v_prodi_id
    from public.rps r
    join public.mata_kuliah mk on mk.id = r.mata_kuliah_id
    where r.id = target_rps_id;

    if v_prodi_id is null then
        raise exception 'RPS tidak ditemukan.';
    end if;

    if not (public.is_admin() or public.is_kaprodi_of(v_prodi_id)) then
        raise exception 'Anda tidak berwenang membuka kembali RPS ini.';
    end if;

    update public.rps
    set status = 'draft',
        catatan_kaprodi = catatan,
        diproses_oleh = null, diproses_pada = null,
        catatan_bpm = null, diproses_oleh_bpm = null, diproses_pada_bpm = null,
        diajukan_pada = null
    where id = target_rps_id and status = 'divalidasi';

    if not found then
        raise exception 'RPS tidak ditemukan, atau statusnya bukan "divalidasi" - cuma RPS yang sudah final yang bisa dibuka kembali dengan cara ini.';
    end if;
end;
$$;

grant execute on function public.buka_kembali_rps(uuid, text) to authenticated;

-- =============================================================================
-- PENYESUAIAN: Sinkronisasi nama Kaprodi/BPM ke SEMUA RPS yang sudah ada -
-- nama_kaprodi/nama_biro_pjm yang tersimpan di rps.data "membeku" sejak RPS
-- itu pertama dibuat (lihat catatan di rps_browse.py) - kalau pejabat resmi
-- berganti SESUDAHNYA, RPS lama tidak otomatis ikut ter-update (dokumen
-- FINAL yang diunduh sudah diperbaiki terpisah supaya selalu pakai nama
-- terkini, tapi tampilan info_umum saat Dosen membuka RPS-nya sendiri, atau
-- cadangan lokal yang diunduh, masih memakai nilai lama tersimpan). Fungsi
-- ini menimpa nama_kaprodi/nama_biro_pjm di SEMUA baris rps sekaligus
-- dengan nilai TERKINI dari get_pejabat_prodi()/get_pejabat_bpm() - jalankan
-- lewat tombol "Sinkronkan Nama Pejabat" di Panel Admin, aman diulang kapan
-- saja (idempotent, tidak menyentuh field lain).
-- =============================================================================
create or replace function public.sinkronkan_nama_pejabat()
returns integer
language plpgsql
security definer set search_path = public
as $$
declare
    v_count integer := 0;
    r record;
    v_nama_kaprodi text;
    v_nama_bpm text;
begin
    if not public.is_admin() then
        raise exception 'Hanya Admin yang boleh menjalankan sinkronisasi ini.';
    end if;

    select bpm_nama into v_nama_bpm from public.get_pejabat_bpm();

    for r in
        select rps.id as rps_id, mk.prodi_id as prodi_id
        from public.rps
        join public.mata_kuliah mk on mk.id = rps.mata_kuliah_id
    loop
        select kaprodi_nama into v_nama_kaprodi from public.get_pejabat_prodi(r.prodi_id);

        update public.rps
        set data = jsonb_set(
            jsonb_set(
                coalesce(data, '{}'::jsonb),
                '{info_umum,nama_kaprodi}', to_jsonb(coalesce(v_nama_kaprodi, '')), true
            ),
            '{info_umum,nama_biro_pjm}', to_jsonb(coalesce(v_nama_bpm, '')), true
        )
        where id = r.rps_id;

        v_count := v_count + 1;
    end loop;

    return v_count;
end;
$$;

grant execute on function public.sinkronkan_nama_pejabat() to authenticated;