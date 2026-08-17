;WITH RAPOR AS







(







    SELECT







        dbo.fn_DepoIsmi(ssip_girdepo) AS MAGAZA,







        SUM(ssip_miktar) AS TOPLAM_SIPARIS,







        SUM(ssip_teslim_miktar) AS TOPLAM_TESLIM_EDILEN,







    SUM







        (







            dbo.fn_Evrak_Kalan_Miktar







            (







                ssip_miktar,







                ssip_teslim_miktar,







                ssip_kapat_fl







            )







        ) AS KALAN_SIPARIS







    FROM dbo.DEPOLAR_ARASI_SIPARISLER WITH (NOLOCK)







    WHERE ssip_tarih >= DATEADD(DAY, -30, GETDATE())







      AND ssip_tarih <= GETDATE()







      AND dbo.fn_StokIsmi(ssip_stok_kod) NOT LIKE 'SRF.%'







      AND dbo.fn_StokIsmi(ssip_stok_kod) NOT LIKE 'OZEN GROSS%'







    GROUP BY







        dbo.fn_DepoIsmi(ssip_girdepo)







),







SONUC AS







(







    SELECT







        MAGAZA,







        TOPLAM_SIPARIS,







        TOPLAM_TESLIM_EDILEN,







        KALAN_SIPARIS,







        CAST







        (







            CASE







                WHEN TOPLAM_SIPARIS = 0







                    THEN 0







                ELSE







                    TOPLAM_TESLIM_EDILEN * 100.0







                    / TOPLAM_SIPARIS







            END







            AS DECIMAL(10,2)







        ) AS KARŞILAMA_YUZDESI,







        0 AS SIRA







    FROM RAPOR







    UNION ALL















    SELECT















        'GENEL TOPLAM',















        SUM(TOPLAM_SIPARIS),















        SUM(TOPLAM_TESLIM_EDILEN),















        SUM(KALAN_SIPARIS),















        CAST







        (







            CASE







                WHEN SUM(TOPLAM_SIPARIS) = 0







                    THEN 0















                ELSE







                    SUM(TOPLAM_TESLIM_EDILEN) * 100.0







                    / SUM(TOPLAM_SIPARIS)















            END







            AS DECIMAL(10,2)







        ),















        1 AS SIRA















    FROM RAPOR







)















SELECT







    MAGAZA AS [MAĞAZA],















    TOPLAM_SIPARIS AS [TOPLAM SİPARİŞ],















    TOPLAM_TESLIM_EDILEN AS [TOPLAM TESLİM EDİLEN],















    KALAN_SIPARIS AS [KALAN SİPARİŞ],















    KARŞILAMA_YUZDESI AS [KARŞILAMA YÜZDESİ]















FROM SONUC















ORDER BY







    SIRA,







    MAGAZA;