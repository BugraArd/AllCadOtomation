# Sematik canli yazma mumkun degil

> Beads kalici hafizasi (`bd recall sematik-canli-yazma-mumkun-degil`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

SEMATIGE CANLI YAZMA - KiCad 10.0.4'te YOK (olculmus, 2026-08-30)

KANIT (sematik editoru PROJE YONETICISINDEN acikken):
  GetOpenDocuments(DOCTYPE_SCHEMATIC) -> calisiyor
  GetItems (dogru header, KOT_SCH_LINE) -> 'no handler available'
  BeginCommit -> mesajin HIC ALANI YOK; belgeye baglanamiyor, yanit gelmiyor
  _pcbnew.dll'de GetItems 65 kez, _eeschema.dll'de 1 kez geciyor
  Eeschema diskteki dis degisikligi de fark etmiyor

CANLI SONDALAMA KiCad'i IKI KEZ COKERTTI (bicimsiz/askida kalan istekler).
Dosya her ikisinde de saglam kaldi. KURAL: canli sondalama yapma; yapilacaksa
yalnizca tam bicimli istek, her adimda surec kontrolu, her komut icin taze
baglanti (bir hata kanali bozuyor).

CALISAN YOL: sematik editoru KAPALIYKEN dosyaya yaz (proje yoneticisi acik
kalabilir, allow_open_project gerekir), sonra editoru ac. Uc parcayi boyle
telledim; KiCad'in netlist'i dogruladi:
  +10V -> C1.1, R1.1     Net-(C1-Pad2) -> C1.2, R1.2

HENUZ OLCULMEDI: PCB tarafinda canli duzenleme. Handler sayilari orada var
gorunuyor - soz vermeden once olc.
