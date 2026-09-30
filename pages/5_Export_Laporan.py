"""
pages/5_Export_Laporan.py
Halaman export laporan PDF
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from utils import (
    load_data, pastikan_database_ada, render_sidebar, terapkan_filter,
    buat_fig_sektor, buat_fig_klaster_pie, buat_fig_top10,
    TAHUN_UTAMA, CSS_UMUM,
)
from pdf_generator import buat_laporan_pdf

st.set_page_config(
    page_title="Export Laporan — UMKM Kab. Semarang",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS_UMUM, unsafe_allow_html=True)

pastikan_database_ada()

df_klaster, df_sektor, df_kop_jenis, df_profil, df_aset = load_data()
filter_kec, filter_klaster = render_sidebar(df_klaster)
df_filtered = terapkan_filter(df_klaster, filter_kec, filter_klaster)

total_umkm     = int(df_filtered["total_umkm"].sum())
total_koperasi = int(df_filtered["total_koperasi"].sum())
total_industri = int(df_filtered["jumlah_industri"].sum())
rata_umkm_kec  = total_umkm / len(df_filtered) if len(df_filtered) else 0


st.markdown(
    '<div class="dinas-header"><h1>Export Laporan</h1>'
    '<p>Unduh laporan PDF sesuai filter yang aktif</p></div>',
    unsafe_allow_html=True,
)
st.caption(
    f"Laporan akan memakai filter yang aktif di sidebar saat ini: "
    f"**{filter_kec}** · **{filter_klaster}**"
)

col_opt1, col_opt2, col_opt3 = st.columns(3)
with col_opt1:
    sertakan_chart = st.checkbox("Sertakan chart", value=True)
with col_opt2:
    sertakan_koperasi = st.checkbox("Sertakan data koperasi", value=True)
with col_opt3:
    nama_file = st.text_input(
        "Nama file",
        value=f"laporan_umkm_{datetime.now().strftime('%Y%m%d')}.pdf",
    )

if st.button("Generate & download PDF", type="primary"):
    with st.spinner("Membuat laporan PDF..."):

        chart_images = {}
        if sertakan_chart:
            try:
                chart_images["UMKM per sektor"] = \
                    buat_fig_sektor(df_sektor).to_image(format="png", width=900, height=400, scale=2)
                chart_images["Sebaran UMKM per klaster"] = \
                    buat_fig_klaster_pie(df_filtered).to_image(format="png", width=900, height=400, scale=2)
                chart_images["Top 10 kecamatan"] = \
                    buat_fig_top10(df_filtered).to_image(format="png", width=900, height=400, scale=2)
            except Exception:
                st.warning(
                    "Chart tidak bisa diekspor (butuh kaleido: "
                    "`pip install kaleido`). PDF tetap dibuat tanpa chart."
                )
                chart_images = {}

        jumlah_jenis_kop = df_kop_jenis["jenis_koperasi"].nunique()
        kpi_list = [
            {"label": "Total UMKM",     "nilai": f"{total_umkm:,}".replace(",", "."),
             "delta": f"dari {len(df_filtered)} kecamatan", "naik": True},
            {"label": "Total Koperasi", "nilai": f"{total_koperasi:,}".replace(",", "."),
             "delta": f"{jumlah_jenis_kop} jenis koperasi", "naik": True},
            {"label": "Industri Kecil", "nilai": f"{total_industri:,}".replace(",", "."),
             "delta": "unit usaha", "naik": True},
            {"label": "Rata-rata UMKM/Kecamatan", "nilai": f"{rata_umkm_kec:,.0f}".replace(",", "."),
             "delta": "per kecamatan tercakup", "naik": True},
        ]

        filter_info = {
            "kecamatan": filter_kec,
            "tahun":     str(TAHUN_UTAMA),
            "sektor":    "Seluruh sektor (Industri Pengolahan dominan)",
        }

        df_umkm_pdf = df_filtered.rename(columns={
            "total_umkm": "jumlah_umkm",
            "jumlah_industri": "industri_kecil",
        })[["kecamatan", "jumlah_umkm", "sektor_dominan", "industri_kecil", "klaster"]]

        pivot_kop = df_kop_jenis.pivot_table(
            index="kecamatan", columns="jenis_koperasi",
            values="jumlah_koperasi", aggfunc="sum", fill_value=0
        ).reset_index()

        pdf_bytes = buat_laporan_pdf(
            df_umkm     = df_umkm_pdf,
            df_koperasi = pivot_kop if sertakan_koperasi else pd.DataFrame(),
            kpi         = kpi_list,
            filter_info = filter_info,
            chart_images= chart_images if sertakan_chart else None,
        )

    st.success("Laporan siap didownload!")
    st.download_button(
        label     = "⬇ Download PDF sekarang",
        data      = pdf_bytes,
        file_name = nama_file,
        mime      = "application/pdf",
    )
    st.caption(
        f"Laporan mencakup {len(df_filtered)} kecamatan · "
        f"Filter: {filter_kec} · {filter_klaster} · Tahun {TAHUN_UTAMA}"
    )
