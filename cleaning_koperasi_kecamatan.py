"""
cleaning_koperasi_kecamatan.py
Membersihkan & merestrukturisasi file Excel Koperasi per Jenis dan Kecamatan
dari format hierarkis menjadi tabel flat siap dimasukkan ke database MySQL.

Input : data/raw/koperasi_kecamatan.xlsx
Output:
  - data/clean/koperasi_flat.csv      → detail per jenis koperasi × kecamatan × tahun
  - data/clean/koperasi_ringkasan.csv → total koperasi per kecamatan per tahun

Jalankan:
    python cleaning_koperasi_kecamatan.py
"""

import pandas as pd
import re
import os

# ── Path ────────────────────────────────────────────────────
FILE_INPUT       = "data/raw/koperasi_kecamatan.xlsx"
FILE_FLAT        = "data/clean/koperasi_flat.csv"
FILE_RINGKASAN   = "data/clean/koperasi_ringkasan.csv"
FILE_GABUNGAN    = "data/clean/umkm_koperasi_gabungan.csv"
os.makedirs("data/clean", exist_ok=True)


# ════════════════════════════════════════════════════════════
# LANGKAH 1: Baca file mentah
# ════════════════════════════════════════════════════════════
def baca_file(path: str) -> pd.DataFrame:
    print(f"Membaca: {path}")
    df = pd.read_excel(path, header=None)
    print(f"  Shape mentah: {df.shape}")
    return df


# ════════════════════════════════════════════════════════════
# LANGKAH 2: Mapping kolom → (tahun, semester)
# ════════════════════════════════════════════════════════════
def bangun_mapping_kolom(df: pd.DataFrame) -> dict:
    tahun_row = df.iloc[3]
    sem_row   = df.iloc[4]
    mapping   = {}
    tahun_aktif = None

    for i in range(1, len(tahun_row)):
        t = tahun_row[i]
        s = sem_row[i]
        if str(t) not in ["nan", "NaN", "None"] and t == t:
            try:
                tahun_aktif = int(float(str(t)))
            except ValueError:
                pass
        if str(s) not in ["nan", "NaN", "None"] and s == s and tahun_aktif:
            mapping[i] = (tahun_aktif, str(s).strip())

    print(f"  Kolom data ditemukan: {len(mapping)} (tahun × semester)")
    return mapping


# ════════════════════════════════════════════════════════════
# LANGKAH 3: Klasifikasi baris
# ════════════════════════════════════════════════════════════

# Jenis koperasi yang dikenali (baris induk)
# "6. Jumlah koperasi" = TOTAL, kita tandai khusus
JENIS_KOPERASI_TOTAL = "jumlah koperasi"

def jenis_baris(nilai: str) -> str:
    val = str(nilai).strip()
    if not val or val in ["nan", "NaN", "None", "-"]:
        return "skip"
    # baris induk: diawali angka + titik
    if re.match(r"^\d+\.\s", val):
        return "jenis_koperasi"
    # baris anak: diawali huruf + .)
    if re.match(r"^[a-zA-Z]+\.\)", val.lstrip()):
        return "kecamatan"
    return "skip"


def bersihkan_nama_kecamatan(nama: str) -> str:
    """'    a.) Getasan' → 'Getasan'"""
    nama = str(nama).strip()
    nama = re.sub(r"^[a-zA-Z]+\.\)\s*", "", nama)
    return nama.strip().title()


def bersihkan_jenis_koperasi(nama: str) -> str:
    """'1. KUD' → 'KUD' | '6. Jumlah koperasi' → 'TOTAL'"""
    nama = str(nama).strip()
    nama = re.sub(r"^\d+\.\s*", "", nama).strip()
    if nama.lower() == JENIS_KOPERASI_TOTAL:
        return "TOTAL"
    return nama.upper()


def konversi_nilai(val) -> int:
    if val is None or val != val:
        return 0
    s = str(val).strip()
    if s in ["-", "", "nan", "NaN"]:
        return 0
    s = s.replace(".", "").replace(",", "")
    try:
        return int(float(s))
    except ValueError:
        return 0


