"""
setup_database.py
Membangun database UMKM & Koperasi Kabupaten Semarang (SQLite)

Kenapa SQLite (bukan MySQL) sebagai default:
  - Tidak perlu install & jalankan server database terpisah — cukup Python
  - File .db bisa langsung dibuka pakai DB Browser for SQLite (gratis, GUI)
  - Tetap relational database sungguhan: PRIMARY KEY, FOREIGN KEY, JOIN,
    VIEW — semua konsep normalisasi tetap berlaku sama seperti MySQL/PostgreSQL
  - Kalau dosen/dinas mewajibkan MySQL, skema setara ada di
    database_schema_mysql.sql — tinggal import lewat phpMyAdmin/Workbench

Skema (10 tabel + 5 view):

  Tabel referensi (lookup):
    kbli_kategori      → 19 nama sektor KBLI
    jenis_koperasi_ref → 8 jenis koperasi (gabungan 2 sumber, kapitalisasi
                         diseragamkan)

  Tabel master & transaksi:
    kecamatan          → 19 baris, SEKARANG termasuk luas_km2 (statis,
                         BPS Kab. Semarang Dalam Angka 2019, data tahun 2018 —
                         luas wilayah jarang berubah jadi tetap relevan)
    penduduk_kecamatan → jumlah penduduk per kecamatan per tahun (time-series,
                         BPS Kab. Semarang Dalam Angka 2024, data tahun 2023 —
                         dipilih karena paling dekat dengan tahun data UMKM 2024)
    sektor_umkm     → UMKM per kecamatan x kbli_id x tahun x semester
    koperasi        → koperasi per kecamatan x jenis_id x tahun x semester
    industri_kecil  → industri kecil per kecamatan x tahun x semester
    aset_koperasi   → aset koperasi per jenis_id x tahun x semester
    hasil_klaster   → OUTPUT data mining (K-Means), disimpan balik ke database
    profil_klaster  → rata-rata & peringkat tiap klaster per indikator

  Catatan sumber data demografi:
  - jumlah_penduduk: sumber PRIMER — file resmi "Jumlah Penduduk Menurut
    Kecamatan dan Jenis Kelamin 2022-2025" (diberikan langsung, mencakup
    4 tahun, tervalidasi: total kabupaten per tahun cocok dengan angka
    publik BPS). Data 2024 dipakai di view supaya sinkron dengan tahun
    data UMKM.
  - luas_km2: masih sumber SEKUNDER (2 laporan akademik UNDIP yang
    saling cocok angkanya, mengutip "Kabupaten Semarang Dalam Angka
    2019"). Luas wilayah jarang berubah jadi risikonya kecil, tapi kalau
    perlu angka yang bisa dikutip resmi di laporan, sebaiknya verifikasi
    ulang ke publikasi BPS aslinya.

  View (lapisan pelaporan):
    view_kecamatan_klaster        → kecamatan + hasil klaster + SEKARANG
                                    juga luas_km2, jumlah_penduduk,
                                    kepadatan_penduduk, umkm_per_km2,
                                    umkm_per_1000_penduduk
    view_sektor_lengkap           → sektor_umkm + nama kbli + nama kecamatan
    view_koperasi_lengkap         → koperasi + nama jenis + nama kecamatan
    view_aset_lengkap             → aset_koperasi + nama jenis
    view_koperasi_total_kecamatan → total koperasi per kecamatan (SUM antar jenis)

Jalankan:
    python setup_database.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
DB_PATH  = DATA_DIR / "db" / "umkm_semarang.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════
# LANGKAH 1: Buat skema (DDL) — tabel referensi, tabel utama, view
# ════════════════════════════════════════════════════════════
def buat_skema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    PRAGMA foreign_keys = ON;

    DROP VIEW  IF EXISTS view_koperasi_total_kecamatan;
    DROP VIEW  IF EXISTS view_aset_lengkap;
    DROP VIEW  IF EXISTS view_koperasi_lengkap;
    DROP VIEW  IF EXISTS view_sektor_lengkap;
    DROP VIEW  IF EXISTS view_kecamatan_klaster;
    DROP TABLE IF EXISTS profil_klaster;
    DROP TABLE IF EXISTS hasil_klaster;
    DROP TABLE IF EXISTS aset_koperasi;
    DROP TABLE IF EXISTS industri_kecil;
    DROP TABLE IF EXISTS koperasi;
    DROP TABLE IF EXISTS sektor_umkm;
    DROP TABLE IF EXISTS penduduk_kecamatan;
    DROP TABLE IF EXISTS jenis_koperasi_ref;
    DROP TABLE IF EXISTS kbli_kategori;
    DROP TABLE IF EXISTS kecamatan;

    -- ── Tabel master ────────────────────────────────────────
    -- luas_km2 statis (jarang berubah) jadi kolom langsung di sini.
    -- jumlah_penduduk time-series (berubah tiap tahun) jadi tabel
    -- terpisah penduduk_kecamatan — konsisten dengan pola tabel lain.
    CREATE TABLE kecamatan (
        kecamatan_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_kecamatan TEXT NOT NULL UNIQUE,
        luas_km2       REAL
    );

    CREATE TABLE penduduk_kecamatan (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        kecamatan_id     INTEGER NOT NULL,
        tahun            INTEGER NOT NULL,
        jumlah_penduduk  INTEGER NOT NULL,
        FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id)
    );

    -- ── Tabel referensi (lookup) — BARU, hasil normalisasi ──
    CREATE TABLE kbli_kategori (
        kbli_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_kbli  TEXT NOT NULL UNIQUE
    );

    CREATE TABLE jenis_koperasi_ref (
        jenis_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_jenis  TEXT NOT NULL UNIQUE
    );

    -- ── Tabel transaksi (sekarang pakai FK, bukan teks) ─────
    CREATE TABLE sektor_umkm (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        kecamatan_id  INTEGER NOT NULL,
        kbli_id       INTEGER NOT NULL,
        tahun         INTEGER NOT NULL,
        semester      TEXT    NOT NULL,
        jumlah_usaha  INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id),
        FOREIGN KEY (kbli_id)      REFERENCES kbli_kategori(kbli_id)
    );

    CREATE TABLE koperasi (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        kecamatan_id     INTEGER NOT NULL,
        jenis_id         INTEGER NOT NULL,
        tahun            INTEGER NOT NULL,
        semester         TEXT    NOT NULL,
        jumlah_koperasi  INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id),
        FOREIGN KEY (jenis_id)     REFERENCES jenis_koperasi_ref(jenis_id)
    );

    CREATE TABLE industri_kecil (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        kecamatan_id     INTEGER NOT NULL,
        tahun            INTEGER NOT NULL,
        semester         TEXT    NOT NULL,
        jumlah_industri  INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id)
    );

    CREATE TABLE aset_koperasi (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        jenis_id        INTEGER NOT NULL,
        tahun           INTEGER NOT NULL,
        semester        TEXT    NOT NULL,
        aset_rupiah     REAL    NOT NULL DEFAULT 0,
        FOREIGN KEY (jenis_id) REFERENCES jenis_koperasi_ref(jenis_id)
    );

    CREATE TABLE hasil_klaster (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        kecamatan_id     INTEGER NOT NULL,
        tahun            INTEGER NOT NULL,
        klaster_id       INTEGER,
        klaster          TEXT,
        total_umkm       INTEGER,
        jumlah_industri  INTEGER,
        total_koperasi   INTEGER,
        total_usaha      INTEGER,
        sektor_dominan   TEXT,
        warna            TEXT,
        FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id)
    );

    CREATE TABLE profil_klaster (
        klaster             TEXT PRIMARY KEY,
        jumlah_kecamatan    INTEGER,
        kecamatan           TEXT,
        rata_umkm           REAL,
        peringkat_umkm      INTEGER,
        rata_industri       REAL,
        peringkat_industri  INTEGER,
        rata_koperasi       REAL,
        peringkat_koperasi  INTEGER
    );

    -- ── VIEW: lapisan pelaporan ──────────────────────────────
    -- view_kecamatan_klaster sekarang juga menghitung metrik per kapita
    -- & per km2 — supaya "kecamatan dengan UMKM terbanyak" tidak cuma
    -- soal angka mentah, tapi bisa dibandingkan adil antar kecamatan
    -- yang ukuran penduduknya beda jauh (mis. Pringapus vs Bancak).
    -- Ambil jumlah_penduduk tahun 2024 SPESIFIK (bukan MAX/tahun terbaru)
    -- supaya sinkron persis dengan tahun data UMKM (h.tahun = 2024) —
    -- penduduk_kecamatan sebenarnya punya data 2022-2025, tapi kalau
    -- pakai MAX akan ambil 2025 dan jadi tidak sezaman dengan UMKM-nya.
    CREATE VIEW view_kecamatan_klaster AS
        SELECT k.kecamatan_id, k.nama_kecamatan, k.luas_km2,
               p.tahun AS tahun_penduduk, p.jumlah_penduduk,
               ROUND(p.jumlah_penduduk / NULLIF(k.luas_km2, 0), 1)
                   AS kepadatan_penduduk,
               h.tahun, h.klaster_id, h.klaster,
               h.total_umkm, h.jumlah_industri, h.total_koperasi,
               h.total_usaha, h.sektor_dominan, h.warna,
               ROUND(h.total_umkm / NULLIF(k.luas_km2, 0), 2)
                   AS umkm_per_km2,
               ROUND(h.total_umkm * 1000.0 / NULLIF(p.jumlah_penduduk, 0), 2)
                   AS umkm_per_1000_penduduk
        FROM kecamatan k
        JOIN hasil_klaster h ON h.kecamatan_id = k.kecamatan_id
        LEFT JOIN penduduk_kecamatan p ON p.kecamatan_id = k.kecamatan_id
            AND p.tahun = h.tahun;

    CREATE VIEW view_sektor_lengkap AS
        SELECT k.nama_kecamatan AS kecamatan, kb.nama_kbli AS sektor_kbli,
               s.tahun, s.semester, s.jumlah_usaha
        FROM sektor_umkm s
        JOIN kecamatan k     ON k.kecamatan_id = s.kecamatan_id
        JOIN kbli_kategori kb ON kb.kbli_id = s.kbli_id;

    CREATE VIEW view_koperasi_lengkap AS
        SELECT k.nama_kecamatan AS kecamatan, j.nama_jenis AS jenis_koperasi,
               kp.tahun, kp.semester, kp.jumlah_koperasi
        FROM koperasi kp
        JOIN kecamatan k          ON k.kecamatan_id = kp.kecamatan_id
        JOIN jenis_koperasi_ref j ON j.jenis_id = kp.jenis_id;

    CREATE VIEW view_aset_lengkap AS
        SELECT j.nama_jenis AS jenis_koperasi, a.tahun, a.semester, a.aset_rupiah
        FROM aset_koperasi a
        JOIN jenis_koperasi_ref j ON j.jenis_id = a.jenis_id;

    CREATE VIEW view_koperasi_total_kecamatan AS
        SELECT k.nama_kecamatan AS kecamatan, kp.tahun, kp.semester,
               SUM(kp.jumlah_koperasi) AS total_koperasi
        FROM koperasi kp
        JOIN kecamatan k ON k.kecamatan_id = kp.kecamatan_id
        GROUP BY k.nama_kecamatan, kp.tahun, kp.semester;
    """)
    conn.commit()
    print("  Skema dibuat: 10 tabel (2 tabel referensi baru: kbli_kategori, "
          "jenis_koperasi_ref) + 5 VIEW")


