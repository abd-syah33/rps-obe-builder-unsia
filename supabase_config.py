# -*- coding: utf-8 -*-
"""
Helper baca kredensial Supabase dari config/supabase.txt, mengikuti pola yang
sudah ada untuk load_default_gemini_config() dan load_pejabat_config() di app.py.

Dipakai oleh scripts/test_supabase_connection.py (Fase 1) dan nantinya oleh
app.py sendiri mulai Fase 2 saat Auth & penyimpanan RPS disambungkan.
"""

import os

SUPABASE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "supabase.txt")


def _normalize_url(value):
    value = value.strip()
    for suffix in ("/rest/v1/", "/rest/v1"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value.rstrip("/")


def load_supabase_config():
    """Baca config/supabase.txt -> {'url': ..., 'anon_key': ..., 'service_role_key': ...}.

    Mengembalikan string kosong untuk field yang tidak ada, supaya pemanggil
    bisa mengecek `if not cfg["url"]` tanpa perlu try/except KeyError.
    """
    result = {"url": "", "anon_key": "", "service_role_key": ""}
    if not os.path.exists(SUPABASE_CONFIG_PATH):
        return result
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
    return result