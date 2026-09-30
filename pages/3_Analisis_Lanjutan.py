"""
pages/3_Analisis_Lanjutan.py
Halaman analisis lanjutan: tren aset koperasi & korelasi antar indikator
"""

import streamlit as st

from utils import (
    load_data, pastikan_database_ada, render_sidebar, terapkan_filter,
    buat_fig_tren_aset, buat_fig_korelasi, CSS_UMUM,
)

st.set_page_config(
    page_title="Analisis Lanjutan — UMKM Kab. Semarang",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS_UMUM, unsafe_allow_html=True)

pastikan_database_ada()

df_klaster, df_sektor, df_kop_jenis, df_profil, df_aset = load_data()
filter_kec, filter_klaster = render_sidebar(df_klaster)


st.markdown(
    '<div class="dinas-header"><h1>Analisis Lanjutan</h1>'
    '<p>Tren aset koperasi & korelasi antar indikator</p></div>',
    unsafe_allow_html=True,
)

al1, al2 = st.columns(2)

with al1:
    st.markdown("**Tren aset koperasi**")
    fig_tren, df_reliable, batas, rasio = buat_fig_tren_aset(df_aset)
    st.plotly_chart(fig_tren, width='stretch')
    st.caption(
        f"Hanya {int(batas)}-{int(df_reliable['tahun'].max())} yang ditampilkan. "
        f"Data sebelum {int(batas)} dikecualikan karena totalnya melonjak "
        f"~{rasio.get(batas, 0):.0f}x dalam satu tahun secara serentak di "
        "semua jenis koperasi."
    )

with al2:
    st.markdown("**Korelasi antar indikator (19 kecamatan, 2024)**")
    fig_heatmap, matriks, selisih_maks = buat_fig_korelasi(df_klaster)
    st.plotly_chart(fig_heatmap, width='stretch')
    st.caption(
        "Ukuran data 19 kecamatan, dan Pringapus adalah outlier UMKM yang "
        f"jelas. Tanpa Pringapus, angka korelasi bergeser hingga "
        f"{selisih_maks:.2f} poin — jadi pola di atas tidak berlaku "
        "umum, sensitif terhadap satu titik data Pringapus."
    )
