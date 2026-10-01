# Tek ai dosyasi agents md

> Beads kalici hafizasi (`bd recall tek-ai-dosyasi-agents-md`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

TEK AI DOSYASI: AGENTS.md (kullanici talimati, 2026-10-01, Kicad-2qj)

KULLANICI DEDI: gitattributes, gitignore, AGENTS.md, CLAUDE.md, README.md cok bos;
uygulamanin temel yapisi, ozelliklerin yeri ve islevi, graphify onemli bilgileri,
test listesi, Python proje yapisi ve KiCad surumu yazilsin; Serena yapidan
kaldirilsin (beads + graphify ile devam); yapay zekanin okuyacagi hafiza ve yapi
bolumleri TEK dosyada birlestirilsin.

KARAR:
 * AGENTS.md = tek AI dosyasi: oturum acilisi, calisma kurallari (graphify
   anlasmasi, karar kayitlari, git politikasi, kod kurallari), surumler, proje
   yapisi, ozellik haritasi (komut -> modul -> islev), mimari, test listesi,
   graphify ozeti, kalici hafiza ozeti (bd anahtarlari), acik isler, yonetilen
   Beads/Codex/graphify bloklari.
 * CLAUDE.md yalnizca '@AGENTS.md' ice aktarimi. bd setup claude / graphify
   claude install yeniden kosarsa CLAUDE.md'ye blok ekleyebilir; ayni bloklar
   AGENTS.md'de var, silinebilir.
 * Beads KANONIK kalir; AGENTS.md bolum 8 bir DIZINDIR (bd recall ile okunur).
   Celiskide Beads dogrudur. 'Ikinci kayit yeri acilmaz' ilkesi korunur: ozet
   ayrinti tasimaz, anahtar + tek satir.
 * Claude dosya hafizasindaki 4 kayit (skorlama yol haritasi, olculmus olumsuz
   sonuclar, graphify anlasmasi, hafiza sistemi) AGENTS.md bolum 1.1 ve 8'e
   tasindi; dosya hafizasi tek yonlendirme kaydina indirildi.
 * Kalicilik artik: AGENTS.md (CLAUDE.md ice aktarir) + Beads + SessionStart
   kancalari. Onceki 'uc yer' listesindeki 'ajanin kendi dosya hafizasi'
   yerine AGENTS.md gecti.
 * README.md (kok) insanlar icin genel bakis; pcbqa/README.md ayrintili kullanim.
 * .gitignore bolumlere ayrildi; eklenenler: KiCad kilit (~*.lck, *.lck),
   _autosave-*, *-bak, Python onbellekleri, Thumbs.db/desktop.ini/.DS_Store.
 * .gitattributes: * text=auto, *.py/KiCad eol=lf, *.cmd/*.bat/*.ps1 eol=crlf,
   ikili dosyalar, merge=graphify korundu, uretilmis dosyalar linguist-generated.
   Olculdu: depo icerigi tamamen LF; sahte degisiklik uretmedi.

BULGU: pcbqa/samples/pic_programmer/~pic_programmer.kicad_pro.lck ilk commit'te
(c2f6d7d) yanlislikla izlenmis; makine+kullanici adi iceriyor. git rm --cached
ile takipten cikarildi (disk dosyasi duruyor; testler kopyalarda zaten siliyor).

SERENA: proje .serena/ klasoru 2026-09-08'de YENIDEN olusmustu (yalniz ayar,
memories bos, git'te izlenmiyor) - silindi. Kaynak: kullanici genelindeki
~/.codex/config.toml [mcp_servers.serena] - calisan 'serena start-mcp-server
--context=codex' sureci goruldu. Kullanici geneli ayar diger projeleri etkiler;
kullaniciya soruldu, dokunulmadi. .gitignore'da .serena/ koruma satiri kaldi.
