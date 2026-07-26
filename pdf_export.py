# -*- coding: utf-8 -*-
"""
Ekspor RPS ke PDF menggunakan reportlab.
Layout mengikuti struktur dokumen RPS asli UNSIA: satu tabel informasi menyatu
(Program Studi s/d Modus Pembelajaran), lalu tabel 16 pertemuan terpisah,
lalu daftar referensi — sesuai urutan pada dokumen resmi.
"""

import io
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image,
)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo_unsia.png")

styles = getSampleStyleSheet()
cell_style = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8, leading=10)
label_style = ParagraphStyle("label_cell", parent=styles["Normal"], fontSize=8, leading=10,
                              fontName="Helvetica-Bold")
title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=15, leading=18,
                              alignment=1, fontName="Helvetica-Bold")
section_style = ParagraphStyle("section", parent=styles["Heading2"], fontSize=12,
                                textColor=colors.HexColor("#1E3A5F"), spaceBefore=14, spaceAfter=6)
ref_style = ParagraphStyle("ref", parent=styles["Normal"], fontSize=9, leading=13, spaceAfter=4,
                            leftIndent=14, firstLineIndent=-14)

NAVY = colors.HexColor("#1E3A5F")
HEADER_BLUE = colors.HexColor("#B7DDE8")  # warna asli header tabel RPS UNSIA
GRID_COLOR = colors.HexColor("#000000")

# --------------------------------------------------------------------------
# Ukuran halaman & lebar tersedia — semua tabel dihitung PROPORSIONAL terhadap
# ini, sehingga tidak akan pernah ada tabel yang melebihi lebar halaman.
# --------------------------------------------------------------------------
MARGIN = 1.3 * cm
PAGE_W, PAGE_H = landscape(A4)
AVAIL_W = PAGE_W - 2 * MARGIN


def cw(*weights):
    total = sum(weights)
    return [w / total * AVAIL_W for w in weights]


def P(text, style=None):
    text = "" if text is None else str(text)
    return Paragraph(text.replace("\n", "<br/>"), style or cell_style)


def with_code(desc, code):
    """Tambahkan kode (CPL/CPMK) dalam kurung di akhir kalimat deskripsi."""
    desc = (desc or "").strip()
    code = (code or "").strip()
    if not code:
        return desc
    if not desc:
        return f"({code})"
    return f"{desc} ({code})"


