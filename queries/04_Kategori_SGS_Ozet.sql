/* ============================================================
   KATEGORİ BAZLI SGS (STOK GÜN SAYISI) ÖZET RAPORU
   Kaynak: sp_KategoriBazliStokRaporuMailGonder (KategoriSGS.sql)
   Kapsam: GIDA / GIDA DIŞI NON FOOD / MANAV VE TAZE GIDA / DİĞER + GENEL TOPLAM
   Formül: SGS = Stok TL / (Son 30 Gün Satış TL / 30)
   Not: fn_ReyonIsmi yerine STOK_REYONLARI tablosuna doğrudan join yapılır.
   ============================================================ */
;WITH Fiyat AS
(
    SELECT
        sas_stok_kod,
        sas_satis_fiyat,
        ROW_NUMBER() OVER
        (
            PARTITION BY sas_stok_kod
            ORDER BY sas_basla_tarih DESC, sas_create_date DESC
        ) AS RN
    FROM SATINALMA_SARTLARI WITH (NOLOCK)
    WHERE sas_satis_fiyat > 0
),
Stok AS
(
    SELECT
        S.sto_kod,
        R.ryn_kod AS REYON_KOD,
        S.sto_anagrup_kod AS ANA_GRUP_KOD,
        CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 101, GETDATE() - 1) AS DECIMAL(18,2)) AS AtaevlerStok,
        CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 102, GETDATE() - 1) AS DECIMAL(18,2)) AS ErikliStok,
        CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 103, GETDATE() - 1) AS DECIMAL(18,2)) AS KutahyaStok,
        CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 104, GETDATE() - 1) AS DECIMAL(18,2)) AS IhsaniyeStok,
        CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 105, GETDATE() - 1) AS DECIMAL(18,2)) AS InegolStok,
        CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 5, GETDATE() - 1) AS DECIMAL(18,2)) AS DepoStok,
        (CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 501, GETDATE() - 1) AS DECIMAL(18,2)) +
         CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 502, GETDATE() - 1) AS DECIMAL(18,2)) +
         CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 503, GETDATE() - 1) AS DECIMAL(18,2)) +
         CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 504, GETDATE() - 1) AS DECIMAL(18,2)) +
         CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 505, GETDATE() - 1) AS DECIMAL(18,2)) +
         CAST(dbo.fn_DepodakiMiktar(S.sto_kod, 6, GETDATE() - 1) AS DECIMAL(18,2))) AS IadeDepolarStok
    FROM STOKLAR S WITH (NOLOCK)
    LEFT JOIN STOK_REYONLARI R WITH (NOLOCK)
        ON R.ryn_kod = S.sto_reyon_kodu
),
Satis AS
(
    SELECT
        sth_stok_kod,
        CAST(ROUND(SUM(CASE
            WHEN sth_cikis_depo_no = 101 AND sth_tip = 1 AND sth_cins = 1 AND sth_normal_iade = 0 AND sth_evraktip IN (1,4) THEN sth_tutar
            WHEN sth_cikis_depo_no = 101 AND sth_tip = 0 AND sth_cins = 1 AND sth_normal_iade = 1 AND sth_evraktip IN (13,3) THEN -sth_tutar
            ELSE 0 END),2) AS DECIMAL(18,2)) AS AtaevlerAylikSatis,
        CAST(ROUND(SUM(CASE
            WHEN sth_cikis_depo_no = 102 AND sth_tip = 1 AND sth_cins = 1 AND sth_normal_iade = 0 AND sth_evraktip IN (1,4) THEN sth_tutar
            WHEN sth_cikis_depo_no = 102 AND sth_tip = 0 AND sth_cins = 1 AND sth_normal_iade = 1 AND sth_evraktip IN (13,3) THEN -sth_tutar
            ELSE 0 END),2) AS DECIMAL(18,2)) AS ErikliAylikSatis,
        CAST(ROUND(SUM(CASE
            WHEN sth_cikis_depo_no = 103 AND sth_tip = 1 AND sth_cins = 1 AND sth_normal_iade = 0 AND sth_evraktip IN (1,4) THEN sth_tutar
            WHEN sth_cikis_depo_no = 103 AND sth_tip = 0 AND sth_cins = 1 AND sth_normal_iade = 1 AND sth_evraktip IN (13,3) THEN -sth_tutar
            ELSE 0 END),2) AS DECIMAL(18,2)) AS KutahyaAylikSatis,
        CAST(ROUND(SUM(CASE
            WHEN sth_cikis_depo_no = 104 AND sth_tip = 1 AND sth_cins = 1 AND sth_normal_iade = 0 AND sth_evraktip IN (1,4) THEN sth_tutar
            WHEN sth_cikis_depo_no = 104 AND sth_tip = 0 AND sth_cins = 1 AND sth_normal_iade = 1 AND sth_evraktip IN (13,3) THEN -sth_tutar
            ELSE 0 END),2) AS DECIMAL(18,2)) AS IhsaniyeAylikSatis,
        CAST(ROUND(SUM(CASE
            WHEN sth_cikis_depo_no = 105 AND sth_tip = 1 AND sth_cins = 1 AND sth_normal_iade = 0 AND sth_evraktip IN (1,4) THEN sth_tutar
            WHEN sth_cikis_depo_no = 105 AND sth_tip = 0 AND sth_cins = 1 AND sth_normal_iade = 1 AND sth_evraktip IN (13,3) THEN -sth_tutar
            ELSE 0 END),2) AS DECIMAL(18,2)) AS InegolAylikSatis
    FROM STOK_HAREKETLERI WITH (NOLOCK)
    WHERE sth_tarih >= DATEADD(DAY, -30, GETDATE())
    GROUP BY sth_stok_kod
),
Sonuc AS
(
    SELECT
        CASE
            WHEN S.REYON_KOD = '100' THEN 'GIDA'
            WHEN S.REYON_KOD = '200' AND S.ANA_GRUP_KOD = '200.30' THEN 'MANAV'
            WHEN S.REYON_KOD = '200' THEN 'TAZE GIDA'
            WHEN S.REYON_KOD = '300' THEN 'GIDA DIŞI'
            WHEN S.REYON_KOD = '400' THEN 'NON FOOD'
            ELSE 'DİĞER REYONLAR'
        END AS KATEGORI,
        S.sto_kod AS STOK_KODU,
        ISNULL(F.sas_satis_fiyat, 0) AS BirimFiyat,
        (S.AtaevlerStok + S.ErikliStok + S.IhsaniyeStok + S.KutahyaStok + S.InegolStok) AS MagazaStok,
        S.DepoStok,
        S.IadeDepolarStok,
        (S.AtaevlerStok + S.ErikliStok + S.IhsaniyeStok + S.KutahyaStok + S.InegolStok) * ISNULL(F.sas_satis_fiyat, 0) AS MagazaTL,
        S.DepoStok * ISNULL(F.sas_satis_fiyat, 0) AS DepoTL,
        S.IadeDepolarStok * ISNULL(F.sas_satis_fiyat, 0) AS IadeDepolarTL,
        ISNULL(T.AtaevlerAylikSatis, 0) + ISNULL(T.ErikliAylikSatis, 0) + ISNULL(T.IhsaniyeAylikSatis, 0) +
        ISNULL(T.KutahyaAylikSatis, 0) + ISNULL(T.InegolAylikSatis, 0) AS ToplamAylikSatis
    FROM Stok S
    LEFT JOIN (SELECT sas_stok_kod, sas_satis_fiyat FROM Fiyat WHERE RN = 1) F
        ON S.sto_kod = F.sas_stok_kod
    LEFT JOIN Satis T
        ON S.sto_kod = T.sth_stok_kod
)
SELECT
    CASE
        WHEN GROUPING(KATEGORI) = 1 THEN 'GENEL TOPLAM'
        ELSE KATEGORI
    END AS Kategori,
    CAST(ROUND(SUM(MagazaStok), 2) AS DECIMAL(18,2)) AS Magaza_Stok,
    CAST(ROUND(SUM(DepoStok), 2) AS DECIMAL(18,2)) AS Depo_Stok,
    CAST(ROUND(SUM(IadeDepolarStok), 2) AS DECIMAL(18,2)) AS Iade_Depo_Stok,
    CAST(ROUND(SUM(MagazaTL), 2) AS DECIMAL(18,2)) AS Magaza_TL,
    CAST(ROUND(SUM(DepoTL), 2) AS DECIMAL(18,2)) AS Depo_TL,
    CAST(ROUND(SUM(IadeDepolarTL), 2) AS DECIMAL(18,2)) AS Iade_Depo_TL,
    CAST(ROUND(SUM(ToplamAylikSatis), 2) AS DECIMAL(18,2)) AS Son30Gun_Satis,
    CAST(ROUND(SUM(ToplamAylikSatis) / 30.0, 2) AS DECIMAL(18,2)) AS Gunluk_Ciro,
    CAST(
        ROUND(
            CASE
                WHEN SUM(ToplamAylikSatis) <= 0 THEN 0
                ELSE SUM(MagazaTL) / NULLIF(SUM(ToplamAylikSatis) / 30.0, 0)
            END, 2) AS DECIMAL(18,2)) AS Magaza_SGS,
    CAST(
        ROUND(
            CASE
                WHEN SUM(ToplamAylikSatis) <= 0 THEN 0
                ELSE SUM(DepoTL) / NULLIF(SUM(ToplamAylikSatis) / 30.0, 0)
            END, 2) AS DECIMAL(18,2)) AS Depo_SGS,
    CAST(
        ROUND(
            CASE
                WHEN SUM(ToplamAylikSatis) <= 0 THEN 0
                ELSE (SUM(MagazaTL) + SUM(DepoTL)) / NULLIF(SUM(ToplamAylikSatis) / 30.0, 0)
            END, 2) AS DECIMAL(18,2)) AS Toplam_SGS
FROM Sonuc
GROUP BY ROLLUP(KATEGORI)
HAVING GROUPING(KATEGORI) = 1
    OR KATEGORI IN ('GIDA', 'TAZE GIDA', 'MANAV', 'GIDA DIŞI', 'NON FOOD')
ORDER BY CASE KATEGORI
            WHEN 'GIDA' THEN 1
            WHEN 'TAZE GIDA' THEN 2
            WHEN 'MANAV' THEN 3
            WHEN 'GIDA DIŞI' THEN 4
            WHEN 'NON FOOD' THEN 5
            ELSE 6
         END;
