SELECT TOP 5

      ryn_ismi AS Kategori_1
    , san_isim AS Kategori_2
    , sth_stok_kod AS Stok_Kodu
    , sto_isim AS Stok_Adi
    , sto_birim1_ad AS Birim

    , ROUND
      (
          SUM
          (
              CASE
                  WHEN sth_tip = 1
                   AND sth_cins = 1
                   AND sth_normal_iade = 0
                   AND sth_evraktip IN (1,4)
                  THEN sth_miktar

                  WHEN sth_tip = 0
                   AND sth_cins = 1
                   AND sth_normal_iade = 1
                   AND sth_evraktip IN (13,3)
                  THEN -sth_miktar

                  ELSE 0
              END
          )
      ,2) AS Toplam_Satis_Miktari

    , ROUND
      (
          SUM
          (
              CASE
                  WHEN sth_tip = 1
                   AND sth_cins = 1
                   AND sth_normal_iade = 0
                   AND sth_evraktip IN (1,4)
                  THEN sth_tutar - sth_iskonto1

                  WHEN sth_tip = 0
                   AND sth_cins = 1
                   AND sth_normal_iade = 1
                   AND sth_evraktip IN (13,3)
                  THEN -(sth_tutar - sth_iskonto1)

                  ELSE 0
              END
          )
      ,2) AS Toplam_Ciro

FROM STOK_HAREKETLERI WITH(NOLOCK)

INNER JOIN STOKLAR WITH(NOLOCK)
        ON sth_stok_kod = sto_kod

LEFT JOIN STOK_REYONLARI WITH(NOLOCK)
       ON ryn_kod = sto_reyon_kodu

LEFT JOIN STOK_ANA_GRUPLARI WITH(NOLOCK)
       ON san_kod = sto_anagrup_kod

WHERE
        sth_tarih >= DATEADD(DAY,-1,CAST(GETDATE() AS DATE))
    AND sth_tarih < CAST(GETDATE() AS DATE)

    AND
    (
           (
                sth_tip = 1
            AND sth_cins = 1
            AND sth_normal_iade = 0
            AND sth_evraktip IN (1,4)
           )

        OR (
                sth_tip = 0
            AND sth_cins = 1
            AND sth_normal_iade = 1
            AND sth_evraktip IN (13,3)
           )
    )

    AND sto_isim NOT LIKE 'Tanım%'
    AND sto_isim NOT LIKE 'srf%'
    AND sto_isim NOT LIKE 'IPTAL%'
    AND sto_isim NOT LIKE 'OZEN GROSS%'

GROUP BY

      sth_stok_kod
    , sto_isim
    , ryn_ismi
    , san_isim
    , sto_birim1_ad

ORDER BY
    Toplam_Ciro DESC;