# ════════════════════════════════════════════════════════════
# LANGKAH 2: Isi tabel master & referensi lebih dulu
# ════════════════════════════════════════════════════════════
def isi_kecamatan(conn: sqlite3.Connection) -> dict:
    df = pd.read_csv(DATA_DIR / "clean" / "master_gabungan.csv")
    nama_list = sorted(df["kecamatan"].dropna().unique())

    df_luas = pd.read_csv(DATA_DIR / "raw" / "demografi_luas.csv")
    luas_map = dict(zip(df_luas["kecamatan"], df_luas["luas_km2"]))

    conn.executemany(
        "INSERT INTO kecamatan (nama_kecamatan, luas_km2) VALUES (?, ?)",
        [(n, luas_map.get(n)) for n in nama_list],
    )
    conn.commit()

    rows = conn.execute("SELECT kecamatan_id, nama_kecamatan FROM kecamatan").fetchall()
    mapping = {nama: kid for kid, nama in rows}
    n_terisi = sum(1 for n in nama_list if n in luas_map)
    print(f"  Tabel kecamatan: {len(mapping)} baris "
          f"(luas_km2 terisi untuk {n_terisi}/{len(nama_list)} kecamatan)")
    return mapping


def isi_penduduk_kecamatan(conn: sqlite3.Connection, kec_map: dict) -> None:
    """
    Sumber PRIMER: file resmi "Jumlah Penduduk Menurut Kecamatan dan
    Jenis Kelamin 2022-2025" (diberikan langsung, bukan hasil kutip
    sumber sekunder). Simpan SEMUA tahun (2022-2025) — bukan cuma satu
    tahun — karena datanya bersih dan konsisten antar tahun (beda dengan
    aset_koperasi yang ada lompatan skala), jadi bisa dipakai untuk
    analisis tren populasi kalau diperlukan nanti.
    """
    df = pd.read_csv(DATA_DIR / "raw" / "demografi_penduduk.csv")
    df["kecamatan_id"] = df["kecamatan"].map(kec_map)
    df = df.dropna(subset=["kecamatan_id"])
    df["kecamatan_id"] = df["kecamatan_id"].astype(int)

    df[["kecamatan_id", "tahun", "jumlah_penduduk"]].to_sql(
        "penduduk_kecamatan", conn, if_exists="append", index=False
    )
    tahun_list = sorted(df["tahun"].unique())
    print(f"  Tabel penduduk_kecamatan: {len(df):,} baris "
          f"(tahun {tahun_list[0]}-{tahun_list[-1]}, sumber primer resmi)")


