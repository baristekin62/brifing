/* ============================================================
   GÜNLÜK SATIŞ ÖZETİ (DÜN) — PosBack SATTM010
   Kapsam: 101 ATAEVLER, 102 ERIKLI, 103 KUTAHYA, 104 IHSANIYE, 105 INEGOL
   Çıktı: Dünün net ciro, hedef, hedef gerçekleşme oranı, müşteri sayısı, sepet
   Not: Mikro satışları dün tarihli işlediği için brifing sabahı DÜN alınır.
   ============================================================ */
DECLARE @BaslangicTarihi DATE = CONVERT(DATE, DATEADD(DAY, -1, GETDATE())); -- Dün at midnight
DECLARE @BitisTarihi DATE = DATEADD(DAY, 1, @BaslangicTarihi); -- Bugün at midnight

WITH DateRange AS (
    SELECT @BaslangicTarihi AS TARIH
),
MagazaList AS (
    SELECT 101 AS MAGNO, 'ATAEVLER' AS Magaza_Adi UNION ALL
    SELECT 102, 'ERIKLI' UNION ALL
    SELECT 103, 'KUTAHYA' UNION ALL
    SELECT 104, 'IHSANIYE' UNION ALL
    SELECT 105, 'INEGOL'
),
MagazaDates AS (
    SELECT ml.MAGNO, ml.Magaza_Adi, d.TARIH
    FROM MagazaList ml CROSS JOIN DateRange d
),
SatTM_Agg AS (
    SELECT
        s10.MAGNO,
        CONVERT(DATE, s10.TARIH, 104) AS Tarih,
        SUM(CASE
                WHEN s10.ISLEM = '0' THEN (s10.BRUTTUT - s10.KDVTUT)
                ELSE 0
            END)
        - SUM(CASE
                WHEN s10.ISLEM = '0' AND s10.BELGETIP IN ('2') THEN (s10.BRUTTUT - s10.KDVTUT)
                ELSE 0
            END) AS Net_Tutar
    FROM [GRFARKSERVER].[PosBack].[dbo].[SATTM010] s10 WITH (NOLOCK)
    WHERE CONVERT(DATE, s10.TARIH, 104) = @BaslangicTarihi
      AND s10.MAGNO IN (101, 102, 103, 104, 105)
    GROUP BY s10.MAGNO, CONVERT(DATE, s10.TARIH, 104)
),
SatTD_Agg AS (
    SELECT
        s10.MAGNO,
        CONVERT(DATE, s10.TARIH, 104) AS Tarih,
        COUNT(s10.PFISNO) AS Musteri_Sayisi
    FROM [GRFARKSERVER].[PosBack].[dbo].[SATTM010] s10 WITH (NOLOCK)
    WHERE CONVERT(DATE, s10.TARIH, 104) = @BaslangicTarihi
      AND s10.MAGNO IN (101, 102, 103, 104, 105)
      AND s10.BELGETIP IN ('EA', 'EF', '2')
      AND s10.ISLEM = 0
    GROUP BY s10.MAGNO, CONVERT(DATE, s10.TARIH, 104)
),
Hedef AS (
    SELECT
        ktgh_date AS Hedef_Tarih,
        ktgh_Store AS Hedef_Magaza,
        CAST(ROUND(SUM(ktgh_Amount), 0) AS INT) AS Hedef
    FROM KATEGORI_HEDEFLERI hd
    WHERE ktgh_Date = @BaslangicTarihi
    GROUP BY ktgh_date, ktgh_Store
)
SELECT
    CONVERT(VARCHAR(MAX), md.TARIH, 104) AS Tarih,
    md.Magaza_Adi,
    CAST(ROUND(ISNULL(s1.Net_Tutar, 0), 2) AS DECIMAL(18,2)) AS Ciro,
    ISNULL(hd.Hedef, 0) AS Hedef,
    CAST(
        CASE
            WHEN ISNULL(hd.Hedef, 0) = 0 THEN 0
            ELSE ROUND((ISNULL(s1.Net_Tutar, 0) / hd.Hedef) * 100, 2)
        END AS DECIMAL(10,2)
    ) AS Hedef_Gerceklesme_Orani,
    ISNULL(s2.Musteri_Sayisi, 0) AS Musteri,
    CAST(
        CASE
            WHEN ISNULL(s2.Musteri_Sayisi, 0) = 0 THEN 0
            ELSE ROUND(ISNULL(s1.Net_Tutar, 0) / s2.Musteri_Sayisi, 2)
        END AS DECIMAL(18,2)
    ) AS Ortalama_Sepet
FROM MagazaDates md
LEFT JOIN SatTM_Agg s1 ON md.MAGNO = s1.MAGNO AND md.TARIH = s1.Tarih
LEFT JOIN SatTD_Agg s2 ON md.MAGNO = s2.MAGNO AND md.TARIH = s2.Tarih
LEFT JOIN Hedef hd ON hd.Hedef_Tarih = md.TARIH AND hd.Hedef_Magaza = md.MAGNO
ORDER BY md.TARIH,
    CASE md.Magaza_Adi
        WHEN 'ATAEVLER' THEN 1
        WHEN 'ERIKLI' THEN 2
        WHEN 'KUTAHYA' THEN 3
        WHEN 'IHSANIYE' THEN 4
        WHEN 'INEGOL' THEN 5
        ELSE 6
    END;