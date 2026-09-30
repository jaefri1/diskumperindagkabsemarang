"""
cleaning_umkm_kbli.py
Membersihkan & merestrukturisasi file Excel UMKM per Kecamatan (KBLI 2 digit)
dari format hierarkis menjadi tabel flat siap dimasukkan ke database MySQL.

Input : Indikator_Jumlah_Jenis_Usaha_Mikro_..._KBLI_2_digit_....xlsx
Output: data/clean/umkm_kbli_flat.csv

Jalankan:
    python cleaning_umkm_kbli.py
"""

import pandas as pd
import re
import os

# ── Path ────────────────────────────────────────────────────
FILE_INPUT  = "data/raw/umkm_kbli.xlsx"   # ganti sesuai nama file yang kamu simpan
FILE_OUTPUT = "data/clean/umkm_kbli_flat.csv"
os.makedirs("data/clean", exist_ok=True)


# ════════════════════════════════════════════════════════════
# LANGKAH 1: Baca file mentah tanpa header
# ════════════════════════════════════════════════════════════
def baca_file(path: str) -> pd.DataFrame:
    print(f"Membaca file: {path}")
    df = pd.read_excel(path, header=None)
    print(f"  Shape mentah: {df.shape}")
    return df


# ════════════════════════════════════════════════════════════
# LANGKAH 2: Bangun mapping kolom → (tahun, semester)
# ════════════════════════════════════════════════════════════
def bangun_mapping_kolom(df: pd.DataFrame) -> dict:
    """
    Baris 3 = tahun (2017, 2018, ... 2026) — hanya kolom genap yang berisi
    Baris 4 = semester (Semester I / Semester II) — semua kolom data berisi

    Kembalikan dict: {index_kolom: (tahun, semester)}
    """
    tahun_row = df.iloc[3]
    sem_row   = df.iloc[4]

    mapping = {}
    tahun_aktif = None

    for i in range(1, len(tahun_row)):
        t = tahun_row[i]
        s = sem_row[i]

        # Update tahun jika baris tahun terisi
        if str(t) not in ["nan", "NaN", "None"] and t == t:
            try:
                tahun_aktif = int(float(str(t)))
            except ValueError:
                pass

        # Ambil kolom yang punya semester
        if str(s) not in ["nan", "NaN", "None"] and s == s and tahun_aktif:
            sem_bersih = str(s).strip()
            mapping[i] = (tahun_aktif, sem_bersih)

    print(f"  Ditemukan {len(mapping)} kolom data (tahun × semester)")
    return mapping


# ════════════════════════════════════════════════════════════
# LANGKAH 3: Tentukan apakah sebuah baris adalah KBLI induk
#            atau baris kecamatan (anak)
# ════════════════════════════════════════════════════════════
def jenis_baris(nilai: str) -> str:
    """
    Kembalikan:
    - 'judul'    : baris judul dataset (baris 5)
    - 'kbli'     : baris induk kategori KBLI  → "1. Pertanian, ..."
    - 'kecamatan': baris anak                 → "    a.) Getasan"
    - 'skip'     : baris header / kosong / lain-lain
    """
    val = str(nilai).strip()
    if not val or val in ["nan", "NaN", "None", "-"]:
        return "skip"
    if re.match(r"^\d+\.\s", val):
        return "kbli"
    if re.match(r"^[a-zA-Z]+\.\)", val.lstrip()):
        return "kecamatan"
    return "skip"


def bersihkan_nama_kecamatan(nama: str) -> str:
    """Hapus prefix huruf dan tanda baca: '    a.) Getasan' → 'Getasan'"""
    nama = str(nama).strip()
    nama = re.sub(r"^[a-zA-Z]+\.\)\s*", "", nama)
    return nama.strip().title()


def bersihkan_nama_kbli(nama: str) -> str:
    """Hapus nomor di depan: '1. Pertanian, ...' → 'Pertanian, ...'"""
    nama = str(nama).strip()
    nama = re.sub(r"^\d+\.\s*", "", nama)
    return nama.strip()


def konversi_nilai(val) -> float:
    """
    Konversi nilai sel ke float.
    Tangani: '-', angka string '1.234', integer, float, NaN
    """
    if val is None or val != val:       # NaN check
        return 0.0
    s = str(val).strip()
    if s in ["-", "", "nan", "NaN"]:
        return 0.0
    # Hapus titik pemisah ribuan (format Indonesia)
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


# ════════════════════════════════════════════════════════════
# LANGKAH 4: Parsing utama — ubah hierarkis → flat
# ════════════════════════════════════════════════════════════
def parse_hierarkis(df: pd.DataFrame, mapping_kolom: dict) -> list[dict]:
    """
    Telusuri baris satu per satu.
    Saat menemukan baris KBLI → simpan sebagai konteks aktif.
    Saat menemukan baris kecamatan → buat record dengan konteks KBLI tersebut.
    """
    records = []
    kbli_aktif = None

    for i, row in df.iterrows():
        if i < 5:           # lewati baris header
            continue

        sel_pertama = row[0]
        tipe = jenis_baris(sel_pertama)

        if tipe == "kbli":
            kbli_aktif = bersihkan_nama_kbli(str(sel_pertama))

        elif tipe == "kecamatan" and kbli_aktif:
            kecamatan = bersihkan_nama_kecamatan(str(sel_pertama))

            # Ambil semua nilai tahun × semester untuk baris ini
            for col_idx, (tahun, semester) in mapping_kolom.items():
                nilai = konversi_nilai(row[col_idx])
                records.append({
                    "kecamatan"   : kecamatan,
                    "sektor_kbli" : kbli_aktif,
                    "tahun"       : tahun,
                    "semester"    : semester,
                    "jumlah_usaha": int(nilai),
                })

    print(f"  Total record dihasilkan: {len(records):,}")
    return records