# ════════════════════════════════════════════════════════════
# LANGKAH 4: Parse hierarkis → flat
# ════════════════════════════════════════════════════════════
def parse_hierarkis(df: pd.DataFrame, mapping: dict) -> list[dict]:
    records      = []
    jenis_aktif  = None

    for i, row in df.iterrows():
        if i < 5:
            continue

        tipe = jenis_baris(row[0])

        if tipe == "jenis_koperasi":
            jenis_aktif = bersihkan_jenis_koperasi(str(row[0]))

        elif tipe == "kecamatan" and jenis_aktif:
            kecamatan = bersihkan_nama_kecamatan(str(row[0]))

            for col_idx, (tahun, semester) in mapping.items():
                nilai = konversi_nilai(row[col_idx])
                records.append({
                    "kecamatan"      : kecamatan,
                    "jenis_koperasi" : jenis_aktif,
                    "tahun"          : tahun,
                    "semester"       : semester,
                    "jumlah_koperasi": nilai,
                })

    print(f"  Total record dihasilkan: {len(records):,}")
    return records


# ════════════════════════════════════════════════════════════
# LANGKAH 5: Bersihkan DataFrame
# ════════════════════════════════════════════════════════════
def bersihkan_hasil(df_flat: pd.DataFrame) -> pd.DataFrame:
    sebelum = len(df_flat)
    df_flat.drop_duplicates(
        subset=["kecamatan", "jenis_koperasi", "tahun", "semester"],
        inplace=True
    )
    df_flat.sort_values(
        ["kecamatan", "jenis_koperasi", "tahun", "semester"],
        inplace=True
    )
    df_flat.reset_index(drop=True, inplace=True)
    print(f"  Duplikat dihapus: {sebelum - len(df_flat)} baris")
    return df_flat


# ════════════════════════════════════════════════════════════
# LANGKAH 6: Buat ringkasan per kecamatan per tahun
# ════════════════════════════════════════════════════════════
def buat_ringkasan(df_flat: pd.DataFrame) -> pd.DataFrame:
    """
    Gunakan baris TOTAL (jenis_koperasi == 'TOTAL') per semester terbaru.
    Hasilkan: kecamatan | tahun | total_koperasi | jenis_terbanyak
    """
    # Ambil hanya baris TOTAL
    df_total = df_flat[df_flat["jenis_koperasi"] == "TOTAL"].copy()

    # Ambil semester terbaru per tahun (Semester II lebih baru dari I)
    urutan = {"Semester II": 1, "Semester I": 2}
    df_total["urutan"] = df_total["semester"].map(urutan).fillna(99)
    df_terbaru = (
        df_total
        .sort_values(["kecamatan", "tahun", "urutan"])
        .groupby(["kecamatan", "tahun"])
        .first()
        .reset_index()
        [["kecamatan", "tahun", "jumlah_koperasi"]]
        .rename(columns={"jumlah_koperasi": "total_koperasi"})
    )

    # Tambah jenis koperasi terbanyak (exclude TOTAL)
    df_jenis = df_flat[df_flat["jenis_koperasi"] != "TOTAL"].copy()
    df_jenis["urutan"] = df_jenis["semester"].map(urutan).fillna(99)
    df_jenis_terbaru = (
        df_jenis
        .sort_values(["kecamatan", "jenis_koperasi", "tahun", "urutan"])
        .groupby(["kecamatan", "jenis_koperasi", "tahun"])
        .first()
        .reset_index()
    )
    idx_max = df_jenis_terbaru.groupby(["kecamatan", "tahun"])["jumlah_koperasi"].idxmax()
    jenis_dominan = (
        df_jenis_terbaru.loc[idx_max]
        [["kecamatan", "tahun", "jenis_koperasi"]]
        .rename(columns={"jenis_koperasi": "jenis_dominan"})
    )

    ringkasan = df_terbaru.merge(jenis_dominan, on=["kecamatan", "tahun"], how="left")
    ringkasan.sort_values(["tahun", "total_koperasi"], ascending=[True, False], inplace=True)
    ringkasan.reset_index(drop=True, inplace=True)
    return ringkasan


