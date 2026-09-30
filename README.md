# Dashboard Analitik UMKM & Koperasi
## Kabupaten Semarang

Project magang MBKM di Dinas Koperasi, Usaha Mikro, Perindustrian dan
Perdagangan Kabupaten Semarang — mata kuliah **Database** & **Data Mining**.

Dashboard interaktif (Streamlit) untuk memantau UMKM, koperasi, dan
industri kecil per kecamatan, dengan segmentasi K-Means clustering,
peta choropleth, dan export laporan PDF.

---

## Struktur folder

Folder dibagi 3 lapis sesuai kebutuhan — tidak semua orang perlu semua file.

### 1. Menjalankan dashboard (wajib, minimal)

```
dashboard-umkm/
├── dashboard.py
├── pdf_generator.py
├── requirements.txt
└── data/
    ├── db/
    │   └── umkm_semarang.db
    └── geo/
        └── kecamatan_semarang.geojson
```

### 2. Memperbarui data (kalau dapat data baru dari dinas)

```
dashboard-umkm/
├── (semua file di atas)
├── setup_database.py
├── cleaning_umkm_kbli.py
├── cleaning_koperasi_kecamatan.py
├── cleaning_sisa.py
├── clustering_kmeans.py
└── data/
    ├── raw/        ← Excel dari dinas ditaruh sini
    ├── clean/       (dibuat otomatis)
    └── processed/   (dibuat otomatis)
```

### 3. Dokumentasi laporan (opsional)

```
dashboard-umkm/
├── query_contoh.py             # 5 contoh query SQL (JOIN, GROUP BY, subquery)
├── analisis_lanjutan.py        # tren aset koperasi & korelasi indikator
└── database_schema_mysql.sql   # skema alternatif kalau perlu MySQL
```

---

## Cara menjalankan (quick start)

```bash
# 1. Install semua library
pip install -r requirements.txt

# 2. Jalankan dashboard
streamlit run dashboard.py
```

Buka browser ke `http://localhost:8501`.

> **Windows / PowerShell:** kalau `pip` atau `streamlit` muncul error
> "not recognized", pakai `python -m pip install -r requirements.txt`
> dan `python -m streamlit run dashboard.py` sebagai gantinya.

---

## Cara memperbarui data

Kalau dapat data Excel baru dari dinas:

```bash
# 1. Taruh 5 file Excel di data/raw/ dengan nama:
#    umkm_kbli.xlsx, koperasi_kecamatan.xlsx,
#    aset_koperasi.xlsx, industri_kecil.xlsx, omset_perdagangan.xlsx

# 2. Jalankan pipeline berurutan:
python cleaning_umkm_kbli.py
python cleaning_koperasi_kecamatan.py
python cleaning_sisa.py
python clustering_kmeans.py
python setup_database.py

# 3. Restart dashboard
streamlit run dashboard.py
```

`setup_database.py` selalu membangun ulang `umkm_semarang.db` dari nol
(DROP + CREATE tabel), jadi aman dijalankan berkali-kali.

---

## Arsitektur & alur data

```
Excel mentah (data.semarangkab.go.id)
        ↓  cleaning_*.py — pembersihan format hierarkis → tabel flat
CSV bersih (data/clean/)
        ↓  clustering_kmeans.py — K-Means (k=4)
CSV hasil klaster (data/processed/)
        ↓  setup_database.py — DDL + import
Database SQLite (data/db/umkm_semarang.db)   ← 7 tabel, ternormalisasi
        ↓  query SQL langsung (sqlite3 + pandas)
Dashboard Streamlit (dashboard.py)
        ↓
Export PDF (pdf_generator.py) · Peta interaktif (folium)
```

Database jadi satu-satunya sumber data dashboard — tidak ada CSV yang
dibaca langsung oleh `dashboard.py`.

---

## Skema database (7 tabel)

| Tabel | Isi |
|---|---|
| `kecamatan` | Master, 19 kecamatan |
| `sektor_umkm` | UMKM × sektor KBLI × tahun × semester |
| `koperasi` | Koperasi × jenis × tahun × semester |
| `industri_kecil` | Industri kecil × tahun × semester |
| `aset_koperasi` | Aset koperasi × jenis × tahun (level kabupaten) |
| `hasil_klaster` | Output K-Means — data mining tersimpan ke database |
| `profil_klaster` | Rata-rata & peringkat tiap klaster per indikator |

Detail relasi & contoh query ada di `query_contoh.py`.

---

## Metodologi klastering

- **Fitur**: total_umkm, jumlah_industri, total_koperasi (3 variabel hitung)
- **k**: 4 (dipilih lewat elbow method + silhouette score, lihat `clustering_kmeans.py`)
- **Silhouette score**: 0.369
- **Penamaan klaster**: sengaja hanya "Klaster 1-4" tanpa kata sifat
  (bukan "unggul"/"perlu pembinaan") — karakteristiknya dibaca dari
  tabel profil & grafik, bukan dari nama yang menyiratkan penilaian.
  3 variabel hitung ini menunjukkan pola, bukan kesimpulan kualitas
  suatu kecamatan.

---

## Keterbatasan data (penting untuk laporan)

- Data omset per unit UMKM **tidak dipakai** — sensitif, tidak
  dipublikasikan dinas secara terbuka.
- UMKM, koperasi, industri kecil hanya lengkap untuk **tahun 2024**;
  tahun-tahun sebelumnya sebagian besar belum dilaporkan ke portal.
- Aset koperasi punya data 2017-2023, tapi ada lompatan skala
  ~2.173× antara 2019→2020 (kemungkinan perubahan satuan/metodologi
  pelaporan) — dashboard hanya menampilkan tren 2020-2023 yang skalanya
  konsisten. Detail deteksinya ada di `analisis_lanjutan.py`.
- Korelasi antar indikator dihitung dari 19 kecamatan saja (sampel
  kecil) dan sensitif terhadap outlier (Pringapus).

---

## Sumber data

| Sumber | URL |
|---|---|
| Portal Satu Data Kab. Semarang | data.semarangkab.go.id |
| GeoJSON batas kecamatan | JfrAziz/indonesia-district (turunan HDX) |

---

## Mahasiswa

Nama  :
NIM   :
Prodi : Matematika
Dosen pembimbing :
Pembimbing lapangan :
Periode magang :
