"""
clustering_kmeans.py
K-Means Clustering UMKM & Koperasi Kabupaten Semarang
Menggunakan data dari master_gabungan.csv (hasil cleaning)

Pendekatan penamaan klaster: klaster diberi NOMOR urut saja (Klaster 1-3),
tanpa nama/kata sifat yang menyimpulkan karakter atau kualitas kecamatan.
Karakteristik tiap klaster ditunjukkan lewat ANGKA (rata-rata & peringkat
per indikator) dan grafik profil di dashboard — bukan lewat kata ringkasan.
Ini pendekatan standar dalam laporan data mining: klaster diberi ID,
maknanya dibaca dari profil datanya, bukan dari nama yang diberikan analis.

Revisi metodologi (dibandingkan versi awal, k=4 pada data mentah):
  - Ketiga fitur ditransformasi log1p sebelum StandardScaler, karena
    jumlah UMKM di Pringapus jauh di atas kecamatan lain dan mendominasi
    jarak Euclidean apabila dipakai dalam skala aslinya. Versi awal (data
    mentah, k=4) menghasilkan satu klaster beranggotakan satu kecamatan
    (Pringapus) — secara definisi Silhouette-nya nol dan tidak bermakna
    sebagai pola kelompok.
  - k dipilih bukan hanya dari Silhouette Score tertinggi, tapi juga dari
    Davies-Bouldin Index, Calinski-Harabasz Index, syarat tidak ada
    klaster tunggal, kestabilan bootstrap (ARI), dan kesesuaian dengan
    Hierarchical Clustering (Ward). Lihat evaluasi_k() di bawah.
  - Baris data diurutkan berdasar nama kecamatan sebelum di-fit, supaya
    korespondensi label mentah KMeans (0/1/2) ke "Klaster 1/2/3" stabil
    dan bisa direproduksi, tidak tergantung urutan baris pada CSV sumber.

Output:
  - data/processed/umkm_klaster.csv    → data per kecamatan + nomor klaster
  - data/processed/klaster_ringkasan.csv → rata-rata tiap klaster
  - data/processed/klaster_profil.csv  → rata-rata & peringkat tiap indikator per klaster

Jalankan:
    python clustering_kmeans.py
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import (
    silhouette_score, davies_bouldin_score, calinski_harabasz_score,
    adjusted_rand_score,
)
import os

os.makedirs("data/processed", exist_ok=True)

# ── Konfigurasi ──────────────────────────────────────────────
TAHUN_ANALISIS = 2024        # Tahun dengan data paling lengkap
N_KLASTER      = 3           # Ditentukan lewat evaluasi_k(): lihat docstring modul
RANDOM_STATE   = 42
N_INIT         = 50          # diulang 50x agar tidak terjebak di optimum lokal
FITUR          = ["total_umkm", "jumlah_industri", "total_koperasi"]

# Label klaster — HANYA nomor urut (mengikuti urutan mentah cluster_id
# dari KMeans, bukan diurutkan ulang berdasar rata-rata apa pun). Sengaja
# tidak diberi nama/kata sifat: 3 variabel hitung ini bisa menunjukkan
# pola, tapi tidak cukup untuk menyimpulkan karakter/kualitas suatu
# kecamatan, dan kata ringkas apa pun berisiko dibaca sebagai penilaian.
#
# Catatan reproduksibilitas: dengan RANDOM_STATE=42, N_INIT=50, dan data
# diurutkan alfabetis berdasar kecamatan (lihat muat_data), label mentah
# KMeans (0,1,2) yang dihasilkan kebetulan sudah berurutan dari rata-rata
# UMKM tertinggi ke terendah — bukan karena diurutkan secara sengaja,
# tapi karena itulah urutan yang konsisten dihasilkan k-means++ pada data
# ini. Nomor klaster di sini karena itu SAMA dengan penomoran pada
# Tabel II.3 laporan. Jika FITUR, urutan baris, atau parameter di atas
# berubah, jalankan ulang evaluasi_k() dan periksa kembali kesesuaian ini
# sebelum mempercayai korespondensi nomor klaster dengan laporan.
LABEL_KLASTER = {
    0: "Klaster 1",
    1: "Klaster 2",
    2: "Klaster 3",
}

WARNA_KLASTER = {
    "Klaster 1": "#378ADD",   # biru
    "Klaster 2": "#1D9E75",   # teal
    "Klaster 3": "#EF9F27",   # amber
}


# ════════════════════════════════════════════════════════════
# LANGKAH 1: Muat & siapkan data
# ════════════════════════════════════════════════════════════
def muat_data(tahun: int) -> pd.DataFrame:
    path = "data/clean/master_gabungan.csv"
    df = pd.read_csv(path)
    df_tahun = df[df["tahun"] == tahun].copy()
    # Diurutkan alfabetis agar urutan baris yang masuk ke KMeans selalu
    # sama tiap kali dijalankan, apa pun urutan aslinya di CSV sumber —
    # lihat catatan reproduksibilitas pada LABEL_KLASTER di atas.
    df_tahun.sort_values("kecamatan", inplace=True)
    df_tahun.reset_index(drop=True, inplace=True)
    print(f"  Data tahun {tahun}: {len(df_tahun)} kecamatan")
    print(f"  Fitur: {FITUR}")
    print(f"  Missing values: {df_tahun[FITUR].isnull().sum().to_dict()}")
    return df_tahun


# ════════════════════════════════════════════════════════════
# LANGKAH 2: Transformasi log1p + normalisasi fitur
# ════════════════════════════════════════════════════════════
def normalisasi(df: pd.DataFrame) -> tuple:
    X = df[FITUR].fillna(0).values
    # log1p dulu: jumlah UMKM Pringapus jauh di atas kecamatan lain, dan
    # tanpa transformasi ini pernah menyebabkan Pringapus jadi klaster
    # tunggal (lihat docstring modul).
    X_log = np.log1p(X)
    scaler = StandardScaler()
    X_sc = scaler.fit_transform(X_log)
    print(f"  Fitur ditransformasi log1p, lalu di-scaling — mean≈0, std≈1 ✓")
    return X, X_sc, scaler


# ════════════════════════════════════════════════════════════
# LANGKAH 3: Evaluasi jumlah klaster — bukan cuma Silhouette
# ════════════════════════════════════════════════════════════
def evaluasi_k(X_sc: np.ndarray, k_range=range(2, 9)) -> pd.DataFrame:
    """Menghitung Silhouette, Davies-Bouldin, dan Calinski-Harabasz untuk
    tiap k, plus ukuran klaster (untuk menandai klaster tunggal)."""
    baris = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=N_INIT,
                    init="k-means++")
        lbl = km.fit_predict(X_sc)
        ukuran = sorted(np.bincount(lbl).tolist())
        baris.append(dict(
            k=k, inertia=km.inertia_,
            silhouette=silhouette_score(X_sc, lbl),
            davies_bouldin=davies_bouldin_score(X_sc, lbl),
            calinski_harabasz=calinski_harabasz_score(X_sc, lbl),
            klaster_tunggal=(ukuran[0] == 1),
            ukuran=ukuran,
        ))
    hasil = pd.DataFrame(baris)

    print("\n  Evaluasi jumlah klaster (data log1p + StandardScaler):")
    print(f"  {'k':>3} {'Inertia':>10} {'Silhouette':>11} {'Davies-Bouldin':>15} "
          f"{'Calinski-Harabasz':>18} {'Ukuran klaster':>20}")
    for _, r in hasil.iterrows():
        marker = " ← dipilih" if r["k"] == N_KLASTER else ""
        peringatan = "  (ada klaster tunggal!)" if r["klaster_tunggal"] else ""
        print(f"  {r['k']:>3} {r['inertia']:>10.3f} {r['silhouette']:>11.3f} {r['davies_bouldin']:>15.3f} "
              f"{r['calinski_harabasz']:>18.1f} {str(r['ukuran']):>20}{marker}{peringatan}")
    return hasil


def uji_stabilitas(X_raw_log: pd.DataFrame, k: int, n_boot: int = 50,
                    frac: float = 0.8, seed: int = 0) -> float:
    """Rata-rata Adjusted Rand Index antara hasil klasterisasi pada
    seluruh data vs subsampel acak — indikasi kestabilan hasil."""
    X_full = StandardScaler().fit_transform(X_raw_log)
    label_penuh = KMeans(k, n_init=N_INIT, random_state=RANDOM_STATE,
                          init="k-means++").fit_predict(X_full)
    rng = np.random.default_rng(seed)
    n = len(X_raw_log)
    skor = []
    for _ in range(n_boot):
        idx = rng.choice(n, int(frac * n), replace=False)
        X_sub = StandardScaler().fit_transform(X_raw_log.iloc[idx])
        label_sub = KMeans(k, n_init=20, random_state=int(rng.integers(1e6)),
                            init="k-means++").fit_predict(X_sub)
        skor.append(adjusted_rand_score(label_penuh[idx], label_sub))
    return float(np.mean(skor))


def bandingkan_dengan_ward(X_sc: np.ndarray, label_kmeans: np.ndarray, k: int) -> float:
    """ARI antara K-Means dan Hierarchical Clustering (Ward) pada k yang
    sama — validasi independen bahwa struktur klaster bukan artefak satu
    algoritma saja."""
    label_ward = AgglomerativeClustering(k, linkage="ward").fit_predict(X_sc)
    return adjusted_rand_score(label_kmeans, label_ward)


# ════════════════════════════════════════════════════════════
# LANGKAH 4: Jalankan K-Means final
# ════════════════════════════════════════════════════════════
def jalankan_kmeans(df: pd.DataFrame, X_sc: np.ndarray) -> pd.DataFrame:
    km = KMeans(
        n_clusters   = N_KLASTER,
        random_state = RANDOM_STATE,
        n_init       = N_INIT,
        init         = "k-means++",
        max_iter     = 300,
    )
    df = df.copy()
    df["klaster_id"]   = km.fit_predict(X_sc)
    df["klaster"]      = df["klaster_id"].map(LABEL_KLASTER)
    df["warna"]        = df["klaster"].map(WARNA_KLASTER)

    sil = silhouette_score(X_sc, df["klaster_id"])
    print(f"\n  Silhouette Score: {sil:.3f}  (mendekati 1 = klaster baik)")
    print(f"  Inertia: {km.inertia_:.3f}")

    ari_ward = bandingkan_dengan_ward(X_sc, df["klaster_id"].values, N_KLASTER)
    print(f"  ARI vs Hierarchical Clustering (Ward): {ari_ward:.3f}  (1,0 = partisi identik)")

    return df, km


# ════════════════════════════════════════════════════════════
# LANGKAH 5: Ringkasan rata-rata tiap klaster
# ════════════════════════════════════════════════════════════
def buat_ringkasan_klaster(df: pd.DataFrame) -> pd.DataFrame:
    ringkasan = (
        df.groupby(["klaster_id", "klaster"])
          .agg(
              jumlah_kecamatan = ("kecamatan",      "count"),
              rata_umkm        = ("total_umkm",      "mean"),
              rata_industri    = ("jumlah_industri", "mean"),
              rata_koperasi    = ("total_koperasi",  "mean"),
              total_umkm       = ("total_umkm",      "sum"),
              total_industri   = ("jumlah_industri", "sum"),
              kecamatan_list   = ("kecamatan",
                                  lambda x: ", ".join(sorted(x))),
          )
          .reset_index()
    )

    for col in ["rata_umkm", "rata_industri", "rata_koperasi"]:
        ringkasan[col] = ringkasan[col].round(1)

    # Urutkan tampilan berdasar klaster_id (urutan asli, netral) —
    # bukan berdasar rata-rata apa pun, supaya urutan baris tidak
    # terbaca sebagai peringkat baik-buruk.
    ringkasan.sort_values("klaster_id", inplace=True)
    ringkasan.reset_index(drop=True, inplace=True)
    return ringkasan


# ════════════════════════════════════════════════════════════
# LANGKAH 6: Profil tiap klaster — murni angka & peringkat
# ════════════════════════════════════════════════════════════
def buat_profil_klaster(ringkasan: pd.DataFrame) -> pd.DataFrame:
    """
    Profil tiap klaster ditulis sebagai ANGKA (rata-rata) dan PERINGKAT
    (1 = tertinggi, N_KLASTER = terendah, dibanding klaster lain) untuk
    tiap indikator. Sengaja tidak ada kata sifat/ringkasan naratif —
    peringkat menunjukkan pola tanpa menyimpulkan baik-buruknya, karena
    "peringkat terendah" pada 3 variabel hitung tidak serta-merta berarti
    kecamatan itu bermasalah; bisa banyak faktor lain yang tidak
    tertangkap di sini.
    """
    profil = ringkasan.copy()

    for kol_rata, kol_peringkat in [
        ("rata_umkm",     "peringkat_umkm"),
        ("rata_industri", "peringkat_industri"),
        ("rata_koperasi", "peringkat_koperasi"),
    ]:
        profil[kol_peringkat] = (
            profil[kol_rata].rank(ascending=False, method="min").astype(int)
        )

    kolom = [
        "klaster", "jumlah_kecamatan", "kecamatan_list",
        "rata_umkm", "peringkat_umkm",
        "rata_industri", "peringkat_industri",
        "rata_koperasi", "peringkat_koperasi",
    ]
    profil = profil[kolom].rename(columns={"kecamatan_list": "kecamatan"})
    profil.sort_values("klaster", inplace=True)
    profil.reset_index(drop=True, inplace=True)
    return profil


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("K-MEANS CLUSTERING UMKM & KOPERASI")
    print(f"Kabupaten Semarang — Tahun {TAHUN_ANALISIS}")
    print("=" * 55)

    # 1. Muat data
    print("\nLangkah 1: Muat data")
    df = muat_data(TAHUN_ANALISIS)

    # 2. Transformasi + normalisasi
    print("\nLangkah 2: Transformasi log1p + normalisasi fitur")
    X, X_sc, scaler = normalisasi(df)
    X_log = pd.DataFrame(np.log1p(df[FITUR].fillna(0).values), columns=FITUR)

    # 3. Evaluasi jumlah klaster
    print("\nLangkah 3: Evaluasi jumlah klaster")
    tabel_evaluasi = evaluasi_k(X_sc)
    tabel_evaluasi.to_csv("data/processed/klaster_evaluasi_k.csv", index=False)
    stabilitas = uji_stabilitas(X_log, N_KLASTER)
    print(f"  Kestabilan bootstrap k={N_KLASTER} (ARI rata-rata, 50 subsampel 80%): {stabilitas:.3f}")

    # 4. K-Means final
    print(f"\nLangkah 4: K-Means final (k={N_KLASTER})")
    df_hasil, km = jalankan_kmeans(df, X_sc)

    # 5. Simpan hasil klaster
    cols_simpan = [
        "kecamatan", "tahun", "total_umkm", "jumlah_industri",
        "total_koperasi", "total_usaha", "sektor_dominan",
        "klaster_id", "klaster", "warna",
    ]
    df_hasil[cols_simpan].to_csv(
        "data/processed/umkm_klaster.csv",
        index=False, encoding="utf-8-sig"
    )
    print(f"  Disimpan: data/processed/umkm_klaster.csv")

    # 6. Ringkasan klaster
    print("\nLangkah 5: Ringkasan klaster")
    ringkasan = buat_ringkasan_klaster(df_hasil)
    ringkasan.to_csv(
        "data/processed/klaster_ringkasan.csv",
        index=False, encoding="utf-8-sig"
    )
    print(f"  Disimpan: data/processed/klaster_ringkasan.csv")

    # 7. Profil klaster (angka & peringkat, tanpa kata sifat)
    print("\nLangkah 6: Profil klaster (angka & peringkat)")
    profil = buat_profil_klaster(ringkasan)
    profil.to_csv(
        "data/processed/klaster_profil.csv",
        index=False, encoding="utf-8-sig"
    )
    print(f"  Disimpan: data/processed/klaster_profil.csv")

    # ── Tampilan hasil ───────────────────────────────────────
    print("\n" + "=" * 55)
    print("HASIL CLUSTERING")
    print("=" * 55)
    for _, row in ringkasan.iterrows():
        print(f"\n  [{row['klaster']}]")
        print(f"  Kecamatan ({int(row['jumlah_kecamatan'])}): {row['kecamatan_list']}")
        print(f"  Rata-rata UMKM     : {row['rata_umkm']:,.0f}")
        print(f"  Rata-rata Industri : {row['rata_industri']:,.0f}")
        print(f"  Rata-rata Koperasi : {row['rata_koperasi']:,.0f}")

    print("\n" + "=" * 55)
    print(f"PROFIL KLASTER (peringkat 1 = tertinggi dari {N_KLASTER} klaster)")
    print("=" * 55)
    print(profil.to_string(index=False))

    print("\n" + "=" * 55)
    print("DETAIL PER KECAMATAN")
    print("=" * 55)
    print(df_hasil[["kecamatan","total_umkm","jumlah_industri",
                    "total_koperasi","klaster"]]
          .sort_values("klaster")
          .to_string(index=False))

    print("\nSelesai! Lanjut ke dashboard Streamlit.")


if __name__ == "__main__":
    main()
