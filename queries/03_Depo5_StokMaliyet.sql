/* ============================================================
   DEPO 5 (SAMANLI ANA DEPO) STOK DEĞERİ — TOPLAM ÖZET
   Yaklaşım: Her ürünün depo 5 miktarı, en son (evrak tarihine göre)
   KDV'siz net SAŞ fiyatı ile çarpılarak TL değeri bulunur.
   Çıktı: Kategori bazlı toplam + GENEL TOPLAM
   ============================================================ */
;WITH SonSas AS
(
    SELECT
        sas_stok_kod,
        sas_evrak_tarih,
        sas_basla_tarih,
        sas_cari_kod,
        sas_brut_fiyat,
        sas_isk_yuzde1,
        sas_isk_yuzde2,
        sas_isk_yuzde3,
        sas_isk_yuzde4,
        sas_isk_yuzde5,
        ROUND(
            CAST(sas_brut_fiyat AS DECIMAL(18,2)) *
            (1 - CAST(ISNULL(sas_isk_yuzde1, 0) AS DECIMAL(18,4)) / 100) *
            (1 - CAST(ISNULL(sas_isk_yuzde2, 0) AS DECIMAL(18,4)) / 100) *
            (1 - CAST(ISNULL(sas_isk_yuzde3, 0) AS DECIMAL(18,4)) / 100) *
            (1 - CAST(ISNULL(sas_isk_yuzde4, 0) AS DECIMAL(18,4)) / 100) *
            (1 - CAST(ISNULL(sas_isk_yuzde5, 0) AS DECIMAL(18,4)) / 100),
            2
        ) AS NetFiyat,
        ROW_NUMBER() OVER (
            PARTITION BY sas_stok_kod
            ORDER BY sas_evrak_tarih DESC, sas_basla_tarih DESC, sas_create_date DESC
        ) AS rn
    FROM SATINALMA_SARTLARI WITH (NOLOCK)
    WHERE sas_evrak_no_seri NOT LIKE 'DVR%'
      AND sas_evrak_no_seri NOT LIKE 'DEMO%'
),
MevcutStoklar AS
(
    SELECT
        S.sto_kod,
        S.sto_reyon_kodu,
        dbo.fn_DepodakiMiktar(S.sto_kod, 5, CAST(GETDATE() AS DATE)) AS Depo5_Miktar
    FROM STOKLAR S WITH (NOLOCK)
    WHERE S.sto_pasif_fl = 0
)
SELECT
    CASE
        WHEN GROUPING(R.ryn_ismi) = 1 THEN 'GENEL TOPLAM'
        ELSE R.ryn_ismi
    END AS Kategori,
    COUNT(*) AS Kalem_Sayisi,
    CAST(ROUND(SUM(M.Depo5_Miktar), 2) AS DECIMAL(18,2)) AS Toplam_Miktar,
    CAST(ROUND(SUM(M.Depo5_Miktar * ISNULL(SAS.NetFiyat, 0)), 2) AS DECIMAL(18,2)) AS Stok_Degeri_TL
FROM MevcutStoklar M
LEFT JOIN STOK_REYONLARI R WITH (NOLOCK)
    ON R.ryn_kod = M.sto_reyon_kodu
LEFT JOIN SonSas SAS
    ON SAS.sas_stok_kod = M.sto_kod
   AND SAS.rn = 1
WHERE M.Depo5_Miktar <> 0
GROUP BY ROLLUP(R.ryn_ismi)
ORDER BY GROUPING(R.ryn_ismi) ASC,
    Stok_Degeri_TL DESC;
