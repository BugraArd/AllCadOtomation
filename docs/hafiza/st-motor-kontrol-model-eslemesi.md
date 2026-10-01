# St motor kontrol model eslemesi

> Beads kalici hafizasi (`bd recall st-motor-kontrol-model-eslemesi`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

ST MOTOR CONTROL BOARDS DESCRIPTION -> PCBQA ESLEMESI (kullanici girdisi, 2026-09-22)

Kaynak: ST wiki "Motor Control Boards Description", descVersion 3 (SDK 6.1.0) ve
4 (SDK 6.2.0). Kullanici tam metni oturuma yapistirdi; asagisi cikarilan model.

ST'NIN KATMANLARI (pcbqa karsiligi):
  Board type: control / power / inverter / bridge   -> pcbqa'da YOK (tek kart)
  Feature    (amac: CurrentSensing, VBusSensing...) -> pcbqa'da YOK (eksik katman)
  HW variant (uygulama: ThreeShunt_AmplifiedCurrents) -> pcbqa sablonu = BU
  Signal     (PWM_CHU_H; adi gorevini ve dogasini belirler) -> pcbqa'da duz ag adi
  Pin/terminal object: name + cost(0..10) + help    -> pcbqa'da YOK

KRITIK: pcbqa sablonu ST'nin HW VARIANT'ina denk. Ustundeki FEATURE katmani yok.
Bu yuzden "CurrentSensing gerekiyor" denip alternatif uygulamalar siralanamiyor,
ayni amacin iki uygulamasi arasindaki DISLAMA (concurrent) ifade edilemiyor.

SINYALLER BAGIMSIZ DEGIL - ST acikca soyluyor. Pin planlayicisinin cozmesi
gereken kisit turleri:
  1. Ayni cevre birimi ornegi: 6 PWM sinyali TEK advanced timer'da
  2. Kanal baglama: faz U<->CH1, V<->CH2, W<->CH3; high<->CHx, low<->CHxN
  3. Yetenek: advanced timer (tamamlayici cikis+dead time+break); Hall/quadrature
     cozebilen general-purpose timer (Hall: ayni timer'in CH1,CH2,CH3)
  4. Capraz ozellik: OC_TRIGGER / DP_TRIGGER, PWM'i ureten AYNI timer'in
     BREAKIN/BREAKIN2 girisine gitmeli. Iki ayri feature tek timer secimine bagli.
  5. Diskalifiye: SWD calinamaz; UART cifti tek USART orneginde

COST ALANI (ST'nin en ucuz iyi fikri): bir sinyali tasiyabilecek birden cok pin
varsa cost=0 "hazir", cost>0 "jumper/lehim koprusu/0R gerekir" + help metni.
"Zero cost olanlar varsayilan bagli." pcbqa'da bunu almak, cozucunun secimini
ACIKLANABILIR yapar - kullaniciya "bu pini sectim cunku digeri lehim ister" denir.

DOGRULANABILIR FORMULLER (uydurma degil, kaynakli - rules katmanina girer):
  V_ADC = opAmpGain * offsetNetworkAttenuation * V_shunt + polarizationOffset
  Dahili op-amp'te: V_ADC = opAmpGain * (offsetNetworkAttenuation*V_shunt
                                          + rawPolarizationOffset)
  Kontrol: amplifyingNetworkImax'ta V_ADC, [0, Vref] araliginda kaliyor mu?
  Profiler: Rs = (Rmeasure - resistorOffset)/2
  Shunt gucu: P = I^2*R  vs  amplifyingNetworkPrating

ST TABLOSUNDA HATA VAR - KOPYALANMAMALI: MotorControlConnector tablosunda MC13
"PWM_CHW_L, PWM_CHU_EN" yaziyor; MC5=PWM_CHU_EN, MC9=PWM_CHV_EN oldugu icin
MC13 PWM_CHW_EN olmali. Bu tablo ice alinirsa duzeltilerek alinmali.

ST'NIN KOPYALANMAMASI GEREKEN MUGLAKLIGI: "pin/terminal dizisinde birden cok
eleman varsa ya hepsi ayni anda bagli ya da her biri alternatif ya da karisimi."
Bu belirsiz. pcbqa alternatifi ACIKCA isaretlemeli.

VERSIYONLAMA FIKRI: ST format versiyonu (descVersion) ile icerik versiyonunu
(contentVersion N.M; minor=hata duzeltmesi, major=yeni ozellik tarifi) AYIRIYOR.
pcbqa sablonlarinda su an tek "version: 1" var; ayni ayrim alinabilir.
