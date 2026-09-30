"""
dashboard.py
Dashboard Analitik UMKM & Koperasi Kabupaten Semarang — Halaman Ringkasan
Ini adalah halaman utama (entry point). Halaman lain ada di folder pages/
dan otomatis muncul di navigasi sidebar.

Sebelum menjalankan dashboard ini, database harus sudah dibuat:
    python setup_database.py

Jalankan: streamlit run dashboard.py
"""

import streamlit as st

from utils import (
    load_data, pastikan_database_ada, render_sidebar, terapkan_filter,
    buat_fig_sektor, buat_fig_klaster_pie, CSS_UMUM, TAHUN_UTAMA,
)

st.set_page_config(
    page_title="Dashboard UMKM Kab. Semarang — Ringkasan",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS_UMUM, unsafe_allow_html=True)

pastikan_database_ada()

df_klaster, df_sektor, df_kop_jenis, df_profil, df_aset = load_data()
filter_kec, filter_klaster = render_sidebar(df_klaster)
df_filtered = terapkan_filter(df_klaster, filter_kec, filter_klaster)


# ── Header halaman ───────────────────────────────────────────
st.markdown(
    f'<div class="dinas-header"><h1>Analitik UMKM & Koperasi</h1>'
    f'<p>Kabupaten Semarang · Provinsi Jawa Tengah · Data tahun {TAHUN_UTAMA}</p></div>',
    unsafe_allow_html=True,
)


# ── KPI cards ────────────────────────────────────────────────
st.markdown('<p class="section-title">Indikator utama</p>', unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)

total_umkm     = int(df_filtered["total_umkm"].sum())
total_koperasi = int(df_filtered["total_koperasi"].sum())
total_industri = int(df_filtered["jumlah_industri"].sum())
rata_umkm_kec  = total_umkm / len(df_filtered) if len(df_filtered) else 0

k1.metric("Total UMKM",       f"{total_umkm:,}".replace(",", "."))
k2.metric("Total Koperasi",   f"{total_koperasi:,}".replace(",", "."))
k3.metric("Industri Kecil",   f"{total_industri:,}".replace(",", "."))
k4.metric("Rata-rata UMKM / Kecamatan", f"{rata_umkm_kec:,.0f}".replace(",", "."))

st.caption(
    f"Berdasarkan {len(df_filtered)} dari 19 kecamatan · "
    "seluruh kecamatan didominasi sektor Industri Pengolahan"
)


# ── Chart ringkas ────────────────────────────────────────────
st.markdown('<p class="section-title">Distribusi & segmentasi</p>', unsafe_allow_html=True)
c1, c2 = st.columns(2)

with c1:
    st.plotly_chart(buat_fig_sektor(df_sektor), width='stretch')
    st.caption(
        "8 sektor dengan UMKM terbanyak dari 19 kategori KBLI — 11 sektor "
        "lainnya jumlahnya jauh lebih kecil. Data tahun 2024, Semester II."
    )

with c2:
    st.plotly_chart(buat_fig_klaster_pie(df_filtered), width='stretch')

st.caption(
    "Klaster bernomor 1-3 tanpa urutan/peringkat kualitas — buka halaman "
    "\"Profil Klaster\" di sidebar untuk detail tiap klaster."
)


# ── Navigasi ke halaman lain ───────────────────────────────────
st.divider()
st.markdown('<p class="section-title">Jelajahi lebih lanjut</p>', unsafe_allow_html=True)

n1, n2, n3, n4, n5 = st.columns(5)
with n1:
    st.page_link("pages/1_Peta_Sebaran.py", label="Peta Sebaran", icon="🗺️")
with n2:
    st.page_link("pages/2_Profil_Klaster.py", label="Profil Klaster", icon="📊")
with n3:
    st.page_link("pages/3_Analisis_Lanjutan.py", label="Analisis Lanjutan", icon="📈")
with n4:
    st.page_link("pages/4_Data_Detail.py", label="Data Detail", icon="📋")
with n5:
    st.page_link("pages/5_Export_Laporan.py", label="Export Laporan", icon="📄")
