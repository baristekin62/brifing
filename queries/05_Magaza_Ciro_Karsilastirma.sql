/* ============================================================
   MAĞAZA ODAKLI CİRO KARŞILAŞTIRMASI (DÜN)
   Kaynak A: PosBack SATTM010 (Anlık Ciro, kasada işlenen)
   Kaynak B: STOK_HAREKETLERI (Mikro ERP — Crystal Rapor mantığı)
     Satış tutarı formülü:
       (tip=1, cins=1, normal_iade=0, evraktip in (1,4) ise sth_tutar - sth_iskonto1)
     - (tip=0, cins=1, normal_iade=1, evraktip in (13,3) ise sth_tutar - sth_iskonto1)
   Not: Mikro satışları dün tarihli işlediği için brifing sabahı DÜN alınır.
   Çıktı: Her mağaza için iki kaynak arasındaki fark ve durum
   ============================================================ */
DECLARE @BaslangicTarihi DATE = CONVERT(DATE, DATEADD(DAY, -1, GETDATE())); -- Dün at midnight
DECLARE @BitisTarihi DATE = DATEADD(DAY, 1, @BaslangicTarihi); -- Bugün at midnight

;WITH MagazaList AS
(
    SELECT 101 AS MAGNO, 'ATAEVLER' AS Magaza_Adi UNION ALL
    SELECT 102, 'ERIKLI' UNION ALL
    SELECT 103, 'KUTAHYA' UNION ALL
    SELECT 104, 'IHSANIYE' UNION ALL
    SELECT 105, 'INEGOL'
),
PosBackCiro AS
(
    SELECT
        s10.MAGNO,
        CAST(ROUND(
            SUM(CASE
                    WHEN s10.ISLEM = '0' THEN (s10.BRUTTUT - s10.KDVTUT)
                    ELSE 0
                END)
            - SUM(CASE
                    WHEN s10.ISLEM = '0' AND s10.BELGETIP IN ('2') THEN (s10.BRUTTUT - s10.KDVTUT)
                    ELSE 0
                END),
            2
        ) AS DECIMAL(18,2)) AS Ciro
    FROM [GRFARKSERVER].[PosBack].[dbo].[SATTM010] s10 WITH (NOLOCK)
    WHERE CONVERT(DATE, s10.TARIH, 104) >= @BaslangicTarihi
      AND CONVERT(DATE, s10.TARIH, 104) < @BitisTarihi
      AND s10.MAGNO IN (101, 102, 103, 104, 105)
    GROUP BY s10.MAGNO
),
StokHareketCiro AS
(
    SELECT
        D.dep_no AS MAGNO,
        CAST(ROUND(
            SUM(
                CASE
                    WHEN H.sth_tip IN (1) AND H.sth_cins = 1 AND H.sth_normal_iade IN (0)
                         AND H.sth_evraktip IN (1, 4)
                    THEN H.sth_tutar - H.sth_iskonto1
                    ELSE 0
                END
            )
            -
            SUM(
                CASE
                    WHEN H.sth_tip IN (0) AND H.sth_cins = 1 AND H.sth_normal_iade IN (1)
                         AND H.sth_evraktip IN (13, 3)
                    THEN H.sth_tutar - H.sth_iskonto1
                    ELSE 0
                END
            ),
            2
        ) AS DECIMAL(18,2)) AS Ciro
    FROM STOK_HAREKETLERI H WITH (NOLOCK)
    INNER JOIN STOKLAR S WITH (NOLOCK)
        ON S.sto_kod = H.sth_stok_kod
    INNER JOIN DEPOLAR D WITH (NOLOCK)
        ON D.dep_no = H.sth_cikis_depo_no
    WHERE H.sth_tarih >= @BaslangicTarihi
      AND H.sth_tarih < @BitisTarihi
      AND D.dep_no >= 101 AND D.dep_no <= 106
      AND NOT (
            S.sto_kod LIKE N'2050000175473%' OR
            S.sto_kod LIKE N'2050000274268%' OR
            S.sto_kod LIKE N'205001%' OR
            S.sto_kod LIKE N'205002%' OR
            S.sto_kod LIKE N'205003%' OR
            S.sto_kod LIKE N'2200000933416%' OR
            S.sto_kod LIKE N'2917998%' OR
            S.sto_kod LIKE N'2917999%' OR
            S.sto_kod LIKE N'2918001%' OR
            S.sto_kod LIKE N'2918002%' OR
            S.sto_kod LIKE N'2918003%' OR
            S.sto_kod LIKE N'2918004%' OR
            S.sto_kod LIKE N'2918008%' OR
            S.sto_kod LIKE N'800000001%' OR
            S.sto_kod LIKE N'8697417891547%'
        )
    GROUP BY D.dep_no
)
SELECT
    ml.Magaza_Adi,
    ISNULL(pb.Ciro, 0) AS PosBack_Ciro,
    ISNULL(sh.Ciro, 0) AS StokHareket_Ciro,
    CAST(ROUND(ISNULL(sh.Ciro, 0) - ISNULL(pb.Ciro, 0), 2) AS DECIMAL(18,2)) AS Ciro_Farki,
    CAST(
        CASE
            WHEN ISNULL(pb.Ciro, 0) = 0 THEN 0
            ELSE (ISNULL(sh.Ciro, 0) - ISNULL(pb.Ciro, 0)) / pb.Ciro * 100
        END AS DECIMAL(10,2)
    ) AS Fark_Orani_Yuzde,
    CASE
        WHEN ABS(ISNULL(sh.Ciro, 0) - ISNULL(pb.Ciro, 0)) < 100 THEN 'UYUMLU'
        WHEN ABS(ISNULL(sh.Ciro, 0) - ISNULL(pb.Ciro, 0)) <= 5000 THEN 'KÜÇÜK FARK'
        ELSE 'DİKKAT - FARK VAR'
    END AS Durum
FROM MagazaList ml
LEFT JOIN PosBackCiro pb ON pb.MAGNO = ml.MAGNO
LEFT JOIN StokHareketCiro sh ON sh.MAGNO = ml.MAGNO
ORDER BY ml.MAGNO;