def isi_kbli_kategori(conn: sqlite3.Connection) -> dict:
    df = pd.read_csv(DATA_DIR / "clean" / "umkm_kbli_flat.csv")
    nama_list = sorted(df["sektor_kbli"].dropna().unique())

    conn.executemany(
        "INSERT INTO kbli_kategori (nama_kbli) VALUES (?)",
        [(n,) for n in nama_list],
    )
    conn.commit()

    rows = conn.execute("SELECT kbli_id, nama_kbli FROM kbli_kategori").fetchall()
    mapping = {nama: kid for kid, nama in rows}
    print(f"  Tabel kbli_kategori: {len(mapping)} baris (sebelumnya teks ini "
          f"diulang di setiap baris sektor_umkm — sekarang cukup 1x + FK)")
    return mapping


def isi_jenis_koperasi_ref(conn: sqlite3.Connection) -> dict:
    """
    Gabungkan jenis koperasi dari 2 sumber yang kapitalisasinya berbeda:
    koperasi_flat.csv pakai UPPERCASE (KOPKAR, KPRI, ...), aset_koperasi.csv
    pakai Title Case (Kopkar, Kpri, ...). Diseragamkan ke Title Case supaya
    jadi SATU referensi, bukan 2 baris berbeda untuk konsep yang sama.
    """
    df_kop  = pd.read_csv(DATA_DIR / "clean" / "koperasi_flat.csv")
    df_aset = pd.read_csv(DATA_DIR / "clean" / "aset_koperasi.csv")

    jenis_kop  = set(
        df_kop[df_kop["jenis_koperasi"] != "TOTAL"]["jenis_koperasi"]
        .dropna().str.title()
    )
    jenis_aset = set(df_aset["jenis_koperasi"].dropna().str.title())
    nama_list  = sorted(jenis_kop | jenis_aset)

    conn.executemany(
        "INSERT INTO jenis_koperasi_ref (nama_jenis) VALUES (?)",
        [(n,) for n in nama_list],
    )
    conn.commit()

    rows = conn.execute("SELECT jenis_id, nama_jenis FROM jenis_koperasi_ref").fetchall()
    mapping = {nama: jid for jid, nama in rows}
    print(f"  Tabel jenis_koperasi_ref: {len(mapping)} baris "
          f"(gabungan 2 sumber, kapitalisasi diseragamkan)")
    print(f"    → {nama_list}")
    return mapping


