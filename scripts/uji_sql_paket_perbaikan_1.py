"""Uji SQL Paket Perbaikan 1 pada Postgres sekali-pakai yang meniru Supabase
(peran authenticated/anon, auth.uid() dari request.jwt.claim.sub).
Jalankan: python3 uji_sql.py  (container rps-uji-db harus menyala)."""
import subprocess, sys

U = {  # id pengguna uji
    "admin": "00000000-0000-0000-0000-0000000000a1",
    "bpm": "00000000-0000-0000-0000-0000000000b1",
    "kap1": "00000000-0000-0000-0000-0000000000c1",
    "d1": "00000000-0000-0000-0000-0000000000d1",
    "d2": "00000000-0000-0000-0000-0000000000d2",
}
P1, P2 = "10000000-0000-0000-0000-000000000001", "10000000-0000-0000-0000-000000000002"


def psql(sql):
    r = subprocess.run(["sudo", "docker", "exec", "-i", "rps-uji-db", "psql", "-U", "postgres", "-qAtX",
                        "-v", "ON_ERROR_STOP=1"], input=sql, capture_output=True, text=True)
    return r.returncode, (r.stdout.strip(), r.stderr.strip())


def sebagai(peran, sql, role="authenticated"):
    sub = U.get(peran, "")
    return psql(f"begin; set local role {role}; select set_config('request.jwt.claim.sub','{sub}',true) \\g /dev/null\n{sql}\ncommit;")


def mk(kode):
    return f"(select id from public.mata_kuliah where kode_mk='{kode}')"


def rps(kode):
    return f"(select id from public.rps where mata_kuliah_id={mk(kode)})"


AI_OK = """'{"info_umum":{"level_ai":"Assisted AI","deskripsi_ai":"AI dipakai untuk menyusun draf materi."}}'"""

seed = f"""
alter table public.rps add column if not exists dikunci_admin boolean not null default false;
\\i /sql/paket-perbaikan-1a-statistik.sql
\\i /sql/paket-perbaikan-1b-wajib-ai.sql
insert into public.prodi(id,nama) values ('{P1}','Informatika PJJ S1'),('{P2}','Sistem Informasi PJJ S1');
insert into auth.users(id,email) values
 ('{U['admin']}','admin@x'),('{U['bpm']}','bpm@x'),('{U['kap1']}','kap1@x'),('{U['d1']}','d1@x'),('{U['d2']}','d2@x');
update public.pengguna set role='admin' where id='{U['admin']}';
update public.pengguna set role='bpm', nama='Ibu BPM' where id='{U['bpm']}';
update public.pengguna set role='kaprodi', prodi_id='{P1}', nama='Kaprodi IF' where id='{U['kap1']}';
update public.pengguna set nama='Dosen Satu' where id='{U['d1']}';
update public.pengguna set nama=null where id='{U['d2']}';  -- tanpa nama: harus jatuh ke email
insert into public.whitelist_pendaftaran(nip,nama) values ('999','Calon Dosen');
insert into public.mata_kuliah(prodi_id,kode_mk,nama_mk,tahun_kurikulum,koordinator_user_id,koordinator_nip) values
 ('{P1}','MK1','Draft',2026,'{U['d1']}',null),
 ('{P1}','MK2','Diajukan',2026,'{U['d1']}',null),
 ('{P1}','MK3','Disetujui',2026,'{U['d2']}',null),
 ('{P1}','MK4','Final tanpa AI',2026,'{U['d2']}',null),
 ('{P1}','MK5','Koordinator pra-daftar',2026,null,'999'),
 ('{P1}','MK6','Tanpa koordinator',2026,null,null),
 ('{P1}','MK7','Ditolak tanpa AI',2026,'{U['d1']}',null),
 ('{P2}','MK8','SI draft',2026,'{U['d2']}',null),
 ('{P2}','MK9','SI final',2026,'{U['d2']}',null);
insert into public.rps(mata_kuliah_id,dosen_user_id,status,data) values
 ({mk('MK1')},'{U['d1']}','draft','{{}}'),
 ({mk('MK2')},'{U['d1']}','diajukan',{AI_OK}),
 ({mk('MK3')},'{U['d2']}','disetujui',{AI_OK}),
 ({mk('MK4')},'{U['d2']}','divalidasi','{{}}'),
 ({mk('MK7')},'{U['d1']}','ditolak','{{}}'),
 ({mk('MK8')},'{U['d2']}','draft','{{}}'),
 ({mk('MK9')},'{U['d2']}','divalidasi',{AI_OK});
"""

