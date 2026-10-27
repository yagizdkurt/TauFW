# UserConfig path geçişi incelemesi

Tarih: 2026-10-27. Kapsam: mevcut checkout üzerinde statik kod incelemesi; uygulama değişikliği yok.

**Öneri:** kişiye/makineye ait dizinleri UserConfig'te tutalım, bunları script veya Framework girişinde okuyup
fonksiyonlara açık parametre olarak geçelim. Bir fonksiyonun path parametresi olması, o parametreyi kaldırmak
için bir neden değil. Analizin hangi veri ve kalibrasyon sürümünü kullandığı recipe/bundle içinde görünür kalmalı.

## 1. Mevcut durum

- Gerçek okuma API'si `UserConfig.get(...)` değil, `config = UserConfig.load()` ardından `config.get(...)` veya
  `config.require(...)`. Kaynak: [UserConfig/_config.py](../../../Utilities/python/UserConfig/_config.py).
- Hazır path ayarları: `runs.run_root`, `production.outdir`, `production.nanodir`, `production.tmpskimdir`.
  Batch/queue ve hadd komutu gibi path dışı ayarlar da mevcut. Kaynak:
  [_template.py](../../../Utilities/python/UserConfig/_template.py),
  [Framework/user_settings.py](../../../Framework/python/user_settings.py).
- Bunlar recipe çalıştıran Framework tarafından kullanılıyor. Doğrudan `pico.py` komutları UserConfig okumuyor;
  kendi PicoProducer config'ini kullanıyor. Aynı key'i eklemek tek başına bütün komutları değiştirmez.
- `Utilities.Paths` zaten checkout köklerini, EOS/AFS/CVMFS köklerini ve endpoint sabitlerini topluyor. Bir sabiti
  burada toplamak ile kullanıcı tarafından seçilebilir hale getirmek farklı işler. Kaynak:
  [Paths/_paths.py](../../../Utilities/python/Paths/_paths.py).
- Kullanıcı kendi bölümlerini ekleyebiliyor. Bu rapordaki **yeni key isimleri öneridir**; otomatik tüketilen
  ayarlar olarak henüz uygulanmış değiller.

## 2. `getmcsample` için karar

Koddaki fonksiyonun adı tekil `getmcsample`; yanında `getsampleset` var.
[sample/utils.py](../../../Histogrammer/python/sample/utils.py), satır 25 ve 115.
Eski `TauFW.Plotter.sample.utils` importu da aynı Histogrammer modülüne yönleniyor.

Şu an ikisi de varsayılan dosya desenindeki `$PICODIR` için `tuples=` bekliyor; verilmezse hata veriyor.
`fname=` içinde `$PICODIR` yoksa dosya deseni doğrudan da verilebiliyor. Bu açıklık korunmalı.

**UserConfig'ten değer alıp `tuples=` ile vermek makul. Fonksiyonun içinde otomatik UserConfig okumak uygun değil.**
İkinci seçenek aynı fonksiyon çağrısının kişisel YAML değişince farklı veriyi açmasına neden olur ve mevcut
“tuple girdisi çağırandan gelir” davranışını değiştirir. Bu davranış
[testTupleLocation.py](../../../Tests/Plotter/testTupleLocation.py) içinde de doğrulanıyor.

Önerilen bağımsız script kullanımı; `args.tuples` scriptin `--tuples` argümanı:

```python
from TauFW.Utilities import UserConfig
from TauFW.Histogrammer.sample.utils import getmcsample

tuples = args.tuples
if tuples is None:
    config = UserConfig.load()
    tuples = config.require("histogrammer.tuples")  # önerilen yeni key
if not isinstance(tuples, str) or not tuples.strip():
    raise ValueError("tuples: boş olmayan bir dizin deseni gerekli")

sample = getmcsample(
    "DY", "DYJets", "Drell-Yan", 1.0, "mumu", "2025", tuples=tuples
)
```