# ════════════════════════════════════════════════════════════
# LANGKAH 7: Gabungkan dengan ringkasan UMKM (jika ada)
# ════════════════════════════════════════════════════════════
def gabungkan_dengan_umkm(ringkasan_kop: pd.DataFrame) -> pd.DataFrame | None:
    path_umkm = "data/clean/umkm_ringkasan.csv"
    if not os.path.exists(path_umkm):
        print("  File umkm_ringkasan.csv belum ada — lewati penggabungan")
        return None

    df_umkm = pd.read_csv(path_umkm)
    df_gabung = pd.merge(
        df_umkm,
        ringkasan_kop[["kecamatan", "tahun", "total_koperasi", "jenis_dominan"]],
        on=["kecamatan", "tahun"],
        how="outer"
    )
    df_gabung.sort_values(["tahun", "kecamatan"], inplace=True)
    df_gabung.reset_index(drop=True, inplace=True)
    print(f"  Tabel gabungan: {df_gabung.shape}")
    return df_gabung


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("CLEANING KOPERASI — HIERARKIS → FLAT")
    print("=" * 55)

    # 1. Baca
    df_raw = baca_file(FILE_INPUT)

    # 2. Mapping kolom
    print("\nLangkah 2: Mapping kolom tahun/semester")
    mapping = bangun_mapping_kolom(df_raw)

    # 3. Parse
    print("\nLangkah 3: Parsing hierarkis")
    records = parse_hierarkis(df_raw, mapping)

    # 4. DataFrame flat
    print("\nLangkah 4: DataFrame flat")
    df_flat = pd.DataFrame(records)

    # 5. Bersihkan
    print("\nLangkah 5: Bersihkan")
    df_flat = bersihkan_hasil(df_flat)

    # Simpan flat
    df_flat.to_csv(FILE_FLAT, index=False, encoding="utf-8-sig")
    print(f"\n  Flat disimpan: {FILE_FLAT}")

    # 6. Ringkasan
    print("\nLangkah 6: Ringkasan per kecamatan per tahun")
    ringkasan = buat_ringkasan(df_flat)
    ringkasan.to_csv(FILE_RINGKASAN, index=False, encoding="utf-8-sig")
    print(f"  Ringkasan disimpan: {FILE_RINGKASAN} ({len(ringkasan)} baris)")

    # 7. Gabungkan dengan UMKM
    print("\nLangkah 7: Gabungkan dengan data UMKM")
    df_gabung = gabungkan_dengan_umkm(ringkasan)
    if df_gabung is not None:
        df_gabung.to_csv(FILE_GABUNGAN, index=False, encoding="utf-8-sig")
        print(f"  Gabungan disimpan: {FILE_GABUNGAN}")

    # ── Preview ──────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("PREVIEW — FLAT (10 baris, jenis=TOTAL)")
    print("=" * 55)
    print(
        df_flat[df_flat["jenis_koperasi"] == "TOTAL"]
        .head(10).to_string(index=False)
    )

    print("\n" + "=" * 55)
    print("PREVIEW — RINGKASAN TAHUN TERBARU")
    print("=" * 55)
    tahun_max = ringkasan[ringkasan["total_koperasi"] > 0]["tahun"].max()
    print(f"Tahun terlengkap: {tahun_max}")
    print(
        ringkasan[ringkasan["tahun"] == tahun_max]
        .sort_values("total_koperasi", ascending=False)
        .to_string(index=False)
    )

    if df_gabung is not None:
        print("\n" + "=" * 55)
        print("PREVIEW — GABUNGAN UMKM + KOPERASI")
        print("=" * 55)
        tahun_g = df_gabung[df_gabung["total_umkm"] > 0]["tahun"].max()
        print(
            df_gabung[df_gabung["tahun"] == tahun_g]
            .sort_values("total_umkm", ascending=False)
            .to_string(index=False)
        )

    print("\n" + "=" * 55)
    print("STATISTIK AKHIR")
    print("=" * 55)
    print(f"  Kecamatan        : {df_flat['kecamatan'].nunique()}")
    print(f"  Jenis koperasi   : {df_flat['jenis_koperasi'].nunique()}")
    print(f"    → {sorted(df_flat['jenis_koperasi'].unique())}")
    print(f"  Rentang tahun    : {df_flat['tahun'].min()}–{df_flat['tahun'].max()}")
    print(f"  Total record flat: {len(df_flat):,}")
    print("\nSelesai! Siap dimasukkan ke database.")


if __name__ == "__main__":
    main()
