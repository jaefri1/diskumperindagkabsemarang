"""
cleaning_sisa.py
Membersihkan 3 file Excel sisa:
  1. Pertumbuhan Aset Koperasi  → data/clean/aset_koperasi.csv
  2. Industri Kecil per Kecamatan → data/clean/industri_kecil.csv
  3. Omset Pelaku Usaha Perdagangan → data/clean/omset_perdagangan.csv
  4. Tabel master gabungan final → data/clean/master_gabungan.csv

Jalankan:
    python cleaning_sisa.py
"""

import pandas as pd
import re
import os

os.makedirs("data/clean", exist_ok=True)

# ── Path input ───────────────────────────────────────────────
PATH_ASET      = "data/raw/aset_koperasi.xlsx"
PATH_INDUSTRI  = "data/raw/industri_kecil.xlsx"
PATH_OMSET     = "data/raw/omset_perdagangan.xlsx"


# ════════════════════════════════════════════════════════════
# HELPER: mapping kolom → (tahun, semester) — sama untuk semua file
# ════════════════════════════════════════════════════════════
def bangun_mapping(df: pd.DataFrame) -> dict:
    tahun_row   = df.iloc[3]
    sem_row     = df.iloc[4]
    mapping     = {}
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
    return mapping


def konversi_rupiah(val) -> float:
    """'32.364.603.631' → 32364603631.0  |  '-' → 0.0"""
    if val is None or val != val:
        return 0.0
    s = str(val).strip()
    if s in ["-", "", "nan", "NaN"]:
        return 0.0
    # Format Indonesia: titik = pemisah ribuan, koma = desimal
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def konversi_int(val) -> int:
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


def bersihkan_nama(nama: str) -> str:
    """'1. KUD' → 'KUD'  |  '1. Getasan' → 'Getasan'"""
    nama = str(nama).strip()
    nama = re.sub(r"^\d+\.\s*", "", nama)
    return nama.strip().title()


def semester_terbaru(df: pd.DataFrame, col_nilai: str) -> pd.DataFrame:
    """Ambil nilai semester terbaru (II lebih baru dari I) per tahun per entitas."""
    urutan = {"Semester II": 1, "Semester I": 2}
    df = df.copy()
    df["_urut"] = df["semester"].map(urutan).fillna(99)
    # key_cols = semua kolom kecuali semester, nilai, _urut (tapi termasuk tahun)
    key_cols = [c for c in df.columns if c not in ["semester", col_nilai, "_urut"]]
    df_terbaru = (
        df.sort_values(key_cols + ["_urut"])
          .groupby(key_cols, as_index=False)
          .first()
          .drop(columns=["_urut"])
    )
    return df_terbaru


# ════════════════════════════════════════════════════════════
# FILE 1: ASET KOPERASI
# Struktur: 1 baris per jenis koperasi (7 jenis), kolom = tahun × semester
# Tidak hierarkis — langsung satu level
# ════════════════════════════════════════════════════════════
def cleaning_aset_koperasi(path: str) -> pd.DataFrame:
    print("\n" + "═" * 50)
    print("FILE 1: ASET KOPERASI")
    print("═" * 50)

    df = pd.read_excel(path, header=None)
    print(f"  Shape mentah: {df.shape}")

    mapping = bangun_mapping(df)
    records = []

    for i, row in df.iterrows():
        if i < 6:       # lewati header (baris 0–5)
            continue
        nama_raw = str(row[0]).strip()
        if not nama_raw or nama_raw in ["nan", "-"]:
            continue

        jenis = bersihkan_nama(nama_raw)
        # Normalkan nama jenis
        jenis = (jenis
                 .replace("Lain - Lain", "Lainnya")
                 .replace("Kopontren", "Kopontren"))

        for col_idx, (tahun, semester) in mapping.items():
            aset = konversi_rupiah(row[col_idx])
            records.append({
                "jenis_koperasi": jenis,
                "tahun"         : tahun,
                "semester"      : semester,
                "aset_rupiah"   : aset,
            })

    df_flat = pd.DataFrame(records)

    # Pivot ke format lebar: satu baris per jenis per tahun (semester terbaru)
    df_terbaru = semester_terbaru(df_flat, "aset_rupiah")

    # Tambah kolom aset dalam miliar (lebih mudah dibaca)
    df_terbaru["aset_miliar"] = (df_terbaru["aset_rupiah"] / 1e9).round(3)

    # Simpan
    df_terbaru.to_csv("data/clean/aset_koperasi.csv", index=False, encoding="utf-8-sig")
    print(f"  Records: {len(df_terbaru)}")
    print(f"  Disimpan: data/clean/aset_koperasi.csv")

    # Preview
    df_ada = df_terbaru[df_terbaru["aset_rupiah"] > 0]
    print(f"\n  Preview (nilai > 0):")
    print(df_ada[["jenis_koperasi","tahun","semester","aset_miliar"]]
          .to_string(index=False))
    return df_terbaru


