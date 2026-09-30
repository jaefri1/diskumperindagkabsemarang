"""
utils.py
Modul bersama untuk semua halaman dashboard: koneksi data, pembuat
chart/peta, dan sidebar filter. Dipakai oleh dashboard.py (halaman
Ringkasan) dan seluruh file di pages/, supaya tidak ada logika yang
diduplikasi di banyak tempat.
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import json
import folium
import plotly.express as px
from pathlib import Path

BASE_DIR     = Path(__file__).parent
DB_PATH      = BASE_DIR / "data" / "db" / "umkm_semarang.db"
GEOJSON_PATH = BASE_DIR / "data" / "geo" / "kecamatan_semarang.geojson"
TAHUN_UTAMA  = 2024   # tahun data terlengkap (hasil audit ketersediaan data —
                       # 2025 baru terisi sebagian saat file ini diperbarui)

WARNA_KLASTER = {
    "Klaster 1": "#378ADD",
    "Klaster 2": "#1D9E75",
    "Klaster 3": "#EF9F27",
}

# Nama sektor KBLI dipersingkat agar enak dibaca di chart
SEKTOR_SINGKAT = {
    "Industri Pengolahan": "Industri Pengolahan",
    "Perdagangan Besar Dan Eceran Reparasi Dan Perawatan Mobil Dan Sepeda Motor": "Perdagangan & Reparasi",
    "Penyediaan Akomodasi Dan Penyediaan Makan Minum": "Akomodasi & Kuliner",
    "Pertanian, Kehutanan, dan Perikanan": "Pertanian & Perikanan",
    "Konstruksi": "Konstruksi",
    "Aktivitas Penyewaan dan Sewa Guna Usaha Tanpa Hak Opsi, Ketenagakerjaan, Agen Perjalanan dan Penunjang Usaha Lainnya": "Jasa Penunjang Usaha",
    "Pendidikan": "Pendidikan",
    "Pengangkutan dan Pergudangan": "Transportasi & Pergudangan",
}


# ════════════════════════════════════════════════════════════
# Cek keberadaan file database — dipanggil di awal tiap halaman
# ════════════════════════════════════════════════════════════
def pastikan_database_ada():
    if not DB_PATH.exists():
        st.error(
            f"File database tidak ditemukan di:\n\n`{DB_PATH}`\n\n"
            "**Cara memperbaiki:**\n"
            "1. Pastikan folder `data/db/` ada di dalam folder project ini "
            "(sejajar dengan `dashboard.py`)\n"
            "2. Pastikan file `umkm_semarang.db` ada di dalam folder tersebut\n"
            "3. Kalau belum punya file databasenya, jalankan "
            "`python setup_database.py` terlebih dahulu"
        )
        st.stop()


# ════════════════════════════════════════════════════════════
# Muat data dari database (dipakai semua halaman, hasilnya di-cache)
# ════════════════════════════════════════════════════════════
@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)

    df_klaster = pd.read_sql_query("""
        SELECT nama_kecamatan AS kecamatan, tahun, total_umkm, jumlah_industri,
               total_koperasi, total_usaha, sektor_dominan, klaster_id, klaster, warna,
               luas_km2, jumlah_penduduk, kepadatan_penduduk,
               umkm_per_km2, umkm_per_1000_penduduk
        FROM view_kecamatan_klaster
    """, conn)

    df_sektor = pd.read_sql_query(f"""
        SELECT kecamatan, sektor_kbli, tahun, semester, jumlah_usaha
        FROM view_sektor_lengkap
        WHERE tahun = {TAHUN_UTAMA} AND semester = 'Semester II'
    """, conn)
    df_sektor["sektor_label"] = df_sektor["sektor_kbli"].map(
        lambda s: SEKTOR_SINGKAT.get(s, s[:28])
    )

    df_kop_jenis = pd.read_sql_query(f"""
        SELECT kecamatan, jenis_koperasi, tahun, semester, jumlah_koperasi
        FROM view_koperasi_lengkap
        WHERE tahun = {TAHUN_UTAMA} AND semester = 'Semester II'
    """, conn)

    df_profil = pd.read_sql_query("SELECT * FROM profil_klaster", conn)

    df_aset = pd.read_sql_query("""
        SELECT jenis_koperasi, tahun, aset_rupiah
        FROM view_aset_lengkap WHERE semester = 'Semester II'
        ORDER BY tahun
    """, conn)

    conn.close()
    return df_klaster, df_sektor, df_kop_jenis, df_profil, df_aset


# ════════════════════════════════════════════════════════════
# Sidebar: branding + filter (session_state, konsisten antar halaman)
# ════════════════════════════════════════════════════════════
def render_sidebar(df_klaster: pd.DataFrame):
    from datetime import datetime

    with st.sidebar:
        st.image(
            str(BASE_DIR / "data" / "pic" / "Seal_of_Semarang_Regency.svg.webp"),
            width=65
        )
        st.markdown(
        '''
        <p style="font-size:11px;color:#5F5E5A;margin-top:-4px;">
        Website Diskumperindag lain: 
        <a href="https://infokas.semarangkab.go.id" target="_blank">INFOKAS</a> | 
        <a href="https://dkupp.semarangkab.go.id" target="_blank">DKUPP</a>
        </p>
        ''',
        unsafe_allow_html=True
        )

        st.title("Dashboard UMKM")
        st.caption("Kab. Semarang · Dinas Koperasi, UMKM, Perindustrian & Perdagangan")
        st.divider()

        kec_list     = ["Semua kecamatan"] + sorted(df_klaster["kecamatan"].unique())
        klaster_list = ["Semua klaster"] + sorted(df_klaster["klaster"].unique())

        # Baca eksplisit dari session_state untuk tentukan index awal —
        # tidak mengandalkan key= saja, karena widget yang didefinisikan
        # ulang di file halaman yang berbeda tidak selalu otomatis
        # mempertahankan nilai sebelumnya.
        kec_default = st.session_state.get("filter_kec", "Semua kecamatan")
        kec_index   = kec_list.index(kec_default) if kec_default in kec_list else 0

        klaster_default = st.session_state.get("filter_klaster", "Semua klaster")
        klaster_index   = klaster_list.index(klaster_default) if klaster_default in klaster_list else 0

        filter_kec = st.selectbox(
            "Kecamatan", kec_list, index=kec_index, key="filter_kec"
        )
        filter_klaster = st.selectbox(
            "Klaster", klaster_list, index=klaster_index, key="filter_klaster"
        )

        st.divider()
        st.caption(f"Tahun data: **{TAHUN_UTAMA}** (data terlengkap)")
        st.caption("Sumber: data.semarangkab.go.id")
        st.caption(f"Terakhir dibuka: {datetime.now().strftime('%d %b %Y')}")

    return filter_kec, filter_klaster


def terapkan_filter(df_klaster: pd.DataFrame, filter_kec: str, filter_klaster: str) -> pd.DataFrame:
    df_filtered = df_klaster.copy()
    if filter_kec != "Semua kecamatan":
        df_filtered = df_filtered[df_filtered["kecamatan"] == filter_kec]
    if filter_klaster != "Semua klaster":
        df_filtered = df_filtered[df_filtered["klaster"] == filter_klaster]
    return df_filtered


# ════════════════════════════════════════════════════════════
# Pembuat chart — dipakai di halaman tampilan MAUPUN saat export PDF,
# supaya gambar yang di-export identik dengan yang tampil di layar.
# ════════════════════════════════════════════════════════════
def buat_fig_sektor(df_sektor: pd.DataFrame):
    df_agg = (
        df_sektor.groupby("sektor_label")["jumlah_usaha"]
        .sum().reset_index()
        .sort_values("jumlah_usaha", ascending=False)
        .head(8)
        .sort_values("jumlah_usaha")
    )
    fig = px.bar(
        df_agg, x="jumlah_usaha", y="sektor_label", orientation="h",
        title="UMKM per sektor (8 teratas dari 19 kategori KBLI)",
        color_discrete_sequence=["#378ADD"],
        labels={"jumlah_usaha": "Jumlah UMKM", "sektor_label": ""},
    )
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=40, b=0),
        height=280, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def buat_fig_klaster_pie(df_filtered: pd.DataFrame):
    df_agg = df_filtered.groupby("klaster")["total_umkm"].sum().reset_index()
    fig = px.pie(
        df_agg, values="total_umkm", names="klaster",
        title="Sebaran UMKM per klaster",
        color="klaster", color_discrete_map=WARNA_KLASTER, hole=0.45,
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0), height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25),
    )
    return fig


def buat_fig_top10(df_filtered: pd.DataFrame):
    fig = px.bar(
        df_filtered.sort_values("total_umkm", ascending=False).head(10),
        x="total_umkm", y="kecamatan", orientation="h",
        title="Top 10 kecamatan berdasarkan jumlah UMKM",
        color="klaster", color_discrete_map=WARNA_KLASTER,
        labels={"total_umkm": "Jumlah UMKM", "kecamatan": ""},
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0), height=320,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.35),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def buat_fig_top10_per_kapita(df_filtered: pd.DataFrame):
    """
    Sama seperti buat_fig_top10, tapi dibagi jumlah penduduk — supaya
    kecamatan berpenduduk banyak tidak otomatis "menang" cuma karena
    populasinya besar. Sumber jumlah_penduduk: lihat catatan sumber di
    setup_database.py (BPS via 2 laporan akademik yang saling cocok).
    """
    fig = px.bar(
        df_filtered.sort_values("umkm_per_1000_penduduk", ascending=False).head(10),
        x="umkm_per_1000_penduduk", y="kecamatan", orientation="h",
        title="Top 10 kecamatan — UMKM per 1.000 penduduk",
        color="klaster", color_discrete_map=WARNA_KLASTER,
        labels={"umkm_per_1000_penduduk": "UMKM per 1.000 penduduk", "kecamatan": ""},
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0), height=320,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.35),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def buat_fig_scatter(df_filtered: pd.DataFrame):
    fig = px.scatter(
        df_filtered,
        x="total_umkm", y="jumlah_industri",
        size="total_koperasi", color="klaster",
        hover_name="kecamatan",
        color_discrete_map=WARNA_KLASTER,
        title="UMKM vs industri kecil (ukuran = jml. koperasi)",
        labels={"total_umkm": "Jumlah UMKM", "jumlah_industri": "Jumlah industri kecil"},
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0), height=320,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.35),
    )
    return fig


def buat_fig_profil(df_profil: pd.DataFrame, kolom_data: str, judul: str):
    fig = px.bar(
        df_profil, x="klaster", y=kolom_data, title=judul,
        color="klaster", color_discrete_map=WARNA_KLASTER,
        labels={kolom_data: "", "klaster": ""},
    )
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=32, b=0), height=200,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickfont=dict(size=10)),
    )
    return fig


def hitung_tren_aset(df_aset: pd.DataFrame):
    """Deteksi otomatis lompatan skala pelaporan, kembalikan data
    yang sudah difilter ke periode yang skalanya konsisten saja."""
    total_tahun = df_aset.groupby("tahun")["aset_rupiah"].sum()
    total_tahun = total_tahun[total_tahun > 0].sort_index()
    rasio = total_tahun / total_tahun.shift(1)
    tahun_lompatan = rasio[rasio > 50].index.tolist()
    batas = min(tahun_lompatan) if tahun_lompatan else total_tahun.index.min()

    df_reliable = df_aset[
        (df_aset["tahun"] >= batas) & (df_aset["aset_rupiah"] > 0)
    ].copy()
    df_reliable["aset_miliar"] = df_reliable["aset_rupiah"] / 1e9
    return df_reliable, batas, rasio


def buat_fig_tren_aset(df_aset: pd.DataFrame):
    df_reliable, batas, rasio = hitung_tren_aset(df_aset)
    fig = px.line(
        df_reliable, x="tahun", y="aset_miliar", color="jenis_koperasi",
        markers=True,
        labels={"aset_miliar": "Aset (miliar Rp)", "tahun": "", "jenis_koperasi": ""},
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0), height=280,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.4, font=dict(size=10)),
        xaxis=dict(dtick=1),
    )
    return fig, df_reliable, batas, rasio


def hitung_korelasi(df_klaster: pd.DataFrame):
    kolom = ["total_umkm", "jumlah_industri", "total_koperasi"]
    matriks = df_klaster[kolom].corr(method="pearson").round(2)
    korelasi_tanpa = (
        df_klaster[df_klaster["kecamatan"] != "Pringapus"][kolom]
        .corr(method="pearson")
    )
    selisih_maks = (matriks - korelasi_tanpa).abs().values[~np.eye(3, dtype=bool)].max()
    return matriks, selisih_maks


def buat_fig_korelasi(df_klaster: pd.DataFrame):
    label = ["UMKM", "Industri kecil", "Koperasi"]
    matriks, selisih_maks = hitung_korelasi(df_klaster)
    fig = px.imshow(
        matriks.values, x=label, y=label,
        color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
        text_auto=True, aspect="auto",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0), height=280,
        coloraxis_showscale=False,
    )
    return fig, matriks, selisih_maks


# ════════════════════════════════════════════════════════════
# Peta choropleth
# ════════════════════════════════════════════════════════════
@st.cache_data
def siapkan_geojson(df_klaster: pd.DataFrame) -> dict:
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        geojson_data = json.load(f)

    df_dict = df_klaster.set_index("kecamatan").to_dict("index")

    for feature in geojson_data["features"]:
        nama  = feature["properties"]["name"]
        info  = df_dict.get(nama, {})
        warna = info.get("warna", "#888888")

        feature["properties"]["total_umkm"]      = int(info.get("total_umkm", 0))
        feature["properties"]["jumlah_industri"] = int(info.get("jumlah_industri", 0))
        feature["properties"]["total_koperasi"]  = int(info.get("total_koperasi", 0))
        feature["properties"]["klaster"]         = info.get("klaster", "-")

        feature["properties"]["popup_html"] = (
            f'<div style="font-family:sans-serif;min-width:190px">'
            f'<h4 style="margin:0 0 6px;border-bottom:2px solid {warna};'
            f'padding-bottom:4px">{nama}</h4>'
            f'<table style="font-size:13px;width:100%">'
            f'<tr><td>UMKM</td><td style="text-align:right;font-weight:600">'
            f'{info.get("total_umkm", 0):,}</td></tr>'
            f'<tr><td>Industri kecil</td><td style="text-align:right;font-weight:600">'
            f'{info.get("jumlah_industri", 0):,}</td></tr>'
            f'<tr><td>Koperasi</td><td style="text-align:right;font-weight:600">'
            f'{info.get("total_koperasi", 0):,}</td></tr>'
            f'<tr><td>Klaster</td><td style="text-align:right">'
            f'<span style="background:{warna};color:white;padding:1px 8px;'
            f'border-radius:8px;font-size:11px">{info.get("klaster", "-")}</span>'
            f'</td></tr></table></div>'
        )
    return geojson_data


def buat_peta_choropleth(df_klaster: pd.DataFrame):
    geojson_data = siapkan_geojson(df_klaster)

    peta = folium.Map(
        location=[-7.2067, 110.4414],
        zoom_start=10.4,
        tiles="OpenStreetMap",
    )

    folium.Choropleth(
        geo_data=geojson_data,
        data=df_klaster,
        columns=["kecamatan", "total_umkm"],
        key_on="feature.properties.name",
        fill_color="YlOrRd",
        fill_opacity=0.75,
        line_opacity=0.6,
        line_color="white",
        legend_name="Jumlah UMKM per kecamatan",
        highlight=True,
        nan_fill_color="lightgray",
    ).add_to(peta)

    folium.GeoJson(
        geojson_data,
        style_function=lambda f: {"fillOpacity": 0, "weight": 0, "color": "transparent"},
        highlight_function=lambda f: {"fillOpacity": 0.15, "weight": 2, "color": "#333"},
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Kecamatan:"]),
        popup=folium.GeoJsonPopup(
            fields=["popup_html"], labels=False, parse_html=True, max_width=280
        ),
    ).add_to(peta)

    return peta


# ════════════════════════════════════════════════════════════
# CSS bersama — nuansa portal resmi dinas (terinspirasi INFOKAS:
# biru sebagai warna utama, tampilan formal khas situs pemerintah)
# ════════════════════════════════════════════════════════════
CSS_UMUM = """
<style>
    /* Header band biru ala portal dinas resmi */
    .dinas-header {
        background: linear-gradient(135deg, #0C4A8C 0%, #185FA5 100%);
        color: white;
        padding: 18px 24px;
        border-radius: 10px;
        margin-bottom: 18px;
    }
    .dinas-header h1 {
        color: white !important;
        font-size: 22px;
        margin: 0 0 4px 0;
    }
    .dinas-header p {
        color: #D6E6F7;
        font-size: 13px;
        margin: 0;
    }

    .section-title  { font-size: 16px; font-weight: 600;
                      color: #185FA5; margin: 16px 0 8px;
                      border-left: 4px solid #185FA5; padding-left: 10px; }
    .sumber-note { font-size: 11px; color: #8a8a86; margin-top: -6px; }

    /* Kartu konten bergaya formal, mirip kartu berita INFOKAS */
    div[data-testid="stMetric"] {
        background: #F4F8FC;
        border: 1px solid #D6E6F7;
        border-radius: 8px;
        padding: 12px 14px;
    }
    section[data-testid="stSidebar"] {
        background: #F4F8FC;
        border-right: 1px solid #D6E6F7;
    }
</style>
"""