Burada config yalnız ihtiyaç varsa, script girişinde bir kez okunur. Eksik zorunlu ayar için `require()` daha
anlaşılır hata verir; sadece `get()` kullanmak eksik değeri `None` olarak aşağıya taşır. `require()` mevcut ama
boş/null/yanlış türde bir değeri reddetmediği için tüketicinin basit değer kontrolü yine gerekir.

Framework için aynı fallback'i eklemeyelim: tuple yolu zaten üretim artifact'ından, başka run'ın manifest'inden
veya recipe'deki `external` girdiden geliyor. Kaynak:
[LocalStage.tuples_pattern](../../../Framework/python/stages/local.py), satır 139;
[ControlHistsStage](../../../Framework/python/stages/controlhists.py), satır 48;
[ShapesStage](../../../Framework/python/stages/shapes.py), satır 62.

## 3. Geçiş adayları

| Öncelik | Bulgu ve kaynak | Önerilen yer / işlem |
|---|---|---|
| Yüksek | [HighPT/utilsHighPT.py](../../../Fitter/python/HighPT/utilsHighPT.py):13–27: `picoFolder`, beş `figuresFolder*`, `datacardsFolder`; `/eos/user/r/rasp/...` ve kişisel AFS alanları | `highpt.tuples_root`, `highpt.figures_root`, `highpt.datacards_root`. Alt plot dizinlerini kökten türet; farklı konum gerekiyorsa ayrı override. Okuma HighPT scriptlerinin girişinde olsun. |
| Yüksek | [CombineCardsHighPT.bash](../../../Fitter/HighPT/CombineCardsHighPT.bash):4, [RunCombineHighPT.bash](../../../Fitter/HighPT/RunCombineHighPT.bash):4, [RunImpactsHighPT.bash](../../../Fitter/HighPT/RunImpactsHighPT.bash):4: kişisel datacards dizini | Python giriş noktası config'ten çözüp shell scriptine argüman versin. Python'daki `datacards_eta` ile shell'deki `datacards` farklı; tek key'e bağlamadan hangi çıktıyı okudukları netleştirilmeli. |
| Yüksek | [fillhists.py](../../../Histogrammer/fillhists.py):168 ve [createinputsTES.py](../../../Histogrammer/shapes/TauES/createinputsTES.py):86: argüman yoksa `script_default_tuples()` | Bağımsız CLI için `histogrammer.tuples` iyi aday. `--tuples` öncelikli kalır. Bu, kütüphanedeki `getmcsample` değişikliği değil, giriş noktası değişikliği olur. |
| Orta | [Trigger_Efficiency_datavsmc.py](../../../Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_datavsmc.py):20–23, [Trigger_Efficiency_dtauvspnet.py](../../../Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_dtauvspnet.py):12–15 | Kullanıcı adı dinamik olsa da EOS ve `analysis/<year>` yerleşimi sabit. `trigger_sf.analysis_root` ve `trigger_sf.plot_root` ile yerleşimin kullanıcı kısmını ayır. Dosya ve yıl seçimi analizde kalsın. |
| Orta | [Trigger_Efficiency_data_generic.py](../../../Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py):39–40,66–67 ve [hadd_files.py](../../../Tau_Trigger_SF/helper_scripts/hadd_files.py):57 | Aynı trigger kökünü kullan. D/I era dosyalarının özel eşlemesi çalışma config'inde kalmalı. Hadd scriptinin giriş/çıkış düzeni de aynı kökten türetilmeli. |
| Orta | [Zpt/copy2www.sh](../../../Fitter/Zpt/copy2www.sh):15–26: `/t3home/ineuteli/eos/www/Zpt/` birkaç kez yazılmış | `zpt.publish_root` kişisel ayarı; script argümanla hedef alsın, bütün alt yollar tek hedef değişkeninden türesin. |
| Koşullu | [PicoProducer/settings/defaults.py](../../../PicoProducer/python/settings/defaults.py):109–113: `jobdir`, `outdir`, `picodir`, `nanodir`, `filelistdir` | `outdir`/`nanodir` Framework için zaten taşındı. `production.jobdir` ve `production.filelistdir` ancak kişisel log/cache konumu ihtiyacı varsa eklensin. Doğrudan `pico.py` desteği ayrı bir kapsam. |
| Koşullu | [storage/base.py](../../../PicoProducer/python/storage/base.py):44; [t2_psi.py](../../../PicoProducer/python/storage/t2_psi.py):32; [t3_psi.py](../../../PicoProducer/python/storage/t3_psi.py):32 | Geçici depolama seçilebilir olabilir; `TMPDIR` ve var olan `tmpdir` geçişiyle uyumlu çözülmeli. `production.tmpskimdir`, storage hadd tmp alanı ve batch worker scratch aynı şey değil; tek ayara birleştirmeyelim. |

