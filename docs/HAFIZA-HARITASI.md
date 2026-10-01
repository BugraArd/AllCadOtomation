# Hafıza haritası — projedeki tüm hafıza, ayar ve belge dosyaları

> Bu sayfa projedeki **bütün** hafıza ve yapılandırma dosyalarını tek yerde
> listeler (kullanıcı talimatı, 2026-10-01). Dosyaların kendisi taşınmadı:
> aşağıdaki "neden orada" sütunu her birinin hangi aracın onu nerede aradığını
> söyler. Taşınabilen her belge zaten bu `docs/` klasöründedir (Kicad-41r).

## Hangi bilgi nerede — kısa yol

| Ne arıyorsunuz | Nereye bakılır |
|---|---|
| Kalıcı kararlar, hafızalar (kanonik) | `bd recall <anahtar>`, `bd memories <kelime>` |
| Açık işler | `bd ready`, `bd list --status=open` |
| Aynı bilginin okunabilir dosya hali | `docs/hafiza/*.md` (üretilmiş) |
| Ajan kuralları + yapı + hafıza özeti | `AGENTS.md` |
| Tam geliştirme bağlamı | `docs/HANDOFF.md` |
| Koddaki ilişkiler, kavramlar | `graphify explain "<kavram>"` |
| Kod geçmişi | `git log` |

## 1. Bu klasörde (`docs/`) — taşınabilen her şey

| Dosya | İçerik | Elle düzenlenir mi |
|---|---|---|
| `HANDOFF.md` | Tam geliştirme bağlamı, ölçülmüş kararlar, tuzaklar | evet |
| `KURULUM.md` | Son kullanıcı kurulumu, kısayol, canlı mod | evet |
| `AGENT_BRIEF.md` | Yerleştirici alt-ajanların brifingi | evet |
| `yol-haritasi-skorlama.md` | Yol haritası | evet |
| `devre-modeli-ve-dogrulama.md` | Devre grafı, 3 seviyeli doğrulama | evet |
| `duzeltme-siralama.md` | ML ilk deneyi: düzeltme adayı sıralama | evet |
| `tasarim-kurallari/` | Kural eşiklerinin kaynakları (5 dosya) | evet |
| `paketler/` | Paket kararları, devir ve açık iş raporları (4 dosya) | evet |
| `hafiza/` | Beads hafızaları + açık/kapalı kayıtlar (20 dosya) | **hayır** — `python .claude/graphify-bilgilendir.py` üretir |
| `HAFIZA-HARITASI.md` | Bu sayfa | evet |

## 2. Depo kökünde kalmak zorunda olanlar

| Yer | İçerik | Neden orada |
|---|---|---|
| `AGENTS.md` | Ajanlar için tek kural/yapı/hafıza dosyası | Codex kökteki `AGENTS.md`'yi okur |
| `CLAUDE.md` | Yalnızca `@AGENTS.md` içe aktarımı | Claude Code kökteki `CLAUDE.md`'yi okur |
| `README.md` | İnsanlar için genel bakış | GitHub depo vitrini |
| `pcbqa/README.md` | Uygulamanın ayrıntılı kullanımı | Paket vitrini |

## 3. Araç klasörleri

### `.beads/` — kanonik hafıza ve iş takibi (Beads, 12 MB)

| Dosya | İçerik |
|---|---|
| `embeddeddolt/` | **Asıl veritabanı** (Dolt): işler, kararlar, `bd remember` hafızaları |
| `issues.jsonl`, `interactions.jsonl` | Pasif dışa aktarım (okumak için; kaynak değil) |
| `backup/` | Dolt yedek parçaları (`*.darc`) |
| `config.yaml`, `metadata.json` | Beads ayarları (önek `Kicad`) |
| `hooks/` | Beads git kancaları |
| `README.md` | Beads'in kendi açıklaması |

Neden orada: `bd` veritabanını çalışma klasöründen yukarı doğru `.beads/`
arayarak bulur. Taşınırsa her komut ve her kanca `--db` ister.

### `.claude/` — Claude Code ayarları ve hafıza kancaları

| Dosya | İçerik |
|---|---|
| `settings.json` | Kancalar: SessionStart (`bd prime`, graphify durumu/etiketleri), PreToolUse hatırlatmaları |
| `settings.local.json` | Yerel izinler (git'e girmez) |
| `graphify-bilgilendir.py` | Beads → `docs/hafiza/` → `graphify update` → etiketler |
| `graphify-durum.py` | Oturum başında grafik yaşı/boyutu |
| `graphify-etiketle.py`, `graphify-etiketler.json` | Topluluk adlarını çapa düğümlerine göre geri uygular |
| `agents/placer-*.md` | Üç yerleştirici alt-ajanın tanımı |
| `worktrees/` | Alt-ajanların geçici git çalışma ağaçları |

Neden orada: Claude Code proje ayarlarını, kancaları ve alt-ajanları yalnızca
kökteki `.claude/` altında arar.

### `.git/` — sürüm geçmişi

- Uzak depo: `origin` → `github.com/BugraArd/AllCadOtomation`
- Beads senkronu `refs/dolt/data` üzerinden bu depoyu kullanır.
- `graph.json` için birleştirme sürücüsü: `merge.graphify.driver`
  (`.gitattributes` içinde `merge=graphify`).

Neden orada: git deposu, çalışma ağacının kökündeki `.git/` klasörüdür.
Taşınırsa geçmiş, dallar ve uzak senkron kaybolur.

### Diğerleri

| Yer | İçerik | Neden orada |
|---|---|---|
| `.codex/config.toml`, `hooks.json` | Codex ayarları ve kancaları | Codex kökte arar |
| `.agents/skills/beads/SKILL.md` | Codex için Beads becerisi | Codex beceri yolu |
| `graphify-out/graph.json` | Bilgi grafiği (git'te izlenir) | graphify varsayılan çıktısı |
| `graphify-out/GRAPH_REPORT.md` | Grafik raporu; tarihli klasörlerde eski raporlar | graphify üretir |
| `graphify-out/manifest.json`, `cache/`, `.graphify_*` | Artımlı güncelleme önbelleği | graphify üretir |

## 4. Depo dışında

| Yer | İçerik |
|---|---|
| `%USERPROFILE%\.claude\projects\C--Users-ardaa-OneDrive-Desktop-Kicad\memory\` | Claude Code oto-hafızası; tek kaydı "proje hafızası AGENTS.md'de" yönlendirmesidir |
| `%USERPROFILE%\.claude\CLAUDE.md` | Kullanıcının tüm projeler için genel talimatı (graphify tetiği) |

## Hafıza akışı (tek yönlü)

```
bd create / bd remember                 -> .beads/ (kanonik)
python .claude/graphify-bilgilendir.py  -> docs/hafiza/*.md (üretilmiş)
                                           graphify update .  -> graphify-out/
                                           graphify-etiketle.py
```
