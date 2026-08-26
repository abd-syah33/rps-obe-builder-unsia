# -*- coding: utf-8 -*-
"""
Helper baca kredensial Supabase - dari config/supabase.txt untuk development
lokal, ATAU dari st.secrets (fitur "Secrets" bawaan Streamlit Community
Cloud) untuk deployment - config/supabase.txt sengaja di-gitignore (tidak
ikut ter-upload ke GitHub), jadi tidak akan ada di server Cloud sama sekali;
st.secrets adalah cara resminya menyediakan kredensial di sana.

Urutan pencarian: file lokal dulu (kalau ada & lengkap, dipakai - ini
menjaga alur kerja development yang sudah ada supaya tidak berubah), baru
kalau kosong/tidak ada, coba st.secrets.

Dipakai oleh scripts/test_supabase_connection.py dan app.py (lewat auth.py).
"""

import os

import streamlit as st

SUPABASE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "supabase.txt")


def _normalize_url(value):
    """Buang trailing '/rest/v1', '/rest/v1/', atau '/' dari SUPABASE_URL.

    Dashboard Supabase kadang menampilkan URL lengkap sampai '/rest/v1/' di
    halaman Data API - kalau itu ikut ditempel apa adanya, supabase-py akan
    menambahkan '/rest/v1' lagi di baliknya sehingga path jadi dobel dan
    PostgREST menolak request dengan error PGRST125 ("Invalid path specified").
    """
    value = value.strip()
    for suffix in ("/rest/v1/", "/rest/v1"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value.rstrip("/")


def load_supabase_config():
    """Kembalikan {'url': ..., 'anon_key': ..., 'service_role_key': ...}.

    Coba config/supabase.txt dulu (development lokal) - kalau salah satu
    field masih kosong setelah itu (termasuk kalau filenya sama sekali tidak
    ada, mis. di Streamlit Community Cloud), coba lengkapi dari st.secrets
    (Settings -> Secrets di dashboard Streamlit Cloud, format TOML):

        SUPABASE_URL = "https://xxxx.supabase.co"
        SUPABASE_ANON_KEY = "xxxx"
        SUPABASE_SERVICE_ROLE_KEY = "xxxx"

    Mengembalikan string kosong untuk field yang benar-benar tidak ditemukan
    di manapun, supaya pemanggil bisa mengecek `if not cfg["url"]` tanpa
    perlu try/except KeyError.
    """
    result = {"url": "", "anon_key": "", "service_role_key": ""}

    if os.path.exists(SUPABASE_CONFIG_PATH):
        try:
            with open(SUPABASE_CONFIG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip()
                    if key == "SUPABASE_URL":
                        result["url"] = _normalize_url(value)
                    elif key == "SUPABASE_ANON_KEY":
                        result["anon_key"] = value
                    elif key == "SUPABASE_SERVICE_ROLE_KEY":
                        result["service_role_key"] = value
        except Exception:
            pass

    if not result["url"] or not result["anon_key"]:
        try:
            if not result["url"] and st.secrets.get("SUPABASE_URL"):
                result["url"] = _normalize_url(st.secrets["SUPABASE_URL"])
            if not result["anon_key"] and st.secrets.get("SUPABASE_ANON_KEY"):
                result["anon_key"] = st.secrets["SUPABASE_ANON_KEY"]
            if not result["service_role_key"] and st.secrets.get("SUPABASE_SERVICE_ROLE_KEY"):
                result["service_role_key"] = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
        except Exception:
            # Tidak ada secrets.toml sama sekali (mis. development lokal murni
            # tanpa pernah setup Secrets) - itu wajar, bukan error yang perlu
            # ditampilkan, cukup diamkan dan biarkan hasilnya tetap string kosong.
            pass

    return result