Histogrammer CLI'lerinin bugünkü fallback'i [sample/tupledir.py](../../../Histogrammer/python/sample/tupledir.py)
içinde: `$TAUFW_PICO_CONFIG` veya `PicoProducer/config/config.json` dosyasındaki `picodir` okunuyor. UserConfig'e
geçerken bu eski fallback'in kaldırılması mı, geçici olarak son sırada tutulması mı istendiği açıkça belirlenmeli.
İki kaynaktan farklı değer okunup sessizce farklı tuple seçilmemeli. Yeni CLI sırası:
`--tuples > UserConfig varsayılanı > belirlenmiş legacy davranış veya açık hata`.

`production.picodir` eklemek Framework çıktısının yerini değiştirmez: Framework merged tuple'ları zaten
`<run_dir>/stages/<id>/` altına yönlendiriyor. Kaynak:
[stages/production.py](../../../Framework/python/stages/production.py), satır 14–18.
Bu yüzden bağımsız Histogrammer'ın **okuma varsayılanına** ayrı bir isim vermek daha anlaşılır.

## 4. Path parametresi alan fonksiyonlar

| Fonksiyon / API | UserConfig ile ilişki |
|---|---|
| `getmcsample(..., tuples=..., fname=...)`, `getsampleset(..., tuples=...)` | Parametreler kalsın; bağımsız script config'ten varsayılanını seçip geçsin. |
| [sample.model.getsampleset(..., model, **kwargs)](../../../Histogrammer/python/sample/model.py), `load_sample_model(path)` | Tuple kökü çağırandan; sample model dosyası recipe/bundle'dan gelsin. Model analizin sample/weight seçimini içeriyor. |
| [sampleHighPt(basefolder, ...)](../../../Fitter/python/HighPT/utilsHighPT.py):456 | İyi bir mevcut parametre örneği. Çağırandaki `utils.picoFolder` yerine çözülmüş `highpt.tuples_root` geçilebilir. |
| Aynı dosyadaki `FakeFactorHighPt(filename)`:420 | Dosya argümanı kalsın. Fake-factor dosyasının sürümü analiz girdisi; kişisel kökü config'ten gelebilir. |
| [ControlHists.request](../../../Histogrammer/python/api/control_hists.py), [TESShapes.shapes_request](../../../Histogrammer/python/api/tes_shapes.py): `tuples`, `outdir`, `configs`, `samples` | Request açık değerleri taşımaya devam etsin. Framework bunları zaten çözüyor; API içinde kişisel YAML fallback'i olmasın. |
| [ControlPlots.request](../../../Plotter/python/api/control_plots.py): `files`, `outdir`; [TESFit.fit_request](../../../Fitter/python/api/tes_id.py): fit girdileri ve `outdir` | Pipeline girdileri artifact/recipe'den gelir. Bağımsız script isterse kişisel çıktı kökünü okuyup request'e geçirir. |
| [PicoProducer.request / merge](../../../PicoProducer/python/api/producer.py): `tupledir`, config ve merge seçenekleri | Framework'ün seçtiği çıktı dizini önceliklidir. Doğrudan kullanımda da seçilmiş değer açıkça geçirilmeli. |
| [FileIO](../../../Utilities/python/FIO/_file_io.py): `read_*`, `write_*`, `copy_file`, `open_root_file`, `merge_root_files` | Genel dosya işlemleri path almaya devam etmeli. `FileIO(temporary_directory=...)` için gerekiyorsa üst katman config okuyup değer geçebilir. |
| [Paths](../../../Utilities/python/Paths/_paths.py): `eos_user`, `afs_work`, `cmssw_src`, `xrootd_url` | Path üretme yardımcıları olarak kalsınlar; kişisel YAML okumaları gerekmez. |

