# Serena kaldirildi graphify eklendi

> Beads kalici hafizasi (`bd recall serena-kaldirildi-graphify-eklendi`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

SERENA KALDIRILDI, GRAPHIFY EKLENDI - 2026-08-30

KULLANICI ISTEGI: 'onceki agentlar biraz kotu gibi ozellikle hafiza isinde
olan' -> Serena MCP sunucusu kaldirildi.

YAPILANLAR:
  claude mcp remove serena -s user   (C:\Users\ardaa\.claude.json guncellendi)
  uv tool install graphifyy          (0.9.53; graphify + graphify-mcp)
  graphify install --platform claude (GENEL kapsam, --project DEGIL)
    -> C:\Users\ardaa\.claude\skills\graphify\SKILL.md
    -> C:\Users\ardaa\.claude\CLAUDE.md olusturuldu (yalnizca graphify blogu)

NEDEN GENEL KAPSAM: --project secenegi projenin SURUM KONTROLUNDEKI
.claude/CLAUDE.md dosyasina always-on blok ekliyor. O dosyada yonetilen Beads
blogu ve karar kayitlari var; disaridan blok eklenmesi istenmez.

SERENA HAFIZASI KAYBOLMADI: .serena/memories/ icerigi HANDOFF.md ve README.md
kopyasiydi (dosyalarin kendisi bunu soyluyor). Ozgun bilgi yoktu.
.serena/ klasoru git'te IZLENIYOR ve hala duruyor - silinmedi, kullaniciya
soruldu.

Sarkan tek atif duzeltildi: pcbqa/docs/yol-haritasi-skorlama.md 'Serena
hafizasi: scoring_roadmap' -> 'bd memories skorlama'.

PROJENIN HAFIZA SISTEMI BEADS'TIR (CLAUDE.md: 'bd remember kullan').