# ════════════════════════════════════════════════════════════
# LANGKAH 3: Isi tabel transaksi (pakai FK ke tabel referensi)
# ════════════════════════════════════════════════════════════
def isi_sektor_umkm(conn: sqlite3.Connection, kec_map: dict, kbli_map: dict) -> None:
    df = pd.read_csv(DATA_DIR / "clean" / "umkm_kbli_flat.csv")
    df["kecamatan_id"] = df["kecamatan"].map(kec_map)
    df["kbli_id"]      = df["sektor_kbli"].map(kbli_map)
    df = df.dropna(subset=["kecamatan_id", "kbli_id"])
    df["kecamatan_id"] = df["kecamatan_id"].astype(int)
    df["kbli_id"]      = df["kbli_id"].astype(int)

    df[["kecamatan_id", "kbli_id", "tahun", "semester", "jumlah_usaha"]].to_sql(
        "sektor_umkm", conn, if_exists="append", index=False
    )
    print(f"  Tabel sektor_umkm: {len(df):,} baris")


def isi_koperasi(conn: sqlite3.Connection, kec_map: dict, jenis_map: dict) -> None:
    df = pd.read_csv(DATA_DIR / "clean" / "koperasi_flat.csv")
    df = df[df["jenis_koperasi"] != "TOTAL"].copy()
    df["kecamatan_id"] = df["kecamatan"].map(kec_map)
    df["jenis_id"]     = df["jenis_koperasi"].str.title().map(jenis_map)
    df = df.dropna(subset=["kecamatan_id", "jenis_id"])
    df["kecamatan_id"] = df["kecamatan_id"].astype(int)
    df["jenis_id"]     = df["jenis_id"].astype(int)

    df[["kecamatan_id", "jenis_id", "tahun", "semester", "jumlah_koperasi"]].to_sql(
        "koperasi", conn, if_exists="append", index=False
    )
    print(f"  Tabel koperasi: {len(df):,} baris")


