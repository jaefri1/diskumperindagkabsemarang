-- ============================================================
-- database_schema_mysql.sql
-- Skema database UMKM & Koperasi Kabupaten Semarang
-- Versi MySQL (setara dengan skema SQLite di setup_database.py)
--
-- Kapan pakai file ini, bukan setup_database.py:
--   - Dosen/kampus secara spesifik mewajibkan MySQL
--   - Sudah punya XAMPP/Laragon/MySQL Workbench terpasang
--   - Ingin database berjalan sebagai server terpisah (bukan file lokal)
--
-- Cara pakai:
--   1. Buka phpMyAdmin atau MySQL Workbench
--   2. Jalankan seluruh isi file ini (Import / Run SQL Script)
--   3. Import data dari CSV di data/clean/, data/processed/, dan
--      data/raw/ (demografi_luas.csv, demografi_penduduk.csv) lewat
--      fitur "Import" masing-masing tool. Untuk kolom kbli_id dan
--      jenis_id, isi tabel referensi (kbli_kategori, jenis_koperasi_ref)
--      LEBIH DULU, baru mapping teks ke id sebelum import tabel transaksi
--      (lihat setup_database.py fungsi isi_kbli_kategori/isi_jenis_koperasi_ref
--      untuk logika lengkapnya, termasuk penyeragaman kapitalisasi jenis
--      koperasi yang di sumber aslinya tidak konsisten).
-- ============================================================

CREATE DATABASE IF NOT EXISTS db_umkm_semarang
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE db_umkm_semarang;

-- ── Tabel master ─────────────────────────────────────────────
CREATE TABLE kecamatan (
    kecamatan_id   INT PRIMARY KEY AUTO_INCREMENT,
    nama_kecamatan VARCHAR(100) NOT NULL UNIQUE,
    luas_km2       DECIMAL(6,2)
);

-- Jumlah penduduk per tahun (time-series, beda dari luas_km2 yang statis)
CREATE TABLE penduduk_kecamatan (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    kecamatan_id     INT NOT NULL,
    tahun            INT NOT NULL,
    jumlah_penduduk  INT NOT NULL,
    FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id)
);

-- ── Tabel referensi (lookup) — hasil normalisasi ───────────────
-- 19 nama sektor KBLI disimpan sekali di sini, direferensi lewat
-- kbli_id di tabel sektor_umkm (sebelumnya teks ~42 karakter diulang
-- di setiap baris — sekarang cukup foreign key integer).
CREATE TABLE kbli_kategori (
    kbli_id    INT PRIMARY KEY AUTO_INCREMENT,
    nama_kbli  VARCHAR(255) NOT NULL UNIQUE
);

-- Gabungan jenis koperasi dari 2 sumber data yang kapitalisasinya
-- berbeda (koperasi_flat.csv pakai UPPERCASE, aset_koperasi.csv pakai
-- Title Case) — diseragamkan jadi satu referensi bersama, 8 jenis unik.
CREATE TABLE jenis_koperasi_ref (
    jenis_id    INT PRIMARY KEY AUTO_INCREMENT,
    nama_jenis  VARCHAR(50) NOT NULL UNIQUE
);

-- ── Tabel transaksi (pakai FK ke tabel referensi) ──────────────
CREATE TABLE sektor_umkm (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    kecamatan_id  INT NOT NULL,
    kbli_id       INT NOT NULL,
    tahun         INT NOT NULL,
    semester      VARCHAR(20) NOT NULL,
    jumlah_usaha  INT NOT NULL DEFAULT 0,
    FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id),
    FOREIGN KEY (kbli_id)      REFERENCES kbli_kategori(kbli_id),
    INDEX idx_sektor_tahun (tahun, semester)
);

CREATE TABLE koperasi (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    kecamatan_id     INT NOT NULL,
    jenis_id         INT NOT NULL,
    tahun            INT NOT NULL,
    semester         VARCHAR(20) NOT NULL,
    jumlah_koperasi  INT NOT NULL DEFAULT 0,
    FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id),
    FOREIGN KEY (jenis_id)     REFERENCES jenis_koperasi_ref(jenis_id),
    INDEX idx_koperasi_tahun (tahun, semester)
);

CREATE TABLE industri_kecil (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    kecamatan_id     INT NOT NULL,
    tahun            INT NOT NULL,
    semester         VARCHAR(20) NOT NULL,
    jumlah_industri  INT NOT NULL DEFAULT 0,
    FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id),
    INDEX idx_industri_tahun (tahun, semester)
);

CREATE TABLE aset_koperasi (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    jenis_id        INT NOT NULL,
    tahun           INT NOT NULL,
    semester        VARCHAR(20) NOT NULL,
    aset_rupiah     DECIMAL(18,2) NOT NULL DEFAULT 0,
    FOREIGN KEY (jenis_id) REFERENCES jenis_koperasi_ref(jenis_id)
);

CREATE TABLE hasil_klaster (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    kecamatan_id     INT NOT NULL,
    tahun            INT NOT NULL,
    klaster_id       INT,
    klaster          VARCHAR(20),
    total_umkm       INT,
    jumlah_industri  INT,
    total_koperasi   INT,
    total_usaha      INT,
    sektor_dominan   VARCHAR(255),
    warna            VARCHAR(9),
    FOREIGN KEY (kecamatan_id) REFERENCES kecamatan(kecamatan_id)
);

CREATE TABLE profil_klaster (
    klaster             VARCHAR(20) PRIMARY KEY,
    jumlah_kecamatan    INT,
    kecamatan           TEXT,
    rata_umkm           DECIMAL(10,1),
    peringkat_umkm      INT,
    rata_industri       DECIMAL(10,1),
    peringkat_industri  INT,
    rata_koperasi       DECIMAL(10,1),
    peringkat_koperasi  INT
);

-- ── VIEW: lapisan pelaporan ──────────────────────────────────
-- Merekonstruksi teks yang mudah dibaca dari tabel yang sudah
-- dinormalisasi, supaya query harian tidak perlu JOIN manual berulang.
-- Sinkronkan p.tahun = h.tahun (bukan MAX/tahun terbaru) supaya data
-- penduduk yang dipakai sezaman persis dengan tahun data UMKM.
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
    JOIN kecamatan k      ON k.kecamatan_id = s.kecamatan_id
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

-- ============================================================
-- Contoh query verifikasi setelah import data (lewat VIEW)
-- ============================================================
-- SELECT nama_kecamatan, klaster, total_umkm
-- FROM view_kecamatan_klaster
-- ORDER BY total_umkm DESC;