hasil = []


def cek(nama, kondisi, detail=""):
    hasil.append((nama, bool(kondisi)))
    print(("LULUS " if kondisi else "GAGAL ") + nama + (f"  [{detail}]" if detail and not kondisi else ""))


rc, (out, err) = psql(seed)
if rc:
    print("seed gagal:", err); sys.exit(1)

Q_STAT = "select kode_mk||':'||status||':'||coalesce(koordinator_nama,'-') from public.statistik_pengisian_rps({}) order by kode_mk;"
Q_LAMA = ("select mk.kode_mk||':'||coalesce((select r.status from public.rps r where r.mata_kuliah_id=mk.id),'belum') "
          "from public.mata_kuliah mk order by mk.kode_mk;")

_, (adm, _) = sebagai("admin", Q_STAT.format("null"))
_, (bpm, e) = sebagai("bpm", Q_STAT.format("null"))
_, (adm_lama, _) = sebagai("admin", Q_LAMA)
_, (bpm_lama, _) = sebagai("bpm", Q_LAMA)
print("\nAdmin (fungsi baru):", adm.replace("\n", " | "))
print("BPM cara lama (bug):", bpm_lama.replace("\n", " | "), "\n")
cek("UAT-10/11 BPM = Admin lewat fungsi baru", adm and adm == bpm, e)
cek("Admin: fungsi baru = cara lama (tidak ada regresi)",
    [l.rsplit(":", 1)[0] for l in adm.splitlines()] == adm_lama.splitlines())
cek("Bug lama terreproduksi (BPM cara lama melihat draft sebagai belum)", "MK1:belum" in bpm_lama)
cek("UAT-12 nama koordinator: akun bernama", "MK1:draft:Dosen Satu" in adm)
cek("UAT-12 nama koordinator: akun tanpa nama -> email", "MK3:disetujui:d2@x" in adm)
cek("UAT-12 nama koordinator: pra-daftar -> nama whitelist", "MK5:belum:Calon Dosen" in adm)
cek("UAT-12 tanpa koordinator -> kosong", "MK6:belum:-" in adm)
_, (isi, _) = sebagai("bpm", "select count(*) from public.rps where status in ('draft','diajukan','ditolak');")
cek("UAT-14 BPM tetap tidak bisa membaca isi RPS draft/diajukan/ditolak", isi == "0", isi)
rc, (k1, _) = sebagai("kap1", Q_STAT.format(f"'{P1}'"))
cek("UAT-15 Kaprodi: statistik prodinya sendiri", rc == 0 and len(k1.splitlines()) == 7)
rc, (_, e) = sebagai("kap1", Q_STAT.format(f"'{P2}'"))
cek("UAT-15 Kaprodi: prodi lain ditolak", rc != 0 and "tidak berwenang" in e, e)
rc, (_, e) = sebagai("kap1", Q_STAT.format("null"))
cek("UAT-15 Kaprodi: semua prodi (null) ditolak", rc != 0 and "tidak berwenang" in e, e)
rc, (_, e) = sebagai("d1", Q_STAT.format("null"))
cek("UAT-16 Dosen biasa ditolak", rc != 0 and "tidak berwenang" in e, e)
rc, (_, e) = sebagai("", Q_STAT.format("null"), role="anon")
cek("Anon (belum login) tidak bisa memanggil", rc != 0 and "permission denied" in e, e)