def isi_industri_kecil(conn: sqlite3.Connection, kec_map: dict) -> None:
    df = pd.read_csv(DATA_DIR / "clean" / "industri_kecil.csv")
    df["kecamatan_id"] = df["kecamatan"].map(kec_map)
    df = df.dropna(subset=["kecamatan_id"])
    df["kecamatan_id"] = df["kecamatan_id"].astype(int)

    df[["kecamatan_id", "tahun", "semester", "jumlah_industri"]].to_sql(
        "industri_kecil", conn, if_exists="append", index=False
    )
    print(f"  Tabel industri_kecil: {len(df):,} baris")


def isi_aset_koperasi(conn: sqlite3.Connection, jenis_map: dict) -> None:
    df = pd.read_csv(DATA_DIR / "clean" / "aset_koperasi.csv")
    df["jenis_id"] = df["jenis_koperasi"].str.title().map(jenis_map)
    df = df.dropna(subset=["jenis_id"])
    df["jenis_id"] = df["jenis_id"].astype(int)

    df[["jenis_id", "tahun", "semester", "aset_rupiah"]].to_sql(
        "aset_koperasi", conn, if_exists="append", index=False
    )
    print(f"  Tabel aset_koperasi: {len(df):,} baris")


def isi_hasil_klaster(conn: sqlite3.Connection, kec_map: dict) -> None:
    df = pd.read_csv(DATA_DIR / "processed" / "umkm_klaster.csv")
    df["kecamatan_id"] = df["kecamatan"].map(kec_map)
    df = df.dropna(subset=["kecamatan_id"])
    df["kecamatan_id"] = df["kecamatan_id"].astype(int)

    kolom = ["kecamatan_id", "tahun", "klaster_id", "klaster", "total_umkm",
              "jumlah_industri", "total_koperasi", "total_usaha",
              "sektor_dominan", "warna"]
    df[kolom].to_sql("hasil_klaster", conn, if_exists="append", index=False)
    print(f"  Tabel hasil_klaster: {len(df):,} baris")