# ════════════════════════════════════════════════════════════
# FILE 2: INDUSTRI KECIL PER KECAMATAN
# Struktur: 1 baris per kecamatan (19 kecamatan), kolom = tahun × semester
# Lebih sederhana dari UMKM/Koperasi — tidak ada sub-kategori
# ════════════════════════════════════════════════════════════
def cleaning_industri_kecil(path: str) -> pd.DataFrame:
    print("\n" + "═" * 50)
    print("FILE 2: INDUSTRI KECIL PER KECAMATAN")
    print("═" * 50)

    df = pd.read_excel(path, header=None)
    print(f"  Shape mentah: {df.shape}")

    mapping = bangun_mapping(df)
    records = []

    for i, row in df.iterrows():
        if i < 6:
            continue
        nama_raw = str(row[0]).strip()
        if not nama_raw or nama_raw in ["nan", "-"]:
            continue

        kecamatan = bersihkan_nama(nama_raw)

        for col_idx, (tahun, semester) in mapping.items():
            jumlah = konversi_int(row[col_idx])
            records.append({
                "kecamatan"      : kecamatan,
                "tahun"          : tahun,
                "semester"       : semester,
                "jumlah_industri": jumlah,
            })

    df_flat = pd.DataFrame(records)

    # Ambil semester terbaru per kecamatan per tahun
    df_terbaru = semester_terbaru(df_flat, "jumlah_industri")
    df_terbaru.sort_values(["tahun", "jumlah_industri"], ascending=[True, False], inplace=True)
    df_terbaru.reset_index(drop=True, inplace=True)

    df_terbaru.to_csv("data/clean/industri_kecil.csv", index=False, encoding="utf-8-sig")
    print(f"  Records: {len(df_terbaru)}")
    print(f"  Disimpan: data/clean/industri_kecil.csv")

    # Preview tahun terlengkap
    df_ada = df_terbaru[df_terbaru["jumlah_industri"] > 0]
    if not df_ada.empty:
        tahun_max = df_ada.groupby("tahun")["jumlah_industri"].sum().idxmax()
        print(f"\n  Preview tahun terlengkap ({tahun_max}):")
        print(df_terbaru[df_terbaru["tahun"] == tahun_max]
              .sort_values("jumlah_industri", ascending=False)
              .to_string(index=False))
    return df_terbaru


# ════════════════════════════════════════════════════════════
# FILE 3: OMSET PERDAGANGAN
# Struktur: hanya 1 baris data ("OMSET PASAR"), kolom = tahun × semester
# Tidak ada breakdown kecamatan — data level kabupaten
# ════════════════════════════════════════════════════════════
def cleaning_omset_perdagangan(path: str) -> pd.DataFrame:
    print("\n" + "═" * 50)
    print("FILE 3: OMSET PELAKU USAHA PERDAGANGAN")
    print("═" * 50)

    df = pd.read_excel(path, header=None)
    print(f"  Shape mentah: {df.shape}")

    mapping = bangun_mapping(df)
    records = []

    for i, row in df.iterrows():
        if i < 6:
            continue
        nama_raw = str(row[0]).strip()
        if not nama_raw or nama_raw in ["nan", "-"]:
            continue

        kategori = bersihkan_nama(nama_raw)

        for col_idx, (tahun, semester) in mapping.items():
            omset = konversi_rupiah(row[col_idx])
            records.append({
                "kategori"      : kategori,
                "tahun"         : tahun,
                "semester"      : semester,
                "omset_rupiah"  : omset,
            })

    df_flat = pd.DataFrame(records)
    df_terbaru = semester_terbaru(df_flat, "omset_rupiah")
    df_terbaru["omset_miliar"] = (df_terbaru["omset_rupiah"] / 1e9).round(3)

    df_terbaru.to_csv("data/clean/omset_perdagangan.csv", index=False, encoding="utf-8-sig")
    print(f"  Records: {len(df_terbaru)}")
    print(f"  Disimpan: data/clean/omset_perdagangan.csv")

    df_ada = df_terbaru[df_terbaru["omset_rupiah"] > 0]
    print(f"\n  Preview (nilai > 0):")
    print(df_ada[["kategori","tahun","semester","omset_miliar"]].to_string(index=False))
    return df_terbaru


