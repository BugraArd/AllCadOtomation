"""Seviye 1 - KiCad'in kendi kontrolleri, uygulamanin icinden.

    kicad-cli sch erc                     -> elektriksel kural kontrolu
    kicad-cli pcb drc --schematic-parity  -> tasarim kurallari + kart/sematik
                                             baglanti esligi
    kicad-cli sch export netlist          -> diger seviyelerin girdisi

KiCad'in GUI'sinde bu uc kontrol zaten var; burada uygulamanin otomatik
akisina (dogrula / uret / kesfet) baglanir ve sonuclari ayni Finding
bicimine cevrilir. Kaynak etiketleri: kicad-erc, kicad-drc, kicad-parite.
"""

from __future__ import annotations

from pathlib import Path

from ..kicadcli import KicadCli, KicadCliError, describe_violation, load_violations
from ..rules import Finding
from .sonuc import SeviyeSonucu, bulgu

_SEVIYE = {"error": "error", "warning": "warning", "exclusion": "info", "info": "info"}


def _bulgular(path: Path | None, kaynak_secici) -> list[Finding]:
    out: list[Finding] = []
    for item in load_violations(path) if path else []:
        severity, code, text = describe_violation(item)
        if severity == "ignore":
            continue
        # refs bos birakilir: KiCad aciklamasindan ("Pad 2 [GND] of U1")
        # referans cikarmak dil ve surume bagli, guvenilir degil.
        out.append(bulgu(code, _SEVIYE.get(severity, "warning"), text or code,
                         source=kaynak_secici(item), rule_type=code))
    return out


def seviye1(
    sematik: Path | None,
    kart: Path | None,
    calisma: Path,
    cli: KicadCli | None = None,
) -> SeviyeSonucu:
    sonuc = SeviyeSonucu(1, "KiCad ERC / DRC / netlist")
    if sematik is None and kart is None:
        sonuc.calisti = False
        sonuc.atlanma_nedeni = "ne sematik ne kart var"
        return sonuc
    try:
        cli = cli or KicadCli()
        sonuc.ekler["kicad"] = cli.version()
    except KicadCliError as exc:
        sonuc.calisti = False
        sonuc.atlanma_nedeni = f"kicad-cli bulunamadi: {exc}"
        return sonuc

    calisma = Path(calisma)
    calisma.mkdir(parents=True, exist_ok=True)

    if sematik is not None:
        net = cli.export_netlist(sematik, calisma / "netlist.xml")
        sonuc.ekler["netlist"] = str(net.output_path) if net.output_path else None
        if not net.ok or net.output_path is None:
            sonuc.bulgular.append(bulgu(
                "netlist-uretilemedi", "error",
                f"netlist disa aktarilamadi: {(net.stderr or net.stdout).strip()[:200]}",
                source="kicad-cli"))
        erc = cli.erc(sematik, calisma / "erc.json")
        sonuc.ekler["erc"] = str(erc.output_path) if erc.output_path else None
        if erc.output_path is None:
            sonuc.bulgular.append(bulgu("erc-calismadi", "error",
                                        f"ERC raporu uretilemedi: {erc.stderr.strip()[:200]}",
                                        source="kicad-erc"))
        sonuc.bulgular += _bulgular(erc.output_path, lambda _i: "kicad-erc")
        sonuc.ekler["erc_ihlal"] = len(load_violations(erc.output_path)) if erc.output_path else None

    if kart is not None:
        # Sematik varsa parite de denetlenir: kartin hedef devreyle ayni
        # baglantilari tasidigini KiCad'in kendisi olcer.
        parite = sematik is not None and sematik.parent == kart.parent
        drc = cli.drc(kart, calisma / "drc.json", schematic_parity=parite)
        sonuc.ekler["drc"] = str(drc.output_path) if drc.output_path else None
        sonuc.ekler["parite_denetlendi"] = parite
        if drc.output_path is None:
            sonuc.bulgular.append(bulgu("drc-calismadi", "error",
                                        f"DRC raporu uretilemedi: {drc.stderr.strip()[:200]}",
                                        source="kicad-drc"))
        sonuc.bulgular += _bulgular(
            drc.output_path,
            lambda i: "kicad-parite" if i.get("_group") == "schematic_parity" else "kicad-drc")
    return sonuc
