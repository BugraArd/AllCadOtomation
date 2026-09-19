# Graph Report - Kicad  (2026-09-20)

## Corpus Check
- 170 files · ~227,504 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 4028 nodes · 8574 edges · 201 communities (168 shown, 33 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 449 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `25941466`
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
- children
- test_intent.py
- load_rules
- PricingTests
- _Model
- SyntheticDiscreteBuckTests
- intent.py
- MeanModel
- codex.py
- FootprintCheckTests
- connect.py
- pcb.py
- __main__.py
- ipc2221.py
- sch_add.py
- parse_with_stats
- canli_sematik.py
- sync
- test_decoupling_count.py
- mpn.py
- _Engine
- expand_intent
- sch_wire.py
- synth.py
- _variant
- pcb_sync.py
- refine.py
- MoveFeaturizer
- run
- propose.py
- Schematic
- improve
- swig_apply.py
- PlacementContext
- parse_value
- ComponentValueRuleTests
- Arayuz
- BuildPlan
- KicadCli
- PencereTests
- test_zones.py
- test_propose.py
- Evaluation
- read_schematic
- Lineer regulator, motor surucu, koruma, sensor, HV (Bolum 4)
- penalty_of
- lexicon.py
- ml/collect_design.py: tasarim seviyesi veri
- circuit.py
- load_design
- ArenaTests
- DiscreteBuckTests
- _courtyard
- MetricTests
- _boxes_overlap
- komut.py
- compare_additive
- auto: uretim yerlestiricisi
- metrics.py
- schematic.py
- WorkerTests
- RidgeModel
- generate.py
- canli.py
- Yuksek hizli ve hassas sinyal arayuzleri (Bolum 3)
- PinRef
- Bagimsiz uygulama: KiCad'in Python'una yaslanmak
- decoupling_count: mesafe degil ADET
- KiCad'in kendi araclari son hakemdir
- test_collect_design.py
- EndToEndTests
- Sessiz hata sinifi: yazilmis ama baglanmamis kod
- KutuphaneTests
- Yorum
- arayuz.py
- ipc.py
- ray_gerilimi
- ShieldTests
- SchematicArena
- uygula
- Model
- crystal_load_capacitor_f
- read_board
- SymLibTests
- InProcessBridgeTests
- Beads skill (bd ile kalici gorev takibi)
- bench.rules.yaml - sentetik tezgah kural seti
- Devre tipine gore PCB tasarim kurallari - kaynakli derleme
- app.py
- kok_sematik
- Netlist degismezligi kalkani (sch_verify)
- generate.py: plandan gercek KiCad projesine
- Oznitelik semasi v3 (75 oznitelik)
- ValueRange
- find_buck_converters
- ReaderTests
- _Node
- netlistte-gorunmeyeni-netlistte-arama.md
- Agirliklar kanit gucune gore bantlanir
- GBTModel
- graphify-bilgilendir.py
- collect_design.py
- verify_against_plan
- ThreePartTests
- learned - ogrenilmis hamle siralayicisi
- f103-usb-swd niyeti
- RouteTests
- IpcApplyError
- default_rules.yaml - pcbqa varsayilan kurallari
- fb_divider_max_bottom_ohms
- evaluate_design
- load_config
- Kicad-5be: Eeschema 10.0.4 canli sematik yazmayi uygulamiyor
- deger_coz
- test_lexicon.py
- ipc_apply.py
- graphify-etiketle.py
- decoupling-mesafe (proximity, 10 mm, error)
- FakeBoard
- LauncherTests
- keep_apart - kaynaklarin 'uzaklastir' dedigi bosluk
- ipc_apply: calisan KiCad'e yazma hatti
- CorpusCalibrationTests
- EndToEndTests
- graphify-kurulumu-ve-hafiza-akisi.md
- test_mpn.py
- .probe
- test_sch_connect.py
- bundle.py
- rules_with
- Pad bakir sekli tam modelleme (copper_shape)
- LookupTests
- ExploreResult
- test_subcircuit.py
- Intent
- label_of
- fit_model
- post-commit
- graphify-durum.py
- Creepage - IEC 60664-1 / IEC 62368-1
- thermal kurali - esik yerine hesap
- _satir
- pcbqa/__init__.py
- calisma-anlasmasi-graphify-entegre.md
- post-checkout
- ValueClassificationTests
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
- _Convergence
- place_point
- Schematic
- DagarcikTests
- RedTests
- Decoupling max mesafe < 6.35 mm
- Board
- Renderer
- FakeSymbol
- noise_floor
- ConnectWritingTests
- _cholesky_solve
- canli-pcb-arayuzu-ve-dogrulama.md
- sentetik-veri-isaretlenmeli.md
- canli-sematik-nightly-dogrulandi.md
- EndToEndTests
- test_circuit.py
- .of
- SampleIntentTests
- GercekKartTests
- README.md
- YorumlayiciTests
- Dataset
- Eylem
- thermal.py
- Connection
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
- `Cok-agentli yerlestirici sinavi kurallari` --conceptually_related_to--> `Faz 1b - Orantili ceza (ihlal buyuklugune gore)`  [INFERRED]
  .claude/agents/placer-force.md → pcbqa/docs/yol-haritasi-skorlama.md
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

## Communities (201 total, 33 thin omitted)

### Community 0 - "Design"
Cohesion: 0.06
Nodes (64): Design, Birlestirilmis tasarim: sematik + PCB., Sematikte var, PCB'de yok., PCB'de var, sematikte yok., _bound(), _check_buck_layout(), _check_clearance_voltage(), _check_component_value() (+56 more)

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
Cohesion: 0.09
Nodes (10): LiveBoard, LiveTests, Canli onizlemenin baska/eski bir karta uygulanmasini engelleyen sinirlar., FakeAngle, FakeField, FakeFootprint, FakeText, FakeVector2 (+2 more)

### Community 6 - "anla"
Cohesion: 0.07
Nodes (19): anla(), Dogal dil cumlesini eylem listesine cevirir. KUTUPHANEYE DOKUNMAZ. Cozumleme…, AnlaTests, BaglamaTests, on" bir dolgu kelimesi sayilirsa Turkce 10 kaybolur., Turkce ondalik ayraci virguldur; "4,7k" bolunurse deger kaybolur., kapasitorleri" taninir; "zimbirti" TANINMAZ ve engel olur., Baglama EKLEME ile ayni cumlede yapilir. Buradaki tehlike ekleme… (+11 more)

### Community 7 - "elektrik.py"
Cohesion: 0.09
Nodes (29): ag_metni(), _akim(), bagli_mi(), build_parser(), csv_yaz(), ElektrikError, _gerilim(), main() (+21 more)

### Community 8 - "add_symbols"
Cohesion: 0.17
Nodes (7): add_symbols(), Path, Proje klasorunu gecici dizine kopyalar; yeni kok sematik yolunu doner., Kutuphaneden sembol(ler) ekler. Varsayilan DRY-RUN'dir. `verify` acikken…, _sandbox_copy(), AddSymbolsTests, Izgara disi konum sessizce kabul edilmez: oturtulur ve soylenir.

### Community 9 - ".routed"
Cohesion: 0.07
Nodes (23): Boards, ClearanceVoltageRuleTests, KeepApartRuleTests, PadShapeTests, Bakir kurallari: iz genisligi, via akimi, gerilim acikligi, keep_apart. Bu…, 0.6 mm via TI tablosunda 1.1 A'de sabitlenir; 5 A tasiyamaz., Katman degistirmeyen net icin via kurali anlamsiz - sessiz kalmali., EN ONEMLI TEST: saglam kart, 5 V - hicbir bulgu olmamali. Bu test gelistirme… (+15 more)

### Community 10 - "Repertoire"
Cohesion: 0.08
Nodes (29): cluster_moves(), _extent(), Compound, Placement, Random, GENIS HAMLE REPERTUARI - takas, kume tasima, bolge sicramasi (Asama 6, Faz A).…, Bilesenin bagli oldugu bilesenlerin agirlik merkezi., Iki bilesenin yer degistirmesi. Ortaklar, `ref`in bagli oldugu bilesenlerin… (+21 more)

### Community 11 - "children"
Cohesion: 0.06
Nodes (61): merge_lib_symbol(), Tanimi `lib_symbols` bolumune ekler. Zaten varsa dokunmaz. Doner: gercekten…, children(), head(), Dugumun etiketi: ['at','1','2'] -> 'at'., Dogrudan alt dugumlerden etiketi `name` olanlar., _deep_copy(), environment() (+53 more)

### Community 12 - "test_intent.py"
Cohesion: 0.17
Nodes (8): Niyet beyanini okur ve bicimini dogrular., read_intent(), IntentFormatTests, make_templates(), Path, Evre 3a: niyet beyani -> sablon kutuphanesi -> insa plani. Iki katman test…, TemplateFormatTests, _write()

### Community 13 - "load_rules"
Cohesion: 0.07
Nodes (16): load_rules(), Path, YAML kural dosyasini okur ve dogrular. `include:` ile baska kural dosyalari…, IncludeTests, PresetLoadTests, Path, Sessizce ezilen bir kural, fark edilmeyen bir bosluktur., Aciklama, bulgunun hangi kaynaga dayandigini tasiyor - zorunlu. (+8 more)

### Community 14 - "PricingTests"
Cohesion: 0.25
Nodes (4): PricingTests, Istenen degismez: buyuk deger daha pahali. Olculdu: ilk iki surumde "gercekci…, Deger bilinmiyorsa fiyat UYDURULMAZ., Ayni girdi ayni katalog - iki kosuda fiyat degisirse guven biter.

### Community 15 - "_Model"
Cohesion: 0.08
Nodes (24): _diff_partner(), ForcePlacer, _Group, _is_ground(), _Item, _Model, Placement, Random (+16 more)

### Community 16 - "SyntheticDiscreteBuckTests"
Cohesion: 0.10
Nodes (17): hot_loop_area_mm2(), hot_loop_polygon(), Giris sicak dongusunun cevreledigi dortgen - ya da None. TI AN-2155 bu alani…, Sicak dongu alani (mm2) - olculemiyorsa None., HotLoopTests, Giris sicak dongusu - projedeki EN GUCLU sayisal kanit. TI AN-2155 bunu…, Olculdu: 0.73 / 0.85 / 1.13 mm2 - TI'in "iyi" degeri 6 mm2. Kalibrasyon ilkesi:…, Buck-boost'ta CIN tanınmiyor - iddia etmek yerine None donmeli. (+9 more)

### Community 17 - "intent.py"
Cohesion: 0.13
Nodes (24): build_parser(), _check_keys(), IntentError, load_templates(), main(), plan_from_file(), ArgumentParser, Path (+16 more)

### Community 18 - "MeanModel"
Cohesion: 0.14
Nodes (4): MeanModel, Any, Taban cizgisi: her zaman egitim ortalamasini soyler.…, Sessizce yanlis sayilari okumaktansa hata vermeli.

### Community 19 - "codex.py"
Cohesion: 0.05
Nodes (65): area(), bbox(), contains(), convex_hull(), distance(), overlap(), Point, Kucuk geometri yardimcilari: dısbukey kabuk, cakisma ve mesafe. Neden gerekli:… (+57 more)

### Community 20 - "FootprintCheckTests"
Cohesion: 0.13
Nodes (6): ConnectEndToEndTests, FootprintCheckTests, FootprintLookupTests, MultiUnitAddTests, skipUnless, SandboxProject

### Community 21 - "connect.py"
Cohesion: 0.08
Nodes (41): apply_to_file(), build_nodes(), build_parser(), ConnectError, ConnectPlan, edit_tree(), junctions_for(), main() (+33 more)

### Community 22 - "pcb.py"
Cohesion: 0.08
Nodes (44): Footprint icindeki metin ve pad acilarini `delta` kadar dondurur. KiCad bir…, _turn_parts(), _chain(), _edges_of(), _local_points(), _node_net(), _pad_copper_layers(), _pad_net() (+36 more)

### Community 23 - "__main__.py"
Cohesion: 0.07
Nodes (42): describe_violation(), load_violations(), ERC/DRC JSON raporunu duz bir ihlal listesine cevirir. Iki dosyanin yapisi…, (severity, kod, aciklama) uclusu dondurur., analyze(), build_parser(), default_rules_path(), discover_project() (+34 more)

### Community 24 - "ipc2221.py"
Cohesion: 0.07
Nodes (23): clearance_mm(), current_capacity_a(), decoupling_max_distance_mm(), FabClass, IPC-2221B hesaplari: akima gore iz genisligi, gerilime gore aciklik. Neden…, IPC-2221B Tablo 6-1: bu gerilimde minimum iletken acikligi (mm). voltage_v: DC…, Bir uretim sinifinin minimumlari (mm)., Bir via'nin tasiyabilecegi akim (A), delik capina gore. Tablo disindaki… (+15 more)

### Community 25 - "sch_add.py"
Cohesion: 0.06
Nodes (54): build_schematic_tree(), Bos sematigi doldurur: (agac, engeller, notlar). Dosyaya YAZMAZ. Semboller…, AddPlan, AddResult, build_connections(), build_parser(), build_symbol_node(), _copy() (+46 more)

### Community 26 - "parse_with_stats"
Cohesion: 0.05
Nodes (52): build_parser(), _edit_tree(), main(), MovePlan, MoveResult, plan_move(), ArgumentParser, Path (+44 more)

### Community 27 - "canli_sematik.py"
Cohesion: 0.38
Nodes (9): configuration(), environment(), main(), open_copy(), Canli sematik icin ayri, surumu eslesen KiCad/Python ortami., Deneysel dosya bicimini kullanicinin asil projesinden ayirir., request(), Calisan KiCad surecleri ("ad (pid)"). Bulunamazsa bos liste. (+1 more)

### Community 28 - "sync"
Cohesion: 0.18
Nodes (10): Sematikte olup kartta olmayan bilesenleri karta ekler. Varsayilan DRY-RUN.…, sync(), KicadAcceptsTheBoardTests, MultiUnitSyncTests, skipUnless, Cok birimli sembol kartta TEK paket olmali., KiCad'in KENDI dogrulamasi: DRC + sematik paritesi., SandboxProject (+2 more)

### Community 29 - "test_decoupling_count.py"
Cohesion: 0.12
Nodes (13): bulk(), BulkFloorTests, ceramic(), ConfigTests, GroundExclusionTests, `decoupling_count` kurali (TI SPRABV2 6). Bu kural MESAFE degil ADET olcuyor -…, Bu projenin en onemli olcutu: gereksiz yerde susmak., U1'in VCC_PIC pini 10.64 mm otede C6'ya (100nF) sahip. 6.35 mm'de bulgu VAR,… (+5 more)

### Community 30 - "mpn.py"
Cohesion: 0.11
Nodes (27): apply_assignment(), Assignment, AssignPlan, _base_price(), build_parser(), candidates(), main(), parse_value() (+19 more)

### Community 31 - "_Engine"
Cohesion: 0.15
Nodes (10): _Engine, _Part, Placement, Random, Netleri turlerine ayirir: toprak / guc / saat / diferansiyel / sinyal., Bir alt agaci, kokunu (0,0)/rot'a koyarak dizer. Doner: {part_idx: (dx, dy,…, Cocugun ebeveyne baglandigi pad'in, alt agac kokunune gore ofseti., Bagimsiz yeniden baslatmalar; en iyisi secilir. Secim olcutu once SERT ihlal… (+2 more)

### Community 32 - "expand_intent"
Cohesion: 0.20
Nodes (7): expand_intent(), IntentBlock, Niyeti plana acar. Kutuphaneye DOKUNMAZ (onu `resolve_plan` yapar)., ExpandTests, intent_of(), Paketle gelen sablonlar - kutuphane gerektirmeyen kisim., RealTemplatesExpandTests

### Community 33 - "sch_wire.py"
Cohesion: 0.13
Nodes (26): blocked_points(), candidates(), existing_pin_point(), junction_node(), junctions_needed(), label_node(), _on_segment(), pin_position() (+18 more)

### Community 34 - "synth.py"
Cohesion: 0.14
Nodes (30): _apply(), BoardSpec, build_bench(), crystal(), _fmt(), header(), main(), PadSpec (+22 more)

### Community 35 - "_variant"
Cohesion: 0.39
Nodes (3): Kaliteden odun verilmez: buyuk ama temiz kart, kucuk ama kusurluyu yener., SelectionTests, _variant()

### Community 36 - "pcb_sync.py"
Cohesion: 0.09
Nodes (29): board_paths(), board_refs(), build_footprint_node(), build_parser(), _copy(), _drop(), free_positions(), main() (+21 more)

### Community 37 - "refine.py"
Cohesion: 0.07
Nodes (37): Move, _as_compounds(), _centroid(), _extent_of(), _finding_moves(), _inside(), keep_best(), _limit_of() (+29 more)

### Community 38 - "MoveFeaturizer"
Cohesion: 0.05
Nodes (34): _bbox_of(), _CompStatic, _kind_index(), _log1p(), MoveFeaturizer, Any, KiCad donme konvansiyonu (Y asagi) - `pcb._rotate` ile ayni formul. Burada…, Bilesenin hamleden bagimsiz, bir kez hesaplanan bilgileri. (+26 more)

### Community 39 - "run"
Cohesion: 0.07
Nodes (15): CurveTests, skipUnless, Termal hesap ve `thermal` kurali. Beklenen degerler DOKUMANDAN alinir (Richtek…, Yazim hatasi kurali SESSIZCE etkisiz birakmamali. Bu projede ayni sinif hata…, Secici hicbir seye uymuyorsa sessizlik korunur - beyan denetlenmez., Bu projenin en onemli olcutu: saglam kartta sessizlik., Gercek SOT-223 regulator: TLV1117LV33, tab pin 2 -> +3V3., Egri, olculen noktalardan TAM gecmeli. (+7 more)

### Community 40 - "propose.py"
Cohesion: 0.14
Nodes (24): _aligned(), alignment_pairs(), _clear_between(), _distance(), free_pins(), occupied_points(), PinRef, power_drops() (+16 more)

### Community 41 - "Schematic"
Cohesion: 0.18
Nodes (12): Sematigin yapisal saglamligini kontrol eder. `schematic` bir…, run_schematic_checks(), Bir dosyadaki alt sayfa kutusu., Bir sematik hiyerarsisinin tamami., Tel uclarinin sayfa bazinda sayim tablosu., Schematic, SchSheetRef, Asama 4a/4b: sematik okuyucu ve netlist degismezligi kalkani. (+4 more)

### Community 42 - "improve"
Cohesion: 0.20
Nodes (9): changed_only(), improve(), improve_file(), Path, SchPlacement, Bir sayfanin yerlesimini iyilestirir. `(placement, onceki_olcum,…, Yalnizca gercekten yeri degisen sembol orneklerini birakir. Anahtar UUID'dir:…, `read_schematic` + `improve` kisayolu. (+1 more)

### Community 43 - "swig_apply.py"
Cohesion: 0.13
Nodes (23): _angle_delta(), apply_placement(), board_name_of(), build_parser(), index_footprints(), load_pcbnew(), main(), open_board() (+15 more)

### Community 44 - "PlacementContext"
Cohesion: 0.05
Nodes (48): Tek bir varyanti yerlestirir ve olcer. Dosyaya DOKUNMAZ. Kart her denemede taze…, run_variant(), _accept(), _build_proximity_group(), Placement, Random, Benzetimli tavlama (simulated annealing) yerlestirici. Fikir:…, Benzetimli tavlama ile detayli yerlesim iyilestirmesi. Maliyet = agirlikli HPWL… (+40 more)

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
Nodes (11): BuildPlan, PlannedComponent, Plandaki tek bir somut bilesen. Referans numarasi (C1, C2...) BURADA verilmez -…, Niyetin acilmis hali - yazilabilir, gosterilebilir, sorgulanabilir., Ag adi -> [(bilesen etiketi, pin anahtari)]. Cozumlemeden once pin anahtarlari,…, Pin anahtarlarini kurulu KiCad kutuphanesine karsi cozer. "#3" pin numarasidir;…, resolve_plan(), _plan_two_resistors() (+3 more)

### Community 49 - "KicadCli"
Cohesion: 0.29
Nodes (7): CliResult, KicadCli, Path, KiCad'in kendi elektriksel kural kontrolu (JSON rapor)., KiCad'in kendi tasarim kurali kontrolu (JSON rapor)., kicad-cli cagrilarini saran ince katman., Sematikten XML netlist. Neyin neye bagli oldugunu buradan ogreniyoruz.

### Community 50 - "PencereTests"
Cohesion: 0.12
Nodes (6): PencereTests, skipUnless, Arka plan isi bitene kadar olay dongusunu cevir., Kilit sadece dugmenin gorunumu degil: `_uygula` kendisi de bakar., Onay diyalogu iptal edilirse hicbir sey yazilmamali., Her test icin TEK bir Tk yorumlayicisi, ayri bir Toplevel penceresi. Test…

### Community 51 - "test_zones.py"
Cohesion: 0.06
Nodes (17): Bir zone'un TEK KATMANDAKI doldurulmus bakiri., Bakir dokum alani (poligon). Iki poligon vardir ve karistirilmamalidir: *…, Bakir alani (mm2). Doldurulmus poligonlarda delikler, poligonun kendisine giren…, Tek bir katmandaki bakir alani., Zone, ZoneFill, CopperAreaMeasurementTests, CopperAreaRuleTests (+9 more)

### Community 52 - "test_propose.py"
Cohesion: 0.18
Nodes (6): GeometryTests, Baglanti ONERISI: uygulamanin "bunlar nasil baglanmali" karari. Burada korunan…, Kanit yoksa oneri de yok - ve bu SESSIZCE olmamali., Onerilmeyen pin, kullaniciya ADIYLA soylenmeli., Telli halde ayni pinler artik 'bos' sayilmamali., SilenceTests

### Community 53 - "Evaluation"
Cohesion: 0.09
Nodes (17): label_of(), Iki degerlendirme arasindaki farki tek sayiya indirir (bkz. modul basi).…, Evaluation, Hakemin bir yerlestirme icin verdigi gercek olcum. Yerlestiriciler vekil…, Siralamada kullanilan anahtar; buyuk olan daha iyidir., Sozluksel siralamayi TEK SAYIYA indirir: pozitif = bu daha iyi. `key` sozluksel…, ModelRanker, Compound (+9 more)

### Community 54 - "read_schematic"
Cohesion: 0.05
Nodes (51): apply_placement(), ApplyPlan, ApplyResult, build_parser(), _drag_map(), _edit_sheet(), main(), optimize_and_apply() (+43 more)

### Community 55 - "Lineer regulator, motor surucu, koruma, sensor, HV (Bolum 4)"
Cohesion: 0.09
Nodes (27): ESD/CMC yerlesim sirasi: konnektor -> ESD -> CMC -> R/C, Lineer regulator, motor surucu, koruma, sensor, HV (Bolum 4), Creepage / clearance ve HV slot genisligi, Elektrolitik kondansator vent bosluğu ve end-seal yasagi, ESD'de belirleyici buyukluk mesafe degil enduktanstir, Gate izi genisligi >= 0.508 mm ve SiC surge korumasi <= 20 mm, Guc izi 0.381 mm/A ve 1 via / 200 mA, IPC-7351B courtyard excess ve govdeler arasi bosluk (+19 more)

### Community 56 - "penalty_of"
Cohesion: 0.09
Nodes (19): overshoot_factor(), penalty_of(), 0-100 arasi kalite skoru. Ceza, bilesen sayisina bolunerek normalize edilir;…, Bir bulgunun skora yazacagi ceza. Kural kendi `weight` degerini verdiyse o…, Ihlalin BUYUKLUGUNE gore ceza carpani (Faz 1b). asim = |measured - limit| /…, OvershootFactorTests, PenaltyOfTests, Kural bazli agirlik (Faz 1a). Skor eskiden yalnizca severity sayiyordu: her… (+11 more)

### Community 57 - "lexicon.py"
Cohesion: 0.16
Nodes (19): build(), build_parser(), Entry, gloss(), harvest(), kapsam(), load(), lookup() (+11 more)

### Community 58 - "ml/collect_design.py: tasarim seviyesi veri"
Cohesion: 0.13
Nodes (20): ml/collect_design.py: tasarim seviyesi veri, Etiket parti medyanina gore HPWL uzerinden, Etiket secimi model seciminden onemli, explore.py: once boyut sonra tohum, Her sira bilgisiz degildir - modeli her yere sokmayin, Kart/grup bazli capraz dogrulama bolmesi, Kart siniri tahmin degil olcum, learned hala auto'yu gecmiyor (+12 more)

### Community 59 - "circuit.py"
Cohesion: 0.16
Nodes (11): i2c_needs_current_source(), i2c_pullup_max_ohms(), i2c_pullup_min_ohms(), i2c_pullup_range(), Devre dogrulugu hesaplari: bilesen DEGERI dogru mu? Mevcut kural tipleri…, Yukselme suresi butcesinin izin verdigi EN BUYUK pull-up direnci., Surucunun sifira cekebilmesi icin gereken EN KUCUK pull-up direnci., 200 pF ustunde duz direnc yetmez (UM10204 7.1). UM10204: 200-400 pF arasi Fast-… (+3 more)

### Community 60 - "load_design"
Cohesion: 0.09
Nodes (38): apply_placement(), discover_boards(), load_design(), locked_refs(), main(), make_evaluator(), Path, Placement (+30 more)

### Community 61 - "ArenaTests"
Cohesion: 0.12
Nodes (7): ArenaTests, Arama ile son olcum ayni koordinatlari gormeli. Kayan noktali bir konum…, Izgara disi adim her denemeyi kural ihlaline dusurur., Cok birimli bilesenin her birimi ayri girdidir. Referansla anahtarlamak U2'nin…, Guc sembolleri pine kaynakli; bagimsiz hareketleri baglantiyi koparir., Netleri birlestiren tasima ucuz olcutle de yakalanmali. Bu delta olculerek…, Govde cakismasi bir UYARIDIR, baglanti kopmasi degil. Sembol tasinirken telleri…

### Community 62 - "DiscreteBuckTests"
Cohesion: 0.23
Nodes (5): DiscreteBuckTests, AYRIK (harici FET'li) tasarim: olcmek yerine SUSMAK. Entegre regulatorde giris…, Ayni karta SW dugumunde bir FET ekler ve tasarimi yeniden kurar., Susmak YETMEZ - gorunmez bir bosluk yine sessiz hatadir., `info` cezasi sifirdir; kapsam disiligi kartin skorunu dusurmemeli.

### Community 63 - "_courtyard"
Cohesion: 0.13
Nodes (8): _courtyard(), CourtyardReadTests, OverlapTests, Icbukey boslukta duran kucuk bir sekil cakismaz., Kenarlar kesismese de icerme cakismadir., Bitisik duran iki courtyard cakismis sayilmaz (clearance_mm: 0.0)., Iki kosegen kose dort koseye acilmali - yoksa sekil dusuyordu., L bicimli courtyard dısbukey kabuga cevrilmemeli.

### Community 65 - "_boxes_overlap"
Cohesion: 0.50
Nodes (3): _boxes_overlap(), Iki sinir kutusu ust uste biniyor mu? Tam temas cakisma SAYILMAZ., 1.27 mm izgarasinda bitisik semboller cok yaygin; tam temas cakisma sayilirsa…

### Community 66 - "komut.py"
Cohesion: 0.08
Nodes (31): Pattern, Baglama, _baglama_ayir(), _baglantilari_dagit(), build_parser(), _dagarcik(), _hedef_olabilir(), _hedef_temizle() (+23 more)

### Community 67 - "compare_additive"
Cohesion: 0.22
Nodes (7): compare_additive(), EKLEME icin kalkan: mevcut devre aynen dursun, yalnizca yenisi eklensin.…, AdditiveShieldTests, Yeni sembol var olan bir tele degerse kalkan yakalamali., ExpectedJoinShieldTests, Tel cizilip baglanmadiysa sessizce gecmemeli., PinKey

### Community 68 - "auto: uretim yerlestiricisi"
Cohesion: 0.12
Nodes (18): Agirlikli skorlama (Evre 1), auto: uretim yerlestiricisi, Bulgu gudumlu cila (refine.polish), auto butce bolusumu (Faz G), Kaynak celiskileri gizlenmedi, parametreye cevrildi, clearance_voltage 6.2x hizlandirma, Degerlendirme maliyeti kartlar arasi ~8000x degisiyor, Uc noktali gerileme korumasi (+10 more)

### Community 69 - "metrics.py"
Cohesion: 0.16
Nodes (17): evals_to_first_gain(), evaluate(), mae(), pairwise_accuracy(), Any, r2(), _ranks(), Metrikler: regresyon dogrulugu VE - asil onemlisi - siralama kalitesi. Bir… (+9 more)

### Community 70 - "schematic.py"
Cohesion: 0.08
Nodes (29): _atom(), _flag(), _lib_extent(), _lib_pins(), _num(), _on_grid(), _properties(), Path (+21 more)

### Community 71 - "WorkerTests"
Cohesion: 0.10
Nodes (4): FrontTests, Canli sematikte yanlis hedef, eski plan ve yari yazma korumalari., Schematic, WorkerTests

### Community 72 - "RidgeModel"
Cohesion: 0.21
Nodes (6): Any, Model, En buyuk mutlak katsayili oznitelikler. Standartlastirilmis uzayda oldugu icin…, Standartlastirilmis ridge regresyon., RidgeModel, ModelTests

### Community 73 - "generate.py"
Cohesion: 0.05
Nodes (59): build_parser(), candidate_sizes(), explore(), explore_from_intent(), main(), plan_variants(), ArgumentParser, Path (+51 more)

### Community 74 - "canli.py"
Cohesion: 0.35
Nodes (16): apply_plan(), board_identity(), check_target(), connection(), describe_connection(), fingerprint(), LivePlan, main() (+8 more)

### Community 75 - "Yuksek hizli ve hassas sinyal arayuzleri (Bolum 3)"
Cohesion: 0.15
Nodes (19): Yuksek hizli ve hassas sinyal arayuzleri (Bolum 3), 20H kurali - CURUTULDU, Diferansiyel cift ayrimi: 5W kurali (3W degil), ADC altinda duzlem bosaltma vs kesintisiz GND celiskisi, 2.4 GHz anten keep-out ve chip anten mm degerleri, BGA decoupling yogunlugu (0.1 uF / 2 guc topu), 50 ohm hat genisligi: CPWG vs mikroserit karistirmasi, DDR3 fly-by topolojisi ve eslestirme butcesi (+11 more)

### Community 76 - "PinRef"
Cohesion: 0.13
Nodes (4): PinRef, Netlist'teki her pini, PCB'deki pad konumuyla eslestirir., Yari-cevre tel uzunlugu (Half-Perimeter Wire Length). Netin tum pinlerini…, Fiziksel konumu cozulmus bir pin.

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
Cohesion: 0.16
Nodes (17): Sozluksel siralama anahtari; BUYUK olan daha iyidir.…, Tek bir deneme: hangi kosullarla, ne cikti., Variant, features_of(), Bir tasarimin yerlestirmeden ONCE bilinen ozellikleri., FEATURE_NAMES ile AYNI sirada oznitelik vektoru. Tohum bilerek yok (bkz. modul…, Bir kesif kosumunu egitim orneklerine cevirir., samples_from_run() (+9 more)

### Community 81 - "EndToEndTests"
Cohesion: 0.13
Nodes (8): EndToEndTests, skipUnless, Regresyon: guc sembolu kalkandan gecemiyordu. Olculdu (2026-08-31): KiCad…, Kalkanin beklenen listesi sanal sembolleri ICERMEMELI. Bu, yukaridaki hatanin…, Reddeden kalkan NEDENINI soylemeli. Olculdu: guc sembolu reddi sirasinda mesaj…, Kalkan kum havuzunda calisir; kullanicinin klasorune kilit birakmaz., Ornek projeyi gecici bir klasore kopyalar (asil dosyaya dokunulmaz)., SandboxProject

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

### Community 87 - "ray_gerilimi"
Cohesion: 0.23
Nodes (6): Net ADINDAN gerilim. Doner: (volt ya da None, nereden bilindigi). Ad bir…, ray_gerilimi(), _sayiya(), +3V3" adli bir agi 3.3 V saymak tahmin degil, adi okumaktir., En onemli test: "VCC 5V'tur" varsayimi 3.3 V'luk kartta yanlis akim…, RayTests

### Community 88 - "ShieldTests"
Cohesion: 0.25
Nodes (5): conn(), Test icin elle baglanti yapisi kurar., Kalkanin dogru degismezi kullandigini dogrular., Otomatik net adlari degisebilir; bolunme ayniysa devre aynidir., ShieldTests

### Community 89 - "SchematicArena"
Cohesion: 0.19
Nodes (6): Sematik uzerinde hizli yerlestirme degerlendirmesi. `refine.polish`in bekledigi…, Yerlestirmeyi taban konumlarla birlestirir (eksikler yerinde kalir). Konumlar…, Kural motorunun gormedigi, tasimaya ozgu riskler., Bir yerlestirmeyi puanlar. Hizli: kicad-cli calistirmaz., _same(), SchematicArena

### Community 90 - "uygula"
Cohesion: 0.16
Nodes (9): Path, Eylemleri sirayla `sch_add.add_symbols`a verir. Kalkan, yedek, kilit kontrolu…, uygula(), Ikinci eylem, birincisinin YAZILMIS halini okumali - yoksa iki plan da ayni…, Isin olcusu sematikteki etiket degil, KiCad'in cikardigi NETLIST'tir: yeni…, Baglama, mevcut aglara pin EKLER; onlardan pin ALMAZ., vcc" diye yazan kullanici "VCC" agina baglanmis olmaz; yazim sematige bakilarak…, Netlist kalkani bunu YAKALAMAZ - yeni ag olusturmak gecerli bir islemdir. Uyari… (+1 more)

### Community 91 - "Model"
Cohesion: 0.15
Nodes (15): Asama 5 - makine ogrenimi altyapisi. Katmanlar bilerek ayri tutuldu; ust katman…, Ridge (L2 cezali) dogrusal regresyon - saf Python. Neden saf Python: proje…, build(), _ensure_registry(), load(), Model, Path, Model sozlesmesi + JSON kaydet/yukle + kayit defteri. Modeller **JSON** olarak… (+7 more)

### Community 92 - "crystal_load_capacitor_f"
Cohesion: 0.24
Nodes (7): crystal_load_capacitor_f(), crystal_load_capacitor_range_f(), Kristalin CL'sini karsilamak icin gereken TEK kondansator degeri., Stray belirsizliginden (2-5 pF) dogan kabul edilebilir aralik. Stray BUYUDUKCE…, CrystalLoadTests, Microchip AN826: CL = C/2 + Cstray, stray 2-5 pF., Stray buyudukce gereken kondansator KUCULUR - aralik yonu bundan.

### Community 93 - "read_board"
Cohesion: 0.06
Nodes (28): BoardParseError, Path, RuntimeError, Kartin kokundeki net tablosu: numara -> ad. NEDEN GEREKLI: iz/via/arc dugumleri…, Kart dosyasi okunamadi. Sessizce bos kart dondurmekten YEGDIR: bos kart butun…, Bir .kicad_pcb dosyasini okur., read_board(), _read_net_table() (+20 more)

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
Cohesion: 0.20
Nodes (12): placer-anneal agent tanimi, Benzetimli tavlama yontemi (anneal), identity / random alt sinir referanslari, Yerlestirme Agent'i Brifingi, Donmus Placer arayuzu (base.py), Sinavi degistiren agent'in sonucu gecersizdir, Sentetik test tezgahi (bench_good / bench_bad), kristal-net-uzunlugu (net_length, XIN/XOUT 12 mm) (+4 more)

### Community 98 - "Devre tipine gore PCB tasarim kurallari - kaynakli derleme"
Cohesion: 0.20
Nodes (10): KiCad'in Python'u PYTHONPATH'i yok sayar (olculmus, 2026-08-30), pcbqa.cmd baslat.py'ye gecti, Devre tipine gore PCB tasarim kurallari - kaynakli derleme, Yol haritasi: agirlikli skorlama, Faz 1a - Agirlik mekanizmasi, Faz 1b - Orantili ceza (ihlal buyuklugune gore), Faz 1c - Kanit gucu agirligi belirler, Mevcut skor formulu (severity-only) (+2 more)

### Community 99 - "app.py"
Cohesion: 0.29
Nodes (9): r"""Onyukleyici - KiCad'in Python'u `PYTHONPATH`'i YOK SAYAR, bu yuzden var.…, diagnose(), _dispatch(), _line(), main(), BAGIMSIZ UYGULAMA - tek giris noktasi. pcbqa tani ortami denetle pcbqa analiz…, Ortami denetler. Doner: (satirlar, engel_sayisi)., run_diagnose() (+1 more)

### Community 100 - "kok_sematik"
Cohesion: 0.21
Nodes (7): Proje metninden kok sematik. Metin ARGUMANDIR, Tk degiskeni degil. tkinter is…, kok_sematik(), KomutError, RuntimeError, Su anki modelimiz" = hedefteki TEK proje. Birden fazla aday varsa secim…, Komut calistirilamadi (hedef sematik bulunamadi gibi)., KokSematikTests

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
Cohesion: 0.12
Nodes (18): BuckConverter, _components_on(), find_buck_converters(), _first_net(), normalize_pin_name(), _pad_xy(), _pins_by_ref(), Alt-devre tanima: karttaki bilinen devre bloklarini topolojiden bulur. Neden… (+10 more)

### Community 106 - "ReaderTests"
Cohesion: 0.15
Nodes (3): R1 90 derece donuk; pinleri govdenin iki yaninda, ayni Y'de olmali., Donusum dogruysa her pin bir capaya oturur. Capa yalnizca tel ucu degildir: bir…, ReaderTests

### Community 107 - "_Node"
Cohesion: 0.20
Nodes (9): _Builder, Tek bir agaci kurar. Histogramlar dugum bazinda yeniden hesaplanir., _cap_value(), _Node, Kume agacinin bir dugumu., Netlist grafigini mantiksal bloklara ayirir. Once "hangi kondansator hangi pine…, 100nF' -> 1e-7. Kondansator buyuklugu, hangi pine ait oldugunu ayirmaya yarar:…, _subtree_refs() (+1 more)

### Community 109 - "Agirliklar kanit gucune gore bantlanir"
Cohesion: 0.15
Nodes (16): Agirliklar kanit gucune gore bantlanir, Kaynaklar arasi celiskiler ve alinan kararlar, IPC-2221B / IPC-7351B, Olcekleme yalnizca kaynak bir formulse, Cogu tavsiyenin sayisi yok, TI AN-2155 (SNVA638A), TI SLVA959B, esd-tvs-konnektore-yakin (proximity, 5 mm, weight 14) (+8 more)

### Community 110 - "GBTModel"
Cohesion: 0.17
Nodes (8): _bin_edges(), GBTModel, _predict_tree(), Any, Model, Gradyan artirmali regresyon agaclari (kare hata)., Hangi oznitelik kac kez bolme icin kullanildi (kaba onem olcusu)., Nicem tabanli kutu sinirlari (artan, tekrarsiz).

### Community 111 - "graphify-bilgilendir.py"
Cohesion: 0.54
Nodes (7): graphify_tazele(), hafiza_anahtarlari(), kabuk(), main(), GRAPHIFY'I BILGILENDIR - her karar, her hata duzeltmesi, her plan sonrasi.…, yaz_hafizalar(), yaz_kayitlar()

### Community 112 - "collect_design.py"
Cohesion: 0.17
Nodes (15): build_parser(), collect(), collect_intent(), CollectError, _design_of(), intent_files(), main(), ArgumentParser (+7 more)

### Community 113 - "verify_against_plan"
Cohesion: 0.26
Nodes (6): KiCad'in netlist'i plani birebir kuruyor mu? (dogrulanan ag, engeller). Ug ayri…, verify_against_plan(), _conn(), Etiket tutmamis: ayni ad iki ayri aga bolunmus., Planda olmayan bir pin aga girmis - sessiz kisa devre., ShieldTests

### Community 114 - "ThreePartTests"
Cohesion: 0.20
Nodes (3): +10V, R1, C1 - hicbiri bagli degil., R1.1-R1.2 onerilirse direnc kisa devre olur. Bu gercekten olmustu: ilk surumde…, ThreePartTests

### Community 115 - "learned - ogrenilmis hamle siralayicisi"
Cohesion: 0.13
Nodes (15): Skorun siniri: skor bir ihlal sayacidir, kalite olcegi degil, Vekil maliyet uydurma - gercek olcumu optimize et, Atomik yazma ve acik-proje korumasi, auto - uretim yerlestiricisi, Bagimliliksizlik ve JSON model dosyalari, Bus iceren sayfalarda optimizasyon kapali, Etiket secimi model seciminden onemli, Gerileme tabani - mevcut kart da bir adaydir (+7 more)

### Community 116 - "f103-usb-swd niyeti"
Cohesion: 0.38
Nodes (7): USB 2.0 diferansiyel empedans 90 ohm +-%15, pcbqa komut seti (tani, kurulum, analiz, uret, kesfet, yerlestir), swd-header sablonu, usb-micro-b sablonu, f103-asgari niyeti, f103-usb-kristal niyeti, f103-usb-swd niyeti

### Community 117 - "RouteTests"
Cohesion: 0.27
Nodes (3): SchWire, Ilk aday baska bir pinin ustunden geciyorsa ikincisi secilir., RouteTests

### Community 118 - "IpcApplyError"
Cohesion: 0.29
Nodes (17): apply(), check_target(), connect(), decode(), digest(), dispatch(), encode(), items() (+9 more)

### Community 119 - "default_rules.yaml - pcbqa varsayilan kurallari"
Cohesion: 0.14
Nodes (15): Beads - AI-native issue tracking, Skorlama yol haritasi - evre durumu (2026-08-28), Sessiz hata sinifi - uretmek olcen katmani denetler, uretim-courtyard-cakisma warning/6'ya cekildi, Korpus kalibrasyonu (19 KiCad demo karti, 2026-08-28), Pad katmanlari okunmuyordu (kalibrasyonun yakaladigi kusur), courtyard-cakisma (courtyard_overlap, warning), default_rules.yaml - pcbqa varsayilan kurallari (+7 more)

### Community 120 - "fb_divider_max_bottom_ohms"
Cohesion: 0.28
Nodes (6): fb_divider_max_bottom_ohms(), fb_divider_range(), Alt bolucu direncinin ust siniri. I_bolucu = Vfb / R2 >= ratio * I_bias -> R2…, `vfb` ve `bias_current_na` beyanlarindan alt direnc ust siniri., FeedbackDividerTests, Richtek AN033: bolucu akimi >= 100 x FB bias akimi.

### Community 121 - "evaluate_design"
Cohesion: 0.20
Nodes (6): evaluate_design(), Bir tasarimi kural motoruyla olcer. Hakemin tek gercek olcutu., EN KRITIK TEST: agirliksiz dosya birebir eski skoru uretmeli., BuckPresetTests, On ayar artik UYARLAMA GEREKTIRMEDEN gercek kartlarda calisiyor., Ad desenleriyle 19-32 bulgu cikiyordu; topolojiyle bir avuc. Olculdu:…

### Community 122 - "load_config"
Cohesion: 0.21
Nodes (11): _as_mapping(), ConfigError, load_config(), Path, RuntimeError, Yapilandirma okuma: YAML varsa YAML, yoksa yaninda duran JSON. ## Neden var…, Yapilandirma dosyasi okunamadi ya da bicimi bozuk., Yapilandirmayi okur. Doner: (veri, json_kullanildi_mi). Bos dosya bos sozluk… (+3 more)

### Community 123 - "Kicad-5be: Eeschema 10.0.4 canli sematik yazmayi uygulamiyor"
Cohesion: 0.36
Nodes (8): Kicad-5be: Eeschema 10.0.4 canli sematik yazmayi uygulamiyor, Kicad-rfz: Kurulumda izinle alinan IPC API + canli sematik yazma, Kicad-6r2: API'siz baglanti - surec-ici SWIG uygulamasi, Kicad-8vp: Canli mod KiCad'in Python'unda calismaz, Kicad-fqn: Bagimsiz uygulama sekli karari, Kicad-i6z: Baslatici PYTHONPATH'e guveniyordu, Kicad-qz5: Canli PCB duzenleme dogrulandi (KiCad 10.0.4), Canli PCB duzenleme calisiyor (KiCad 10.0.4)

### Community 124 - "deger_coz"
Cohesion: 0.27
Nodes (5): deger_coz(), 100nf" -> "100nF", "4u7" -> "4u7", "10" -> None (o bir SAYI). Onek ya da birim…, DegerTests, 10 kapasitor" 10 ADET demektir, 10 farad degil., 10M" mega, "10m" milidir - sadelestirilmis kelimeden okunsaydi ikisi ayni…

### Community 125 - "test_lexicon.py"
Cohesion: 0.05
Nodes (19): BuiltLexiconTests, GlossTests, LookupTests, NormalizeTests, skipUnless, Iki dilli bilesen sozlugu. Bu sozluk ilerideki makine ogreniminin GIRDISI…, Olculdu: alt dizi aramasi 'C' icin 41 onek donduruyordu - gurultu., Uretilmis sozluk - KiCad kurulu makinede. (+11 more)

### Community 126 - "ipc_apply.py"
Cohesion: 0.11
Nodes (26): best_result(), Sozlesme ihlali olmayan ve karti KOTULESTIRMEYEN en iyi sonucu secer. Gerileme…, render(), Result, Score, build_parser(), Candidate, _competitive_placers() (+18 more)

### Community 127 - "graphify-etiketle.py"
Cohesion: 0.50
Nodes (4): main(), Elle verilen topluluk adlarini graph.json'a geri uygular. ## Neden gerekiyor…, Doner: (adlandirilan topluluk, bulunamayan capalar, birlesen adlar)., uygula()

### Community 128 - "decoupling-mesafe (proximity, 10 mm, error)"
Cohesion: 0.14
Nodes (15): decoupling-mesafe (proximity, 10 mm, error), ldo-ams1117-3v3 sablonu, mcu-stm32f103c8 sablonu (LQFP-48 cekirdek blogu), boot0-pulldown (10k), Kosullu cevre pinleri (interfaces), nrst-kondansator (100 nF), ST AN2586, vdd-decoupling (3 x 100 nF) (+7 more)

### Community 130 - "LauncherTests"
Cohesion: 0.05
Nodes (18): CompletedProcess, ArayuzLauncherTests, CommandTableTests, DiagnoseTests, DispatchTests, LauncherTests, skipUnless, Bagimsiz uygulama: tek giris noktasi ve baslatici. Dagitilan sey bu: bir klasor… (+10 more)

### Community 131 - "keep_apart - kaynaklarin 'uzaklastir' dedigi bosluk"
Cohesion: 0.29
Nodes (7): keep_apart - kaynaklarin 'uzaklastir' dedigi bosluk, ROHM 66AN015E, TI SNOA986A, manyetik-sensor-guc-izinden-uzak (keep_apart, 10 mm, weight 4), sensor-bypass-kondansatoru (proximity, 5 mm, weight 12), sensor-pullup-uzak-dursun (keep_apart, >= 10 mm, weight 12), buck_layout - ad degil topoloji

### Community 132 - "ipc_apply: calisan KiCad'e yazma hatti"
Cohesion: 0.29
Nodes (7): Canli duzenleme: sematikte yok, PCB'de var, Canli mod ve API'siz mod, ipc_apply: calisan KiCad'e yazma hatti, Bilinen IPC bug'lari, pcbqa kurulum: izinle alinan API, Duzeltilen yanilgi: sematik komutlari belge turunden bagimsiz, Canli calisirken tek KiCad ornegi

### Community 133 - "CorpusCalibrationTests"
Cohesion: 0.10
Nodes (13): CorpusCalibrationTests, PadLayerTests, PinFunctionTests, skipUnless, Asil kazanc: `function:` seciciSi sematik olmadan da eslesmeli. Aranacak adi…, `uretim` on ayari gercek kartlarda makul davranmali., Ayristirici gercek kartlarin hepsini okuyabilmeli., `uretim` devre tipinden bagimsiz; profesyonel kartlarda yuksek olmali. Olculdu… (+5 more)

### Community 134 - "EndToEndTests"
Cohesion: 0.31
Nodes (4): EndToEndTests, skipUnless, Dongunun varlik sebebi: kucuk kart. Kazanan en buyuk aday olmamali., Skorun neyi yargilamadigi SESSIZ kalmamali.

### Community 136 - "test_mpn.py"
Cohesion: 0.11
Nodes (8): AssignmentTests, Sentetik MPN ve fiyat alanlari. Bu modul sematige TEDARIK VERISI yaziyor ve o…, Ornekte C1'in degeri 'C' - okunamaz, fiyat almamali., Ikinci kez atamak alani COGALTMAMALI., Uydurma veri UYDURMA GORUNMELI., SandboxSchematic, SyntheticMarkerTests, ValueParsingTests

### Community 137 - ".probe"
Cohesion: 0.12
Nodes (7): Uctan uca: buyuk ihlal, kucuk ihlalden daha pahali olmali., Ayni kural, olcekleme kapali -> Faz 1a davranisi., BULGU BASINA ceza; cezalar dogrudan toplanir. Bulgu sayisina bolmek sart:…, Bulgu basina ceza, ihlal buyudukce artmali. Faz 1b'nin butun gerekcesi bu:…, Olcekleme cezayi yalnizca BUYUTUR, asla azaltmaz., ScaledScoreTests, WeightedScoreTests

### Community 138 - "test_sch_connect.py"
Cohesion: 0.19
Nodes (7): allocate_units(), (referans yuvasi, birim) ciftleri. Cok birimli sembollerde (74LS125 -> 4 kapi +…, ConnectionParsingTests, FakeSymbol, Asama 4f devami: cok birim, footprint dogrulama ve BAGLAMA. `test_sch_add.py`…, 74LS125 -> 4 kapi + guc birimi; 6 istek iki referansa dagilir., UnitAllocationTests

### Community 139 - "bundle.py"
Cohesion: 0.26
Nodes (11): build(), build_parser(), main(), ArgumentParser, Path, Calisma zamani kopyalarini uretir: YAML -> JSON. python -m pcbqa.bundle # uret…, Paketle birlikte dagitilan YAML dosyalari., JSON metni - bicimi SABIT olmali ki `--check` gurultu uretmesin. (+3 more)

### Community 140 - "rules_with"
Cohesion: 0.22
Nodes (7): gap(), KeepApartPlacementTests, Path, Catisan bir kisit pesinde kartin geri kalani bozulmamali. Kristali USB…, bench kurallari + ek bir kural iceren gecici kural dosyasi., Ucuz bir kisit skora girince auto onu saglar. Bu, keep_apart'in ucu uca…, rules_with()

### Community 141 - "Pad bakir sekli tam modelleme (copper_shape)"
Cohesion: 0.33
Nodes (6): Ayrik sicak dongu: altigen akim yolu, Ayrik regulator: yanlis olcmektense olcmemek, Bakir kurallari yonlendirilmemis kartta sessizce atlanir, Pad bakir sekli tam modelleme (copper_shape), geom.segment_distance, Zone okuma - tahmin fazla iyimserdi

### Community 143 - "ExploreResult"
Cohesion: 0.22
Nodes (3): ExploreResult, GenerateResult, Uretimin sonucu - her adim ayri ayri gorunur.

### Community 144 - "test_subcircuit.py"
Cohesion: 0.09
Nodes (19): BuckLayoutRuleTests, demos_available(), find_demo(), NoFalsePositiveTests, Path, skipUnless, Alt-devre tanima: karttaki regulatorleri TOPOLOJIDEN bulmak. Neden gerekli: on…, jetson / U69: VIN pini "V_{IN}" yaziyor. Normalizasyon olmadan vin_net None… (+11 more)

### Community 145 - "Intent"
Cohesion: 0.33
Nodes (4): Intent, EndToEndTests, skipUnless, Kucuk bir niyetten gercek proje - KiCad kendi netlist'iyle dogruluyor.

### Community 146 - "label_of"
Cohesion: 0.31
Nodes (5): _clamp(), label_of(), Parti medyanina gore kalite. Buyuk olan daha iyi. Skor farki baskindir…, LabelTests, Kaliteden odun verilmez: dusuk skorlu ama kisa telli kart yenilmeli.

### Community 147 - "fit_model"
Cohesion: 0.28
Nodes (9): cross_validate(), fit_model(), main(), Any, Egitim hedefi. Hangisini sectiginiz MODEL SECIMINDEN daha onemli - olculdu.…, Adi verilen modeli egitir ve semasini icine yazar., Gruplu k-kat capraz dogrulama; ortalama metrikleri dondurur., _row() (+1 more)

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

### Community 153 - "pcbqa/__init__.py"
Cohesion: 0.17
Nodes (18): pcbqa - KiCad tasarimlari icin salt-okunur kalite/uygunluk analizi (Asama 0)., find_kicad_cli(), KicadCliError, RuntimeError, `kicad-cli` sarmalayicisi. Asama 0'in tamami bu arac uzerinden calisir; IPC API…, kicad-cli'yi bulur. Sirasiyla: parametre, ortam degiskeni, PATH, bilinen…, kicad_available(), Masaustu arayuzu. Arayuzun goruntusu sinanmaz - sinanan sey GUVENLIK KILIDIDIR:… (+10 more)

### Community 155 - "post-checkout"
Cohesion: 0.50
Nodes (3): post-checkout script, GRAPHIFY_REBUILD_LOG, PYTHONHASHSEED

### Community 156 - "ValueClassificationTests"
Cohesion: 0.22
Nodes (5): skipUnless, Cozulemeyen deger HER IKI kovaya sayilir - yanlilik yon degistirmesin.…, Kaynagin GERCEKTEN konustugu olcek: 29 guc pinli bir ray., RealBoardTests, ValueClassificationTests

### Community 157 - "runtime_twin"
Cohesion: 0.22
Nodes (7): Bir YAML dosyasinin calisma zamani JSON esi., runtime_twin(), yaml_available(), BundleTests, API'siz baglanti: yapilandirma tasinabilirligi + surec-ici uygulama. ## Korunan…, Kullanicinin KENDI kural dosyasi da KiCad icinde okunabilmeli., YAML duzeltilip JSON eski kalirsa KiCad ICINDE eski kural kosar. Bu testin…

### Community 158 - "decoupling_count kurali - mesafe degil adet"
Cohesion: 0.67
Nodes (3): decoupling_count kurali - mesafe degil adet, Cozulemeyen deger her iki kovaya sayilir, TI SPRABV2

### Community 174 - "_Convergence"
Cohesion: 0.29
Nodes (3): _Convergence, Bir asamanin ne zaman devredecegini soyler. ## Neden basit bir "iyilesme yok"…, Her asama kendi sayacini tutar.

### Community 175 - "place_point"
Cohesion: 0.31
Nodes (5): place_point(), Kutuphane noktasini sayfa ofsetine cevirir. Modul basligindaki deneysel olarak…, Kutuphane -> sayfa donusumu (deneysel olarak secildi, bkz. schematic.py)., Ters sirada uygulanirsa 90 derecede farkli sonuc cikar., TransformTests

### Community 176 - "Schematic"
Cohesion: 0.25
Nodes (6): _key(), Schematic, Kural motorunun anlayacagi hafif bir Schematic goruntusu uretir. Yalnizca…, Bir sembol ORNEGININ tasimaya hazir on-hesaplanmis hali. Anahtar UUID'dir,…, _SymbolInfo, _WireInfo

### Community 177 - "DagarcikTests"
Cohesion: 0.15
Nodes (5): DagarcikTests, Tablolar buyudukce bozulur; bu testler bozulmayi ilk kosuda yakalar., Bir kere oldu: "on" Ingilizce edat diye dolguya kondu ve Turkce "on adet"…, Baglama pin NUMARASI ister; tabloya tur eklenip `uclar` unutulursa…, toprak" gecerli bir hedeftir; yapi sozcugu sayilsaydi "VCC ile toprak arasina"…

### Community 178 - "RedTests"
Cohesion: 0.18
Nodes (4): Reddedilmesi gerekenler. Bir cozumleyicinin degeri buradadir., Anlamadim" ile "henuz yapmiyorum" ayri seylerdir., Kaynagi olmayan varsayilan (or. "kondansator = 100nF") yazilmaz., RedTests

### Community 179 - "Decoupling max mesafe < 6.35 mm"
Cohesion: 0.29
Nodes (7): placer-force agent tanimi, Cok-agentli yerlestirici sinavi kurallari, Kuvvet tabanli yerlestirme yontemi, Decoupling max mesafe < 6.35 mm, Decoupling icin lambda/40 kurali, Genel IC bypass -> besleme pini <= 5 mm, 'Yakin olmali' tavsiyelerinin sayisallastirilmasi (27 madde)

### Community 180 - "Board"
Cohesion: 0.29
Nodes (3): Board, Bilesenlerin kapladigi alan, kart yuzune gore ayri ayri. Cift tarafli kartlarda…, Bir netin toplam bakir alani (mm2). UYARI - bu bir FAZLA TAHMINDIR: ustuste…

### Community 182 - "FakeSymbol"
Cohesion: 0.38
Nodes (4): FakeSymbol, _plan_with(), Kutuphane gerektirmeden referans on eki tasiyan en kucuk sembol., RefTests

### Community 183 - "noise_floor"
Cohesion: 0.53
Nodes (3): noise_floor(), Ayni oznitelik vektorunun etiket yayilimi: modelin ASAMAYACAGI taban. Tohum…, NoiseFloorTests

### Community 185 - "_cholesky_solve"
Cohesion: 0.40
Nodes (4): _cholesky_solve(), Sutun ortalamalari ve standart sapmalari (sifir sapma -> 1)., A simetrik pozitif tanimli iken A x = b cozumu., _standardize()

### Community 190 - "test_circuit.py"
Cohesion: 0.21
Nodes (7): decoupling_counts(), (gereken 0.1 uF sayisi, gereken bulk sayisi) - TI SPRABV2 6. TI: her 2 guc topu…, DecouplingCountTests, Devre dogrulugu hesaplari (`pcbqa/circuit.py`). Kural motoru simdiye kadar…, TI SPRABV2 6: her 2 guc topu icin 0.1 uF, her ~10 icin bulk., Oranlar TI SPRABV2'nin kendi sayilari olmali., SourceRatioTests

### Community 193 - "GercekKartTests"
Cohesion: 0.22
Nodes (4): GercekKartTests, skipUnless, Bos hucrenin yaninda sebep yoksa kullanici hatamizi goremez., samples/pic_programmer C4'un degeri "0" - fiyat uydurulmaz. Bu satir bir…

### Community 196 - "YorumlayiciTests"
Cohesion: 0.29
Nodes (3): Bunlar Tk penceresi ACMADAN kosar., KiCad'in Python'unda tkinter yok; ayirt edebilmeliyiz., YorumlayiciTests

### Community 197 - "Dataset"
Cohesion: 0.09
Nodes (15): Dataset, Any, Path, Veri kumesi: JSONL depolama + KART BAZLI bolme. Alan bagimsizdir - burada ne…, Gruplari (kartlari) butun halinde egitim/test olarak ayirir., Gruplu k-kat capraz dogrulama. Az grup varsa kat sayisi kisilir., Ornekleri aday listesine gore gruplar (siralama metrikleri icin)., JSONL: ilk satir baslik, sonraki her satir bir ornek. (+7 more)

### Community 287 - "thermal.py"
Cohesion: 0.27
Nodes (9): is_area_dependent(), junction_temp_c(), Termal hesaplar: bakir alanindan jonksiyon sicakligina. `ipc2221.py` ile ayni…, Tj'yi sinirda tutan EN KUCUK bakir alani. None doner: * paketin alan…, Bu paket icin theta_JA'nin bakir alanina bagimliligi OLCULMUS mu?, Verilen bakir alaninda theta_JA (C/W). Ara degerler log10(alan) uzerinde…, Tj = TA + P * theta_JA(alan). Kararli hal, tek isi kaynagi. Komsu bilesenlerin…, required_area_mm2() (+1 more)

### Community 336 - "Connection"
Cohesion: 0.20
Nodes (7): _expected_joins(), Kalkana "bu pin SU pinle ayni aga girmeli" listesi. Ag adiyla baglanirken…, Connection, pins_on_net(), Tek bir baglama istegi: hangi pin, neye., Hedef bir pin mi (`R1.2`), yoksa ag adi mi (`VCC`)?, Bir ag adina bugun bagli olan pinler. Ad karsilastirmasi hosgorulu: KiCad kok…

## Ambiguous Edges - Review These
- `Benzetimli tavlama yontemi (anneal)` → `Vekil maliyet uydurma - gercek olcumu optimize et`  [AMBIGUOUS]
  .claude/agents/placer-anneal.md · relation: conceptually_related_to
- `f103-usb-kristal niyeti` → `Kristal -> MCU pini mesafesi: sayisal deger BULUNAMADI`  [AMBIGUOUS]
  pcbqa/samples/niyetler/f103-usb-kristal.yaml · relation: conceptually_related_to

## Knowledge Gaps
- **59 isolated node(s):** `AllCadOtomation`, `Calisma anlasmasi graphify entegre`, `Canli pcb arayuzu ve dogrulama`, `Canli sematik nightly dogrulandi`, `Graphify kurulumu ve hafiza akisi` (+54 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1477 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **33 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Benzetimli tavlama yontemi (anneal)` and `Vekil maliyet uydurma - gercek olcumu optimize et`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `f103-usb-kristal niyeti` and `Kristal -> MCU pini mesafesi: sayisal deger BULUNAMADI`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `load_design()` connect `load_design` to `Design`, `CorpusCalibrationTests`, `.routed`, `Repertoire`, `.probe`, `load_rules`, `test_subcircuit.py`, `SyntheticDiscreteBuckTests`, `__main__.py`, `ValueClassificationTests`, `test_decoupling_count.py`, `refine.py`, `MoveFeaturizer`, `run`, `swig_apply.py`, `ComponentValueRuleTests`, `test_zones.py`, `penalty_of`, `test_circuit.py`, `.of`, `DiscreteBuckTests`, `generate.py`, `canli.py`, `test_collect_design.py`, `read_board`, `evaluate_design`, `ipc_apply.py`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `PlacementContext` connect `PlacementContext` to `refine.py`, `MoveFeaturizer`, `generate.py`, `Repertoire`, `swig_apply.py`, `_Model`, `codex.py`, `load_design`, `ipc_apply.py`, `_Engine`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `Design` connect `Design` to `MoveFeaturizer`, `find_buck_converters`, `PinRef`, `PlacementContext`, `collect_design.py`, `SyntheticDiscreteBuckTests`, `codex.py`, `Board`, `__main__.py`, `evaluate_design`, `load_design`, `ipc_apply.py`, `.of`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 45 inferred relationships involving `PlacementContext` (e.g. with `SimulatedAnnealing` and `Auto`) actually correct?**
  _`PlacementContext` has 45 INFERRED edges - model-reasoned connections that need verification._
- **Are the 42 inferred relationships involving `Schematic` (e.g. with `junctions_for()` and `_net_check()`) actually correct?**
  _`Schematic` has 42 INFERRED edges - model-reasoned connections that need verification._