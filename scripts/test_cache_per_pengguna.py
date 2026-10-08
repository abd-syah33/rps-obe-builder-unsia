"""Uji regresi: cache tidak boleh tercampur antar pengguna/peran.

Klien palsu meniru RLS: BPM hanya melihat RPS berstatus disetujui/divalidasi,
Admin melihat semua. Jalankan:  python scripts/test_cache_per_pengguna.py
Tidak butuh koneksi Supabase.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.getLogger("streamlit").setLevel(logging.ERROR)

import stats_ui  # noqa: E402
import rps_store  # noqa: E402

MK = [
    {"kode_mk": "IF101", "nama_mk": "A", "prodi_id": 1, "tahun_kurikulum": 2026,
     "koordinator_user_id": None, "koordinator_nip": None, "prodi": {"nama": "Informatika"}, "status": "draft"},
    {"kode_mk": "IF102", "nama_mk": "B", "prodi_id": 1, "tahun_kurikulum": 2026,
     "koordinator_user_id": None, "koordinator_nip": None, "prodi": {"nama": "Informatika"}, "status": "disetujui"},
    {"kode_mk": "MN101", "nama_mk": "C", "prodi_id": 2, "tahun_kurikulum": 2026,
     "koordinator_user_id": None, "koordinator_nip": None, "prodi": {"nama": "Manajemen"}, "status": "diajukan"},
]


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, role, table, calls):
        self.role, self.table, self.filters, self.calls = role, table, {}, calls

    def select(self, *_a, **_k): return self
    def order(self, *_a, **_k): return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def _rls_rps_visible(self, status, prodi_id):
        if self.role == "admin": return True
        if self.role == "bpm": return status in ("disetujui", "divalidasi")
        if self.role.startswith("kaprodi"): return prodi_id == int(self.role[-1])
        return False

    def execute(self):
        self.calls.append((self.role, self.table))
        if self.table == "mata_kuliah":
            out = []
            for m in MK:
                vis = self._rls_rps_visible(m["status"], m["prodi_id"])
                row = {k: v for k, v in m.items() if k != "status"}
                row["rps"] = [{"status": m["status"]}] if vis else []
                if "prodi_id" in self.filters and m["prodi_id"] != self.filters["prodi_id"]:
                    continue
                out.append(row)
            return _Resp(out)
        if self.table == "rps":
            out = [{"id": i, "status": m["status"], "prodi": m["prodi_id"]} for i, m in enumerate(MK)
                   if m["status"] == self.filters.get("status") and self._rls_rps_visible(m["status"], m["prodi_id"])]
            return _Resp(out)
        return _Resp([])


class FakeClient:
    def __init__(self, role, calls):
        self.role, self.calls = role, calls

    def table(self, name):
        return _Query(self.role, name, self.calls)


def as_user(scope):
    stats_ui.cache_scope = lambda: scope
    rps_store.cache_scope = lambda: scope


def main():
    calls = []
    admin, bpm = FakeClient("admin", calls), FakeClient("bpm", calls)
    kap1, kap2 = FakeClient("kaprodi1", calls), FakeClient("kaprodi2", calls)

    # 1) Statistik institusi: Admin memuat duluan, lalu BPM (dalam jendela TTL).
    as_user("u-admin|admin|None")
    st_admin = sorted(r["status"] for r in stats_ui.get_rps_progress_raw(admin, prodi_id=None))
    as_user("u-bpm|bpm|None")
    st_bpm = sorted(r["status"] for r in stats_ui.get_rps_progress_raw(bpm, prodi_id=None))
    assert st_admin == ["diajukan", "disetujui", "draft"], st_admin
    assert st_bpm == ["belum", "belum", "disetujui"], f"BPM melihat data Admin: {st_bpm}"
    print("PASS statistik: Admin dan BPM masing-masing melihat datanya sendiri")

    # 2) Antrian Kaprodi: Kaprodi prodi 2 tidak boleh melihat cache Kaprodi prodi 1.
    as_user("u-k1|kaprodi|1")
    q1 = rps_store.list_diajukan(kap1)
    as_user("u-k2|kaprodi|2")
    q2 = rps_store.list_diajukan(kap2)
    assert [r["prodi"] for r in q1] == [] and [r["prodi"] for r in q2] == [2], (q1, q2)
    print("PASS antrian Kaprodi: tidak bocor antar Prodi")

    # 3) Setelah transisi status, cache dibuang untuk semua pengguna.
    n_before = len(calls)
    as_user("u-bpm|bpm|None")
    stats_ui.get_rps_progress_raw(bpm, prodi_id=None)          # masih dari cache
    assert len(calls) == n_before, "seharusnya masih tersaji dari cache"
    rps_store.segarkan_cache_rps()
    stats_ui.get_rps_progress_raw(bpm, prodi_id=None)          # harus query ulang
    assert len(calls) == n_before + 1, "cache tidak dibuang setelah transisi status"
    print("PASS segarkan_cache_rps: data langsung terbaru setelah aksi")

    # 4) .clear() lama tetap berfungsi (kompatibilitas).
    rps_store.list_bpm_queue.clear(); rps_store.list_diajukan.clear(); stats_ui.get_rps_progress_raw.clear()
    print("PASS kompatibilitas .clear()")


if __name__ == "__main__":
    main()