Özellikle `FileIO` içine UserConfig okuması koymak ters bağımlılık da doğurur: UserConfig'in YAML okuması zaten
`FileIO` kullanıyor. Her path alan fonksiyonun config'e bağımlı hale getirilmesi uygun bir geçiş yöntemi değil.

## 5. UserConfig'e doğrudan taşınmaması gerekenler

1. **Analizin ortak tuple kaynağı.** [tes_id_2025/recipe.yml](../../../Analyses/tes_id_2025/recipe.yml):42 içindeki
   `/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP` belirli bir kampanyayı seçiyor.
   Recipe'de açık kalmalı. Kullanıcının aynı verinin yerel kopyasını seçmesi ileride desteklenirse, çözülen gerçek
   path ve kaynak run kaydına yazılmalı; bugün recipe'de UserConfig referansı çözme mekanizması yok.
2. **NanoAOD sample katalogları.** Örneğin
   [samples_2022_postEE.py](../../../PicoProducer/samples/samples_2022_postEE.py):4–6 içinde normal, `new` ve
   era-E için farklı storage kaynakları var. `irandreo` ismini mevcut kullanıcıyla değiştirmek veri kaynağını
   değiştirir. Aynı değerlendirme eski TauID kataloglarının kişisel alanları için de geçerli. Bunlar kampanya
   kaynakları olarak korunmalı; alternatif kopya desteği ayrı ve açık bir override olmalı.
3. **Checkout'a ait veri dosyaları.**
   [WmassCorrection.py](../../../PicoProducer/python/corrections/WmassCorrection.py):7 ve
   [MetTriggerSF.py](../../../PicoProducer/python/corrections/MetTriggerSF.py):8 içindeki
   `$CMSSW_BASE/src/TauFW/PicoProducer/data/...` bağımlılığı `PICO_DATA_DIR` gibi mevcut checkout sabitleriyle
   temizlenebilir. Her kullanıcıdan bu path'i ayarlamasını istemek gereksiz.
4. **Kalibrasyonun kimliği/sürümü, filename desenleri ve çıktı sözleşmesi.** `$SAMPLE_$CHANNEL$TAG.root`,
   `input_pt_less_region`, `stages/<id>` gibi düzenler tüketicilerle ortak sözleşmedir. Bunlar sırf string olarak
   yazıldıkları için kişisel config ayarı olmamalı. Run çıktılarının üst kökü için zaten `runs.run_root` var.
5. **Site altyapısı.** Storage factory'nin `/pnfs/...` tanıması, CMS redirector'ları ve CVMFS kurulum yolları site
   tanımıdır. Tekrarları `Utilities.Paths` üzerinden azaltılabilir; hepsini UserConfig'e eklemek gerekmiyor.
   Kullanıcıya gerçekten site/endpoint seçtiren ihtiyaç varsa ayrı, açık bir seçenek düşünülebilir.
6. **Yorumlar, örnekler, test fixture'ları.** `Histogrammer/plot_postfit*.py` ve `plot_v10.py` içindeki yorumlanmış
   `/nfs/user/pmastra/...` örnekleri çalışan path bağımlılığı değil. Doküman ve menü preview örneklerini de gerçek
   migration adayı saymadım.

