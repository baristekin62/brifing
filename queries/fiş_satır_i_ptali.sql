SELECT  convert(varchar(max),[TARIH],104) as 'Tarih'
      ,case when [MAGNO]=101 then 'Ataevler'
	  when [MAGNO]=102 then 'Erikli'
	  when [MAGNO]=103 then 'Kütahya'
	  when [MAGNO]=104 then 'İhsaniye'
	  when [MAGNO]=105 then 'İnegöl'
	  when [MAGNO]=900 then 'Gülbahçe' else '' end as 'Mağaza'
      ,[KASANO]
	  ,[KASIYER]
	  ,PER.ADSOYAD AS 'Kasiyer Adı'
      ,[PFISNO]
      ,[SAAT]
      ,S11.[STKKOD]
,S10.STOKAD AS 'Stok Adı'
      ,[BARKOD]
      , CASE WHEN S11.[BIRIM]=0 THEN 'ADET' WHEN S11.[BIRIM]=1 THEN 'KG' ELSE '' END AS 'Birim'
      ,[BIRFIAT]
      ,[MIKTAR]
      ,[TUTAR]

  FROM  [GRFARKSERVER].[PosBack].[dbo].[SATTD011] S11
  LEFT JOIN [GRFARKSERVER].[PosBack].[dbo].[STKTM010] S10 ON S11.STKKOD=S10.STKKOD
  LEFT JOIN [GRFARKSERVER].[PosBack].[dbo].[PERTT005] PER ON PER.PERNO=S11.KASIYER
  where TARIH >= CONVERT(DATE, DATEADD(DAY, -1, GETDATE()))
and TARIH < CONVERT(DATE, GETDATE())
AND SNO<0
  ORDER BY s11.TARIH,s11.MAGNO asc, s11.KASANO asc,s11.KASIYER asc, s11.PFISNO asc;