def base_table_style(spans=None):
    style = [
        ("GRID", (0, 0), (-1, -1), 0.6, GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if spans:
        for s in spans:
            style.append(("SPAN",) + s)
    return TableStyle(style)


# ============================================================================
# TABEL INFORMASI UTAMA (menyatu — meniru struktur dokumen RPS asli)
# ============================================================================
def build_info_table(prodi, mk_row, cpl_df, info_umum, cpmk_data, komponen_data, bobot_kategori):
    col_w = cw(1.3, 1.1, 1.3, 1.9)  # label kiri = label kanan; kode/nilai kiri dipersempit
    rows = []
    spans = []
    blue_cells = []  # daftar (col, row) yang diberi warna biru header seperti dokumen asli
    r = 0

    # --- baris identitas MK (dua label per baris, keduanya biru) ---
    rows.append([P("Program Studi", label_style), P(prodi),
                 P("Semester", label_style), P(str(mk_row.get("Semester", "-")))])
    blue_cells += [(0, r), (2, r)]
    r += 1

    rows.append([P("Mata Kuliah", label_style), P(mk_row.get("Nama Mata Kuliah", "-")),
                 P("Beban SKS", label_style), P(f"{mk_row.get('SKS', '-')} SKS")])
    blue_cells += [(0, r), (2, r)]
    r += 1

    rows.append([P("Ranah Topik", label_style), P(mk_row.get("Ranah Topik", "-")),
                 P("Dosen Koordinator", label_style), P(info_umum.get("dosen_koordinator", "-") or "-")])
    blue_cells += [(0, r), (2, r)]
    r += 1

    rows.append([P("Kode Mata Kuliah", label_style), P(str(mk_row.get("Kode MK", "-"))),
                 P("Dosen Pengampu", label_style), P(info_umum.get("dosen_pengampu", "-") or "-")])
    blue_cells += [(0, r), (2, r)]
    r += 1

    # --- CPL (label kolom-0 menyatu untuk semua baris CPL, kode & deskripsi putih) ---
    cpl_start = r
    cpl_selected = [cpmk_data[i]["cpl_kode"] for i in range(1, 6)]
    seen = set()
    n_cpl_rows = 0
    for kode in cpl_selected:
        if kode in seen:
            continue
        seen.add(kode)
        desk = cpl_df.loc[cpl_df["Kode CPL"] == kode, "Deskripsi CPL"]
        deskripsi = desk.values[0] if len(desk) else ""
        label = P("Capaian Pembelajaran\nLulusan (CPL)", label_style) if n_cpl_rows == 0 else P("")
        rows.append([label, P(kode), P(deskripsi), P("")])
        spans.append(((2, r), (3, r)))
        n_cpl_rows += 1
        r += 1
    if n_cpl_rows > 1:
        spans.append(((0, cpl_start), (0, cpl_start + n_cpl_rows - 1)))
    blue_cells += [(0, cpl_start)]

    # --- CPMK (deskripsi + kode CPL di akhir kalimat) ---
    cpmk_start = r
    for i in range(1, 6):
        c = cpmk_data[i]
        label = P("Capaian Pembelajaran\nMata Kuliah (CP-MK)", label_style) if i == 1 else P("")
        rows.append([label, P(f"CPMK-{i}"), P(with_code(c["deskripsi"], c["cpl_kode"])), P("")])
        spans.append(((2, r), (3, r)))
        r += 1
    spans.append(((0, cpmk_start), (0, cpmk_start + 4)))
    blue_cells += [(0, cpmk_start)]

    # --- Deskripsi Mata Kuliah ---
    rows.append([P("Deskripsi Mata Kuliah", label_style), P(info_umum.get("deskripsi_mk", "-")), P(""), P("")])
    spans.append(((1, r), (3, r)))
    blue_cells += [(0, r)]
    r += 1

    # --- Komponen Penilaian: tabel ceklist (CPMK x kategori) + baris bobot ---
    kategori_list = list(bobot_kategori.keys())
    n_kat = len(kategori_list)
    komp_header = [P("CPMK", label_style)] + [P(k, label_style) for k in kategori_list]
    komp_rows = [komp_header]
    for i in range(1, 6):
        cpmk_kat = komponen_data.get(i)
        row_cells = [P(f"CPMK-{i}")]
        for k in kategori_list:
            row_cells.append(P("\u2713" if k == cpmk_kat else "\u00b7"))
        komp_rows.append(row_cells)
    bobot_row = [P("Bobot", label_style)] + [P(f"{bobot_kategori[k]}%", label_style) for k in kategori_list]
    komp_rows.append(bobot_row)

    komp_col_w = cw(1.3, 1.1, 1.3, 1.9)
    komp_value_w = sum(komp_col_w[1:])
    cpmk_col_w = komp_value_w * 0.22
    kat_col_w = (komp_value_w - cpmk_col_w) / n_kat
    komp_table = Table(komp_rows, colWidths=[cpmk_col_w] + [kat_col_w] * n_kat)
    komp_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEAF2")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F0F0F0")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    rows.append([P("Komponen Penilaian", label_style), komp_table, P(""), P("")])
    spans.append(((1, r), (3, r)))
    blue_cells += [(0, r)]
    r += 1

    # --- Media & Modus Pembelajaran ---
    rows.append([P("Media Pembelajaran", label_style), P(info_umum.get("media", "-")), P(""), P("")])
    spans.append(((1, r), (3, r)))
    blue_cells += [(0, r)]
    r += 1

    rows.append([P("Modus Pembelajaran", label_style), P(info_umum.get("modus", "-")), P(""), P("")])
    spans.append(((1, r), (3, r)))
    blue_cells += [(0, r)]
    r += 1

    table = Table(rows, colWidths=col_w, repeatRows=0)
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.6, GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for s in spans:
        style_cmds.append(("SPAN",) + s)
    for (col, row) in blue_cells:
        style_cmds.append(("BACKGROUND", (col, row), (col, row), HEADER_BLUE))
    table.setStyle(TableStyle(style_cmds))
    return table


# ============================================================================
# TABEL 16 PERTEMUAN
# ============================================================================
def build_pertemuan_table(pertemuan_data):
    headers = ["Minggu", "Kemampuan Akhir\n(Sub-CPMK)", "Bloom's\nTaxonomy", "Materi Pembelajaran",
               "Metode\nPembelajaran", "Bentuk\nPembelajaran Online", "Deskripsi Quiz/\nTugas/Assignment",
               "Kriteria\nPenilaian", "Indikator\nPenilaian", "Referensi", "Bobot\nPenilaian (%)"]
    rows = [[P(h, label_style) for h in headers]]
    for m in range(1, 17):
        p = pertemuan_data[m]
        sub_text = with_code(p.get("sub_cpmk_desc", ""), p.get("cpmk_ref"))
        rows.append([
            P(m), P(sub_text), P(", ".join(p.get("bloom", []))), P(p.get("materi", "")),
            P(", ".join(p.get("metode", []))), P(", ".join(p.get("bentuk", []))),
            P(p.get("tugas", "")), P(p.get("kriteria", "")), P(p.get("indikator", "")),
            P(p.get("referensi", "")), P(f"{p.get('bobot', 0)}"),
        ])
    weights = [0.6, 1.8, 0.9, 3.2, 1.3, 1.5, 2.2, 1.8, 1.8, 0.9, 0.9]
    t = Table(rows, colWidths=cw(*weights), repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#555555")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


CATATAN_POINTS = [
    "Capaian Pembelajaran Lulusan Program Studi (CPL-PRODI) adalah kemampuan yang dimiliki oleh setiap lulusan "
    "prodi yang merupakan internalisasi dari sikap, penguasaan pengetahuan, dan keterampilan sesuai dengan "
    "jenjang prodinya yang diperoleh melalui proses pembelajaran",
    "CPL di Ranah Topik yang dibebankan pada mata kuliah adalah beberapa capaian pembelajaran lulusan program "
    "studi (CPL-PRODI) yang digunakan untuk pembentukan/pengembangan sebuah mata kuliah, terdiri dari aspek "
    "sikap, keterampilan umum, keterampilan khusus, dan pengetahuan",
    "CP Mata Kuliah (CP-MK) adalah kemampuan yang dijabarkan secara spesifik dari CPL yang dibebankan pada mata "
    "kuliah dan bersifat spesifik terhadap bahan kajian atau materi pembelajaran mata kuliah tersebut",
    "Sub-CP Mata Kuliah (Sub-CPMK) adalah kemampuan yang dijabarkan secara spesifik dari CPMK yang dapat diukur "
    "atau diamati dan merupakan kemampuan akhir yang direncanakan pada tiap tahap pembelajaran, bersifat "
    "spesifik terhadap materi pembelajaran mata kuliah tersebut.",
    "Kriteria Penilaian adalah patokan yang digunakan sebagai ukuran atau tolok ukur ketercapaian pembelajaran "
    "dalam penilaian berdasarkan indikator-indikator yang telah ditetapkan. Kriteria penilaian merupakan "
    "pedoman bagi penilai agar penilaian konsisten dan tidak bias. Kriteria dapat berupa kuantitatif ataupun "
    "kualitatif.",
    "Indikator Penilaian kemampuan dalam proses maupun hasil belajar mahasiswa adalah pernyataan spesifik dan "
    "terukur yang mengidentifikasi kemampuan atau kinerja hasil belajar mahasiswa yang disertai bukti-bukti",
]

SKS_ROWS = [
    ("a", "Kuliah, Responsi, Tutorial", "Tatap Muka (TM) 50 menit/minggu/semester; Penugasan Terstruktur (PT) 60 "
     "menit/minggu/semester; Belajar Mandiri (BM) 60 menit/minggu/semester", "2,5"),
    ("b", "Seminar atau bentuk pembelajaran lain yang sejenis", "Tatap muka 100 menit/minggu/semester; Belajar "
     "Mandiri 70 menit/minggu/semester", "2,5"),
    ("c", "Praktikum, praktik studio, praktik bengkel, praktik lapangan, penelitian, pengabdian kepada "
     "masyarakat, dan/atau bentuk pembelajaran lain yang setara", "170 menit/minggu/semester", "2,5"),
]

BLOOM_TABLE = [(1, "Remembering", "C1"), (2, "Understanding", "C2"), (3, "Applying", "C3"),
               (4, "Analyzing", "C4"), (5, "Evaluating", "C5"), (6, "Creating", "C6")]

METODE_TABLE = [(1, "Small Group Discussion", "SGD"), (2, "Role-Play & Simulation", "RPlS"),
                (3, "Discovery Learning", "DL"), (4, "Self-Directed Learning", "SDL"),
                (5, "Cooperative Learning", "CoL"), (6, "Collaborative Learning", "CbL"),
                (7, "Contextual Learning", "CtL"), (8, "Problem Based Learning & Inquiry", "PjBL"),
                (9, "Project Based Learning", "PBL")]

BENTUK_TABLE = [(1, "Video E-Learning", "EL-1"), (2, "Discussion at Forum", "EL-2"),
                (3, "Reading Module", "EL-3"), (4, "Video Conference atau Webinar (Web Seminar)", "EL-4"),
                (5, "E-simulation using software (Virtual Lab)", "EL-5"),
                (6, "E-learning Link (online journal, online library, digital learning dari URL/HTTP)", "EL-6"),
                (7, "Vlog Presentation", "EL-7"), (8, "Assignment", "EL-8")]

KOMPONEN_PENJELASAN = [
    ("Kehadiran dan Sikap",
     "(tugas kasus yang disiapkan dosen dan dikerjakan di kelas, simulation case). Komponen ini memiliki poin "
     "sebesar 30% dari total pertemuan tatap muka di kelas (16). Kehadiran, sikap dan perilaku merupakan salah "
     "satu komponen penunjang dalam melakukan proses penilaian, dimana keaktifan di kelas dalam bentuk "
     "kehadiran, keaktifan berdiskusi, dan etika perilaku menjadi unsur-unsur utamanya."),
    ("Tugas",
     "Selama 1 semester, mahasiswa wajib diberikan tugas minimal sejumlah 2 tugas yang terdiri dari 1 tugas "
     "mandiri dan 1 tugas kelompok. Tugas ini diberikan sebanyak 1x sebelum UTS dan 1x setelah UTS atau "
     "sebelum UAS. Komponen keseluruhan tugas memiliki poin sebesar 20%."),
    ("Ujian Tengah Semester (UTS)",
     "UTS dilakukan pada pertemuan minggu ke-8. UTS merupakan asesmen atas kemampuan akhir mahasiswa sesuai "
     "dengan rancangan materi/topik pembelajaran dari pertemuan ke-1 hingga ke-7. Bentuk UTS dapat berupa ujian "
     "tertulis atau presentasi tugas mandiri atau tugas kelompok dan lain-lain yang juga menyesuaikan dengan "
     "metode pembelajaran. Bobot nilai UTS yang diberikan adalah sebesar 20%."),
    ("UAS (PbL) — Menghasilkan produk (desain produk/hasil konfigurasi)",
     "idealnya real case lapangan. UAS dilakukan pada pertemuan minggu ke-16 dari keseluruhan total pertemuan. "
     "UAS merupakan asesmen atas kemampuan akhir mahasiswa sesuai dengan rancangan materi/topik pembelajaran "
     "dari pertemuan ke-9 hingga ke-15. Bentuk UAS dapat berupa ujian tertulis atau presentasi tugas mandiri "
     "atau tugas kelompok dan lain-lain yang juga menyesuaikan dengan metode pembelajaran. Bobot nilai UAS yang "
     "diberikan adalah sebesar 30%."),
]

RUBRIK_ROWS = [
    ("A", "80,00 – 100", "Merupakan perolehan mahasiswa superior: mengikuti perkuliahan dengan sangat baik, "
     "memahami materi dengan sangat baik, bahkan tertantang untuk memahami lebih jauh, memiliki tingkat "
     "proaktif dan kreativitas tinggi dalam mencari informasi terkait materi, mampu menyelesaikan masalah "
     "dengan akurasi sempurna bahkan mampu mengenali masalah nyata pada masyarakat/industri dan mampu "
     "mengusulkan konsep solusinya"),
    ("A-", "77,00 – 79,99", "Mengikuti perkuliahan dengan sangat baik, memahami materi dengan sangat baik, "
     "memiliki tingkat proaktif dan kreativitas tinggi dalam mencari informasi terkait materi, mampu "
     "menyelesaikan masalah/tugas dengan akurasi sangat bagus."),
    ("B+", "74,00 – 76,99", "Mengikuti perkuliahan dengan baik, mampu memahami materi dan mampu menyelesaikan "
     "masalah/tugas dengan akurasi sangat bagus"),
    ("B", "71,00 – 73,99", "Mengikuti perkuliahan dengan baik, mampu memahami materi dan mampu menyelesaikan "
     "masalah/tugas dengan akurasi bagus"),
    ("B-", "68,00 – 70,99", "Mengikuti perkuliahan dengan baik, mampu memahami materi dan mampu menyelesaikan "
     "masalah/tugas dengan akurasi cukup"),
    ("C+", "64,00 – 67,99", "Mengikuti perkuliahan dengan baik, berusaha memahami materi, tetapi baru mampu "
     "menyelesaikan sebagian masalah/tugas dengan akurasi cukup"),
    ("C", "56,00 – 63,99", "Mengikuti perkuliahan dengan cukup baik, berusaha memahami materi, tetapi kurang "
     "persisten sehingga baru mampu menyelesaikan sebagian dari masalah/tugas dengan akurasi yang kurang"),
    ("D", "46,00 – 55,99", "Mengikuti perkuliahan dan mengerjakan tugas seadanya, tidak memiliki kemauan dan "
     "tanggung jawab untuk memahami materi"),
    ("E", "≤ 45,99", "Tidak melaksanakan tugas dan sama sekali tidak memahami materi"),
]

small_style = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=11)


def legend_table(rows, headers, weights, total_width):
    data = [[P(h, label_style) for h in headers]]
    for row in rows:
        data.append([P(v) for v in row])
    col_widths = [w / sum(weights) * total_width for w in weights]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def build_appendix_flowables(info_umum):
    """Bagian baku RPS setelah Referensi: Catatan, penjelasan SKS, legenda
    Bloom/Metode/Bentuk, penjelasan Komponen Penilaian, Rubrik Penilaian, dan
    blok validasi (nama diisi manual, tanpa QR)."""
    flow = []

    flow.append(Spacer(1, 18))
    flow.append(Paragraph("Catatan", section_style))
    for i, point in enumerate(CATATAN_POINTS, start=1):
        flow.append(Paragraph(f"{i}. {point}", ref_style))

    flow.append(Spacer(1, 10))
    flow.append(Paragraph("Pengertian 1 SKS dalam Bentuk Pembelajaran", section_style))
    sks_data = [[P("", label_style), P("Durasi (Jam)", label_style)]]
    for kode, judul, detail, durasi in SKS_ROWS:
        sks_data.append([P(f"{kode}. {judul} — {detail}"), P(durasi)])
    t_sks = Table(sks_data, colWidths=cw(6, 1), repeatRows=1)
    t_sks.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    flow.append(t_sks)

    flow.append(PageBreak())
    flow.append(Paragraph("Legenda Bloom's Taxonomy, Metode & Bentuk Pembelajaran", section_style))
    wrapper_widths = cw(1, 1.15, 1.3)
    pad = 8  # margin aman supaya sub-tabel tidak menyentuh tepi kolom pembungkus
    row3 = Table([[
        legend_table(BLOOM_TABLE, ["No", "Level", "Kode"], [1, 3, 1.5], wrapper_widths[0] - pad),
        legend_table(METODE_TABLE, ["No", "Metode Pembelajaran SCL", "Kode"], [1, 4, 1.5], wrapper_widths[1] - pad),
        legend_table(BENTUK_TABLE, ["No", "Bentuk Pembelajaran On-Line", "Kode"], [1, 4.5, 1.5], wrapper_widths[2] - pad),
    ]], colWidths=wrapper_widths)
    row3.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    flow.append(row3)

    flow.append(Spacer(1, 12))
    flow.append(Paragraph("Komponen Penilaian", section_style))
    flow.append(Paragraph(
        "Proses penilaian pada mata kuliah ini dibedakan dalam 4 komponen, di antaranya adalah sebagai berikut:",
        small_style))
    for label, teks in KOMPONEN_PENJELASAN:
        flow.append(Paragraph(f"<b>{label}</b> — {teks}", ParagraphStyle(
            "komp_p", parent=small_style, spaceBefore=4, spaceAfter=4, leftIndent=10)))

    flow.append(PageBreak())
    flow.append(Paragraph("Rubrik Penilaian", section_style))
    rubrik_data = [[P("Jenjang", label_style), P("Angka/Skor", label_style), P("Deskripsi/Indikator Kinerja", label_style)]]
    for jenjang, skor, desk in RUBRIK_ROWS:
        rubrik_data.append([P(jenjang), P(skor), P(desk)])
    t_rubrik = Table(rubrik_data, colWidths=cw(1, 1.3, 7.7), repeatRows=1)
    t_rubrik.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    flow.append(t_rubrik)

    # --- Blok Validasi (nama diisi manual, tanpa QR) ---
    flow.append(Spacer(1, 16))
    tgl = info_umum.get("tanggal_dokumen", "") or "…………………"
    val_header_style = ParagraphStyle("val_head", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold")
    val_style = ParagraphStyle("val", parent=styles["Normal"], fontSize=8, leading=11)
    sign_block = [
        [P(f"Disetujui,\nTgl: {tgl}", val_header_style),
         P(f"Diperiksa,\nTgl: {tgl}", val_header_style),
         P(f"Dibuat,\nTgl: {tgl}", val_header_style)],
        [P("Ketua Prodi", val_style), P("Koordinator Mata Kuliah/Bidang Keahlian", val_style),
         P("Dosen yang bersangkutan", val_style)],
        [Spacer(1, 40), Spacer(1, 40), Spacer(1, 40)],
        [P(info_umum.get("nama_kaprodi", "") or "…………………………", val_style),
         P(info_umum.get("nama_koordinator", "") or "…………………………", val_style),
         P(info_umum.get("nama_penyusun", "") or "…………………………", val_style)],
    ]
    t_sign = Table(sign_block, colWidths=cw(1, 1, 1))
    t_sign.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, GRID_COLOR),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 3), (-1, 3), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    flow.append(t_sign)

    flow.append(Spacer(1, 4))
    biro_block = [
        [P("Periksa: Biro Penjaminan Mutu", val_header_style)],
        [Spacer(1, 30)],
        [P(info_umum.get("nama_biro_pjm", "") or "…………………………", val_style)],
    ]
    t_biro = Table(biro_block, colWidths=cw(1))
    t_biro.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, GRID_COLOR),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    flow.append(t_biro)

    return flow


