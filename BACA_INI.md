# Paket revisi klastering (k=4 → k=3)

Folder ini adalah **subset** dari `dashboard-umkm/`, berisi hanya file yang
sempat diunggah dan ditinjau. Belum termasuk: `requirements.txt`,
`cleaning_umkm_kbli.py`, `cleaning_koperasi_kecamatan.py`, `cleaning_sisa.py`,
isi `data/raw/`, dan `data/geo/`. Salin file di sini menimpa file yang sama
di repo Anda.

## File yang diubah

| File | Perubahan |
|---|---|
| `clustering_kmeans.py` | Transformasi log1p sebelum StandardScaler; k=3 (dari 4); `n_init` 10→50, `init="k-means++"` eksplisit; fungsi baru `evaluasi_k()` (Silhouette, Davies-Bouldin, Calinski-Harabasz, deteksi klaster tunggal), `uji_stabilitas()` (ARI bootstrap), `bandingkan_dengan_ward()`; data diurutkan alfabetis sebelum fit (lihat komentar reproduksibilitas di file) |
| `utils.py` | `TAHUN_UTAMA` 2025→2024 (2025 baru terisi sebagian, lihat catatan di kode); `WARNA_KLASTER` dari 4 warna jadi 3; path gambar lambang (`st.image`) diperbaiki dari backslash Windows ke `BASE_DIR / "data" / "pic" / ...` — **cek apakah file gambarnya memang ada di path itu, folder `data/pic/` tidak muncul di struktur yang diberikan** |
| `dashboard.py` | Teks "Klaster bernomor 1-4" → "1-3" |
| `pages/2_Profil_Klaster.py` | Teks "4 klaster" → "3 klaster"; "4 = terendah dari 4 klaster" → "3 = terendah dari 3 klaster" |
| `setup_database.py` | Pesan cetak "9 tabel" → "10 tabel" (salah hitung dari versi awal, sama dengan yang diperbaiki di laporan) |
| `pages/5_Export_Laporan.py` | KPI PDF "5 jenis koperasi" (hardcode) → dihitung otomatis dari data (`df_kop_jenis["jenis_koperasi"].nunique()`) |
| `data/db/umkm_semarang.db` | `hasil_klaster` & `profil_klaster` diisi ulang hasil k=3 |

## File yang dicek, TIDAK diubah

`pages/1_Peta_Sebaran.py`, `pages/3_Analisis_Lanjutan.py`,
`pages/4_Data_Detail.py`, `pdf_generator.py`, `database_schema_mysql.sql`,
`query_contoh.py`, `analisis_lanjutan.py`, `.github/workflows/update-database.yml`
— semuanya menarik jumlah/warna klaster secara dinamis dari data, jadi
otomatis ikut benar tanpa perlu disentuh.

## Setelah menyalin file ini ke repo

1. Jalankan ulang pipeline lokal untuk memastikan semua konsisten:
   ```
   python cleaning_umkm_kbli.py
   python cleaning_koperasi_kecamatan.py
   python cleaning_sisa.py
   python clustering_kmeans.py
   python setup_database.py
   ```
   (atau cukup push ke `data/raw/` dan biarkan GitHub Actions yang jalan)
2. `data/db/umkm_semarang.db` di paket ini sudah berisi hasil k=3 — bisa
   langsung dipakai untuk `streamlit run dashboard.py` tanpa menjalankan
   pipeline dulu, kalau cuma mau lihat hasilnya.
3. Cek path gambar lambang di `utils.py` (lihat catatan di tabel atas).
