"""
pages/1_Peta_Sebaran.py
Halaman peta choropleth sebaran UMKM per kecamatan
"""

import streamlit as st
from streamlit_folium import st_folium

from utils import (
    load_data, pastikan_database_ada, render_sidebar, terapkan_filter,
    buat_peta_choropleth, CSS_UMUM,
)

st.set_page_config(
    page_title="Peta Sebaran — UMKM Kab. Semarang",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS_UMUM, unsafe_allow_html=True)

pastikan_database_ada()

df_klaster, df_sektor, df_kop_jenis, df_profil, df_aset = load_data()
filter_kec, filter_klaster = render_sidebar(df_klaster)
df_filtered = terapkan_filter(df_klaster, filter_kec, filter_klaster)


st.markdown(
    '<div class="dinas-header"><h1>Peta Sebaran</h1>'
    '<p>Sebaran UMKM per kecamatan · Kabupaten Semarang</p></div>',
    unsafe_allow_html=True,
)
st.caption(
    "Warna wilayah menunjukkan jumlah UMKM (semakin gelap = semakin banyak). "
    "Klik kecamatan untuk detail lengkap. Peta menampilkan seluruh 19 "
    "kecamatan, tidak terpengaruh filter di sidebar."
)

peta = buat_peta_choropleth(df_klaster)
st_folium(peta, width=None, height=600, returned_objects=[])