# ============================================================================
# DOKUMEN UTAMA
# ============================================================================
def build_pdf(prodi, mk_row, cpl_df, info_umum, cpmk_data,
              pertemuan_data, referensi_data, komponen_data, bobot_kategori):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=1.0 * cm, bottomMargin=1.0 * cm,
    )
    story = []

    # --- Header: logo + judul, meniru tata letak dokumen asli ---
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=4.2 * cm, height=4.2 * cm * 170 / 549)
    else:
        logo = P("")
    header_tbl = Table(
        [[logo, P("RENCANA PEMBELAJARAN SEMESTER (RPS)<br/>UNIVERSITAS SIBER ASIA", title_style)]],
        colWidths=cw(1, 5),
    )
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 10))

    # --- Tabel informasi utama (menyatu) ---
    story.append(build_info_table(prodi, mk_row, cpl_df, info_umum, cpmk_data, komponen_data, bobot_kategori))

    # --- Tabel 16 Pertemuan ---
    story.append(PageBreak())
    story.append(Paragraph("Rencana Pembelajaran per Minggu", section_style))
    story.append(build_pertemuan_table(pertemuan_data))

    # --- Referensi (daftar bernomor, seperti dokumen asli) ---
    story.append(PageBreak())
    story.append(Paragraph("Referensi", section_style))
    if referensi_data:
        for i, ref in enumerate(referensi_data, start=1):
            story.append(Paragraph(f"{i}. {ref['sitasi']}", ref_style))
    else:
        story.append(Paragraph("—", ref_style))

    # --- Bagian baku setelah Referensi (Catatan s/d blok validasi) ---
    story.extend(build_appendix_flowables(info_umum))

    doc.build(story)
    buf.seek(0)
    return buf
