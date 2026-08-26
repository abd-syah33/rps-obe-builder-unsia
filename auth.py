# -*- coding: utf-8 -*-
"""
Login & Peran (Supabase Auth) untuk RPS Builder.

Streamlit tidak native mendukung Supabase Auth, jadi modul ini menjembatani
secara manual: form Masuk/Daftar biasa (email+password), simpan token sesi di
st.session_state, lalu pakai token itu supaya query ke database (lewat client
Supabase yang sama) otomatis kena Row Level Security sebagai user yang login.

PENTING - kenapa client TIDAK di-@st.cache_resource:
    st.cache_resource membuat objek jadi SATU instance yang dipakai bersama oleh
    SEMUA user aplikasi (bukan per-sesi browser). Kalau client Supabase (yang
    menyimpan token login di dalam dirinya) di-cache_resource, sesi Dosen A bisa
    "bocor"/tertimpa sesi Dosen B saat banyak orang pakai app bersamaan. Karena
    itu, client dibuat sekali PER SESI BROWSER dan disimpan di st.session_state
    (state per-sesi, bukan global) - lihat get_client() di bawah.

Keterbatasan yang disengaja (supaya tetap sederhana & 100% bisa diandalkan):
    Sesi login hanya bertahan selama tab browser terbuka (disimpan di
    st.session_state server-side, BUKAN cookie browser). Refresh halaman /
    tutup tab = perlu Masuk lagi.

    RIWAYAT: sempat dicoba login persisten (~30 menit) lewat cookie browser
    (extra-streamlit-components), TAPI dibatalkan - ditemukan race condition
    nyata: cookies.delete() di komponen itu memanggil komponen dua-arah
    (Python <-> JS browser) yang butuh round-trip untuk benar-benar
    menghapus cookie; kalau langsung disusul st.rerun() (seperti alur
    Logout), rerun bisa terjadi SEBELUM penghapusan itu benar-benar sampai
    ke browser - akibatnya Logout kelihatan berhasil sesaat, lalu sesi lama
    "hidup lagi" dari cookie yang ternyata belum sempat terhapus. Ini
    ditemukan lewat pengujian nyata (bukan cuma dugaan), dan dianggap tidak
    cukup layak diandalkan untuk sesuatu sesensitif Logout - terutama untuk
    dipakai di komputer bersama, di mana Logout yang tidak benar-benar keluar
    bisa jadi masalah privasi nyata untuk pengguna berikutnya. Diputuskan
    dibatalkan sepenuhnya (bukan ditambal) - kembali ke session_state biasa
    yang sudah teruji stabil sepanjang proyek ini. Kalau nanti mau dicoba
    lagi, pertimbangkan komponen cookie yang berbeda, atau tunda st.rerun()
    setelah delete() dengan mekanisme konfirmasi tambahan.
"""

import streamlit as st
from supabase import create_client

from supabase_config import load_supabase_config


# --------------------------------------------------------------------------
# Client Supabase - satu instance per sesi browser (lihat catatan di atas)
# --------------------------------------------------------------------------
def get_client():
    if "_supabase_client" not in st.session_state:
        cfg = load_supabase_config()
        if not cfg["url"] or not cfg["anon_key"]:
            st.error(
                "config/supabase.txt belum diisi lengkap. Salin "
                "config/supabase.txt.example -> config/supabase.txt, isi "
                "SUPABASE_URL & SUPABASE_ANON_KEY, lalu jalankan ulang aplikasi."
            )
            st.stop()
        st.session_state["_supabase_client"] = create_client(cfg["url"], cfg["anon_key"])

    client = st.session_state["_supabase_client"]

    # Kalau sesi login ada di session_state, pastikan client memakainya
    # (perlu diulang tiap rerun karena Streamlit menjalankan ulang script dari
    # atas setiap kali ada interaksi).
    session = st.session_state.get("supabase_session")
    if session:
        try:
            client.auth.set_session(session["access_token"], session["refresh_token"])
        except Exception:
            # token kadaluarsa/invalid -> anggap belum login, biar require_login()
            # yang menampilkan form Masuk lagi
            st.session_state.pop("supabase_session", None)

    return client


