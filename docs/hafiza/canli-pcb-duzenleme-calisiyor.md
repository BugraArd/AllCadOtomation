# Canli pcb duzenleme calisiyor

> Beads kalici hafizasi (`bd recall canli-pcb-duzenleme-calisiyor`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

CANLI PCB DUZENLEME CALISIYOR - KiCad 10.0.4 (olculmus 2026-08-30)

Sematikte yok (bkz. sematik-canli-yazma-mumkun-degil) ama PCB'de VAR:
  GetItems(KOT_PCB_FOOTPRINT) -> 18 oge okundu
  board.begin_commit / update_items / push_commit -> kabul, J1 1 mm tasindi
  python -m pcbqa.ipc_apply --board <kart> --apply -> 16 footprint CANLI
    tasindi, kilitli olanlar atlandi, KiCad undo gecmisine TEK islem girdi

Yani kullanicinin istedigi 'ben bakarken arac calissin, hatasina Ctrl+Z ile
mudahale edeyim' akisi PCB tarafinda gerceklesiyor. Urunun asil degeri de
orada (yerlestirme, skor, yonlendirme).

ONEMLI DUZELTME: 'bagimsiz editor API sunucusuna kaydolmuyor' tespitim
YANLISTI. Tek basina calisan pcbnew.exe soketi kendisi bariniyor. Onceki
eeschema denemesinde kicad.exe soketi zaten tutuyordu - cakismaydi.
KURAL: canli calisirken ayni anda TEK KiCad ornegi acik olsun.

kipy API notu: Vector2(x=,y=) yok; Vector2.from_xy() / from_xy_mm() kullan.
