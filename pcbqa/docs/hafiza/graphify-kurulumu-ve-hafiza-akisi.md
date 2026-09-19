# Graphify kurulumu ve hafiza akisi

> Beads kalici hafizasi (`bd recall graphify-kurulumu-ve-hafiza-akisi`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

GRAPHIFY KURULUMU VE HAFIZA AKISI - 2026-08-31 (tamamlandi)

SERENA KALDIRILDI (MCP sunucusu + .serena/ klasoru, git indeksinden de).
Icerigi HANDOFF.md/README.md kopyasiydi; ozgun bilgi kaybolmadi.

GRAFIK: 3423 dugum, 7350 kenar, 174 topluluk.
  3006 AST (tree-sitter, YEREL, 0 jeton) + 417 anlamsal (4 alt-ajan, 664.798 jeton)
  Anlamsal dugumlerin 417/417'si GEREKCE (rationale) tasiyor - asil deger bu.
  Kimlik cakismasi 0: alt-ajanlara verilen ID kurali AST ile uyustu.
  Saglik: 336 sarkan, 480 cokmus kenar (AST'nin grafik disi sembol referanslari).

HER OTURUMDA ACIK - dort katman:
  1) CLAUDE.md '## graphify' bolumu (graphify claude install)
  2) PreToolUse kancalari (Bash|Grep, Read|Glob): hatirlatma ENJEKTE eder,
     ENGELLEMEZ - olculdu, cikis 0
  3) SessionStart: 'python .claude/graphify-durum.py' - BUNU BEN YAZDIM.
     graphify'in kendi kurulumu grafigin VAR oldugunu soyluyor ama NE KADAR
     BAYAT oldugunu soylemiyor. Betik dugum/kenar/topluluk, yas ve commit
     edilmemis .py sayisini basar.
  4) graphify hook install: post-commit/post-checkout otomatik tazeleme

BEADS BILGISI DOSYAYA AKTARILDI: pcbqa/docs/hafiza/ (8 hafiza ayri dosya +
beads-acik/kapali-kayitlar.md). Beads Dolt'ta duruyor, dosya tarayicisi goremez.
Tazeleme mantigi: bd recall + bd list --json.
DIKKAT: 'bd' bir npm shim'i; Windows'ta subprocess uzantisiz bulamaz, bd.cmd ver.

TUZAKLAR:
  * graph.json node-link biciminde - kenarlar 'links' altinda, 'edges' DEGIL.
    'edges' diye okuyunca sessizce 0 cikiyor.
  * Kumeleme her yeniden kurulumda BASTAN kosuyor; topluluk NUMARALARI degisiyor,
    elle verilen adlar eskiyor. Adlari numaraya degil icerige gore yeniden ver.
  * graphify claude install --project projenin SURUM KONTROLUNDEKI CLAUDE.md'sine
    yazar. Genel kapsam (--project'siz) ~/.claude altina yazar.

KANIT: 'graphify explain pcbqa_handoff_sessiz_hata_sinifi' -> HANDOFF'un dort
ayri bolumundeki ALTI gercek hatayi tek kavram altinda bagliyor. Boyle bir liste
hicbir dosyada yok; grafik onu kendi kurdu.