# ════════════════════════════════════════════════════════════
# LANGKAH 5: Bersihkan dan validasi hasil
# ════════════════════════════════════════════════════════════
def bersihkan_hasil(df_flat: pd.DataFrame) -> pd.DataFrame:
    """Hapus duplikat, filter baris kosong, urutkan."""

    sebelum = len(df_flat)

    # Hapus baris yang jumlah_usaha = 0 DAN bukan karena memang 0
    # (bedakan 0 asli vs belum diisi — kita tandai dengan NaN)
    # Di sini kita pertahankan 0 karena bisa jadi sektor memang tidak ada

    # Hapus duplikat
    df_flat.drop_duplicates(
        subset=["kecamatan", "sektor_kbli", "tahun", "semester"],
        inplace=True
    )

    # Urutkan
    df_flat.sort_values(
        ["kecamatan", "sektor_kbli", "tahun", "semester"],
        inplace=True
    )
    df_flat.reset_index(drop=True, inplace=True)

    sesudah = len(df_flat)
    print(f"  Duplikat dihapus: {sebelum - sesudah} baris")
    return df_flat


# ════════════════════════════════════════════════════════════
# LANGKAH 6: Buat ringkasan agregat per kecamatan per tahun
#            (lebih praktis untuk clustering & dashboard)
# ════════════════════════════════════════════════════════════
def buat_ringkasan(df_flat: pd.DataFrame) -> pd.DataFrame:
    """
    Agregasi: total UMKM per kecamatan per tahun
    (gabungkan semua sektor, ambil semester terbaru per tahun)
    """
    # Ambil data semester terbaru per tahun
    urutan_sem = {"Semester II": 1, "Semester I": 2}
    df_flat["urutan_sem"] = df_flat["semester"].map(urutan_sem).fillna(99)

    df_terbaru = (
        df_flat
        .sort_values(["kecamatan", "sektor_kbli", "tahun", "urutan_sem"])
        .groupby(["kecamatan", "sektor_kbli", "tahun"])
        .first()
        .reset_index()
    )

    # Total semua sektor per kecamatan per tahun
    ringkasan = (
        df_terbaru
        .groupby(["kecamatan", "tahun"])["jumlah_usaha"]
        .sum()
        .reset_index()
        .rename(columns={"jumlah_usaha": "total_umkm"})
    )

    # Tambah kolom sektor dominan
    sektor_dominan = (
        df_terbaru
        .loc[df_terbaru.groupby(["kecamatan", "tahun"])["jumlah_usaha"].idxmax()]
        [["kecamatan", "tahun", "sektor_kbli"]]
        .rename(columns={"sektor_kbli": "sektor_dominan"})
    )

    ringkasan = ringkasan.merge(sektor_dominan, on=["kecamatan", "tahun"], how="left")
    ringkasan.sort_values(["kecamatan", "tahun"], inplace=True)
    ringkasan.reset_index(drop=True, inplace=True)

    return ringkasan


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("CLEANING UMKM KBLI — HIERARKIS → FLAT")
    print("=" * 55)

    # 1. Baca
    df_raw = baca_file(FILE_INPUT)

    # 2. Mapping kolom
    print("\nLangkah 2: Mapping kolom tahun/semester")
    mapping = bangun_mapping_kolom(df_raw)

    # 3. Parse
    print("\nLangkah 3: Parsing data hierarkis")
    records = parse_hierarkis(df_raw, mapping)

    # 4. Buat DataFrame flat
    print("\nLangkah 4: Membuat DataFrame flat")
    df_flat = pd.DataFrame(records)
    print(f"  Shape awal: {df_flat.shape}")

    # 5. Bersihkan
    print("\nLangkah 5: Membersihkan & validasi")
    df_flat = bersihkan_hasil(df_flat)
    print(f"  Shape akhir: {df_flat.shape}")

    # 6. Simpan flat lengkap
    df_flat.to_csv(FILE_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"\nFile flat disimpan: {FILE_OUTPUT}")

    # 7. Buat dan simpan ringkasan
    print("\nLangkah 6: Membuat ringkasan per kecamatan per tahun")
    ringkasan = buat_ringkasan(df_flat)
    path_ringkasan = FILE_OUTPUT.replace("umkm_kbli_flat", "umkm_ringkasan")
    ringkasan.to_csv(path_ringkasan, index=False, encoding="utf-8-sig")
    print(f"  Shape ringkasan: {ringkasan.shape}")
    print(f"  File ringkasan disimpan: {path_ringkasan}")

    # 8. Preview
    print("\n" + "=" * 55)
    print("PREVIEW — 10 BARIS PERTAMA (flat)")
    print("=" * 55)
    print(df_flat.head(10).to_string(index=False))

    print("\n" + "=" * 55)
    print("PREVIEW — RINGKASAN PER KECAMATAN (tahun terbaru)")
    print("=" * 55)
    tahun_max = ringkasan["tahun"].max()
    print(ringkasan[ringkasan["tahun"] == tahun_max].to_string(index=False))

    print("\n" + "=" * 55)
    print("STATISTIK AKHIR")
    print("=" * 55)
    print(f"  Jumlah kecamatan : {df_flat['kecamatan'].nunique()}")
    print(f"  Jumlah sektor KBLI: {df_flat['sektor_kbli'].nunique()}")
    print(f"  Rentang tahun     : {df_flat['tahun'].min()} – {df_flat['tahun'].max()}")
    print(f"  Total record flat : {len(df_flat):,}")
    print(f"  Total record ringkasan: {len(ringkasan):,}")
    print("\nSelesai! Siap dimasukkan ke database.")


if __name__ == "__main__":
    main()
