"""
query_contoh.py
Kumpulan contoh query SQL terhadap database umkm_semarang.db
Untuk didokumentasikan di laporan magang (bukti penerapan mata kuliah Database)

Jalankan:
    python query_contoh.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/db/umkm_semarang.db")


def jalankan(conn, judul, sql):
    print(f"\n{'─' * 60}")
    print(f"  {judul}")
    print(f"{'─' * 60}")
    df = pd.read_sql_query(sql, conn)
    print(df.to_string(index=False))
    return df


def main():
    conn = sqlite3.connect(DB_PATH)

    # 1. JOIN sederhana: kecamatan + hasil klaster
    jalankan(conn, "1. Semua kecamatan beserta klasternya (JOIN)", """
        SELECT k.nama_kecamatan, h.klaster, h.total_umkm
        FROM hasil_klaster h
        JOIN kecamatan k ON k.kecamatan_id = h.kecamatan_id
        ORDER BY h.total_umkm DESC;
    """)

    # 2. Agregasi + GROUP BY: total UMKM per klaster
    jalankan(conn, "2. Total & rata-rata UMKM per klaster (GROUP BY + agregasi)", """
        SELECT klaster,
               COUNT(*)         AS jumlah_kecamatan,
               SUM(total_umkm)  AS total_umkm,
               ROUND(AVG(total_umkm), 1) AS rata_rata_umkm
        FROM hasil_klaster
        GROUP BY klaster
        ORDER BY rata_rata_umkm DESC;
    """)

    # 3. JOIN 3 tabel + filter: sektor UMKM di kecamatan dengan koperasi terbanyak
    #    Sekarang JOIN 3 tabel (bukan 2) karena sektor_kbli sudah dinormalisasi
    #    jadi tabel referensi kbli_kategori — sektor_umkm cuma simpan kbli_id.
    jalankan(conn, "3. Top 5 sektor UMKM di kecamatan dengan koperasi terbanyak (JOIN 3 tabel + subquery)", """
        SELECT k.nama_kecamatan, kb.nama_kbli AS sektor_kbli, s.jumlah_usaha
        FROM sektor_umkm s
        JOIN kecamatan k      ON k.kecamatan_id = s.kecamatan_id
        JOIN kbli_kategori kb ON kb.kbli_id = s.kbli_id
        WHERE k.kecamatan_id = (
            SELECT kecamatan_id FROM hasil_klaster
            ORDER BY total_koperasi DESC LIMIT 1
        )
        AND s.tahun = 2024 AND s.semester = 'Semester II'
        ORDER BY s.jumlah_usaha DESC
        LIMIT 5;
    """)

    # 4. Agregasi lintas tabel: bandingkan koperasi vs industri per kecamatan
    #    Catatan: masing-masing tabel fakta di-agregasi dulu di subquery
    #    SEBELUM di-JOIN. Kalau langsung JOIN tabel mentah (yang punya
    #    banyak baris per kecamatan), angkanya akan salah kelipatan
    #    (fan-out) — pelajaran penting saat menulis query ini.
    jalankan(conn, "4. Perbandingan koperasi vs industri kecil per kecamatan (JOIN + subquery teragregasi)", """
        SELECT kc.nama_kecamatan,
               COALESCE(kop.total_koperasi, 0)  AS koperasi_2024,
               COALESCE(ind.total_industri, 0)  AS industri_2024
        FROM kecamatan kc
        LEFT JOIN (
            SELECT kecamatan_id, SUM(jumlah_koperasi) AS total_koperasi
            FROM koperasi
            WHERE tahun = 2024 AND semester = 'Semester II'
            GROUP BY kecamatan_id
        ) kop ON kop.kecamatan_id = kc.kecamatan_id
        LEFT JOIN (
            SELECT kecamatan_id, SUM(jumlah_industri) AS total_industri
            FROM industri_kecil
            WHERE tahun = 2024 AND semester = 'Semester II'
            GROUP BY kecamatan_id
        ) ind ON ind.kecamatan_id = kc.kecamatan_id
        ORDER BY koperasi_2024 DESC
        LIMIT 8;
    """)

    # 5. Tren waktu: pertumbuhan aset koperasi per tahun
    jalankan(conn, "5. Tren total aset koperasi per tahun (GROUP BY tahun)", """
        SELECT tahun, ROUND(SUM(aset_rupiah) / 1e9, 2) AS total_aset_miliar
        FROM aset_koperasi
        WHERE semester = 'Semester II' AND aset_rupiah > 0
        GROUP BY tahun
        ORDER BY tahun;
    """)

    # 6. Query yang SAMA persis dengan #3, tapi lewat VIEW — bandingkan
    #    panjangnya. VIEW menyimpan JOIN-nya sekali di definisi skema,
    #    jadi query harian tidak perlu mengulang JOIN 3 tabel setiap kali.
    jalankan(conn, "6. Query sama dengan #3, tapi lewat VIEW (bandingkan kesederhanaannya)", """
        SELECT kecamatan, sektor_kbli, jumlah_usaha
        FROM view_sektor_lengkap
        WHERE kecamatan = (
            SELECT nama_kecamatan FROM view_kecamatan_klaster
            ORDER BY total_koperasi DESC LIMIT 1
        )
        AND tahun = 2024 AND semester = 'Semester II'
        ORDER BY jumlah_usaha DESC
        LIMIT 5;
    """)

    conn.close()
    print("\n" + "─" * 60)
    print("Selesai — 6 contoh query berhasil dijalankan.")


if __name__ == "__main__":
    main()
