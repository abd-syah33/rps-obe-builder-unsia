# -*- coding: utf-8 -*-
"""Layanan ekspor RPS Builder v2: data RPS (JSON) masuk, Word/PDF keluar.

Sengaja tipis: memakai docx_export.py v1 apa adanya supaya dokumen resmi v2
identik dengan v1. Tidak punya akses database; hanya menerima permintaan dari
server Next.js yang membawa token rahasia (EKSPOR_TOKEN).
"""
import hashlib
import io
import hmac
import json
import os
import threading
import time
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from docx_export import BOBOT_KATEGORI, build_docx, build_pdf_via_libreoffice

TOKEN = os.environ.get("EKSPOR_TOKEN", "")
CACHE = Path(os.environ.get("EKSPOR_CACHE", "/tmp/ekspor-cache"))
CACHE_MAKS_BYTE = 200 * 1024 * 1024
CACHE_UMUR_DETIK = 7 * 24 * 3600
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(title="RPS Builder - layanan ekspor", docs_url=None, redoc_url=None)
_kunci_pdf = threading.Lock()  # LibreOffice ~220 MB per konversi: satu per satu


class Cpl(BaseModel):
    kode: str
    deskripsi: str = ""


class DataRps(BaseModel):
    prodi: str
    mk: dict          # {"Nama Mata Kuliah", "Kode MK", "SKS", "Semester"} seperti mk_row v1
    cpl: list[Cpl]
    info_umum: dict
    cpmk_data: dict
    pertemuan_data: dict
    referensi_data: list = []
    komponen_data: dict = {}


def cek_token(authorization: str = Header(default="")):
    if not TOKEN or not hmac.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(status_code=401, detail="Token tidak valid")


def _docx_bytes(d: DataRps) -> bytes:
    cpl_df = pd.DataFrame({"Kode CPL": [c.kode for c in d.cpl], "Deskripsi CPL": [c.deskripsi for c in d.cpl]})
    buf = build_docx(
        prodi=d.prodi, mk_row=d.mk, cpl_df=cpl_df, info_umum=d.info_umum,
        cpmk_data={int(k): v for k, v in d.cpmk_data.items()},
        pertemuan_data={int(k): v for k, v in d.pertemuan_data.items()},
        referensi_data=d.referensi_data,
        komponen_data={int(k): v for k, v in d.komponen_data.items()},
        bobot_kategori=BOBOT_KATEGORI,
    )
    return buf.getvalue()


def _rapikan_cache():
    berkas = sorted(CACHE.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
    sekarang, total = time.time(), sum(p.stat().st_size for p in berkas)
    for p in berkas:
        if sekarang - p.stat().st_mtime > CACHE_UMUR_DETIK or total > CACHE_MAKS_BYTE:
            total -= p.stat().st_size
            p.unlink(missing_ok=True)


@app.get("/sehat")
def sehat():
    return {"ok": True}


@app.post("/docx", dependencies=[Depends(cek_token)])
def docx(d: DataRps):
    return Response(_docx_bytes(d), media_type=DOCX)


@app.post("/pdf", dependencies=[Depends(cek_token)])
def pdf(d: DataRps):
    # Kunci cache = isi data itu sendiri: RPS yang sama persis tidak dikonversi ulang.
    kunci = hashlib.sha256(json.dumps(d.model_dump(), sort_keys=True, default=str).encode()).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    jalur = CACHE / f"{kunci}.pdf"
    with _kunci_pdf:
        if not jalur.exists():
            hasil = build_pdf_via_libreoffice(io.BytesIO(_docx_bytes(d)))
            if hasil is None:
                raise HTTPException(status_code=500, detail="Konversi PDF gagal")
            jalur.write_bytes(hasil.getvalue())
            _rapikan_cache()
    return Response(jalur.read_bytes(), media_type="application/pdf")