## 6. 2025 weight scriptleri: ayrı ele alınmalı

[add_pileup_weights.py](../../../Legacy/OldAnalysis/2025-2026/add_pileup_weights.py):57–62 ve
[add_muon_weights.py](../../../Legacy/OldAnalysis/2025/add_muon_weights.py):43–49 iki tür path'i karıştırıyor:

- EOS tuple kaynağı: bu işlem hangi kampanyayı değiştirecek, recipe girdisi veya açık CLI argümanı olmalı.
- Kişisel AFS checkout'u: repo içindeki `PicoProducer/data/...` dosyalarına `PICO_DATA_DIR` üzerinden erişilmeli.
  Ayrı bir dış kalibrasyon dosyası gerekiyorsa onun path'i ve sürümü analiz config'inde açıkça verilmeli.

Bu dosyaları sadece UserConfig'e taşımak, hangi pileup/scale-factor sürümü kullanıldığını yeniden üretilebilir
hale getirmiyor. `MC_PileUp_2025.root` ve `_v2`/`_v3` soruları da devam ediyor. Mevcut issue:
[2025-tuple-weight-branches.md](2025-tuple-weight-branches.md). Planlanan weights step'e geçerken pathler çözülmeli.

## 7. Küçük bir geçiş sırası

1. Bağımsız Histogrammer CLI için `histogrammer.tuples`; kütüphane imzalarını ve Framework artifact akışını koru.
2. HighPT'nin kişisel pathlerini giriş noktalarında çöz; shell/Python datacards farkını koruyarak netleştir.
3. Trigger scriptlerinin ortak kişisel köklerini ve Zpt yayın hedefini ayır.
4. İhtiyaç varsa doğrudan `pico.py` kullanımının UserConfig politikasını ayrıca tasarla; mevcut production key'lerini
   ikinci bir isimle çoğaltma. Storage scratch ve worker scratch düzenini bu adıma körlemesine bağlama.
5. Weight scriptlerini mevcut weights-step işiyle birlikte ele al.

Yeni resmi ayarlar için `_template.py` kaydı, tüketici, gerekiyorsa `_guesses.py` aktarımı ve Manual güncellemesi
birlikte yapılmalı. Mevcut kullanıcı dosyaları yeniden oluşturulmadığı için eksik yeni key'in davranışı da açık olmalı.

Path çözümleme kuralları küçük ve açık kalmalı: `Config.get()` otomatik `~`, ortam değişkeni veya `$ERA/$GROUP`
genişletmesi yapmıyor. Analiz placeholder'ları tüketici tarafından işleniyor. Yeni path key'lerinin relatif/absolute
anlamı ve desteklediği placeholder'lar tanımlanmalı. Bu rapor tuple okuma tarafına yeni `root://` desteği önermiyor;
mevcut yerel dosya kontrolleri ayrıca değerlendirilmeden dizin yerine URL koymak yeterli değil.

Bir run'ın veri kaynağını etkileyen yeni config çözümlemesi eklenirse sonuç run kaydında sabitlenmeli. Mevcut Framework
production ayarlarının snapshot'ını kaydetse de sonraki `advance` çağrılarında config'i yeniden okuyor; bu zaten
[Framework README](../../../Framework/README.md) içinde açık TODO. Yeni tuple fallback'iyle bu davranış genişletilmemeli.

Uygulama sırasında gereken doğrulama sınırlı: argümanın config'e üstün gelmesi, eksik/boş config değerinin anlaşılır
hatası ve açık `tuples=` değerinin doğru dosyaya gitmesi. Bu rapor için kod veya analiz çalıştırılmadı; ROOT/CMSSW,
EOS erişimi ve dosyaların mevcut olup olmadığı doğrulanmadı.
