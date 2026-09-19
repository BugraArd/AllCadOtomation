# Netlistte gorunmeyeni netlistte arama

> Beads kalici hafizasi (`bd recall netlistte-gorunmeyeni-netlistte-arama`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

SINIF HATA: NETLIST'TE GORUNMEYENI NETLIST'TE ARAMA (2026-08-31)

KiCad netlist'i SANAL sembolleri (#PWR, #FLG) HIC yazmaz. Ne bilesen olarak
gorunurler, ne de pinleri dugum olarak. Bunu iki kez ayri yerde unuttuk:

1) connect.py hakemi: '#PWR01.1 R1.1 C1.1' agini dogrularken netlist'te
   #PWR01.1 pinini aradi -> DOGRU bir telleme reddedildi.
   Cozum: guc icin agin ADINA bak (NetCheck.power_name); KiCad agi guc
   sembolunun degeriyle adlandirir.

2) sch_add kalkani: beklenen eklenenler listesine '#PWR2'yi koydu ->
   'set(added) == set(expected_added)' HER ZAMAN dustu, hicbir guc sembolu
   eklenemedi. Olculdu: power:+24V eklendikten sonra netlist bilesen kumesi
   17 -> 17, hic degismiyor.
   Cozum: beklenen listesinden '#' ile baslayanlari cikar.

KURAL: netlist tabanli bir dogrulama yazarken once sor - bu sey netlist'te
GORUNUYOR MU? Gorunmuyorsa dogrulamayi baska bir kanittan kur (ag adi,
dosya okumasi), yoksa gecmesi mumkun olmayan bir sart koymus olursun.

YAN DERS: red mesaji BOS kalmamali. sch_add yalnizca regrouped/removed/lost
basiyordu; bu durumda ucu de bos oldugu icin ekranda gerekcesiz bir
'KALKAN REDDETTI:' kaliyordu. Artik diff.describe() + details() basiyor.
