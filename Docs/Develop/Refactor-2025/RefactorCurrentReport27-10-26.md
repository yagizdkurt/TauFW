<Dear other maintainers, Im sorry this file in turkish. Its spesifically for me to understand thats why, I will remove this soon. If I forget please tell me -Yagizhan Dinçkurt>

# Refactor-2025: durum raporu (27 Ekim 2026)

Branch `Refactor-2025`. Kaynaklar: aktif plan `LocalR/architecture/ModuleIsolationFinalizations.md`,
[TODO.md](TODO.md) ve changelog [Refactor-2025.md](Refactor-2025.md) (§1–§41).

Kısa cevap: modernizasyonun büyük kısmı bitti. Kalan iş çoğunlukla geriye uyumluluk kodunun silinmesi, birkaç eski
script ve iç temizlik. Altyapı kullanılabilir durumda, ama recipe'lerle uçtan uca çalışmayı şimdiye kadar yalnızca
Yagiz denedi.

## Ne yapıldı

**Altyapı ve testler (§1–§8)**
- BBB regresyon testleri, FastSetup, Python 2 script'lerinin temizliği, `TauFW.Utilities` paketi.
- PicoProducer temizliği: settings, datasets, storage, batch ve jobs ayrıldı; public API, CLI ve workers katmanı var.