# ════════════════════════════════════════════════════════════
# FILE 4: GABUNGKAN SEMUA → MASTER TABEL
# Gabungkan: umkm_ringkasan + koperasi_ringkasan +
#            industri_kecil + omset_perdagangan (level kab)
# ════════════════════════════════════════════════════════════
def buat_master_gabungan(df_industri: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "═" * 50)
    print("LANGKAH AKHIR: MASTER GABUNGAN")
    print("═" * 50)

    path_gabungan = "data/clean/umkm_koperasi_gabungan.csv"
    if not os.path.exists(path_gabungan):
        print("  File umkm_koperasi_gabungan.csv belum ada.")
        print("  Jalankan cleaning_umkm_kbli.py dan cleaning_koperasi_kecamatan.py dulu.")
        return None

    df_master = pd.read_csv(path_gabungan)

    # Gabungkan industri kecil
    df_industri_merge = df_industri[["kecamatan", "tahun", "jumlah_industri"]]
    df_master = df_master.merge(df_industri_merge, on=["kecamatan", "tahun"], how="left")
    df_master["jumlah_industri"] = df_master["jumlah_industri"].fillna(0).astype(int)

    # Tambah kolom total_usaha = UMKM + industri
    df_master["total_usaha"] = df_master["total_umkm"] + df_master["jumlah_industri"]

    # Urutkan
    df_master.sort_values(["tahun", "total_usaha"], ascending=[True, False], inplace=True)
    df_master.reset_index(drop=True, inplace=True)

    df_master.to_csv("data/clean/master_gabungan.csv", index=False, encoding="utf-8-sig")
    print(f"  Shape master: {df_master.shape}")
    print(f"  Disimpan: data/clean/master_gabungan.csv")

    # Preview tahun terlengkap
    df_ada = df_master[df_master["total_usaha"] > 0]
    if not df_ada.empty:
        tahun_max = df_ada.groupby("tahun")["total_usaha"].sum().idxmax()
        print(f"\n  Preview master tahun {tahun_max}:")
        cols = ["kecamatan", "total_umkm", "jumlah_industri",
                "total_usaha", "total_koperasi", "sektor_dominan"]
        cols_ada = [c for c in cols if c in df_master.columns]
        print(df_master[df_master["tahun"] == tahun_max][cols_ada]
              .to_string(index=False))
    return df_master


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    print("═" * 50)
    print("CLEANING 3 FILE SISA")
    print("═" * 50)

    df_aset     = cleaning_aset_koperasi(PATH_ASET)
    df_industri = cleaning_industri_kecil(PATH_INDUSTRI)
    df_omset    = cleaning_omset_perdagangan(PATH_OMSET)
    df_master   = buat_master_gabungan(df_industri)

    print("\n" + "═" * 50)
    print("RINGKASAN SEMUA FILE CLEAN")
    print("═" * 50)

    files_clean = {
        "umkm_kbli_flat.csv"         : "UMKM detail per sektor",
        "umkm_ringkasan.csv"          : "UMKM total per kecamatan",
        "koperasi_flat.csv"           : "Koperasi detail per jenis",
        "koperasi_ringkasan.csv"      : "Koperasi total per kecamatan",
        "umkm_koperasi_gabungan.csv"  : "UMKM + Koperasi gabungan",
        "aset_koperasi.csv"           : "Aset koperasi per jenis",
        "industri_kecil.csv"          : "Industri kecil per kecamatan",
        "omset_perdagangan.csv"       : "Omset perdagangan Kab. Semarang",
        "master_gabungan.csv"         : "MASTER — semua data digabung",
    }

    for fname, keterangan in files_clean.items():
        path = f"data/clean/{fname}"
        if os.path.exists(path):
            df_tmp = pd.read_csv(path)
            print(f"  ✅ {fname:<35} {keterangan} ({len(df_tmp)} baris)")
        else:
            print(f"  ⏳ {fname:<35} {keterangan} (belum ada)")

    print("\nSemua selesai! File master_gabungan.csv siap untuk clustering K-Means.")


if __name__ == "__main__":
    main()
