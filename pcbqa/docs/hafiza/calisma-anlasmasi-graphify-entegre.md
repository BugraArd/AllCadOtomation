# Calisma anlasmasi graphify entegre

> Beads kalici hafizasi (`bd recall calisma-anlasmasi-graphify-entegre`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

CALISMA ANLASMASI - GRAPHIFY ILE ENTEGRE (kullanici talimati, 2026-08-31)

KULLANICI DEDI: 'bundan sonra graphify ile entegre calis, her yeni kararda her
hata duzeltmesinde graphify'a bilgilendirme yap, her gelecek plani yaptigimizda
graphify'a ekle, her oturum acildiginda ya da konustugumuzda da unutma'.

ZORUNLU UC TETIK:
  1. her yeni KARAR (mimari, esik, bagimlilik, arayuz, urun sekli)
  2. her HATA DUZELTMESI (kok sebep + basarisiz denemeler + dogrulama)
  3. her GELECEK PLANI (evre, yol haritasi, siradaki is)

AKIS (tek yonlu, ikinci kayit yeri acilmaz):
  bd create / bd remember          -> beads KANONIK kaynak
  python .claude/graphify-bilgilendir.py
      beads -> pcbqa/docs/hafiza/*.md
      graphify update .
      .claude/graphify-etiketle.py
pcbqa/docs/hafiza/ ELLE DUZENLENMEZ - betik uretir.

SINIR: bilgilendir betigi yeni kaydin METNINI dosyaya dusurur ve aranabilir
yapar, ama KAVRAM DUGUMU ve GEREKCE KENARLARI olusturmaz - onlar anlamsal
tarama ister (/graphify --update, ALT-AJAN gerektirir, kullanici onayi ile).
Betik bunu her kosuda soyler; 'guncellendi' deyip gecmez.

KOD SORUSUNDAN ONCE GRAFIGE SOR:
  graphify explain '<kavram>'   en isabetlisi
  graphify path '<A>' '<B>'
  graphify query '<soru>' --budget N

KALICILIK - kural UC yerde, cunku tek yer unutulur:
  1) CLAUDE.md '## Calisma Anlasmasi' (yonetilen bloklarin DISINDA)
  2) bu beads hafizasi
  3) ajanin kendi dosya hafizasi
Ayrica MEKANIZMA: SessionStart kancalari her oturumda etiketleri geri uygular
ve grafik durumunu basar; PreToolUse kancalari her Read/Grep oncesi hatirlatir.

KULLANICI TEYIDI (2026-09-07): Serena MCP gerekli degil; bu proje icin kurma/kullanma. Graphify proje boyunca kullanilacak. Kural AGENTS.md ve CLAUDE.md dosyalarina eklendi. Kalici hafiza yalnizca Beads'tedir; ayri ajan hafiza dosyasi acilmaz. Dogrulama: graphify 0.9.53 ve explain pcbqa_handoff_sessiz_hata_sinifi calisti (7 baglanti). Sandbox Windows Store Python erisimini engelliyor; yetkili ortamda calisti, yeniden kurulum gerekmiyor. Windows bd.cmd cok satirli argumani ilk satira indirdi; tam metin hook kaydindan geri alindi ve dogrudan bd.exe ile yazildi. Gorev: Kicad-vdb.
