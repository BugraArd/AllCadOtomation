# Canli mod ve sematik api

> Beads kalici hafizasi (`bd recall canli-mod-ve-sematik-api`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

CANLI MOD (KiCad ACIKKEN calisma) - 2026-08-29

KULLANICI ISTEGI: KiCad acikken degisiklik yapilabilsin ki es zamanli
calisirken kullanici aracin hatasina MUDAHALE edebilsin. Ayrica API iznini
her seferinde istemek yeni kullaniciya zorlayici - KURULUMDA bir kez alinsin.

*** ONCEKI TESPITIM YANLISTI, DUZELTILDI ***
'KiCad 10'da sematik API'si yok' demistim. YANLIS. schematic_commands diye
AYRI bir dosya yok ama GEREK DE YOK: common/commands/editor_commands BELGE
TURUNDEN BAGIMSIZ ve sunlari iceriyor:
  CreateItems / UpdateItems / DeleteItems / GetItems
  ParseAndCreateItemsFromString  <- s-expression metnini DOGRUDAN alir
  BeginCommit / EndCommit        <- tek, GERI ALINABILIR islem
  RefreshEditor / SaveDocument / RevertDocument
Ve base_types_pb2'de DOCTYPE_SCHEMATIC = 1 tanimli.
BeginCommit/EndCommit tam olarak kullanicinin istedigi seyi verir: arac ne
yaparsa KiCad'in kendi GERI ALMA yiginina girer -> Ctrl+Z ile mudahale.

ENGEL: kipy 0.7.1'in ust duzey  sarmalayicisi BOZUK (kendi
protobuf'unda BusEntryType yok). 0.7.1 en guncel surum. COZUM: KiCadClient.
send(command, response_type) HAM bir kanal - sarmalayici atlanip genel
komutlar dogrudan gonderilebilir.

HENUZ DOGRULANMADI: KiCad 10.0.4'un SUNUCUSU bu komutlari sematik icin
gercekten uyguluyor mu? Sonda hazir: scratchpad/sonda_canli.py - baglanti,
acik sematik belgesi, oge okuma, ve BOS commit ile yazma yolunu olcer.
API acilir acilmaz kosturulacak.

KURULUM (pcbqa/kurulum.py, 'pcbqa kurulum'):
  api.enable_server'i IZINLE acar (izin = --uygula bayragi; once ne
  degisecegi gosterilir). KULLANICININ KENDI YAPILANDIRMASINA DOKUNAN TEK
  YER, kurallari sert:
   - KiCad CALISIYORSA yazma (KiCad ayarlari bellekte tutar ve CIKARKEN
     dosyanin uzerine yazar -> degisiklik kaybolur). Surec adi+pid soylenir.
   - YALNIZCA api.enable_server degisir; tema/kutuphane yollari/Turkce
     anahtarlar aynen kalir (test sozlugun TAMAMINI karsilastirir).
   - yedek + atomik yazma + geri okuyup dogrulama + --geri-al
  Sonra KiCad YENIDEN BASLATILMALI (soket acilista baglanir).

IKI MOD (ikisi de gecerli, dagitim hikayesi DEGISMEDI):
  API'siz mod (varsayilan, sifir ayar): dosyaya yazar, pcbnew ile uygular,
    KiCad acikken dosyaya yazmaz.
  Canli mod (kurulum ister): acik belgeye dokunur, Ctrl+Z ile geri alinir,
    sematige canli mudahalenin TEK yolu.
'pcbqa tani' hangi modun acik oldugunu bildirir.
