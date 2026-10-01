# Evre 3 uretken tasarim fazlama

> Beads kalici hafizasi (`bd recall evre-3-uretken-tasarim-fazlama`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

EVRE 3 FAZLAMASI - uretken tasarim (2026-08-28)

HEDEF: sistem otomatik devre olusturup PCB'ye aktarsin, sonra ML ile
iyilestirsin. ML'e gecis OLCUMLE kapilanir.

3a BITTI - niyet + sablon + surucu:
  intent.py (niyet YAML -> insa plani), templates/ (6 sablon), generate.py
  (plandan SIFIRDAN KiCad projesi -> pcb_sync -> auto -> skor).
  Kalkan: 'KiCad'in kendi netlist'i plani birebir kuruyor mu'.
3b BITTI - varyant dongusu (explore.py):
  Secim (skor, -hata, -uyari, -ALAN, -HPWL). Kazanan 40x30, tek atislik
  generate'in sectiginden %31 kucuk. Yonlendirme karari: dis autorouter YOK
  (kicad-cli'de DSN/SES yok).
3c BITTI - veri toplama (ml/collect_design.py + samples/niyetler/ 7 niyet):
  Veri ml/dataset.py bicimini paylasiyor; grup=niyet, parti=kesif kosumu.
  Etiket parti MEDYANINA gore (skor doydugu icin ham skor kullanilamaz).
  Tohum BILEREK oznitelik degil -> gurultu tabani olculebilir oluyor.
  Lisans zorunlu (LM5116 emsali).

*** 3d KAPISI ACIK DEGIL - OLCULDU (en onemli sonuc) ***
  Varyant siralayici SU AN OGRENMIYOR. Grup bazli 3 kat CV:
    temel cizgi (mean): ikili dogruluk 0.500
    ridge:              0.422
    gbt:                0.495
  Yani yazi tura. Sebep olculdu: varyansin ~%69'u TOHUM (aciklanabilir ust
  sinir %31.4). Butceyi 6->20 sn cikarmak yayilimi AZALTMADI (std 13->25),
  yani gurultu 'yakinsamamis arama' degil auto'nun kendi dogasi.

  SONRAKI ADIM (Kicad-a27): etiketi K tohum uzerinden ORTALA. Model tek
  kosumu tahmin etmeye calisiyor; tahmin edilebilir olan KOSULUN
  ORTALAMASIDIR. Sinyal varsa orada gorunur. Ikinci aday: veri kucuk
  (7 grup/56 ornek) ve 7 niyetin 6'si ayni MCU - sablon kutuphanesi
  buyumeden topoloji cesitliligi gelmez.

  KURAL: bu olcum yapilmadan model YAZILMAZ (learned yerlestirici dersi).

ACIK BEADS: Kicad-a27 (3d kapisi, P1), Kicad-4ro (courtyard mikron esigi,
P2), Kicad-ywm (ipek cakismasi, P3), Kicad-xpi (ayrik sicak dongu, P3).

DURUM: 586 test. Korpus medyan 95.9, ceyrekler 80.7/95.9/100.0.