def isi_profil_klaster(conn: sqlite3.Connection) -> None:
    df = pd.read_csv(DATA_DIR / "processed" / "klaster_profil.csv")
    kolom = ["klaster", "jumlah_kecamatan", "kecamatan",
              "rata_umkm", "peringkat_umkm",
              "rata_industri", "peringkat_industri",
              "rata_koperasi", "peringkat_koperasi"]
    df[kolom].to_sql("profil_klaster", conn, if_exists="append", index=False)
    print(f"  Tabel profil_klaster: {len(df):,} baris")


# ════════════════════════════════════════════════════════════
# LANGKAH 4: Verifikasi — tabel, view, dan contoh query lewat view
# ════════════════════════════════════════════════════════════
def verifikasi(conn: sqlite3.Connection) -> None:
    print("\n" + "=" * 55)
    print("VERIFIKASI — JUMLAH BARIS TIAP TABEL")
    print("=" * 55)
    tabel_list = ["kecamatan", "penduduk_kecamatan", "kbli_kategori", "jenis_koperasi_ref",
                   "sektor_umkm", "koperasi", "industri_kecil",
                   "aset_koperasi", "hasil_klaster", "profil_klaster"]
    for t in tabel_list:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<20} {n:>6,} baris")

    print("\n" + "=" * 55)
    print("VERIFIKASI — 5 VIEW TERSEDIA")
    print("=" * 55)
    views = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()
    for v in views:
        n = conn.execute(f"SELECT COUNT(*) FROM {v[0]}").fetchone()[0]
        print(f"  {v[0]:<32} {n:>6,} baris")

    print("\n" + "=" * 55)
    print("CONTOH — query lewat VIEW (tanpa JOIN manual)")
    print("=" * 55)
    hasil = conn.execute("""
        SELECT nama_kecamatan, klaster, total_umkm, total_koperasi
        FROM view_kecamatan_klaster
        ORDER BY total_umkm DESC LIMIT 5
    """).fetchall()
    print(f"  {'Kecamatan':<16}{'Klaster':<12}{'UMKM':>8}{'Koperasi':>10}")
    for row in hasil:
        print(f"  {row[0]:<16}{row[1]:<12}{row[2]:>8}{row[3]:>10}")

    print()
    hasil2 = conn.execute("""
        SELECT sektor_kbli, SUM(jumlah_usaha) AS total
        FROM view_sektor_lengkap
        WHERE tahun = 2024 AND semester = 'Semester II'
        GROUP BY sektor_kbli ORDER BY total DESC LIMIT 3
    """).fetchall()
    print("  Top 3 sektor KBLI (lewat view_sektor_lengkap, nama sudah utuh):")
    for row in hasil2:
        print(f"    {row[0]:<70} {row[1]:>6,}")


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("SETUP DATABASE — UMKM & Koperasi Kabupaten Semarang")
    print("=" * 55)

    conn = sqlite3.connect(DB_PATH)

    print("\nLangkah 1: Membuat skema (tabel + view)")
    buat_skema(conn)

    print("\nLangkah 2: Mengisi tabel master & referensi")
    kec_map   = isi_kecamatan(conn)
    isi_penduduk_kecamatan(conn, kec_map)
    kbli_map  = isi_kbli_kategori(conn)
    jenis_map = isi_jenis_koperasi_ref(conn)

    print("\nLangkah 3: Mengisi tabel transaksi (pakai FK, bukan teks)")
    isi_sektor_umkm(conn, kec_map, kbli_map)
    isi_koperasi(conn, kec_map, jenis_map)
    isi_industri_kecil(conn, kec_map)
    isi_aset_koperasi(conn, jenis_map)
    isi_hasil_klaster(conn, kec_map)
    isi_profil_klaster(conn)

    verifikasi(conn)

    conn.close()
    print(f"\nSelesai! Database tersimpan di: {DB_PATH}")
    print("Bisa dibuka pakai DB Browser for SQLite (gratis, GUI) untuk dicek visual.")


if __name__ == "__main__":
    main()