# --- BUG-01: trigger wajib AI ---
def ajukan(peran, kode):
    return sebagai(peran, f"select public.ajukan_rps({rps(kode)});")


def set_ai(kode, level, desk):
    import json
    data = json.dumps({"info_umum": {"level_ai": level, "deskripsi_ai": desk}}).replace("'", "''")
    psql(f"update public.rps set data='{data}' where id={rps(kode)};")


def status(kode):
    return psql(f"select status from public.rps where id={rps(kode)};")[1][0]


rc, (_, e) = ajukan("d1", "MK1")
cek("UAT-01 ajukan tanpa Level AI ditolak", rc != 0 and "Level Penggunaan AI" in e and status("MK1") == "draft", e)
set_ai("MK1", "Assisted AI", "")
rc, (_, e) = ajukan("d1", "MK1")
cek("UAT-02 Level ada, Deskripsi kosong ditolak", rc != 0 and "Deskripsi" in e, e)
set_ai("MK1", "Assisted AI", "   \n  ")
rc, (_, e) = ajukan("d1", "MK1")
cek("UAT-03a Deskripsi hanya spasi ditolak", rc != 0 and "Deskripsi" in e, e)
set_ai("MK1", "Assisted AI", "pakai AI.")
rc, (_, e) = ajukan("d1", "MK1")
cek("UAT-03b Deskripsi 9 karakter ditolak", rc != 0 and "Deskripsi" in e, e)
set_ai("MK1", "Level Ngawur", "AI dipakai untuk menyusun draf materi.")
rc, (_, e) = ajukan("d1", "MK1")
cek("Level di luar pilihan resmi ditolak", rc != 0 and "Level" in e, e)
set_ai("MK1", "Tanpa AI", "Mata kuliah ini fokus praktik manual.")
rc, (_, e) = ajukan("d1", "MK1")
cek("UAT-05 Tanpa AI + alasan berhasil diajukan", rc == 0 and status("MK1") == "diajukan", e)
rc, (_, e) = ajukan("d1", "MK7")
cek("UAT-09 ajukan ulang RPS ditolak tanpa AI diminta melengkapi", rc != 0 and status("MK7") == "ditolak", e)
cek("UAT-08 RPS final tanpa AI tetap divalidasi", status("MK4") == "divalidasi")
rc, (_, e) = sebagai("kap1", f"select public.setujui_rps({rps('MK2')}, null);")
cek("Kaprodi menyetujui tidak terganggu trigger", rc == 0 and status("MK2") == "disetujui", e)
rc, (_, e) = sebagai("bpm", f"select public.validasi_bpm_rps({rps('MK2')}, null);")
cek("BPM memvalidasi tidak terganggu trigger", rc == 0 and status("MK2") == "divalidasi", e)
rc, (_, e) = sebagai("kap1", f"select public.buka_kembali_rps({rps('MK4')}, 'revisi');")
cek("Kaprodi membuka kembali RPS final tanpa AI tetap bisa", rc == 0 and status("MK4") == "draft", e)
rc, (_, e) = ajukan("d2", "MK4")
cek("RPS yang dibuka kembali wajib melengkapi AI saat diajukan ulang", rc != 0 and "Level" in e, e)
rc, (_, e) = psql(f"update public.rps set status='diajukan' where id={rps('MK8')};")
cek("UAT-07 pengaman berlaku walau status diubah di luar ajukan_rps()", rc != 0 and "Level" in e, e)

_, (bpm2, _) = sebagai("bpm", Q_STAT.format("null"))
cek("UAT-13 perubahan status langsung terlihat di statistik BPM", "MK1:diajukan" in bpm2 and "MK4:draft" in bpm2)

lulus = sum(ok for _, ok in hasil)
print(f"\n{lulus}/{len(hasil)} lulus")
sys.exit(0 if lulus == len(hasil) else 1)