**Framework, yani orkestratör (§9–§17)**
- `taufw.py` ve YAML recipe'ler var. Stage'ler: production, controlhists, controlplots, shapes, fit, python.
- Her run `run_root` altında kendi klasörünü alıyor (`logs/`, `stages/<id>/`, manifest'ler). Tuple'lar input olarak
  verilebiliyor, başka bir run'ın stage çıktısı da input olabiliyor.

**Modül izolasyonu**
- Plotter ikiye ayrıldı: Histogrammer histogramları dolduruyor, yeni Plotter sadece çiziyor (§21).
- TES shape'leri Fitter'dan Histogrammer'a taşındı. Eski ve yeni sonuçlar gürültü seviyesinde (~1e-12) aynı (§22).
- "Inputlar verilir, aranmaz" kuralı tamamlandı (§37–§39). Histogrammer artık PicoProducer'ı import etmiyor.
- Data contract'lar yazıldı ve test ediliyor: control-histograms v2, tes-shapes, pico-tuples ve production record
  (`kind`, `sumw`) (§26–§27, §35–§36).
- Import sınırı testi var. Ölçülen bağımlılık 25'ten 19'a indi.

**Config ve sample modeli**
- `Configs/` altında id, versiyon ve lock taşıyan şablonlar (§19).
- Sample listeleri YAML veri olarak tutuluyor (§20).

**Menü (§18, §28–§34)**
- Tek curses oturumunda çalışıyor. Start ve Continue run'ları menünün arkasında yürütüyor.
- Run lock, güvenli durdurma, plan ve status ekranları, grid şifresinin menüden girilmesi var. Listeler önceden
  okunduğu için menü hızlı açılıyor.

**User config (§40–§41)**
- `Analyses/UserConfig.yaml` ve editörü var; `run_root` ve production ayarları buradan geliyor.

**Dokümantasyon**
- Yeni başlayanlar için `Docs/Manual`: GettingStarted, FirstSession, UserConfig, ilk production tutorial'ı, Glossary.

Planın 19 Ekim'deki kendi tahmini: orkestratör ~%85, IO'nun Framework'e geçmesi ~%75, kod izolasyonu ~%75. O
tarihten beri §3 D ve C de bitti, yani bugün bu oranlar biraz daha yüksek.

## Ne kaldı

**1. lxplus kontrolleri (en acil)**
- §40/§41 (user config): `userconfig` ve `plan` lxplus'ta çalıştı. `bbb check` sonucu ve Manual'e yapıştırılacak
  iki çıktı eksik: FastSetup özeti ve `taufw.py --help`.
- §39 (`getmcsample` `tuples=` alıyor): `normal` testleri, `checks` ve `bbb check` 24/24, re-lock olmadan.
- §35/§36: pico tuple contract ve production record. Plan 22'ye göre `framework.production` case'inin re-lock'u da
  burada bekliyor. Bunlar geçince data contract planı da kapanıyor.

**2. Kalan Fitter importları (§3 B)**
- `Fitter/Zpt`: Plotter'ı import ediyor. Taşınacak mı, emekliye mi ayrılacak, sahibi karar vermeli.
- `Fitter/MuTauFR/createinputs.py`: import'u zaten bozuk. Tamir mi edilecek, Legacy'ye mi gidecek, workflow sahibi
  karar vermeli.

**3. Migration point (§3 E), en büyük açık karar**
- Geriye uyumluluk kodları bir noktada hep birlikte silinecek: 13 Plotter alias shim'i, `samples_v15.py`,
  `$PICODIR`/`$TAUFW_PICO_CONFIG`, eski stub'lar, `fillhists.py`'nin varsayılan olarak çizmesi gibi.
- Bu noktanın ne zaman olacağı henüz seçilmedi. Seçilmezse bu kodlar kalıcı hale gelir.

**4. Modüllerin içi (§3 F)**
- Fitter: `os.system` çağrıları, F08–F10 bug'ları, 7 farklı `run_*.sh`. Recipe'de yalnızca DeepTau option-3 fit'i
  sarılı.
- Histogrammer: import sırasında yan etkiler (`SetBatch`, `QCD_OSSS` monkey-patch), büyük dosyalar, L serisi
  bug'lar.
- PicoProducer Part 6/7 (`analysis/`, `corrections/`): `pico.channel_tau_pair` BBB case'i olmadan başlanamıyor, o
  case de yalnızca lxplus'ta kilitlenebiliyor.
- `common` içinde kalanların `Utilities`'e taşınması.

**5. Framework özellikleri (§3 G, TODO §6), ihtiyaç oldukça**
- Bir run'ın başladığı ayarlarla devam etmesi. Bu bugün açıldı: şimdilik run sırasında `outdir` değiştirilmemeli.
- Job submit'in yarıda kalması (SIGKILL) durumuna karşı koruma.
- Provenance (git revizyonu `run.json`'a), weights stage'i, variation production, trigger stage'i, EOS'u `run_root`
  olarak kullanmak.
- Gruptan gelen hız isteği (~40 dk'lık histogram doldurma): skim adımı ya da hadd'i atlamak.

**6. Açık sorular**
- 2025 ağırlık branch'leri ([issues/2025-tuple-weight-branches.md](../issues/2025-tuple-weight-branches.md)).
- Contract testinde bilinen borçlar.

## Kullanılabilirlik

- **Script'ler:** `pico.py`, `fillhists.py`, `draw.py` ve Fitter script'leri eskisi gibi çalışıyor; eski davranış
  korunuyor. Mevcut kullanıcılar için kırılan bir şey yok, BBB bunu kontrol ediyor.
- **Recipe ve menü:** `python3 taufw.py` ve menüyle production'dan fit'e kadar uçtan uca çalışıyor (`tes_id_2025`,
  `example_mutau_*`). Run'lar takip edilebiliyor, durdurulup devam ettirilebiliyor. Ancak bunu gerçek bir analizde
  Yagiz'den başka kimse kullanmadı. Grupta ilk kullanıcılar çıktığında hatalar ve UX sorunları çıkacaktır.
- **Yeni gelen biri için:** FastSetup, user config ve Manual sayesinde başlangıç yolu var. Ama Manual daha ince
  (Tutorials'da tek sayfa var) ve lxplus çıktıları kısmen eksik.
- **Sınırlar:**
  - Fitter'da yalnızca bir fit varyantı sarılı.
  - Variation tuple'ları recipe ile üretilemiyor.
  - Lokal stage'ler yarıda kalınca kaldığı yerden devam edemiyor.
  - Run sırasında ayar değiştirmek riskli.

## Önerilen sıra

1. Önce "Ne kaldı" 1. maddedeki lxplus kontrollerini kapat.
2. Sonra B'yi (Zpt ve MuTauFR) ilgili kişilere sor.
3. Ardından migration point için bir tarih ya da tag belirle.
4. Yeni Framework özelliklerini ancak gruptan biri recipe'leri gerçekten kullanmaya başladığında ve ihtiyaç doğdukça
   ekle.
