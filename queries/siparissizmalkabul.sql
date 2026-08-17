/* ============================================================
   SİPARİŞSİZ MAL KABUL (Dün)
   Siparişi olmadan (sth_sip_uid boş) depoya giriş yapılan ürünler.
   Not: fn_* fonksiyonları çapraz DB erişimi istediği için doğrudan
   tablo join'leri kullanılır. Dünün TAM GÜNÜ alınır.
   ============================================================ */
SELECT
    R.ryn_ismi AS 'Reyon Adı',
    AG.san_isim AS 'Ana Grup Adı',
    ALG.sta_isim AS 'Alt Grup Adı',
    CONVERT(VARCHAR(MAX), H.sth_tarih, 104) AS 'Kayıt Tarihi',
    CONCAT(H.sth_evrakno_seri, '-', H.sth_evrakno_sira) AS 'Evrak No',
    H.sth_stok_kod AS 'Stok Kodu',
    S.sto_isim AS 'Stok İsmi',
    ISNULL(MAX(SD.sdp_yerkodu), '') AS 'Mal Kabul Şekli',
    H.sth_miktar AS 'Miktar',
    CASE
        WHEN H.sth_giris_depo_no = 101 THEN 'Ataevler'
        WHEN H.sth_giris_depo_no = 102 THEN 'Erikli'
        WHEN H.sth_giris_depo_no = 103 THEN 'Kütahya'
        WHEN H.sth_giris_depo_no = 104 THEN 'İhsaniye'
        WHEN H.sth_giris_depo_no = 105 THEN 'İnegöl'
        WHEN H.sth_giris_depo_no = 10 THEN 'Gülbahçe Ana Depo'
        ELSE ''
    END AS 'Mağaza Adi',
    ISNULL(C.cari_unvan1, '') AS 'Cari Adı'
FROM STOK_HAREKETLERI H WITH (NOLOCK)
INNER JOIN STOKLAR S WITH (NOLOCK)
    ON S.sto_kod = H.sth_stok_kod
LEFT JOIN STOK_REYONLARI R WITH (NOLOCK)
    ON R.ryn_kod = S.sto_reyon_kodu
LEFT JOIN STOK_ANA_GRUPLARI AG WITH (NOLOCK)
    ON AG.san_kod = S.sto_anagrup_kod
LEFT JOIN STOK_ALT_GRUPLARI ALG WITH (NOLOCK)
    ON ALG.sta_kod = S.sto_altgrup_kod
LEFT JOIN STOK_DEPO_DETAYLARI SD WITH (NOLOCK)
    ON SD.sdp_depo_kod = S.sto_kod
   AND SD.sdp_depo_no = H.sth_giris_depo_no
LEFT JOIN CARI_HESAPLAR C WITH (NOLOCK)
    ON C.cari_kod = H.sth_cari_kodu
WHERE H.sth_sip_uid = '{00000000-0000-0000-0000-000000000000}'
  AND H.sth_tip = 0
  AND H.sth_cins = 0
  AND H.sth_normal_iade = 0
  AND H.sth_evraktip IN (3, 13)
  AND H.sth_tarih >= CONVERT(DATE, DATEADD(DAY, -1, GETDATE()))
  AND H.sth_tarih < CONVERT(DATE, GETDATE())
AND AG.san_kod <>'200.30'
GROUP BY
    H.sth_tarih,
    H.sth_stok_kod,
    S.sto_isim,
    R.ryn_ismi,
    AG.san_isim,
    ALG.sta_isim,
    H.sth_giris_depo_no,
    H.sth_evrakno_seri,
    H.sth_evrakno_sira,
    H.sth_cari_kodu,
    H.sth_miktar,
    C.cari_unvan1
ORDER BY H.sth_tarih DESC;