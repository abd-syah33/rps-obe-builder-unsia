# -*- coding: utf-8 -*-
"""
Ekspor RPS ke Word (.docx) menggunakan python-docx.
Layout mengikuti struktur dokumen RPS asli UNSIA, sama seperti pdf_export.py,
supaya hasil PDF dan Word konsisten satu sama lain.
"""

import io
import os

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from pdf_export import (
    with_code, CATATAN_POINTS, SKS_ROWS, BLOOM_TABLE, METODE_TABLE, BENTUK_TABLE,
    KOMPONEN_PENJELASAN, RUBRIK_ROWS,
)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo_unsia.png")
HEADER_BLUE = "B7DDE8"  # tanpa '#': format yang dipakai OXML shading


# --------------------------------------------------------------------------
# Helper umum
# --------------------------------------------------------------------------
def shade_cell(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_text(cell, text, bold=False, size=9, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    if align:
        p.alignment = align
    run = p.add_run("" if text is None else str(text))
    run.bold = bold
    run.font.size = Pt(size)
    return p


def set_col_widths(table, widths_cm):
    table.autofit = False
    for row in table.rows:
        for i, w in enumerate(widths_cm):
            row.cells[i].width = Cm(w)
    for i, w in enumerate(widths_cm):
        table.columns[i].width = Cm(w)


def set_landscape(document, margin_cm=1.3):
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.left_margin = section.right_margin = Cm(margin_cm)
    section.top_margin = section.bottom_margin = Cm(1.0)
    return section


def usable_width_cm(section):
    return (section.page_width - section.left_margin - section.right_margin) / 360000


def add_heading(document, text, size=12, color="1E3A5F", space_before=10, space_after=4):
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    return p


# ============================================================================
# TABEL INFORMASI UTAMA (menyatu, meniru struktur dokumen RPS asli)
# ============================================================================
def build_info_table(document, avail_w, prodi, mk_row, cpl_df, info_umum, cpmk_data,
                      komponen_data, bobot_kategori):
    col_w = [avail_w * f for f in (0.17, 0.145, 0.17, 0.515)]  # label|kode/nilai|label2|deskripsi

    cpl_selected = [cpmk_data[i]["cpl_kode"] for i in range(1, 6)]
    seen = set()
    cpl_rows_data = []
    for kode in cpl_selected:
        if kode in seen:
            continue
        seen.add(kode)
        desk = cpl_df.loc[cpl_df["Kode CPL"] == kode, "Deskripsi CPL"]
        cpl_rows_data.append((kode, desk.values[0] if len(desk) else ""))

    n_cpl = len(cpl_rows_data)
    total_rows = 4 + n_cpl + 5 + 1 + 1 + 2  # identitas + CPL + CPMK + deskripsi + komponen + media/modus
    table = document.add_table(rows=total_rows, cols=4, style="Table Grid")
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, col_w)

    r = 0

    def cell(row, col):
        return table.cell(row, col)

    # --- identitas ---
    set_text(cell(r, 0), "Program Studi", bold=True); shade_cell(cell(r, 0), HEADER_BLUE)
    set_text(cell(r, 1), prodi)
    set_text(cell(r, 2), "Semester", bold=True); shade_cell(cell(r, 2), HEADER_BLUE)
    set_text(cell(r, 3), str(mk_row.get("Semester", "-")))
    r += 1

    set_text(cell(r, 0), "Mata Kuliah", bold=True); shade_cell(cell(r, 0), HEADER_BLUE)
    set_text(cell(r, 1), mk_row.get("Nama Mata Kuliah", "-"))
    set_text(cell(r, 2), "Beban SKS", bold=True); shade_cell(cell(r, 2), HEADER_BLUE)
    set_text(cell(r, 3), f"{mk_row.get('SKS', '-')} SKS")
    r += 1

    set_text(cell(r, 0), "Ranah Topik", bold=True); shade_cell(cell(r, 0), HEADER_BLUE)
    set_text(cell(r, 1), mk_row.get("Ranah Topik", "-"))
    set_text(cell(r, 2), "Dosen Koordinator", bold=True); shade_cell(cell(r, 2), HEADER_BLUE)
    set_text(cell(r, 3), info_umum.get("dosen_koordinator", "-") or "-")
    r += 1

    set_text(cell(r, 0), "Kode Mata Kuliah", bold=True); shade_cell(cell(r, 0), HEADER_BLUE)
    set_text(cell(r, 1), str(mk_row.get("Kode MK", "-")))
    set_text(cell(r, 2), "Dosen Pengampu", bold=True); shade_cell(cell(r, 2), HEADER_BLUE)
    set_text(cell(r, 3), info_umum.get("dosen_pengampu", "-") or "-")
    r += 1

    # --- CPL ---
    cpl_start = r
    for idx, (kode, desk) in enumerate(cpl_rows_data):
        if idx == 0:
            set_text(cell(r, 0), "Capaian Pembelajaran Lulusan (CPL)", bold=True)
            shade_cell(cell(r, 0), HEADER_BLUE)
        set_text(cell(r, 1), kode)
        merged = cell(r, 2).merge(cell(r, 3))
        set_text(merged, desk)
        r += 1
    if n_cpl > 1:
        cell(cpl_start, 0).merge(cell(cpl_start + n_cpl - 1, 0))

    # --- CPMK ---
    cpmk_start = r
    for i in range(1, 6):
        c = cpmk_data[i]
        if i == 1:
            set_text(cell(r, 0), "Capaian Pembelajaran Mata Kuliah (CP-MK)", bold=True)
            shade_cell(cell(r, 0), HEADER_BLUE)
        set_text(cell(r, 1), f"CPMK-{i}")
        merged = cell(r, 2).merge(cell(r, 3))
        set_text(merged, with_code(c["deskripsi"], c["cpl_kode"]))
        r += 1
    cell(cpmk_start, 0).merge(cell(cpmk_start + 4, 0))

    # --- Deskripsi Mata Kuliah ---
    set_text(cell(r, 0), "Deskripsi Mata Kuliah", bold=True); shade_cell(cell(r, 0), HEADER_BLUE)
    merged = cell(r, 1).merge(cell(r, 3))
    set_text(merged, info_umum.get("deskripsi_mk", "-"))
    r += 1

    # --- Komponen Penilaian: tabel bersarang (ceklist) ---
    set_text(cell(r, 0), "Komponen Penilaian", bold=True); shade_cell(cell(r, 0), HEADER_BLUE)
    komp_host = cell(r, 1).merge(cell(r, 3))
    komp_host.text = ""
    kategori_list = list(bobot_kategori.keys())
    n_kat = len(kategori_list)
    komp_table = komp_host.add_table(rows=len(kategori_list) + 2, cols=n_kat + 1)
    komp_table.style = document.styles["Table Grid"]
    komp_w = avail_w * 0.515
    komp_col_w = [komp_w * 0.18] + [komp_w * 0.82 / n_kat] * n_kat
    set_col_widths(komp_table, komp_col_w)
    set_text(komp_table.cell(0, 0), "CPMK", bold=True, size=8)
    shade_cell(komp_table.cell(0, 0), "DCEAF2")
    for j, kat in enumerate(kategori_list, start=1):
        set_text(komp_table.cell(0, j), kat, bold=True, size=8, align=WD_ALIGN_PARAGRAPH.CENTER)
        shade_cell(komp_table.cell(0, j), "DCEAF2")
    for i in range(1, 6):
        cpmk_kat = komponen_data.get(i)
        set_text(komp_table.cell(i, 0), f"CPMK-{i}", size=8)
        for j, kat in enumerate(kategori_list, start=1):
            mark = "\u2713" if kat == cpmk_kat else "\u00b7"
            set_text(komp_table.cell(i, j), mark, size=8, align=WD_ALIGN_PARAGRAPH.CENTER)
    bobot_row = len(kategori_list) + 1
    set_text(komp_table.cell(bobot_row, 0), "Bobot", bold=True, size=8)
    shade_cell(komp_table.cell(bobot_row, 0), "F0F0F0")
    for j, kat in enumerate(kategori_list, start=1):
        set_text(komp_table.cell(bobot_row, j), f"{bobot_kategori[kat]}%", bold=True, size=8,
                  align=WD_ALIGN_PARAGRAPH.CENTER)
        shade_cell(komp_table.cell(bobot_row, j), "F0F0F0")
    r += 1

    # --- Media & Modus ---
    set_text(cell(r, 0), "Media Pembelajaran", bold=True); shade_cell(cell(r, 0), HEADER_BLUE)
    merged = cell(r, 1).merge(cell(r, 3))
    set_text(merged, info_umum.get("media", "-"))
    r += 1

    set_text(cell(r, 0), "Perangkat Lunak/Laboratorium", bold=True); shade_cell(cell(r, 0), HEADER_BLUE)
    merged = cell(r, 1).merge(cell(r, 3))
    set_text(merged, info_umum.get("modus", "-"))
    r += 1

    return table


# ============================================================================
# TABEL 16 PERTEMUAN
# ============================================================================
def build_pertemuan_table(document, avail_w, pertemuan_data):
    headers = ["Minggu", "Kemampuan Akhir (Sub-CPMK)", "Bloom's Taxonomy", "Materi Pembelajaran",
               "Metode Pembelajaran", "Bentuk Pembelajaran Online", "Deskripsi Quiz/Tugas/Assignment",
               "Kriteria Penilaian", "Indikator Penilaian", "Referensi", "Bobot (%)"]
    weights = [0.035, 0.11, 0.06, 0.18, 0.08, 0.09, 0.14, 0.11, 0.11, 0.05, 0.045]
    col_w = [avail_w * w for w in weights]

    table = document.add_table(rows=17, cols=len(headers), style="Table Grid")
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, col_w)

    for j, h in enumerate(headers):
        set_text(table.cell(0, j), h, bold=True, size=8)
        shade_cell(table.cell(0, j), HEADER_BLUE)

    for m in range(1, 17):
        p = pertemuan_data[m]
        sub_text = with_code(p.get("sub_cpmk_desc", ""), p.get("cpmk_ref"))
        vals = [
            m, sub_text, ", ".join(p.get("bloom", [])), p.get("materi", ""),
            ", ".join(p.get("metode", [])), ", ".join(p.get("bentuk", [])),
            p.get("tugas", ""), p.get("kriteria", ""), p.get("indikator", ""),
            p.get("referensi", ""), p.get("bobot", 0),
        ]
        for j, v in enumerate(vals):
            set_text(table.cell(m, j), v, size=7.5)
    return table