def _store_session(session):
    st.session_state["supabase_session"] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }


def _fetch_pengguna(client, user_id):
    resp = client.table("pengguna").select("*").eq("id", user_id).limit(1).execute()
    return resp.data[0] if resp.data else None


# --------------------------------------------------------------------------
# Form Masuk / Daftar / Lupa Password
# --------------------------------------------------------------------------
def _login_form():
    st.title("📘 RPS Builder · UNSIA")
    st.caption("Masuk dengan email untuk melanjutkan.")

    tab_masuk, tab_daftar, tab_lupa = st.tabs(["Masuk", "Daftar Akun Baru", "Lupa Password"])

    with tab_masuk:
        with st.form("form_masuk"):
            email = st.text_input("Email", key="masuk_email")
            password = st.text_input("Password", type="password", key="masuk_password")
            submitted = st.form_submit_button("Masuk")
        if submitted:
            client = get_client()
            try:
                auth_resp = client.auth.sign_in_with_password({"email": email, "password": password})
                _store_session(auth_resp.session)
                st.rerun()
            except Exception as e:
                st.error(f"Gagal masuk: {e}")

    with tab_daftar:
        st.caption(
            "Daftar hanya bisa dengan NIP yang sudah didaftarkan Admin terlebih "
            "dahulu. Nama akan terisi otomatis sesuai data yang didaftarkan. Peran "
            "Kaprodi/Admin diatur kemudian oleh pengelola sistem."
        )
        with st.form("form_daftar"):
            nip_d = st.text_input("NIP", key="daftar_nip")
            email_d = st.text_input("Email", key="daftar_email")
            password_d = st.text_input("Password (minimal 6 karakter)", type="password", key="daftar_password")
            submitted_d = st.form_submit_button("Daftar")
        if submitted_d:
            nip_bersih = nip_d.strip()
            if not nip_bersih:
                st.error("NIP wajib diisi.")
            else:
                client = get_client()
                try:
                    cek = client.rpc("cek_nip_terdaftar", {"nip_input": nip_bersih}).execute()
                    nama_terdaftar = cek.data
                except Exception as e:
                    st.error(f"Gagal memeriksa NIP: {e}")
                    nama_terdaftar = None
                    st.stop()

                if not nama_terdaftar:
                    st.error(
                        "NIP tidak ditemukan dalam daftar pra-pendaftaran. "
                        "Hubungi Admin untuk didaftarkan dulu sebelum bisa Daftar."
                    )
                else:
                    try:
                        client.auth.sign_up({
                            "email": email_d, "password": password_d,
                            "options": {"data": {"nip": nip_bersih}},
                        })
                        st.success(
                            f"Akun berhasil dibuat atas nama **{nama_terdaftar}**. Kalau konfirmasi "
                            "email masih aktif di pengaturan project Supabase, cek inbox dulu sebelum "
                            "bisa Masuk. Kalau sudah dimatikan, langsung bisa dipakai di tab \"Masuk\"."
                        )
                    except Exception as e:
                        st.error(f"Gagal daftar: {e}")

    with tab_lupa:
        st.caption(
            "Masukkan email untuk menerima **kode 6 digit** lewat email, lalu "
            "gunakan kode itu di bawah untuk membuat password baru."
        )
        with st.form("form_kirim_kode_reset"):
            email_reset = st.text_input("Email", key="reset_email")
            kirim_kode = st.form_submit_button("Kirim Kode Reset")
        if kirim_kode:
            email_reset_bersih = email_reset.strip()
            if not email_reset_bersih:
                st.error("Email wajib diisi.")
            else:
                client = get_client()
                try:
                    client.auth.reset_password_for_email(email_reset_bersih)
                    st.success(
                        "Kalau email tersebut terdaftar, kode reset (6 digit) sudah "
                        "dikirim - cek inbox (dan folder spam), lalu isi form di bawah."
                    )
                except Exception as e:
                    st.error(f"Gagal mengirim kode reset: {e}")

        st.divider()
        st.caption("Sudah punya kode dari email? Buat password baru di sini:")
        with st.form("form_set_password_baru"):
            email_confirm = st.text_input("Email (sama seperti di atas)", key="reset_email_confirm")
            kode = st.text_input("Kode Reset (6 digit dari email)", key="reset_kode")
            password_baru = st.text_input(
                "Password Baru (minimal 6 karakter)", type="password", key="reset_password_baru",
            )
            submit_reset = st.form_submit_button("Reset Password")
        if submit_reset:
            if not (email_confirm.strip() and kode.strip() and password_baru):
                st.error("Semua field wajib diisi.")
            else:
                client = get_client()
                try:
                    auth_resp = client.auth.verify_otp({
                        "email": email_confirm.strip(), "token": kode.strip(), "type": "recovery",
                    })
                    client.auth.update_user({"password": password_baru})
                    _store_session(auth_resp.session)
                    st.success("Password berhasil diubah. Anda otomatis masuk.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal reset password: {e} (kemungkinan kode salah/kedaluwarsa, atau email tidak cocok)")


