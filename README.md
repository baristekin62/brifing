# ÖZEN Brifing — Günlük Yönetici Raporlama Sistemi

Mikro ERP veritabanından sorgular çalıştırıp, yöneticiler için günlük brifing raporu (HTML + Excel) üretir ve e-posta ile gönderir. Flask web paneli ile yönetilir, Windows Görev Zamanlayıcı ile otomatik çalışır.

## Özellikler
- 📊 **Sorgu tabanlı raporlar** — `queries/` altındaki SQL dosyaları çalıştırılır
- 🧠 **İçgörü katmanı** — kural tabanlı günlük özet + geçmiş ortalamayla anomali tespiti
- 📈 **KPI kartları** — brifing üstünde özet metrikler
- 📨 **E-posta** — HTML rapor + Excel eki
- ⏰ **Zamanlayıcı** — günlük/haftalık/aylık, Windows `schtasks` ile
- 👥 **Profiller** — farklı alıcı/saat/konu kombinasyonları

## Kurulum (yeni PC)

```bat
paketler.bat
```

1. Python 3 + paketler (flask, pyodbc, openpyxl) kurulur
2. ODBC Driver 18 kontrol/otomatik kurulum
3. `.env` yoksa durur ve şablon dosyaları `config.json`, `erp_connection.json`, `smtp_profiles.json` olarak kopyalar

### Şifreler (güvenli saklama)

Şifreler **Windows DPAPI** ile şifrelenerek `secrets.dat` dosyasında tutulur — yalnızca o bilgisayarda çözülebilir. Panelde **🔐 Şifre Yönetimi** sayfasından girilir.

Panel girişi **master şifre** (19811203) ile yapılır — hash olarak kodda saklanır, düz metin hiçbir yerde bulunmaz.

Yeni PC'ye taşırken: `paketler.bat` çalıştırın → panelle girin → 🔐 Şifre Yönetimi'nden şifreleri yeniden girin.

## Çalıştırma

```bat
baslat_panel.bat     # Web paneli → http://127.0.0.1:8080
python run_briefing.py   # tek seferlik rapor üretimi
```

Panelden **Profiller → Düzenle → Kaydet** ile Görev Zamanlayıcı otomatik kurulur.

## Yapı

```
D:\BRIFING
├── app.py                    # Flask paneli
├── run_briefing.py           # rapor üretimi + e-posta + zamanlayıcı
├── insights.py               # özet + anomali katmanı
├── config.json               # (gizli) ana ayarlar — şablon: config.example.json
├── erp_connection.json       # (gizli) ERP bağlantı — şablon: erp_connection.example.json
├── smtp_profiles.json        # (gizli) SMTP profiller — şablon: smtp_profiles.example.json
├── secrets.dat               # (gizli) DPAPI ile şifreli şifreler
├── queries/                  # SQL sorguları
├── queries_meta.json         # sorgu sırası/başlık/KPI/özet yapılandırması
├── briefing_profiles.json    # (gizli) profiller
├── history/                  # içgörü geçmişi (anomali verisi)
├── output/                   # üretilen raporlar
└── logs/                     # çalışma günlükleri
```

## Taşınabilirlik

Tüm yollar `BASE_DIR`'e göre göreli çözülür — klasörü kopyalamak yeterlidir. Yeni PC'de yalnızca:
1. `paketler.bat` çalıştırın
2. `.env` dosyasını oluşturun (gerçek şifrelerle)
3. Profillerden saatleri yeniden kaydedin (Görev Zamanlayıcı kayıtları PC'ye özeldir)