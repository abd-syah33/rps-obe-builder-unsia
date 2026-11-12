# -*- coding: utf-8 -*-
"""Uji Paket Perbaikan 1 sisi Python (tanpa database).
Jalankan dari akar repo: python -m pytest -q tests/"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from validasi_rps import LEVEL_AI_PILIHAN, MIN_DESKRIPSI_AI, masalah_penggunaan_ai

DESK_OK = "AI dipakai untuk menyusun draf materi."


# ---------------- BUG-01: wajib Level & Deskripsi AI ----------------
@pytest.mark.parametrize("info, kata_kunci", [
    (None, ["Level", "Deskripsi"]),
    ({}, ["Level", "Deskripsi"]),
    ({"level_ai": "", "deskripsi_ai": DESK_OK}, ["Level"]),
    ({"level_ai": "Ngawur", "deskripsi_ai": DESK_OK}, ["Level"]),
    ({"level_ai": "Assisted AI", "deskripsi_ai": ""}, ["belum diisi"]),
    ({"level_ai": "Assisted AI", "deskripsi_ai": "   \n\t "}, ["belum diisi"]),
    ({"level_ai": "Assisted AI", "deskripsi_ai": "pakai AI."}, ["terlalu singkat"]),
])
def test_ai_belum_lengkap(info, kata_kunci):
    masalah = " | ".join(masalah_penggunaan_ai(info))
    for k in kata_kunci:
        assert k in masalah


@pytest.mark.parametrize("level", LEVEL_AI_PILIHAN)
def test_ai_lengkap_semua_level(level):
    assert masalah_penggunaan_ai({"level_ai": level, "deskripsi_ai": DESK_OK}) == []


def test_batas_panjang_dihitung_setelah_spasi_dirapikan():
    pas = "a" * MIN_DESKRIPSI_AI
    assert masalah_penggunaan_ai({"level_ai": "Tanpa AI", "deskripsi_ai": f"  {pas}  "}) == []
    # 19 huruf + spasi berulang di tengah tetap kurang dari 20 setelah dirapikan
    kurang = "a" * 9 + "     \n\n   " + "b" * 9
    assert masalah_penggunaan_ai({"level_ai": "Tanpa AI", "deskripsi_ai": kurang})


def test_angka_sama_dengan_sql():
    sql = open(os.path.join(os.path.dirname(__file__), "..", "sql", "paket-perbaikan-1b-wajib-ai.sql")).read()
    assert f"< {MIN_DESKRIPSI_AI}" in sql
    for level in LEVEL_AI_PILIHAN:
        assert f"'{level}'" in sql


# ---------------- BUG-02: statistik lewat fungsi database ----------------
class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, data):
        self._data = data

    def eq(self, *a, **k):
        return self

    def select(self, *a, **k):
        return self

    def execute(self):
        if isinstance(self._data, Exception):
            raise self._data
        return _Resp(self._data)


class FakeClient:
    def __init__(self, rpc_data, tabel_data=None):
        self.rpc_data, self.tabel_data, self.rpc_dipanggil = rpc_data, tabel_data or [], []

    def rpc(self, nama, params):
        self.rpc_dipanggil.append((nama, params))
        return _Query(self.rpc_data)

    def table(self, nama):
        return _Query(self.tabel_data)


def _baris(kode, status, prodi="Informatika PJJ S1", tahun=2026, nama="Dosen Satu"):
    return {"kode_mk": kode, "nama_mk": kode, "prodi_id": "p", "prodi_nama": prodi, "tahun_kurikulum": tahun,
            "koordinator_user_id": "u", "koordinator_nip": None, "koordinator_nama": nama, "status": status}


@pytest.fixture()
def stats_ui():
    import stats_ui as s
    s.get_rps_progress_raw.clear()
    return s


def test_statistik_memakai_fungsi_dan_status_draft_tidak_hilang(stats_ui):
    client = FakeClient([_baris("MK1", "draft"), _baris("MK2", "diajukan"), _baris("MK3", "belum"),
                         _baris("LAMA", "draft", tahun=2021)])
    rows = stats_ui.get_rps_progress_raw(client, prodi_id=None)
    assert client.rpc_dipanggil == [("statistik_pengisian_rps", {"target_prodi_id": None})]
    assert sorted(r["status"] for r in rows) == ["belum", "diajukan", "draft"]  # kurikulum 2021 tersaring
    assert all(r["koordinator_nama"] == "Dosen Satu" for r in rows)


def test_jatuh_balik_ke_cara_lama_bila_fungsi_belum_ada(stats_ui):
    lama = [{"kode_mk": "MK1", "nama_mk": "MK1", "prodi_id": "p", "tahun_kurikulum": 2026,
             "koordinator_user_id": None, "koordinator_nip": None,
             "prodi": {"nama": "Informatika PJJ S1"}, "rps": [{"status": "draft"}]}]
    client = FakeClient(Exception("Could not find the function public.statistik_pengisian_rps"), lama)
    rows = stats_ui.get_rps_progress_raw(client, prodi_id="p")
    assert [r["status"] for r in rows] == ["draft"]
    assert "koordinator_nama" not in rows[0]


def test_tabel_per_dosen_memakai_nama_dari_fungsi():
    """BPM tidak bisa membaca tabel pengguna; tabel Per Dosen harus memakai
    koordinator_nama dari fungsi database, tanpa menyentuh client."""
    from streamlit.testing.v1 import AppTest

    def app():
        import os, sys
        sys.path.insert(0, os.getcwd())
        from stats_ui import render_tabel_per_dosen

        def b(kode, status, nama):
            return {"kode_mk": kode, "nama_mk": kode, "prodi_nama": "SI", "tahun_kurikulum": 2026,
                    "koordinator_user_id": None, "koordinator_nip": None,
                    "koordinator_nama": nama, "status": status}
        rows = [b("MK1", "draft", "Dosen Satu"), b("MK2", "diajukan", "Dosen Satu"),
                b("MK3", "divalidasi", "Dosen Dua"), b("MK4", "belum", None)]
        render_tabel_per_dosen(None, rows, tampilkan_chart=False)

    at = AppTest.from_function(app).run(timeout=30)
    assert not at.exception
    df = at.dataframe[0].value
    satu = df[df["Dosen"] == "Dosen Satu"].iloc[0]
    assert satu["MK Diampu"] == 2 and satu["\U0001F4DD Draft"] == 1 and satu["\U0001F4E4 Diajukan"] == 1
    assert set(df["Dosen"]) == {"Dosen Satu", "Dosen Dua"}
    assert "MK4" in at.warning[0].value  # MK tanpa koordinator tetap diperingatkan