# ============================================================================
# DOKUMEN UTAMA
# ============================================================================
def build_docx(prodi, mk_row, cpl_df, info_umum, cpmk_data,
                pertemuan_data, referensi_data, komponen_data, bobot_kategori):
    document = Document()
    section = set_landscape(document)
    avail_w = usable_width_cm(section)

    # gaya dasar
    style = document.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(9)

    # --- Header: logo + judul ---
    header_table = document.add_table(rows=1, cols=2)
    header_table.autofit = False
    set_col_widths(header_table, [avail_w * 0.18, avail_w * 0.82])
    logo_cell = header_table.cell(0, 0)
    logo_cell.text = ""
    if os.path.exists(LOGO_PATH):
        p = logo_cell.paragraphs[0]
        run = p.add_run()
        run.add_picture(LOGO_PATH, width=Cm(4.0))
    title_cell = header_table.cell(0, 1)
    title_cell.text = ""
    p1 = title_cell.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p1.add_run("RENCANA PEMBELAJARAN SEMESTER (RPS)")
    r1.bold = True
    r1.font.size = Pt(15)
    p2 = title_cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run("UNIVERSITAS SIBER ASIA")
    r2.bold = True
    r2.font.size = Pt(15)
    document.add_paragraph()

    # --- Tabel informasi utama ---
    build_info_table(document, avail_w, prodi, mk_row, cpl_df, info_umum, cpmk_data,
                      komponen_data, bobot_kategori)

    # --- Tabel 16 Pertemuan ---
    document.add_paragraph()
    add_heading(document, "Rencana Pembelajaran per Minggu")
    build_pertemuan_table(document, avail_w, pertemuan_data)

    # --- Referensi ---
    document.add_paragraph()
    add_heading(document, "Referensi")
    if referensi_data:
        for i, ref in enumerate(referensi_data, start=1):
            p = document.add_paragraph(f"{i}. {ref['sitasi']}")
            p.paragraph_format.space_after = Pt(3)
    else:
        document.add_paragraph("(belum diisi)")

    # --- Catatan ---
    add_heading(document, "Catatan")
    for i, point in enumerate(CATATAN_POINTS, start=1):
        p = document.add_paragraph(f"{i}. {point}")
        p.paragraph_format.space_after = Pt(3)

    # --- Pengertian 1 SKS ---
    add_heading(document, "Pengertian 1 SKS dalam Bentuk Pembelajaran")
    sks_table = document.add_table(rows=len(SKS_ROWS) + 1, cols=2, style="Table Grid")
    set_col_widths(sks_table, [avail_w * 0.85, avail_w * 0.15])
    set_text(sks_table.cell(0, 0), "", bold=True); shade_cell(sks_table.cell(0, 0), HEADER_BLUE)
    set_text(sks_table.cell(0, 1), "Durasi (Jam)", bold=True); shade_cell(sks_table.cell(0, 1), HEADER_BLUE)
    for i, (kode, judul, detail, durasi) in enumerate(SKS_ROWS, start=1):
        set_text(sks_table.cell(i, 0), f"{kode}. {judul}: {detail}", size=8)
        set_text(sks_table.cell(i, 1), durasi, size=8)

    # --- Legenda Bloom's / Metode / Bentuk ---
    document.add_paragraph()
    add_heading(document, "Legenda Bloom's Taxonomy, Metode & Bentuk Pembelajaran")
    legend_table = document.add_table(rows=1, cols=3)
    set_col_widths(legend_table, [avail_w / 3] * 3)
    legend_specs = [
        (BLOOM_TABLE, ["No", "Level", "Kode"], [0.2, 0.55, 0.25]),
        (METODE_TABLE, ["No", "Metode Pembelajaran SCL", "Kode"], [0.15, 0.65, 0.2]),
        (BENTUK_TABLE, ["No", "Bentuk Pembelajaran On-Line", "Kode"], [0.13, 0.67, 0.2]),
    ]
    for col_idx, (data_rows, headers, sub_weights) in enumerate(legend_specs):
        host = legend_table.cell(0, col_idx)
        host.text = ""
        sub_w = avail_w / 3 - 0.3
        sub_table = host.add_table(rows=len(data_rows) + 1, cols=3)
        sub_table.style = document.styles["Table Grid"]
        set_col_widths(sub_table, [sub_w * w for w in sub_weights])
        for j, h in enumerate(headers):
            set_text(sub_table.cell(0, j), h, bold=True, size=7.5)
            shade_cell(sub_table.cell(0, j), HEADER_BLUE)
        for i, row in enumerate(data_rows, start=1):
            for j, v in enumerate(row):
                set_text(sub_table.cell(i, j), v, size=7.5)

    # --- Penjelasan Komponen Penilaian ---
    document.add_paragraph()
    add_heading(document, "Komponen Penilaian")
    document.add_paragraph(
        "Proses penilaian pada mata kuliah ini dibedakan dalam 4 komponen, di antaranya adalah sebagai berikut:"
    )
    for label, teks in KOMPONEN_PENJELASAN:
        p = document.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"{label}: ")
        r1.bold = True
        p.add_run(teks)

    # --- Rubrik Penilaian ---
    document.add_paragraph()
    add_heading(document, "Rubrik Penilaian")
    rubrik_table = document.add_table(rows=len(RUBRIK_ROWS) + 1, cols=3, style="Table Grid")
    set_col_widths(rubrik_table, [avail_w * 0.08, avail_w * 0.14, avail_w * 0.78])
    for j, h in enumerate(["Jenjang", "Angka/Skor", "Deskripsi/Indikator Kinerja"]):
        set_text(rubrik_table.cell(0, j), h, bold=True)
        shade_cell(rubrik_table.cell(0, j), HEADER_BLUE)
    for i, (jenjang, skor, desk) in enumerate(RUBRIK_ROWS, start=1):
        set_text(rubrik_table.cell(i, 0), jenjang, size=8)
        set_text(rubrik_table.cell(i, 1), skor, size=8)
        set_text(rubrik_table.cell(i, 2), desk, size=8)

    # --- Blok Validasi (nama diisi manual, tanpa QR) ---
    document.add_paragraph()
    tgl = info_umum.get("tanggal_dokumen", "") or "…………………"
    sign_table = document.add_table(rows=4, cols=3, style="Table Grid")
    set_col_widths(sign_table, [avail_w / 3] * 3)
    heads = [f"Disetujui,\nTgl: {tgl}", f"Diperiksa,\nTgl: {tgl}", f"Dibuat,\nTgl: {tgl}"]
    roles = ["Ketua Prodi", "Koordinator Mata Kuliah/Bidang Keahlian", "Dosen yang bersangkutan"]
    names = [
        info_umum.get("nama_kaprodi", "") or "…………………………",
        info_umum.get("nama_koordinator", "") or "…………………………",
        info_umum.get("nama_penyusun", "") or "…………………………",
    ]
    for j in range(3):
        cell_h = sign_table.cell(0, j)
        cell_h.text = ""
        for line_idx, line in enumerate(heads[j].split("\n")):
            para = cell_h.paragraphs[0] if line_idx == 0 else cell_h.add_paragraph()
            run = para.add_run(line)
            run.bold = True
            run.font.size = Pt(8)
        shade_cell(cell_h, HEADER_BLUE)
        set_text(sign_table.cell(1, j), roles[j], size=8)
        set_text(sign_table.cell(2, j), "")  # ruang kosong tanda tangan
        sign_table.cell(2, j).height = Cm(1.2)
        set_text(sign_table.cell(3, j), names[j], size=8, align=WD_ALIGN_PARAGRAPH.CENTER)

    document.add_paragraph()
    biro_table = document.add_table(rows=3, cols=1, style="Table Grid")
    set_col_widths(biro_table, [avail_w])
    set_text(biro_table.cell(0, 0), "Periksa: Biro Penjaminan Mutu", bold=True, size=8,
              align=WD_ALIGN_PARAGRAPH.CENTER)
    shade_cell(biro_table.cell(0, 0), HEADER_BLUE)
    biro_table.cell(1, 0).height = Cm(1.0)
    set_text(biro_table.cell(2, 0), info_umum.get("nama_biro_pjm", "") or "…………………………",
              size=8, align=WD_ALIGN_PARAGRAPH.CENTER)

    buf = io.BytesIO()
    document.save(buf)
    buf.seek(0)
    return buf
