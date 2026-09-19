# Graph Report - Kicad  (2026-09-08)

## Corpus Check
- 170 files · ~231,228 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 4027 nodes · 8574 edges · 202 communities (172 shown, 30 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 449 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0a57915a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Design
- Kaynak kalitesi uyarisi: sayisal kriter veren tek sistematik kaynak
- JunctionTests
- kurulum.py
- minyaml.py
- test_ipc_apply.py
- anla
- elektrik.py
- add_symbols
- .routed
- Repertoire
- symlib.py
- test_intent.py
- load_rules
- PricingTests
- _Model
- SyntheticDiscreteBuckTests
- intent.py
- penalty_of
- PlacementContext
- MoveFeaturizer
- connect.py
- pcb.py
- __main__.py
- ipc2221.py
- sch_add.py
- sch_move.py
- canli_sematik.py
- test_pcb_sync.py
- test_decoupling_count.py
- mpn.py
- cluster.py
- expand_intent
- sch_wire.py
- synth.py
- _variant
- children
- refine.py
- bench_context
- run
- propose.py
- Schematic
- sch_place.py
- swig_apply.py
- base.py
- parse_value
- ComponentValueRuleTests
- Arayuz
- BuildPlan
- KicadCli
- PencereTests
- ZoneReadTests
- schematic.py
- Evaluation
- sch_apply.py
- buck.rules.yaml on ayari
- .f
- lexicon.py
- ml/collect_design.py: tasarim seviyesi veri
- circuit.py
- harness.py
- apply_move
- DiscreteBuckTests
- OverlapTests
- test_ml.py
- _boxes_overlap
- komut.py
- compare_additive
- auto: uretim yerlestiricisi
- metrics.py
- SchSymbol
- WorkerTests
- RidgeModel
- generate.py
- canli.py
- Yuksek hizli ve hassas sinyal arayuzleri (Bolum 3)
- Connectivity
- Bagimsiz uygulama: KiCad'in Python'una yaslanmak
- decoupling_count: mesafe degil ADET
- KiCad'in kendi araclari son hakemdir
- test_collect_design.py
- CopperAreaRuleTests
- Sessiz hata sinifi: yazilmis ama baglanmamis kod
- KutuphaneTests
- Yorum
- arayuz.py
- ipc.py
- anneal.py
- ConnectivityDiff
- choose_paper
- uygula
- Model
- test_circuit.py
- read_board
- SymLibTests
- InProcessBridgeTests
- Beads skill (bd ile kalici gorev takibi)
- bench.rules.yaml - sentetik tezgah kural seti
- Yol haritasi: agirlikli skorlama
- app.py
- test_komut.py
- Netlist degismezligi kalkani (sch_verify)
- generate.py: plandan gercek KiCad projesine
- Oznitelik semasi v3 (75 oznitelik)
- ValueRange
- find_buck_converters
- plan_nets
- TermTableTests
- netlistte-gorunmeyeni-netlistte-arama.md
- Agirliklar kanit gucune gore bantlanir
- GBTModel
- graphify-bilgilendir.py
- collect_design.py
- test_generate.py
- ThreePartTests
- learned - ogrenilmis hamle siralayicisi
- Lineer regulator, motor surucu, koruma, sensor, HV (Bolum 4)
- LauncherTests
- IpcApplyError
- default_rules.yaml - pcbqa varsayilan kurallari
- fb_divider_max_bottom_ohms
- parse_with_stats
- load_config
- Kicad-5be: Eeschema 10.0.4 canli sematik yazmayi uygulamiyor
- deger_coz
- test_lexicon.py
- RegressionGuardTests
- graphify-etiketle.py
- ST AN2586
- normalize_pin_name
- test_app.py
- keep_apart - kaynaklarin 'uzaklastir' dedigi bosluk
- ipc_apply: calisan KiCad'e yazma hatti
- CorpusCalibrationTests
- Intent
- graphify-kurulumu-ve-hafiza-akisi.md
- read_schematic
- .probe
- allocate_units
- bundle.py
- BuiltLexiconTests
- Pad bakir sekli tam modelleme (copper_shape)
- ConnectError
- GlossTests
- load_design
- ArayuzLauncherTests
- .evaluate
- next_references
- post-commit
- graphify-durum.py
- Creepage - IEC 60664-1 / IEC 62368-1
- thermal kurali - esik yerine hesap
- _satir
- connectivity_of
- calisma-anlasmasi-graphify-entegre.md
- post-checkout
- RealBoardDetectionTests
- runtime_twin
- decoupling_count kurali - mesafe degil adet
- post-merge
- pre-commit
- pre-push
- prepare-commit-msg
- Olculemeyenler - eksik veri sinifi
- Kicad-5or: Karar katmani propose.py + connect.py
- Kapsam uyarisi - clearance creepage degildir
- hs-ethernet-cift-eslestirme kurali (Microchip DS00002054A)
- hs-i2c-pullup kurali (NXP UM10204)
- hs-usb-cift-eslestirme kurali
- hs-usb-net-uzunlugu kurali
- cikis-kondansatoru (22 uF, dusuk ESR)
- Bozuk s-expression dayanikliligi
- Sematik pin konumu donusumu - deneysel dogrulama
- Genis hamle repertuari varsayilan kapali
- Pad
- place_point
- CurveTests
- DagarcikTests
- RedTests
- .refresh
- RequiredAreaTests
- HotLoopTests
- ExpectedJoinShieldTests
- ConnectionParsingTests
- Path
- BoardWriteTests
- canli-pcb-arayuzu-ve-dogrulama.md
- sentetik-veri-isaretlenmeli.md
- canli-sematik-nightly-dogrulandi.md
- decoupling_counts
- GercekKartTests
- ModelRanker
- YorumlayiciTests
- Dataset
- ._overlap_state
- .__init__
- ._finding_block
- Eylem
- geom.py
- thermal.py
- AddPlan
- ParseTests

## God Nodes (most connected - your core abstractions)
1. `PlacementContext` - 99 edges
2. `read_schematic()` - 80 edges
3. `load_design()` - 78 edges
4. `Schematic` - 78 edges
5. `Design` - 68 edges
6. `load_rules()` - 65 edges
7. `add_symbols()` - 63 edges
8. `anla()` - 57 edges
9. `read_board()` - 57 edges
10. `children()` - 53 edges

## Surprising Connections (you probably didn't know these)
- `CLAUDE.md proje talimatlari` --semantically_similar_to--> `AGENTS.md ajan talimatlari`  [INFERRED] [semantically similar]
  CLAUDE.md → AGENTS.md
- `Benzetimli tavlama yontemi (anneal)` --conceptually_related_to--> `Vekil maliyet uydurma - gercek olcumu optimize et`  [AMBIGUOUS]
  .claude/agents/placer-anneal.md → pcbqa/pcbqa/placement/AGENT_BRIEF.md
- `KiCad Local History dizini` --conceptually_related_to--> `Atomik yazma ve acik-proje korumasi`  [AMBIGUOUS]
  KicadOtomasyon1/.history/README.txt → pcbqa/README.md
- `placer-cluster: kumeleme tabanli hiyerarsik yerlestirme ajani` --conceptually_related_to--> `Kicad-47f: learned hala auto'yu gecmiyor`  [INFERRED]
  .claude/agents/placer-cluster.md → pcbqa/docs/hafiza/beads-kapali-kayitlar.md
- `Serena kaldirildi, graphify eklendi` --references--> `CLAUDE.md proje talimatlari`  [EXTRACTED]
  pcbqa/docs/hafiza/serena-kaldirildi-graphify-eklendi.md → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Agirlikli skorlama faz zinciri (1a -> 1b -> 1c -> 1d)** — pcbqa_docs_yol_haritasi_skorlama_faz_1a_agirlik, pcbqa_docs_yol_haritasi_skorlama_faz_1b_orantili_ceza, pcbqa_docs_yol_haritasi_skorlama_kanit_sinifi_tablosu, pcbqa_docs_yol_haritasi_skorlama_faz_1d_korpus_kalibrasyonu, pcbqa_docs_yol_haritasi_skorlama_mevcut_skor_formulu [EXTRACTED 1.00]
- **Evre 3 uretken tasarim zinciri: niyet -> surucu -> varyant -> veri -> ML kapisi** — pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_o2c_niyet_semasi, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_ab6_evre3a_surucusu, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_raz_varyant_dongusu, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_8ow_tasarim_veri_toplama, pcbqa_docs_hafiza_beads_acik_kayitlar_kicad_a27_tohum_ortalama [EXTRACTED 1.00]
- **Kaynak -> kanit sinifi -> agirlik -> olcekleme zinciri** — pcbqa_docs_tasarim_kurallari_readme_sayisal_kriter_yoklugu, pcbqa_docs_tasarim_kurallari_readme_agirlik_kanit_bandi, pcbqa_docs_tasarim_kurallari_readme_olcekleme_formul_kurali, pcbqa_readme_kural_agirligi, pcbqa_readme_orantili_ceza [EXTRACTED 1.00]
- **Kaynakli esik ve agirlik sistemi: kanit gucu -> weight -> orantili ceza -> korpus kalibrasyonu** — pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_os1_agirlik_mekanizmasi, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_zoi_orantili_ceza, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_0nb_kanit_gucu_agirlik, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_f0b_korpus_kalibrasyonu, pcbqa_pcbqa_presets_yuksek_hiz_rules_hs_kristal_regulatorden_uzak [EXTRACTED 1.00]
- **Monotonluk garantisi: hicbir katman karti kotulestiremez** — pcbqa_handoff_gerileme_korumasi, pcbqa_handoff_bulgu_gudumlu_cila, pcbqa_handoff_model_karar_vermez_sira_onerir, pcbqa_handoff_metropolis_tavlama, pcbqa_handoff_auto_yerlestirici [EXTRACTED 1.00]
- **Niyet -> sablon -> blok bagimliligi (provides/requires) zinciri** — pcbqa_samples_niyetler_f103_harici_guc_swd_niyet, pcbqa_samples_niyetler_guc_modulu_niyet, pcbqa_pcbqa_templates_mcu_stm32f103c8_blok, pcbqa_pcbqa_templates_ldo_ams1117_3v3_blok, pcbqa_pcbqa_templates_mcu_stm32f103c8_interfaces [EXTRACTED 1.00]
- **Sessiz hata ailesi: yazilmis ama etkisiz kod** — pcbqa_handoff_sessiz_hata_sinifi, pcbqa_handoff_pinfunction_sessiz_hata, pcbqa_handoff_bayat_model_yolu, pcbqa_handoff_kicad5_module_korlugu, pcbqa_handoff_sayisal_iz_netleri, pcbqa_handoff_decoupling_count [EXTRACTED 1.00]
- **Sessiz hata sinifi: kural susar, skor yanlis yuksek cikar** — pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_76v_pin_function, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_eb9_kicad5_korlugu, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_vf0_sayisal_iz_netleri, pcbqa_docs_hafiza_beads_kapali_kayitlar_kicad_9ve_decoupling_adedi [EXTRACTED 1.00]
- **Uretken tasarim zinciri: niyetten olculmus karta** — pcbqa_handoff_intent_niyet_semasi, pcbqa_handoff_generate_surucusu, pcbqa_handoff_pcb_sync, pcbqa_handoff_auto_yerlestirici, pcbqa_handoff_explore_varyant_arama, pcbqa_handoff_agirlikli_skor [EXTRACTED 1.00]
- **Yerlestirme yarismasi: donmus arayuz, gercek hakem, alt sinirlar, sinav dokunulmazligi** — pcbqa_pcbqa_placement_agent_brief_placer_arayuzu, pcbqa_pcbqa_placement_agent_brief_vekil_maliyet_dersi, pcbqa_pcbqa_placement_agent_brief_alt_sinir_referanslari, pcbqa_pcbqa_placement_agent_brief_sinav_degistirmek_hile, _claude_agents_placer_anneal_benzetimli_tavlama [EXTRACTED 1.00]
- **Canli mod yigini: baglanti yollari, kurulum izni ve olculmus sematik sinirlamasi** — pcbqa_docs_hafiza_kicad_baglanti_yollari_uc_baglanti_yolu, pcbqa_docs_hafiza_canli_mod_ve_sematik_api_kurulum_kurallari, pcbqa_docs_hafiza_sematik_canli_yazma_mumkun_degil, pcbqa_kurulum_iki_calisma_modu, pcbqa_kurulum_acik_proje_korumasi [INFERRED 0.85]
- **Niyetten karta uretim akisi (niyet -> sablon -> komut)** — pcbqa_samples_niyetler_f103_usb_swd, pcbqa_pcbqa_templates_usb_micro_b, pcbqa_pcbqa_templates_swd_header, pcbqa_kurulum_komut_seti, pcbqa_kurulum_bilinen_sinirlar [INFERRED 0.85]

## Communities (202 total, 30 thin omitted)

### Community 0 - "Design"
Cohesion: 0.05
Nodes (69): Design, PinRef, Birlestirilmis tasarim: sematik + PCB., Netlist'teki her pini, PCB'deki pad konumuyla eslestirir., Sematikte var, PCB'de yok., PCB'de var, sematikte yok., Yari-cevre tel uzunlugu (Half-Perimeter Wire Length). Netin tum pinlerini…, Fiziksel konumu cozulmus bir pin. (+61 more)

### Community 1 - "Kaynak kalitesi uyarisi: sayisal kriter veren tek sistematik kaynak"
Cohesion: 0.05
Nodes (72): .beads/config.yaml yapilandirmasi, placer-cluster: kumeleme tabanli hiyerarsik yerlestirme ajani, AGENTS.md ajan talimatlari, Beads sync mimarisi (Dolt + refs/dolt/data), Karar kayitlari ilkesi (Beads decision records), Kod ve yorum yazim ilkeleri, pcbqa katmanli mimarisi, CLAUDE.md proje talimatlari (+64 more)

### Community 3 - "kurulum.py"
Cohesion: 0.05
Nodes (40): apply(), build_parser(), config_files(), ConfigFile, describe(), install_live_deps(), kicad_python(), live_deps() (+32 more)

### Community 4 - "minyaml.py"
Cohesion: 0.05
Nodes (41): _fail(), _lines(), MiniYamlError, _parse_block(), parse_flow(), _parse_list(), _parse_map(), parse_scalar() (+33 more)

### Community 5 - "test_ipc_apply.py"
Cohesion: 0.06
Nodes (15): Candidate, Karta yazilacak adayi secer. Gerileme koruyucusu (Asama 3): karti mevcut…, select_winner(), LiveBoard, LiveTests, Canli onizlemenin baska/eski bir karta uygulanmasini engelleyen sinirlar., FakeAngle, FakeBoard (+7 more)

### Community 6 - "anla"
Cohesion: 0.07
Nodes (19): anla(), Dogal dil cumlesini eylem listesine cevirir. KUTUPHANEYE DOKUNMAZ. Cozumleme…, AnlaTests, BaglamaTests, on" bir dolgu kelimesi sayilirsa Turkce 10 kaybolur., Turkce ondalik ayraci virguldur; "4,7k" bolunurse deger kaybolur., kapasitorleri" taninir; "zimbirti" TANINMAZ ve engel olur., Baglama EKLEME ile ayni cumlede yapilir. Buradaki tehlike ekleme… (+11 more)

### Community 7 - "elektrik.py"
Cohesion: 0.07
Nodes (35): ag_metni(), _akim(), bagli_mi(), build_parser(), csv_yaz(), ElektrikError, _gerilim(), main() (+27 more)

### Community 8 - "add_symbols"
Cohesion: 0.06
Nodes (21): add_symbols(), RuntimeError, Kutuphaneden sembol(ler) ekler. Varsayilan DRY-RUN'dir. `verify` acikken…, SchAddError, AddSymbolsTests, EndToEndTests, skipUnless, Izgara disi konum sessizce kabul edilmez: oturtulur ve soylenir. (+13 more)

### Community 9 - ".routed"
Cohesion: 0.07
Nodes (23): Boards, ClearanceVoltageRuleTests, KeepApartRuleTests, PadShapeTests, Bakir kurallari: iz genisligi, via akimi, gerilim acikligi, keep_apart. Bu…, 0.6 mm via TI tablosunda 1.1 A'de sabitlenir; 5 A tasiyamaz., Katman degistirmeyen net icin via kurali anlamsiz - sessiz kalmali., EN ONEMLI TEST: saglam kart, 5 V - hicbir bulgu olmamali. Bu test gelistirme… (+15 more)

### Community 10 - "Repertoire"
Cohesion: 0.07
Nodes (30): cluster_moves(), _extent(), Compound, Placement, Random, GENIS HAMLE REPERTUARI - takas, kume tasima, bolge sicramasi (Asama 6, Faz A).…, Bilesenin bagli oldugu bilesenlerin agirlik merkezi., Iki bilesenin yer degistirmesi. Ortaklar, `ref`in bagli oldugu bilesenlerin… (+22 more)

### Community 11 - "symlib.py"
Cohesion: 0.07
Nodes (54): _deep_copy(), environment(), expand(), _field(), _flatten(), footprint_exists(), footprint_libraries(), footprint_path() (+46 more)

### Community 12 - "test_intent.py"
Cohesion: 0.14
Nodes (16): _check_keys(), IntentError, RuntimeError, Bilinmeyen anahtar = buyuk olasilikla yazim hatasi; sessizce yutulmaz., Tek bir sablon dosyasini okur ve bicimini dogrular., Niyet beyanini okur ve bicimini dogrular., Niyet ya da sablon dosyasi okunamadi / bicimi bozuk. Bicim hatasi (yanlis…, read_intent() (+8 more)

### Community 13 - "load_rules"
Cohesion: 0.06
Nodes (18): load_rules(), Path, YAML kural dosyasini okur ve dogrular. `include:` ile baska kural dosyalari…, IncludeTests, PresetLoadTests, Path, On ayar kutuphanesi ve `include` mekanizmasi. En onemli olcut: `uretim` on…, Sessizce ezilen bir kural, fark edilmeyen bir bosluktur. (+10 more)

### Community 14 - "PricingTests"
Cohesion: 0.25
Nodes (4): PricingTests, Istenen degismez: buyuk deger daha pahali. Olculdu: ilk iki surumde "gercekci…, Deger bilinmiyorsa fiyat UYDURULMAZ., Ayni girdi ayni katalog - iki kosuda fiyat degisirse guven biter.

### Community 15 - "_Model"
Cohesion: 0.08
Nodes (24): _diff_partner(), ForcePlacer, _Group, _is_ground(), _Item, _Model, Placement, Random (+16 more)

### Community 16 - "SyntheticDiscreteBuckTests"
Cohesion: 0.15
Nodes (10): hot_loop_area_mm2(), Sicak dongu alani (mm2) - olculemiyorsa None., Ayrik dongu ALTIGENI - analitik dogrulama. Neden sentetik kart: korpusta ayrik…, Sira YANLIS olsaydi shoelace baska (kucuk) bir alan verirdi. Ayni alti noktayi…, Bootstrap diyodu SW'dedir ama GND'de pad'i YOKTUR., Ayrik denetleyicilerde faz pini cogu zaman "SW" YAZMAZ. Intersil/Renesas…, RC snubber SW'dedir ama anahtar degildir - rol almamali., Yuksek akimda alt kol paralel FET olabilir. Q3 bilerek uzaga konuldu. Keyfi… (+2 more)

### Community 17 - "intent.py"
Cohesion: 0.11
Nodes (18): build_parser(), load_templates(), main(), plan_from_file(), ArgumentParser, Path, Niyet beyani -> bilesen/baglanti plani (Evre 3a, uretken tasarim). Kullanici…, Acikca beyan edilenler + arayuz adlari. Bir arayuz tanimlamak onu saglamak… (+10 more)

### Community 18 - "penalty_of"
Cohesion: 0.16
Nodes (9): penalty_of(), 0-100 arasi kalite skoru. Ceza, bilesen sayisina bolunerek normalize edilir;…, Bir bulgunun skora yazacagi ceza. Kural kendi `weight` degerini verdiyse o…, PenaltyOfTests, Kural bazli agirlik (Faz 1a). Skor eskiden yalnizca severity sayiyordu: her…, `penalty_of` saf bir fonksiyon - once onu tek basina sinayalim., Agirlik ne olursa olsun `info` sifirdir. Somut nedeni: `max_findings` sinirina…, Agirlik severity sirasini bilerek bozabilir - amac bu. (+1 more)

### Community 19 - "PlacementContext"
Cohesion: 0.11
Nodes (43): Component, Karta yerlestirilmis bir bilesen (footprint)., Bileseni yeni konuma tasir; pad ve courtyard mutlak konumlarini yeniden…, Courtyard'in sinir kutusu (hizli on eleme ve yogunluk icin)., Kapladigi alan. Courtyard yoksa pad'lerin sinir kutusuna duser., PlacementContext, Yerlestiriciye verilen her sey. Salt-okunur kabul edin. `design` uzerinden…, Tasinabilir bilesenlerin referanslari. (+35 more)

### Community 20 - "MoveFeaturizer"
Cohesion: 0.15
Nodes (9): MoveFeaturizer, Bir tasarim icin oznitelik cikarici. Kullanim: fz = MoveFeaturizer(design,…, Verilen bilesenlerin dokundugu netler (tekrarsiz, kararli sirada)., Ayni nete bagli bilesenlere en kisa ve ortalama mesafe. `proximity`…, Bilesenin merkezinden en uzak pinine mesafe. Merkez tabanli ozniteliklerin ne…, Tek bilesenli hamle icin oznitelik vektoru (1 elemanli birlesik)., Birlesik hamle icin oznitelik vektoru. `FEATURE_NAMES` ile ayni sirada. Ilk…, Birden fazla BIRLESIK hamle icin vektorler. (+1 more)

### Community 21 - "connect.py"
Cohesion: 0.20
Nodes (16): apply_to_file(), build_nodes(), build_parser(), ConnectPlan, edit_tree(), main(), parse_net(), plan_from_proposals() (+8 more)

### Community 22 - "pcb.py"
Cohesion: 0.08
Nodes (44): _chain(), _edges_of(), _local_points(), _node_net(), _pad_copper_layers(), _pad_net(), _points_of(), `.kicad_pcb` okuyucu: bilesenlerin ve pad'lerin FIZIKSEL konumu. Bu katman… (+36 more)

### Community 23 - "__main__.py"
Cohesion: 0.06
Nodes (45): describe_violation(), (severity, kod, aciklama) uclusu dondurur., analyze(), build_parser(), default_rules_path(), discover_project(), kicad_findings(), main() (+37 more)

### Community 24 - "ipc2221.py"
Cohesion: 0.07
Nodes (23): clearance_mm(), current_capacity_a(), decoupling_max_distance_mm(), FabClass, IPC-2221B hesaplari: akima gore iz genisligi, gerilime gore aciklik. Neden…, IPC-2221B Tablo 6-1: bu gerilimde minimum iletken acikligi (mm). voltage_v: DC…, Bir uretim sinifinin minimumlari (mm)., Bir via'nin tasiyabilecegi akim (A), delik capina gore. Tablo disindaki… (+15 more)

### Community 25 - "sch_add.py"
Cohesion: 0.09
Nodes (41): build_schematic_tree(), Bos sematigi doldurur: (agac, engeller, notlar). Dosyaya YAZMAZ. Semboller…, build_parser(), build_symbol_node(), _copy(), edit_tree(), free_slots(), _instances_for() (+33 more)

### Community 26 - "sch_move.py"
Cohesion: 0.10
Nodes (28): Placement, Footprint icindeki metin ve pad acilarini `delta` kadar dondurur. KiCad bir…, Yerlestirmeyi kaynak dosyaya uygulayip yeni bir .kicad_pcb yazar. KiCad'de…, _turn_parts(), write_board(), build_parser(), main(), MoveResult (+20 more)

### Community 27 - "canli_sematik.py"
Cohesion: 0.38
Nodes (9): configuration(), environment(), main(), open_copy(), Canli sematik icin ayri, surumu eslesen KiCad/Python ortami., Deneysel dosya bicimini kullanicinin asil projesinden ayirir., request(), Calisan KiCad surecleri ("ad (pid)"). Bulunamazsa bos liste. (+1 more)

### Community 28 - "test_pcb_sync.py"
Cohesion: 0.12
Nodes (17): Schematic, Sembolun KiCad yolu: `/<sayfa-uuid>/<sembol-uuid>`. Kart bileseni sematik…, Sematikte olup kartta olmayan bilesenleri karta ekler. Varsayilan DRY-RUN.…, symbol_path(), sync(), SyncResult, KicadAcceptsTheBoardTests, MultiUnitSyncTests (+9 more)

### Community 29 - "test_decoupling_count.py"
Cohesion: 0.09
Nodes (18): bulk(), BulkFloorTests, ceramic(), ConfigTests, GroundExclusionTests, skipUnless, `decoupling_count` kurali (TI SPRABV2 6). Bu kural MESAFE degil ADET olcuyor -…, Cozulemeyen deger HER IKI kovaya sayilir - yanlilik yon degistirmesin.… (+10 more)

### Community 30 - "mpn.py"
Cohesion: 0.11
Nodes (27): apply_assignment(), Assignment, AssignPlan, _base_price(), build_parser(), candidates(), main(), parse_value() (+19 more)

### Community 31 - "cluster.py"
Cohesion: 0.11
Nodes (18): _cap_value(), _Engine, _Node, _Part, Placement, Random, Kumeleme tabanli hiyerarsik yerlestirme. Fikir: bir kartin gercek yapisi…, Kume agacinin bir dugumu. (+10 more)

### Community 32 - "expand_intent"
Cohesion: 0.24
Nodes (7): expand_intent(), IntentBlock, Niyeti plana acar. Kutuphaneye DOKUNMAZ (onu `resolve_plan` yapar)., ExpandTests, intent_of(), Paketle gelen sablonlar - kutuphane gerektirmeyen kisim., RealTemplatesExpandTests

### Community 33 - "sch_wire.py"
Cohesion: 0.12
Nodes (30): build_connections(), Baglanti dugumleri (tel + etiket + junction) uretir. Iki yol var ve ikisi de…, blocked_points(), candidates(), existing_pin_point(), junction_node(), junctions_needed(), label_node() (+22 more)

### Community 34 - "synth.py"
Cohesion: 0.14
Nodes (30): _apply(), BoardSpec, build_bench(), crystal(), _fmt(), header(), main(), PadSpec (+22 more)

### Community 35 - "_variant"
Cohesion: 0.39
Nodes (3): Kaliteden odun verilmez: buyuk ama temiz kart, kucuk ama kusurluyu yener., SelectionTests, _variant()

### Community 36 - "children"
Cohesion: 0.10
Nodes (31): board_paths(), board_refs(), build_footprint_node(), build_parser(), _copy(), _drop(), free_positions(), main() (+23 more)

### Community 37 - "refine.py"
Cohesion: 0.09
Nodes (28): Move, _as_compounds(), _centroid(), _Convergence, _extent_of(), _finding_moves(), _inside(), _limit_of() (+20 more)

### Community 38 - "bench_context"
Cohesion: 0.15
Nodes (9): AdversarialRankerTests, bench_context(), FeatureCorrectnessTests, named(), Takasta A'nin yeni HPWL'i B ESKI yerindeymis gibi hesaplanamaz. Hesaplanirsa…, v3'un cekirdegi: acik bir `proximity` bulgusu hamleden sonra BIREBIR yeniden…, Yerel yeniden hesap ile kural motorunun kendi olcumu ortusmeli., Model tamamen yanilsa bile sistem gerileyemez. ML'i uretim hattina sokmanin… (+1 more)

### Community 39 - "run"
Cohesion: 0.12
Nodes (10): skipUnless, Yazim hatasi kurali SESSIZCE etkisiz birakmamali. Bu projede ayni sinif hata…, Secici hicbir seye uymuyorsa sessizlik korunur - beyan denetlenmez., Bu projenin en onemli olcutu: saglam kartta sessizlik., Gercek SOT-223 regulator: TLV1117LV33, tab pin 2 -> +3V3., Yapilandirma hatasi SESSIZ gecmemeli - gorunmez etkisiz kural olurdu., RealBoardTests, RuleConfigTests (+2 more)

### Community 40 - "propose.py"
Cohesion: 0.14
Nodes (24): _aligned(), alignment_pairs(), _clear_between(), _distance(), free_pins(), occupied_points(), PinRef, power_drops() (+16 more)

### Community 41 - "Schematic"
Cohesion: 0.18
Nodes (12): Sematigin yapisal saglamligini kontrol eder. `schematic` bir…, run_schematic_checks(), Bir dosyadaki alt sayfa kutusu., Bir sematik hiyerarsisinin tamami., Tel uclarinin sayfa bazinda sayim tablosu., Schematic, SchSheetRef, Asama 4a/4b: sematik okuyucu ve netlist degismezligi kalkani. (+4 more)

### Community 42 - "sch_place.py"
Cohesion: 0.05
Nodes (33): changed_only(), _context_for(), improve(), improve_file(), _key(), Path, Schematic, SchPlacement (+25 more)

### Community 43 - "swig_apply.py"
Cohesion: 0.13
Nodes (23): _angle_delta(), apply_placement(), board_name_of(), build_parser(), index_footprints(), load_pcbnew(), main(), open_board() (+15 more)

### Community 44 - "base.py"
Cohesion: 0.07
Nodes (29): Placement, AUTO - uretim yerlestiricisi (Asama 3'un ciktisi). Yarisan dort motorun tek tek…, Placer, DONMUS ARAYUZ - yerlestirme motorlarinin uymak zorunda oldugu sozlesme. Bu…, Bir yerlestirme stratejisi., Identity, Placement, RandomShuffle (+21 more)

### Community 45 - "parse_value"
Cohesion: 0.16
Nodes (9): parse_value(), Bir bilesen degerini SI taban birimine cevirir (ohm / farad / henry). Birimi…, ParseValueTests, Deger alanina serbest metin yazmak yaygin; hata saymak gurultu uretir., KiCad deger alanlari duzensizdir; ayristirici bunu yutmali., IEC 60062: carpan harfi ONDALIK NOKTANIN yerine gecer., Deger alanina gerilim/tolerans/paket yazmak yaygin., M' mega, 'm' mili. Karistirmak 10^9 kat hata demek. (+1 more)

### Community 46 - "ComponentValueRuleTests"
Cohesion: 0.13
Nodes (10): ComponentValueRuleTests, `component_value` kural tipi - hesabi devreye baglar. bench_bad kartinda gercek…, Filtre olmadan USB seri dirençleri de yakalanir - `on_net` bunu ayirir., 4k7, 200 pF fast-mode icin fazla buyuk (max ~1770 ohm)., Ayni 4k7, 50 pF'lik hafif bir bus'ta sorunsuz., Sinirlar "1k"/"10k" gibi yazilabilmeli; farad'i ondalikla yazmak eziyet., Deger alanina serbest metin yazmak yaygin - hata degil, sessiz gecis., 400 pF fast-mode'da duz direncle COZUM YOK - kural bunu soylemeli. Sessizce… (+2 more)

### Community 47 - "Arayuz"
Cohesion: 0.11
Nodes (3): Arayuz, Cumle ya da proje degisti - gosterilen plan artik gecerli degil., Sonuc

### Community 48 - "BuildPlan"
Cohesion: 0.17
Nodes (10): BuildPlan, PlannedComponent, Plandaki tek bir somut bilesen. Referans numarasi (C1, C2...) BURADA verilmez -…, Niyetin acilmis hali - yazilabilir, gosterilebilir, sorgulanabilir., Ag adi -> [(bilesen etiketi, pin anahtari)]. Cozumlemeden once pin anahtarlari,…, Pin anahtarlarini kurulu KiCad kutuphanesine karsi cozer. "#3" pin numarasidir;…, resolve_plan(), Sablonlar gercek kutuphaneyle SINANMADAN yasayamaz. Sessiz hata dersinin sablon… (+2 more)

### Community 49 - "KicadCli"
Cohesion: 0.24
Nodes (9): CliResult, KicadCli, load_violations(), Path, KiCad'in kendi elektriksel kural kontrolu (JSON rapor)., KiCad'in kendi tasarim kurali kontrolu (JSON rapor)., ERC/DRC JSON raporunu duz bir ihlal listesine cevirir. Iki dosyanin yapisi…, kicad-cli cagrilarini saran ince katman. (+1 more)

### Community 50 - "PencereTests"
Cohesion: 0.12
Nodes (6): PencereTests, skipUnless, Arka plan isi bitene kadar olay dongusunu cevir., Kilit sadece dugmenin gorunumu degil: `_uygula` kendisi de bakar., Onay diyalogu iptal edilirse hicbir sey yazilmamali., Her test icin TEK bir Tk yorumlayicisi, ayri bir Toplevel penceresi. Test…

### Community 51 - "ZoneReadTests"
Cohesion: 0.09
Nodes (10): Bir zone'un TEK KATMANDAKI doldurulmus bakiri., Bakir dokum alani (poligon). Iki poligon vardir ve karistirilmamalidir: *…, Bakir alani (mm2). Doldurulmus poligonlarda delikler, poligonun kendisine giren…, Tek bir katmandaki bakir alani., Zone, ZoneFill, KiCad'de nete BAGLI OLMAYAN dokum olabilir; ad bos string gelir., Sinir poligonu kullanicinin cizdigi; GERCEK bakir doldurulmus olandir. Ikisi… (+2 more)

### Community 52 - "schematic.py"
Cohesion: 0.17
Nodes (19): _atom(), _flag(), _lib_extent(), _lib_pins(), _num(), _properties(), Sematik okuyucu (Asama 4a) - .kicad_sch dosyalarini veri modeline cevirir.…, Junction / no_connect gibi tek noktali ogeler. (+11 more)

### Community 53 - "Evaluation"
Cohesion: 0.10
Nodes (18): Evaluation, Hakemin bir yerlestirme icin verdigi gercek olcum. Yerlestiriciler vekil…, Siralamada kullanilan anahtar; buyuk olan daha iyidir., Sozluksel siralamayi TEK SAYIYA indirir: pozitif = bu daha iyi. `key` sozluksel…, keep_best(), Metropolis, polish(), TAVLAMA BENZERI KABUL - yerel en iyiden kacmak icin. `polish` bugun yalnizca… (+10 more)

### Community 54 - "sch_apply.py"
Cohesion: 0.10
Nodes (25): apply_placement(), ApplyPlan, ApplyResult, build_parser(), _drag_map(), _edit_sheet(), main(), optimize_and_apply() (+17 more)

### Community 55 - "buck.rules.yaml on ayari"
Cohesion: 0.10
Nodes (24): placer-force agent tanimi, Cok-agentli yerlestirici sinavi kurallari, Creepage / clearance ve HV slot genisligi, Guc izi 0.381 mm/A ve 1 via / 200 mA, IPC-7351B courtyard excess ve govdeler arasi bosluk, Beyan eksikligi politikasi: acik kural susar, kapali kural bagirir, Faz 1b - Orantili ceza (ihlal buyuklugune gore), Faz 1d - Korpus kalibrasyonu (+16 more)

### Community 56 - ".f"
Cohesion: 0.18
Nodes (10): overshoot_factor(), Ihlalin BUYUKLUGUNE gore ceza carpani (Faz 1b). asim = |measured - limit| /…, OvershootFactorTests, Ihlalin buyuklugune gore ceza carpani (Faz 1b)., Net uzunlugu gibi: measured > limit., Iz genisligi gibi: measured < limit. Ayni oran, ayni carpan., Tavan olmasa via_current'ta tek bulgu butun skoru yutardi., Cakisan bakir (negatif aciklik), dar aciklikitan daha kotudur. (+2 more)

### Community 57 - "lexicon.py"
Cohesion: 0.14
Nodes (21): build(), build_parser(), Entry, gloss(), harvest(), kapsam(), load(), lookup() (+13 more)

### Community 58 - "ml/collect_design.py: tasarim seviyesi veri"
Cohesion: 0.13
Nodes (20): ml/collect_design.py: tasarim seviyesi veri, Etiket parti medyanina gore HPWL uzerinden, Etiket secimi model seciminden onemli, explore.py: once boyut sonra tohum, Her sira bilgisiz degildir - modeli her yere sokmayin, Kart/grup bazli capraz dogrulama bolmesi, Kart siniri tahmin degil olcum, learned hala auto'yu gecmiyor (+12 more)

### Community 59 - "circuit.py"
Cohesion: 0.16
Nodes (11): i2c_needs_current_source(), i2c_pullup_max_ohms(), i2c_pullup_min_ohms(), i2c_pullup_range(), Devre dogrulugu hesaplari: bilesen DEGERI dogru mu? Mevcut kural tipleri…, Yukselme suresi butcesinin izin verdigi EN BUYUK pull-up direnci., Surucunun sifira cekebilmesi icin gereken EN KUCUK pull-up direnci., 200 pF ustunde duz direnc yetmez (UM10204 7.1). UM10204: 200-400 pF arasi Fast-… (+3 more)

### Community 60 - "harness.py"
Cohesion: 0.07
Nodes (43): discover_boards(), locked_refs(), main(), Path, HAKEM - bir yerlestiriciyi calistirir, oncesi/sonrasi puanlar. python -m…, Konum olarak sabit kabul edilen bilesenler., Bir klasordeki tum .kicad_pcb dosyalarini bulur (yedekler haric)., Yerlestiricileri bir kart kumesinde kosturur. Asama 3'un asil kabul olcutu… (+35 more)

### Community 61 - "apply_move"
Cohesion: 0.08
Nodes (22): apply_move(), MovePlan, plan_move(), Path, RuntimeError, Schematic, Tasimayi planlar; dosyaya dokunmaz. `snap` verilirse sembol izgaraya oturtulur…, Projeyi gecici bir dizine kopyalar; kok sematigin yeni yolunu dondurur. Kalkan… (+14 more)

### Community 62 - "DiscreteBuckTests"
Cohesion: 0.23
Nodes (5): DiscreteBuckTests, AYRIK (harici FET'li) tasarim: olcmek yerine SUSMAK. Entegre regulatorde giris…, Ayni karta SW dugumunde bir FET ekler ve tasarimi yeniden kurar., Susmak YETMEZ - gorunmez bir bosluk yine sessiz hatadir., `info` cezasi sifirdir; kapsam disiligi kartin skorunu dusurmemeli.

### Community 63 - "OverlapTests"
Cohesion: 0.20
Nodes (4): OverlapTests, Icbukey boslukta duran kucuk bir sekil cakismaz., Kenarlar kesismese de icerme cakismadir., Bitisik duran iki courtyard cakismis sayilmaz (clearance_mm: 0.0).

### Community 64 - "test_ml.py"
Cohesion: 0.16
Nodes (7): label_of(), Iki degerlendirme arasindaki farki tek sayiya indirir (bkz. modul basi).…, Veri kumesi: JSONL depolama + KART BAZLI bolme. Alan bagimsizdir - burada ne…, LabelTests, MetricTests, Asama 5 garantileri: oznitelik dogrulugu, model cekirdegi, guvenli baglanti. En…, Taban cizgisi 0.5 vermeli; vermiyorsa metrik sisiyordur.

### Community 65 - "_boxes_overlap"
Cohesion: 0.50
Nodes (3): _boxes_overlap(), Iki sinir kutusu ust uste biniyor mu? Tam temas cakisma SAYILMAZ., 1.27 mm izgarasinda bitisik semboller cok yaygin; tam temas cakisma sayilirsa…

### Community 66 - "komut.py"
Cohesion: 0.08
Nodes (32): Pattern, Baglama, _baglama_ayir(), _baglantilari_dagit(), build_parser(), _dagarcik(), _hedef_olabilir(), _hedef_temizle() (+24 more)

### Community 67 - "compare_additive"
Cohesion: 0.35
Nodes (5): compare_additive(), EKLEME icin kalkan: mevcut devre aynen dursun, yalnizca yenisi eklensin.…, AdditiveShieldTests, Yeni sembol var olan bir tele degerse kalkan yakalamali., PinKey

### Community 68 - "auto: uretim yerlestiricisi"
Cohesion: 0.12
Nodes (18): Agirlikli skorlama (Evre 1), auto: uretim yerlestiricisi, Bulgu gudumlu cila (refine.polish), auto butce bolusumu (Faz G), Kaynak celiskileri gizlenmedi, parametreye cevrildi, clearance_voltage 6.2x hizlandirma, Degerlendirme maliyeti kartlar arasi ~8000x degisiyor, Uc noktali gerileme korumasi (+10 more)

### Community 69 - "metrics.py"
Cohesion: 0.16
Nodes (17): evals_to_first_gain(), evaluate(), mae(), pairwise_accuracy(), Any, r2(), _ranks(), Metrikler: regresyon dogrulugu VE - asil onemlisi - siralama kalitesi. Bir… (+9 more)

### Community 70 - "SchSymbol"
Cohesion: 0.09
Nodes (13): _on_grid(), Guc sembolu mu? (GND, VCC...), Gercek bir bilesen degil. KiCad sanal sembolleri `#` ile baslayan referans…, Hiyerarside benzersiz anahtar., Sanal semboller (#PWR, #FLG...) haric gercek bilesenler., Sayfa bazinda pin konumu -> (sembol, pin) listesi., Sayfa koordinatina cozulmus bir sembol pini., Sayfaya yerlestirilmis bir sembol ornegi. (+5 more)

### Community 71 - "WorkerTests"
Cohesion: 0.10
Nodes (4): FrontTests, Canli sematikte yanlis hedef, eski plan ve yari yazma korumalari., Schematic, WorkerTests

### Community 72 - "RidgeModel"
Cohesion: 0.11
Nodes (9): Any, Model, En buyuk mutlak katsayili oznitelikler. Standartlastirilmis uzayda oldugu icin…, Standartlastirilmis ridge regresyon., RidgeModel, MeanModel, Taban cizgisi: her zaman egitim ortalamasini soyler.…, ModelTests (+1 more)

### Community 73 - "generate.py"
Cohesion: 0.05
Nodes (63): build_parser(), candidate_sizes(), explore(), explore_from_intent(), main(), plan_variants(), ArgumentParser, Path (+55 more)

### Community 74 - "canli.py"
Cohesion: 0.35
Nodes (16): apply_plan(), board_identity(), check_target(), connection(), describe_connection(), fingerprint(), LivePlan, main() (+8 more)

### Community 75 - "Yuksek hizli ve hassas sinyal arayuzleri (Bolum 3)"
Cohesion: 0.15
Nodes (19): Kuvvet tabanli yerlestirme yontemi, Yuksek hizli ve hassas sinyal arayuzleri (Bolum 3), 20H kurali - CURUTULDU, Diferansiyel cift ayrimi: 5W kurali (3W degil), ADC altinda duzlem bosaltma vs kesintisiz GND celiskisi, 2.4 GHz anten keep-out ve chip anten mm degerleri, BGA decoupling yogunlugu (0.1 uF / 2 guc topu), 50 ohm hat genisligi: CPWG vs mikroserit karistirmasi (+11 more)

### Community 76 - "Connectivity"
Cohesion: 0.23
Nodes (8): NetCheck, Hakemin dogrulayacagi tek bir ag. Guc sembolleri (`#PWR`, `#FLG`) netlist'te…, Connectivity, Bir sematigin kanonik baglanti yapisi., ArbiterTests, BAGLA: var olan sembolleri tellemek. Bu komut sematige YAZIYOR, yani bir hatasi…, Hakem gercekten REDDEDEBILMELI - yoksa gecmesi bir sey kanitlamaz., Guc sembolu netlist'te dugum olarak GORUNMEZ; adindan anlariz. Olculdu:…

### Community 77 - "Bagimsiz uygulama: KiCad'in Python'una yaslanmak"
Cohesion: 0.14
Nodes (15): Bagimsiz uygulama: KiCad'in Python'una yaslanmak, baslat.py: yola degil bilinen klasore guvenmek, bundle --check: kopyalarin ayrismasi, confload: YAML kaynak, JSON calisma zamani kopyasi, PyYAML ile diferansiyel test, Katman ayrimi: cekirdek KiCad'i bilmez, Lisans zemini: ayri surec mimarisi, minyaml: bagimliliksiz YAML okuyucu (+7 more)

### Community 78 - "decoupling_count: mesafe degil ADET"
Cohesion: 0.14
Nodes (15): Bilincli iyimser yanlilik ve 'EN AZ' ifadesi, bulk_min_power_pins: kaynagin biriminin altina inilmedi, circuit.py: deger kurallari (IEC 60062 RKM), Birinci sinif kaynaklarin cogu mm cinsinden sayi vermez, decoupling_count: mesafe degil ADET, proximity exclusive: her partner bir hedefe, Minimum iz genisligi esigi 0.15 -> 0.10 mm, Korpus kalibrasyonu (1d) (+7 more)

### Community 79 - "KiCad'in kendi araclari son hakemdir"
Cohesion: 0.14
Nodes (15): Cok birimli parca kartta tek fiziksel paket, fp_rect courtyard'larin dusmesi, Gercek poligon kesisimi (disbukey kabuk + SAT), Icbukey courtyard: zincirleme + kenar kesisimi, KiCad DRC'si her seyi yakalamaz, KiCad'in kendi araclari son hakemdir, Mikron seviyesi degme: esik uydurulmadi, Pad acisinin cift sayilmasi (+7 more)

### Community 80 - "test_collect_design.py"
Cohesion: 0.09
Nodes (27): ExploreResult, Sozluksel siralama anahtari; BUYUK olan daha iyidir.…, Tek bir deneme: hangi kosullarla, ne cikti., Variant, GenerateResult, Uretimin sonucu - her adim ayri ayri gorunur., _clamp(), CollectError (+19 more)

### Community 81 - "CopperAreaRuleTests"
Cohesion: 0.21
Nodes (5): CopperAreaRuleTests, SW bakir alani <= 100 mm2 (ROHM 66AN015E) bu bicimde ifade edilir., Termal bakir alani (Richtek AN044) bu bicimde ifade edilir., Bakiri olmayan net sessiz gecilir - min_mm2 orada yanlis alarm olurdu., run()

### Community 82 - "Sessiz hata sinifi: yazilmis ama baglanmamis kod"
Cohesion: 0.16
Nodes (14): Buck-boost buck saniliyordu, Niyet semasi ve sablon kutuphanesi (intent.py), KiCad 5 kartlari sessizce bos okunuyordu, normalize_pin_name: pin adinda bicimleme, Pin ADI ile baglama, pinfunction hic okunmuyordu, ROHM kontrol listesi kendi icinde celisiyor, Her sablon gercek kutuphaneden gecirilir (+6 more)

### Community 83 - "KutuphaneTests"
Cohesion: 0.22
Nodes (5): KutuphaneTests, skipUnless, Tablodaki her kimlik GERCEK olmali - uydurma sembol adi yazilmaz., `uclar` uydurulmaz: baglanti tam bu numaralarla kurulur., Kutupluluk NOTU kullanicinin karti nasil baglayacagini belirler. KiCad diyot…

### Community 84 - "Yorum"
Cohesion: 0.17
Nodes (9): _aglari_coz(), _fiil_bul(), mevcut_aglar(), Schematic, Cumlenin anlasilan hali. Dosyaya DOKUNMAZ; once gosterilir., Cumlenin fiili. Bilinmeyen fiil sessizce "ekle" sayilmaz., Sematikte BUGUN duran ag adlari (etiketler + guc sembolleri). Netlist'ten degil…, Hedef ag adlarini sematikteki GERCEK yazimla esler. Neden gerekli: baglanti bir… (+1 more)

### Community 85 - "arayuz.py"
Cohesion: 0.15
Nodes (14): ayar_oku(), ayar_yaz(), build_parser(), main(), ArgumentParser, MASAUSTU ARAYUZU (tkinter) - islerin pencereden yurutulmesi. pcbqa arayuz Alti…, Zamanlayiciyi iptal eder. Pencereyi YOK ETMEZ., Bu (ya da verilen) Python tkinter'i getiriyor mu? (+6 more)

### Community 86 - "ipc.py"
Cohesion: 0.20
Nodes (16): _angle_delta(), apply_placement_to_board(), apply_placement_to_running_kicad(), _index_footprints(), IpcApplySummary, _orientation_degrees(), _pose_changed(), _position_mm() (+8 more)

### Community 87 - "anneal.py"
Cohesion: 0.23
Nodes (9): _accept(), _build_proximity_group(), Placement, Random, Benzetimli tavlama (simulated annealing) yerlestirici. Fikir:…, Benzetimli tavlama ile detayli yerlesim iyilestirmesi. Maliyet = agirlikli HPWL…, `proximity` kuralinin ayni netteki hedef/partner eslesmesini onceden cikarir…, SimulatedAnnealing (+1 more)

### Community 88 - "ConnectivityDiff"
Cohesion: 0.19
Nodes (9): compare(), ConnectivityDiff, Iki baglanti yapisini karsilastirir. Net adlari ve kodlari yok sayilir;…, Iki baglanti yapisi arasindaki fark., conn(), Test icin elle baglanti yapisi kurar., Kalkanin dogru degismezi kullandigini dogrular., Otomatik net adlari degisebilir; bolunme ayniysa devre aynidir. (+1 more)

### Community 89 - "choose_paper"
Cohesion: 0.27
Nodes (6): choose_paper(), pack_rows(), Sembolleri satir satir dizer: (merkezler, kullanilan yukseklik). Satir…, Isin sigdigi en kucuk standart kagit; (kagit, merkezler, not)., _snap(), LayoutTests

### Community 90 - "uygula"
Cohesion: 0.16
Nodes (9): Path, Eylemleri sirayla `sch_add.add_symbols`a verir. Kalkan, yedek, kilit kontrolu…, uygula(), Ikinci eylem, birincisinin YAZILMIS halini okumali - yoksa iki plan da ayni…, Isin olcusu sematikteki etiket degil, KiCad'in cikardigi NETLIST'tir: yeni…, Baglama, mevcut aglara pin EKLER; onlardan pin ALMAZ., vcc" diye yazan kullanici "VCC" agina baglanmis olmaz; yazim sematige bakilarak…, Netlist kalkani bunu YAKALAMAZ - yeni ag olusturmak gecerli bir islemdir. Uyari… (+1 more)

### Community 91 - "Model"
Cohesion: 0.15
Nodes (12): Asama 5 - makine ogrenimi altyapisi. Katmanlar bilerek ayri tutuldu; ust katman…, build(), _ensure_registry(), load(), Model, Any, Path, Model sozlesmesi + JSON kaydet/yukle + kayit defteri. Modeller **JSON** olarak… (+4 more)

### Community 92 - "test_circuit.py"
Cohesion: 0.22
Nodes (8): crystal_load_capacitor_f(), crystal_load_capacitor_range_f(), Kristalin CL'sini karsilamak icin gereken TEK kondansator degeri., Stray belirsizliginden (2-5 pF) dogan kabul edilebilir aralik. Stray BUYUDUKCE…, CrystalLoadTests, Devre dogrulugu hesaplari (`pcbqa/circuit.py`). Kural motoru simdiye kadar…, Microchip AN826: CL = C/2 + Cstray, stray 2-5 pF., Stray buyudukce gereken kondansator KUCULUR - aralik yonu bundan.

### Community 93 - "read_board"
Cohesion: 0.05
Nodes (29): BoardParseError, Path, RuntimeError, Kartin kokundeki net tablosu: numara -> ad. NEDEN GEREKLI: iz/via/arc dugumleri…, Kart dosyasi okunamadi. Sessizce bos kart dondurmekten YEGDIR: bos kart butun…, Bir .kicad_pcb dosyasini okur., read_board(), _read_net_table() (+21 more)

### Community 94 - "SymLibTests"
Cohesion: 0.17
Nodes (4): Dosya icine yazilan tanim `Kutuphane:Ad` adini tasir., Tablo eski surum adini tasiyorsa ayni turden degiskene duser., `extends` cozulurken birim dugumleri TUREVIN adini almali. KiCad birim…, SymLibTests

### Community 95 - "InProcessBridgeTests"
Cohesion: 0.24
Nodes (5): InProcessBridgeTests, skipUnless, KiCad'in KENDI yorumlayicisinda kosar - baska turlu bu yol sinanmaz., Asil degismez: pyyaml OLMADAN kural okunabilmeli., API yok: dogrudan pcbnew ile tasi, sonra DISKTEN geri oku.

### Community 96 - "Beads skill (bd ile kalici gorev takibi)"
Cohesion: 0.15
Nodes (18): Beads OpenAI agent arayuz tanimi, Beads skill (bd ile kalici gorev takibi), Canli mod ve sematik API (Beads hafizasi, 2026-08-29), Kurulum kurallari: kullanici yapilandirmasina dokunan tek yer, Duzeltme: 'KiCad 10'da sematik API'si yok' tespiti YANLISTI, KiCad baglanti yollari (Beads hafizasi), minyaml diferansiyel testi ve YAML 1.1 tuzaklari, Uc KiCad baglanti yolu (dosya / surec-ici / IPC) (+10 more)

### Community 97 - "bench.rules.yaml - sentetik tezgah kural seti"
Cohesion: 0.13
Nodes (18): placer-anneal agent tanimi, decoupling-mesafe (proximity, 10 mm, error), identity / random alt sinir referanslari, Yerlestirme Agent'i Brifingi, Donmus Placer arayuzu (base.py), Sinavi degistiren agent'in sonucu gecersizdir, vdd-decoupling (3 x 100 nF), proximity exclusive eslesmesi (+10 more)

### Community 98 - "Yol haritasi: agirlikli skorlama"
Cohesion: 0.29
Nodes (7): Beads - AI-native issue tracking, KiCad'in Python'u PYTHONPATH'i yok sayar (olculmus, 2026-08-30), pcbqa.cmd baslat.py'ye gecti, Yol haritasi: agirlikli skorlama, Faz 1a - Agirlik mekanizmasi, Mevcut skor formulu (severity-only), pcbqa - KiCad tasarim kalite analizi ve otomatik yerlestirme

### Community 99 - "app.py"
Cohesion: 0.29
Nodes (9): r"""Onyukleyici - KiCad'in Python'u `PYTHONPATH`'i YOK SAYAR, bu yuzden var.…, diagnose(), _dispatch(), _line(), main(), BAGIMSIZ UYGULAMA - tek giris noktasi. pcbqa tani ortami denetle pcbqa analiz…, Ortami denetler. Doner: (satirlar, engel_sayisi)., run_diagnose() (+1 more)

### Community 100 - "test_komut.py"
Cohesion: 0.19
Nodes (8): Proje metninden kok sematik. Metin ARGUMANDIR, Tk degiskeni degil. tkinter is…, kok_sematik(), KomutError, RuntimeError, Su anki modelimiz" = hedefteki TEK proje. Birden fazla aday varsa secim…, Komut calistirilamadi (hedef sematik bulunamadi gibi)., KokSematikTests, Asama 4g: dogal dil komutu -> ekleme. Burada korunan sey DOGRU ANLAMA degil,…

### Community 101 - "Netlist degismezligi kalkani (sch_verify)"
Cohesion: 0.20
Nodes (11): Acik-proje (lck) korumasi, Atomik yazma (sch_write), Bayat model yolu: move-v2 vs move-v3, Beklediginizi dogrulayan olcum bozuk olabilir, Capa kumesi darligi: %79 yanilgisi, Kalkanin iki kum havuzu kopyasi, Netlist degismezligi kalkani (sch_verify), Pin geometrisi: tahmin degil olcum (+3 more)

### Community 102 - "generate.py: plandan gercek KiCad projesine"
Cohesion: 0.18
Nodes (11): Ayni sembolun pinleri asla eslesmez, compare_additive: eklemeye izin veren kalkan, connect.py (pcbqa bagla): karari yurutur, generate.py: plandan gercek KiCad projesine, Guc sembolleri KiCad netlist'inde dugum olarak gorunmez, KiCad 10 instances blogu, Ipek baski cakismasi: yerlestirici metinleri gormuyor, propose.py: yerlesimden niyet cikarma (+3 more)

### Community 103 - "Oznitelik semasi v3 (75 oznitelik)"
Cohesion: 0.20
Nodes (11): base.Compound: birlesik hamle, Finding.rule_type ve Finding.pins, Evaluation.gain_over, Genis hamle repertuari (Faz A), Metropolis kabul kurali (Faz E), Denenip calismayan uc yakinsama olcutu, Oznitelik semasi v3 (75 oznitelik), HPWL hamleleri plato asma mekanizmasidir (+3 more)

### Community 104 - "ValueRange"
Cohesion: 0.31
Nodes (5): crystal_load_range(), Bir bilesen degerinin kabul araligi ve nereden geldigi., `cl_pf` beyanindan yuk kondansatoru araligi., ValueRange, ValueRangeTests

### Community 105 - "find_buck_converters"
Cohesion: 0.17
Nodes (15): BuckConverter, _components_on(), find_buck_converters(), _first_net(), hot_loop_polygon(), _pad_xy(), _pins_by_ref(), Alt-devre tanima: karttaki bilinen devre bloklarini topolojiden bulur. Neden… (+7 more)

### Community 106 - "plan_nets"
Cohesion: 0.27
Nodes (11): junctions_for(), _net_check(), _order_chain(), pin_point(), plan_nets(), Point, Schematic, Pinleri en yakin komsu zinciriyle sirala. Ucten fazla pinli bir agda hangi… (+3 more)

### Community 107 - "TermTableTests"
Cohesion: 0.20
Nodes (5): Ad ezberden degil olcumden geldi; `ornek` o olcumun izidir., Arama kucuk harfle yapiliyor; buyuk harfli anahtar hic tutmaz., Paket ve uretici adlari CEVRILMEZ; TERMS'e girerlerse cevrilirler., Kod ve veri ASCII (proje kurali); 'kondansator', 'kondansatör' degil., TermTableTests

### Community 109 - "Agirliklar kanit gucune gore bantlanir"
Cohesion: 0.13
Nodes (18): Agirliklar kanit gucune gore bantlanir, Kaynaklar arasi celiskiler ve alinan kararlar, Devre tipine gore PCB tasarim kurallari - kaynakli derleme, IPC-2221B / IPC-7351B, Olcekleme yalnizca kaynak bir formulse, Cogu tavsiyenin sayisi yok, TI AN-2155 (SNVA638A), TI SLVA959B (+10 more)

### Community 110 - "GBTModel"
Cohesion: 0.07
Nodes (27): _cholesky_solve(), Ridge (L2 cezali) dogrusal regresyon - saf Python. Neden saf Python: proje…, Sutun ortalamalari ve standart sapmalari (sifir sapma -> 1)., A simetrik pozitif tanimli iken A x = b cozumu., _standardize(), register(), cross_validate(), fit_model() (+19 more)

### Community 111 - "graphify-bilgilendir.py"
Cohesion: 0.54
Nodes (7): graphify_tazele(), hafiza_anahtarlari(), kabuk(), main(), GRAPHIFY'I BILGILENDIR - her karar, her hata duzeltmesi, her plan sonrasi.…, yaz_hafizalar(), yaz_kayitlar()

### Community 112 - "collect_design.py"
Cohesion: 0.15
Nodes (13): build_parser(), collect(), collect_intent(), intent_files(), main(), ArgumentParser, Path, TASARIM SEVIYESI VERI TOPLAMA (Evre 3c) - varyant siralayici icin. python -m… (+5 more)

### Community 113 - "test_generate.py"
Cohesion: 0.15
Nodes (12): KiCad'in netlist'i plani birebir kuruyor mu? (dogrulanan ag, engeller). Ug ayri…, verify_against_plan(), _conn(), FakeSymbol, _plan_two_resistors(), _plan_with(), Evre 3a surucusu: insa planindan gercek KiCad projesi. Uc katman ayri ayri…, Kutuphane gerektirmeden referans on eki tasiyan en kucuk sembol. (+4 more)

### Community 114 - "ThreePartTests"
Cohesion: 0.20
Nodes (3): +10V, R1, C1 - hicbiri bagli degil., R1.1-R1.2 onerilirse direnc kisa devre olur. Bu gercekten olmustu: ilk surumde…, ThreePartTests

### Community 115 - "learned - ogrenilmis hamle siralayicisi"
Cohesion: 0.10
Nodes (21): Benzetimli tavlama yontemi (anneal), KiCad Local History dizini, Skorlama yol haritasi - evre durumu (2026-08-28), Sessiz hata sinifi - uretmek olcen katmani denetler, Skorun siniri: skor bir ihlal sayacidir, kalite olcegi degil, Korpus kalibrasyonu (19 KiCad demo karti, 2026-08-28), Pad katmanlari okunmuyordu (kalibrasyonun yakaladigi kusur), Vekil maliyet uydurma - gercek olcumu optimize et (+13 more)

### Community 116 - "Lineer regulator, motor surucu, koruma, sensor, HV (Bolum 4)"
Cohesion: 0.12
Nodes (19): ESD/CMC yerlesim sirasi: konnektor -> ESD -> CMC -> R/C, Kristal -> MCU pini mesafesi: sayisal deger BULUNAMADI, USB 2.0 diferansiyel empedans 90 ohm +-%15, Lineer regulator, motor surucu, koruma, sensor, HV (Bolum 4), Genel IC bypass -> besleme pini <= 5 mm, Elektrolitik kondansator vent bosluğu ve end-seal yasagi, ESD'de belirleyici buyukluk mesafe degil enduktanstir, Gate izi genisligi >= 0.508 mm ve SiC surge korumasi <= 20 mm (+11 more)

### Community 117 - "LauncherTests"
Cohesion: 0.18
Nodes (6): CompletedProcess, LauncherTests, Baslatici son kullanicinin gordugu sey - sanal ortam olmadan kosar., Regresyon: kullanici paket klasorunde DEGILDIR. Baslatici once `python -m…, KiCad'in Python'u PYTHONPATH'i YOK SAYIYOR - buna guvenilmemeli. Olcum (KiCad…, `baslat.py` paketin YANINDA olmali - sys.path[0]'i o konum veriyor.

### Community 118 - "IpcApplyError"
Cohesion: 0.29
Nodes (17): apply(), check_target(), connect(), decode(), digest(), dispatch(), encode(), items() (+9 more)

### Community 119 - "default_rules.yaml - pcbqa varsayilan kurallari"
Cohesion: 0.20
Nodes (10): uretim-courtyard-cakisma warning/6'ya cekildi, courtyard-cakisma (courtyard_overlap, warning), default_rules.yaml - pcbqa varsayilan kurallari, defaults.ignore_nets (toprak/genis netler), kart-kenari-mesafesi (edge_clearance, 0.5 mm), net-uzunluk-butcesi (net_length, 120 mm HPWL), veri-hatti-pullup (require_on_net), HPWL (Half-Perimeter Wire Length) (+2 more)

### Community 120 - "fb_divider_max_bottom_ohms"
Cohesion: 0.28
Nodes (6): fb_divider_max_bottom_ohms(), fb_divider_range(), Alt bolucu direncinin ust siniri. I_bolucu = Vfb / R2 >= ratio * I_bias -> R2…, `vfb` ve `bias_current_na` beyanlarindan alt direnc ust siniri., FeedbackDividerTests, Richtek AN033: bolucu akimi >= 100 x FB bias akimi.

### Community 121 - "parse_with_stats"
Cohesion: 0.07
Nodes (22): pcbqa - KiCad tasarimlari icin salt-okunur kalite/uygunluk analizi (Asama 0)., parse(), parse_with_stats(), ValueError, _quote(), QuotedStr, Kucuk, bagimliliksiz bir s-expression okuyucu. KiCad'in .kicad_pcb / .kicad_sch…, Dosyada tirnak icinde yazilmis bir atom. Ayrimi korumak sart: `(at 110.49… (+14 more)

### Community 122 - "load_config"
Cohesion: 0.18
Nodes (12): _as_mapping(), ConfigError, load_config(), Path, RuntimeError, Yapilandirma okuma: YAML varsa YAML, yoksa yaninda duran JSON. ## Neden var…, Yapilandirma dosyasi okunamadi ya da bicimi bozuk., Yapilandirmayi okur. Doner: (veri, json_kullanildi_mi). Bos dosya bos sozluk… (+4 more)

### Community 123 - "Kicad-5be: Eeschema 10.0.4 canli sematik yazmayi uygulamiyor"
Cohesion: 0.36
Nodes (8): Kicad-5be: Eeschema 10.0.4 canli sematik yazmayi uygulamiyor, Kicad-rfz: Kurulumda izinle alinan IPC API + canli sematik yazma, Kicad-6r2: API'siz baglanti - surec-ici SWIG uygulamasi, Kicad-8vp: Canli mod KiCad'in Python'unda calismaz, Kicad-fqn: Bagimsiz uygulama sekli karari, Kicad-i6z: Baslatici PYTHONPATH'e guveniyordu, Kicad-qz5: Canli PCB duzenleme dogrulandi (KiCad 10.0.4), Canli PCB duzenleme calisiyor (KiCad 10.0.4)

### Community 124 - "deger_coz"
Cohesion: 0.27
Nodes (5): deger_coz(), 100nf" -> "100nF", "4u7" -> "4u7", "10" -> None (o bir SAYI). Onek ya da birim…, DegerTests, 10 kapasitor" 10 ADET demektir, 10 farad degil., 10M" mega, "10m" milidir - sadelestirilmis kelimeden okunsaydi ikisi ayni…

### Community 125 - "test_lexicon.py"
Cohesion: 0.14
Nodes (6): LookupTests, NormalizeTests, Iki dilli bilesen sozlugu. Bu sozluk ilerideki makine ogreniminin GIRDISI…, Olculdu: alt dizi aramasi 'C' icin 41 onek donduruyordu - gurultu., `U6`, `RL2`, `MES?` ayri onek DEGIL - kutuphane yazim tutarsizligi., Kirpma sonucu tanimli bir onege dusmuyorsa dokunulmaz. Yoksa gercekten yeni bir…

### Community 126 - "RegressionGuardTests"
Cohesion: 0.39
Nodes (4): best_result(), Sozlesme ihlali olmayan ve karti KOTULESTIRMEYEN en iyi sonucu secer. Gerileme…, RegressionGuardTests, Result

### Community 127 - "graphify-etiketle.py"
Cohesion: 0.50
Nodes (4): main(), Elle verilen topluluk adlarini graph.json'a geri uygular. ## Neden gerekiyor…, Doner: (adlandirilan topluluk, bulunamayan capalar, birlesen adlar)., uygula()

### Community 128 - "ST AN2586"
Cohesion: 0.29
Nodes (8): ldo-ams1117-3v3 sablonu, mcu-stm32f103c8 sablonu (LQFP-48 cekirdek blogu), boot0-pulldown (10k), Kosullu cevre pinleri (interfaces), nrst-kondansator (100 nF), ST AN2586, f103-harici-guc-swd niyeti, guc-modulu niyeti

### Community 129 - "normalize_pin_name"
Cohesion: 0.31
Nodes (5): normalize_pin_name(), Pin adindan bicimleme isaretlemesini atar: "V_{IN}" -> "VIN"., PinNameNormalisationTests, KiCad sembollerinde pin adi bicimleme isaretlemesi tasiyabilir., jetson'daki TPS564247'nin VIN pini dosyada "V_{IN}" yaziyor.

### Community 130 - "test_app.py"
Cohesion: 0.11
Nodes (5): CommandTableTests, DiagnoseTests, DispatchTests, Bagimsiz uygulama: tek giris noktasi ve baslatici. Dagitilan sey bu: bir klasor…, Tabloya yazilan her komutun `main()`i olmali.

### Community 131 - "keep_apart - kaynaklarin 'uzaklastir' dedigi bosluk"
Cohesion: 0.29
Nodes (7): keep_apart - kaynaklarin 'uzaklastir' dedigi bosluk, ROHM 66AN015E, TI SNOA986A, manyetik-sensor-guc-izinden-uzak (keep_apart, 10 mm, weight 4), sensor-bypass-kondansatoru (proximity, 5 mm, weight 12), sensor-pullup-uzak-dursun (keep_apart, >= 10 mm, weight 12), buck_layout - ad degil topoloji

### Community 132 - "ipc_apply: calisan KiCad'e yazma hatti"
Cohesion: 0.29
Nodes (7): Canli duzenleme: sematikte yok, PCB'de var, Canli mod ve API'siz mod, ipc_apply: calisan KiCad'e yazma hatti, Bilinen IPC bug'lari, pcbqa kurulum: izinle alinan API, Duzeltilen yanilgi: sematik komutlari belge turunden bagimsiz, Canli calisirken tek KiCad ornegi

### Community 133 - "CorpusCalibrationTests"
Cohesion: 0.22
Nodes (5): CorpusCalibrationTests, `uretim` on ayari gercek kartlarda makul davranmali., Ayristirici gercek kartlarin hepsini okuyabilmeli., `uretim` devre tipinden bagimsiz; profesyonel kartlarda yuksek olmali. Olculdu…, Bir kural gercek kartlarin cogunda atesleniyorsa KURAL suphelidir. Kartlar…

### Community 134 - "Intent"
Cohesion: 0.15
Nodes (9): Intent, EndToEndTests, skipUnless, Dongunun varlik sebebi: kucuk kart. Kazanan en buyuk aday olmamali., Skorun neyi yargilamadigi SESSIZ kalmamali., EndToEndTests, skipUnless, Kucuk bir niyetten gercek proje - KiCad kendi netlist'iyle dogruluyor. (+1 more)

### Community 136 - "read_schematic"
Cohesion: 0.05
Nodes (19): Bir .kicad_sch dosyasini (ve tum alt sayfalarini) okur. Klasor verilirse…, read_schematic(), WriteTests, AssignmentTests, Sentetik MPN ve fiyat alanlari. Bu modul sematige TEDARIK VERISI yaziyor ve o…, Ornekte C1'in degeri 'C' - okunamaz, fiyat almamali., Ikinci kez atamak alani COGALTMAMALI., Uydurma veri UYDURMA GORUNMELI. (+11 more)

### Community 137 - ".probe"
Cohesion: 0.12
Nodes (7): Uctan uca: buyuk ihlal, kucuk ihlalden daha pahali olmali., Ayni kural, olcekleme kapali -> Faz 1a davranisi., BULGU BASINA ceza; cezalar dogrudan toplanir. Bulgu sayisina bolmek sart:…, Bulgu basina ceza, ihlal buyudukce artmali. Faz 1b'nin butun gerekcesi bu:…, Olcekleme cezayi yalnizca BUYUTUR, asla azaltmaz., ScaledScoreTests, WeightedScoreTests

### Community 138 - "allocate_units"
Cohesion: 0.33
Nodes (5): allocate_units(), (referans yuvasi, birim) ciftleri. Cok birimli sembollerde (74LS125 -> 4 kapi +…, FakeSymbol, 74LS125 -> 4 kapi + guc birimi; 6 istek iki referansa dagilir., UnitAllocationTests

### Community 139 - "bundle.py"
Cohesion: 0.26
Nodes (11): build(), build_parser(), main(), ArgumentParser, Path, Calisma zamani kopyalarini uretir: YAML -> JSON. python -m pcbqa.bundle # uret…, Paketle birlikte dagitilan YAML dosyalari., JSON metni - bicimi SABIT olmali ki `--check` gurultu uretmesin. (+3 more)

### Community 140 - "BuiltLexiconTests"
Cohesion: 0.22
Nodes (4): BuiltLexiconTests, skipUnless, Uretilmis sozluk - KiCad kurulu makinede., Kullanicinin ornegi: C = kapasitor/kondansator, iki dilde.

### Community 141 - "Pad bakir sekli tam modelleme (copper_shape)"
Cohesion: 0.33
Nodes (6): Ayrik sicak dongu: altigen akim yolu, Ayrik regulator: yanlis olcmektense olcmemek, Bakir kurallari yonlendirilmemis kartta sessizce atlanir, Pad bakir sekli tam modelleme (copper_shape), geom.segment_distance, Zone okuma - tahmin fazla iyimserdi

### Community 142 - "ConnectError"
Cohesion: 0.25
Nodes (4): ConnectError, RuntimeError, Baglanti planlanamadi., LookupTests

### Community 143 - "GlossTests"
Cohesion: 0.25
Nodes (4): GlossTests, Hicbir terim tutmazsa BOS doner - yarim ceviriyi Turkce diye sunmayiz., Kelime kelime cevirmek bunlari bozuyordu: 'Through hole' -> 'Through delik'., Parca numarasi ve paket adi cevrilmemeli.

### Community 144 - "load_design"
Cohesion: 0.08
Nodes (26): load_design(), PadLayerTests, PinFunctionTests, skipUnless, Asil kazanc: `function:` seciciSi sematik olmadan da eslesmeli. Aranacak adi…, Pad'in bakir katmanlari - kalibrasyonun yakaladigi hata., interf_u'daki BUS1: ayni x/y, farkli net, farkli YUZ. BUS1.29 (VCC) ve BUS1.60…, Gercek, calisan bir kartta 0.000 mm aciklik = kisa devre demek olurdu. (+18 more)

### Community 145 - "ArayuzLauncherTests"
Cohesion: 0.21
Nodes (7): ArayuzLauncherTests, skipUnless, Arayuzun kendi baslaticisi (kisayolun hedefi). Ayri bir dosya olmasinin sebebi…, `--nerede` tanilamasini calistirir; etiket -> deger., Varsayilmaz, sinanir: secilen yorumlayici tkinter'i ICE AKTARABILMELI., Ilk surumdeki gercek hata buydu. `pythonw` PATH'ten aliniyordu ve bu makinede…, KiCad'in Python'u tkinter getirmiyor; secilirse arayuz acilmaz. Denetim YOL…

### Community 146 - ".evaluate"
Cohesion: 0.29
Nodes (4): Placement, Bir yerlestirmeyi hakemin kendi olcutuyle puanlar. Vekil maliyetle ugrasmak…, Kartin su anki yerlesimi - iyilestirmeye buradan baslamak gercek kartlarda…, Yeni konumlari dondurur. Kurallar: * `ctx.locked` icindeki referanslari SONUCA…

### Community 147 - "next_references"
Cohesion: 0.38
Nodes (4): next_references(), Kullanilmayan `prefix1..N` referanslari. Numaralandirma TUM sematik uzerinden…, R1 ve R3 kullanimdaysa sirada R2 vardir - KiCad de boyle yapar., ReferenceNumberingTests

### Community 148 - "post-commit"
Cohesion: 0.40
Nodes (4): post-commit script, GRAPHIFY_CHANGED, GRAPHIFY_REBUILD_LOG, PYTHONHASHSEED

### Community 149 - "graphify-durum.py"
Cohesion: 0.50
Nodes (4): degisen_kod_dosyalari(), main(), Oturum basi graphify durumu - bilgi grafigi acik mi, guncel mi. Neden var:…, Grafik yazildigindan beri kac kod dosyasi degisti (git'e gore).

### Community 150 - "Creepage - IEC 60664-1 / IEC 62368-1"
Cohesion: 0.40
Nodes (5): Creepage - IEC 60664-1 / IEC 62368-1, Delik-bakir ve via-via mesafeleri, Kart kenari acikligi, IPC-2221B Tablo 6-1: gerilime gore minimum iletken acikligi, PCB ureticisi minimumlari (JLCPCB / PCBWay / OSH Park)

### Community 151 - "thermal kurali - esik yerine hesap"
Cohesion: 0.40
Nodes (5): component_value - ilk devre dogrulugu kurali, NXP UM10204 (I2C spesifikasyonu), Richtek AN044, thermal kurali - esik yerine hesap, regulator-jonksiyon-sicakligi (thermal, KAPALI ornek)

### Community 152 - "_satir"
Cohesion: 0.29
Nodes (3): AkimTests, Test icin elle bir satir; gerilimler ag ADINDAN turetilir., _satir()

### Community 153 - "connectivity_of"
Cohesion: 0.11
Nodes (29): find_kicad_cli(), KicadCliError, RuntimeError, `kicad-cli` sarmalayicisi. Asama 0'in tamami bu arac uzerinden calisir; IPC API…, kicad-cli'yi bulur. Sirasiyla: parametre, ortam degiskeni, PATH, bilinen…, connectivity_of(), export_netlist(), parse_netlist() (+21 more)

### Community 155 - "post-checkout"
Cohesion: 0.50
Nodes (3): post-checkout script, GRAPHIFY_REBUILD_LOG, PYTHONHASHSEED

### Community 156 - "RealBoardDetectionTests"
Cohesion: 0.23
Nodes (6): jetson / U69: VIN pini "V_{IN}" yaziyor. Normalizasyon olmadan vin_net None…, One-Air-Max / U5 (BQ25672): induktor IKI anahtar arasinda. Orada "diger uc"…, Tanınan her devrede SW neti ve o nette bir induktor olmali., CM5_MINIMA_3 / U702: rollerin tamami cikmalı., One-Air-Max / U2: FB neti "Net-(U2-FB{slash}VSET)". Hicbir net ADI deseni bunu…, RealBoardDetectionTests

### Community 157 - "runtime_twin"
Cohesion: 0.27
Nodes (6): Bir YAML dosyasinin calisma zamani JSON esi., runtime_twin(), yaml_available(), BundleTests, Kullanicinin KENDI kural dosyasi da KiCad icinde okunabilmeli., YAML duzeltilip JSON eski kalirsa KiCad ICINDE eski kural kosar. Bu testin…

### Community 158 - "decoupling_count kurali - mesafe degil adet"
Cohesion: 0.67
Nodes (3): decoupling_count kurali - mesafe degil adet, Cozulemeyen deger her iki kovaya sayilir, TI SPRABV2

### Community 174 - "Pad"
Cohesion: 0.13
Nodes (6): Pad, Bir footprint pad'i. x/y kart uzerindeki MUTLAK konum (mm)., Pad bakirinin alani (mm2). Sekle gore tam hesaplanir., Pad'i cevreleyen dairenin yaricapi (kaba olcum icin)., Pad bakiri: (noktalar, sisme_yaricapi). Sonuc, noktalarin `r` kadar sisirilmis…, PadAreaTests

### Community 175 - "place_point"
Cohesion: 0.31
Nodes (5): place_point(), Kutuphane noktasini sayfa ofsetine cevirir. Modul basligindaki deneysel olarak…, Kutuphane -> sayfa donusumu (deneysel olarak secildi, bkz. schematic.py)., Ters sirada uygulanirsa 90 derecede farkli sonuc cikar., TransformTests

### Community 177 - "DagarcikTests"
Cohesion: 0.15
Nodes (5): DagarcikTests, Tablolar buyudukce bozulur; bu testler bozulmayi ilk kosuda yakalar., Bir kere oldu: "on" Ingilizce edat diye dolguya kondu ve Turkce "on adet"…, Baglama pin NUMARASI ister; tabloya tur eklenip `uclar` unutulursa…, toprak" gecerli bir hedeftir; yapi sozcugu sayilsaydi "VCC ile toprak arasina"…

### Community 178 - "RedTests"
Cohesion: 0.18
Nodes (4): Reddedilmesi gerekenler. Bir cozumleyicinin degeri buradadir., Anlamadim" ile "henuz yapmiyorum" ayri seylerdir., Kaynagi olmayan varsayilan (or. "kondansator = 100nF") yazilmaz., RedTests

### Community 179 - ".refresh"
Cohesion: 0.22
Nodes (6): Any, KiCad donme konvansiyonu (Y asagi) - `pcb._rotate` ile ayni formul. Burada…, Yerlesim onbelleklerini tazeler. Yerlesim her degistiginde cagirin., Verilen netlerin HPWL toplami ve net basina degerleri. `moved` verilirse o…, Bu bilesenin PINLERI ile net ortaklarinin PINLERI arasi en kisa mesafe.…, _rotate()

### Community 181 - "HotLoopTests"
Cohesion: 0.29
Nodes (5): HotLoopTests, Giris sicak dongusu - projedeki EN GUCLU sayisal kanit. TI AN-2155 bunu…, Olculdu: 0.73 / 0.85 / 1.13 mm2 - TI'in "iyi" degeri 6 mm2. Kalibrasyon ilkesi:…, Buck-boost'ta CIN tanınmiyor - iddia etmek yerine None donmeli., Esik gercek degerin altina cekilince kural ateslemeli.

### Community 185 - "BoardWriteTests"
Cohesion: 0.43
Nodes (3): BoardWriteTests, `harness.write_board` bir HARNESS islevi ama hatasi burada bulundu. Uretilen 18…, Metinler VE pad'ler donmeli - KiCad kendi dondurdugunde oyle yazar. Pad acisi…

### Community 190 - "decoupling_counts"
Cohesion: 0.24
Nodes (6): decoupling_counts(), (gereken 0.1 uF sayisi, gereken bulk sayisi) - TI SPRABV2 6. TI: her 2 guc topu…, DecouplingCountTests, TI SPRABV2 6: her 2 guc topu icin 0.1 uF, her ~10 icin bulk., Oranlar TI SPRABV2'nin kendi sayilari olmali., SourceRatioTests

### Community 193 - "GercekKartTests"
Cohesion: 0.22
Nodes (4): GercekKartTests, skipUnless, Bos hucrenin yaninda sebep yoksa kullanici hatamizi goremez., samples/pic_programmer C4'un degeri "0" - fiyat uydurulmaz. Bu satir bir…

### Community 195 - "ModelRanker"
Cohesion: 0.47
Nodes (3): ModelRanker, Aday BIRLESIK hamleleri modelin tahminine gore buyukten kucuge dizer. `top_k`…, RankerTests

### Community 196 - "YorumlayiciTests"
Cohesion: 0.29
Nodes (3): Bunlar Tk penceresi ACMADAN kosar., KiCad'in Python'unda tkinter yok; ayirt edebilmeliyiz., YorumlayiciTests

### Community 197 - "Dataset"
Cohesion: 0.08
Nodes (17): noise_floor(), Ayni oznitelik vektorunun etiket yayilimi: modelin ASAMAYACAGI taban. Tohum…, Dataset, Any, Path, Gruplari (kartlari) butun halinde egitim/test olarak ayirir., Gruplu k-kat capraz dogrulama. Az grup varsa kat sayisi kisilir., Ornekleri aday listesine gore gruplar (siralama metrikleri icin). (+9 more)

### Community 201 - "._overlap_state"
Cohesion: 0.40
Nodes (3): _bbox_of(), Yaricap icindeki bilesenler - izgara sorgusu., (cakisan komsu sayisi, en kucuk aciklik, yaricaptaki komsu sayisi). Cakisma…

### Community 202 - ".__init__"
Cohesion: 0.40
Nodes (4): _CompStatic, _kind_index(), _log1p(), Bilesenin hamleden bagimsiz, bir kez hesaplanan bilgileri.

### Community 210 - "geom.py"
Cohesion: 0.16
Nodes (21): area(), bbox(), contains(), convex_hull(), distance(), overlap(), Point, Kucuk geometri yardimcilari: dısbukey kabuk, cakisma ve mesafe. Neden gerekli:… (+13 more)

### Community 287 - "thermal.py"
Cohesion: 0.27
Nodes (9): is_area_dependent(), junction_temp_c(), Termal hesaplar: bakir alanindan jonksiyon sicakligina. `ipc2221.py` ile ayni…, Tj'yi sinirda tutan EN KUCUK bakir alani. None doner: * paketin alan…, Bu paket icin theta_JA'nin bakir alanina bagimliligi OLCULMUS mu?, Verilen bakir alaninda theta_JA (C/W). Ara degerler log10(alan) uzerinde…, Tj = TA + P * theta_JA(alan). Kararli hal, tek isi kaynagi. Komsu bilesenlerin…, required_area_mm2() (+1 more)

### Community 336 - "AddPlan"
Cohesion: 0.14
Nodes (9): AddPlan, _expected_joins(), Kalkana "bu pin SU pinle ayni aga girmeli" listesi. Ag adiyla baglanirken…, Ne eklenecegi - yazmadan once gosterilebilir., Connection, pins_on_net(), Tek bir baglama istegi: hangi pin, neye., Hedef bir pin mi (`R1.2`), yoksa ag adi mi (`VCC`)? (+1 more)

## Ambiguous Edges - Review These
- `Benzetimli tavlama yontemi (anneal)` → `Vekil maliyet uydurma - gercek olcumu optimize et`  [AMBIGUOUS]
  .claude/agents/placer-anneal.md · relation: conceptually_related_to
- `KiCad Local History dizini` → `Atomik yazma ve acik-proje korumasi`  [AMBIGUOUS]
  KicadOtomasyon1/.history/README.txt · relation: conceptually_related_to
- `f103-usb-kristal niyeti` → `Kristal -> MCU pini mesafesi: sayisal deger BULUNAMADI`  [AMBIGUOUS]
  pcbqa/samples/niyetler/f103-usb-kristal.yaml · relation: conceptually_related_to

## Knowledge Gaps
- **59 isolated node(s):** `Calisma anlasmasi graphify entegre`, `Canli pcb arayuzu ve dogrulama`, `Canli sematik nightly dogrulandi`, `Graphify kurulumu ve hafiza akisi`, `Netlistte gorunmeyeni netlistte arama` (+54 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1476 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Benzetimli tavlama yontemi (anneal)` and `Vekil maliyet uydurma - gercek olcumu optimize et`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `KiCad Local History dizini` and `Atomik yazma ve acik-proje korumasi`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `f103-usb-kristal niyeti` and `Kristal -> MCU pini mesafesi: sayisal deger BULUNAMADI`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `load_design()` connect `load_design` to `Design`, `.routed`, `Repertoire`, `.probe`, `load_rules`, `penalty_of`, `__main__.py`, `RealBoardDetectionTests`, `test_decoupling_count.py`, `bench_context`, `run`, `swig_apply.py`, `ComponentValueRuleTests`, `Evaluation`, `HotLoopTests`, `harness.py`, `DiscreteBuckTests`, `test_ml.py`, `generate.py`, `canli.py`, `test_collect_design.py`, `CopperAreaRuleTests`, `test_circuit.py`, `read_board`, `collect_design.py`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `PlacementContext` connect `PlacementContext` to `test_ml.py`, `refine.py`, `bench_context`, `generate.py`, `Repertoire`, `sch_place.py`, `base.py`, `swig_apply.py`, `_Model`, `load_design`, `.evaluate`, `Evaluation`, `anneal.py`, `harness.py`, `cluster.py`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `Design` connect `Design` to `generate.py`, `.__init__`, `find_buck_converters`, `base.py`, `load_design`, `collect_design.py`, `SyntheticDiscreteBuckTests`, `PlacementContext`, `__main__.py`, `harness.py`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 45 inferred relationships involving `PlacementContext` (e.g. with `SimulatedAnnealing` and `Auto`) actually correct?**
  _`PlacementContext` has 45 INFERRED edges - model-reasoned connections that need verification._