def logout():
    for key in ("supabase_session", "_supabase_client"):
        st.session_state.pop(key, None)
    st.rerun()


# --------------------------------------------------------------------------
# Gate utama - dipanggil di awal app.py
# --------------------------------------------------------------------------
def require_login():
    """Pastikan user sudah login. Kalau belum, tampilkan form Masuk/Daftar/
    Lupa Password dan hentikan render halaman (st.stop()). Kalau sudah login,
    tampilkan badge kecil + tombol Logout di sidebar, dan kembalikan dict
    baris `pengguna` (berisi id, email, role, prodi_id).
    """
    if not st.session_state.get("supabase_session"):
        _login_form()
        st.stop()

    client = get_client()
    try:
        user_resp = client.auth.get_user()
    except Exception:
        user_resp = None

    if not user_resp or not user_resp.user:
        st.session_state.pop("supabase_session", None)
        _login_form()
        st.stop()

    user = user_resp.user
    pengguna = _fetch_pengguna(client, user.id)
    if pengguna is None:
        st.error(
            "Berhasil masuk, tapi profil belum ada di tabel `pengguna` (harusnya "
            "otomatis dibuat trigger saat daftar). Coba Logout lalu Daftar ulang, "
            "atau hubungi admin kalau masalah berlanjut."
        )
        if st.button("Logout"):
            logout()
        st.stop()

    with st.sidebar:
        nama_tampil = pengguna.get("nama") or pengguna["email"]
        st.caption(f"👤 {nama_tampil} · peran: **{pengguna['role']}**")

        with st.expander("✏️ Ubah Nama"):
            nama_baru = st.text_input(
                "Nama Lengkap", value=pengguna.get("nama") or "", key="nama_saya_input",
            )
            if st.button("Simpan Nama", key="simpan_nama_btn"):
                try:
                    client.rpc("update_nama_saya", {"nama_baru": nama_baru.strip()}).execute()
                    st.success("Nama berhasil diperbarui.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal memperbarui nama: {e}")

        if st.button("Logout", key="logout_btn"):
            logout()
        st.divider()

    return pengguna


def render_role_placeholder(pengguna):
    """Layar untuk peran yang tidak dikenali sama sekali (di luar dosen/
    kaprodi/admin) - dalam praktiknya seharusnya tidak pernah muncul, karena
    kolom `role` di database dibatasi CHECK constraint ke tiga nilai itu."""
    st.title("📘 RPS Builder · UNSIA")
    st.warning(f"Peran '{pengguna['role']}' belum dikenali aplikasi ini. Hubungi admin.")