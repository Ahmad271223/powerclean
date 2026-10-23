"""Gemeinsame PDF-Grundlagen für serverseitige PDFs.

- Eingebettete TrueType-Schrift (Pflicht für PDF/A; die Standard-Schrift Helvetica wäre nicht eingebettet).
- Umwandlung einer Rechnung in PDF/A-3 mit eingebetteter E-Rechnungs-XML (ZUGFeRD 2.x / Factur-X, Profil EN 16931):
  Anhang factur-x.xml mit AFRelationship, /AF-Verweis im Katalog, XMP-Metadaten mit PDF/A-Kennung und
  Factur-X-Erweiterungsschema, sRGB-Ausgabeprofil (OutputIntent).
"""
from __future__ import annotations

import io
import os
from datetime import datetime, timezone

import pikepdf
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

SCHRIFT = "Vera"
SCHRIFT_FETT = "VeraBd"
ERZEUGER = "Stundenzettel Pro"
_registriert = False


def schrift_registrieren() -> None:
    """Bitstream Vera (liegt reportlab bei, freie Lizenz) als eingebettete Schrift registrieren."""
    global _registriert
    if _registriert:
        return
    ordner = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    pdfmetrics.registerFont(TTFont(SCHRIFT, os.path.join(ordner, "Vera.ttf")))
    pdfmetrics.registerFont(TTFont(SCHRIFT_FETT, os.path.join(ordner, "VeraBd.ttf")))
    _registriert = True


def _xml_text(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def xmp_paket(titel: str, autor: str, erstellt: datetime, faktur_x: bool) -> bytes:
    """XMP-Metadaten: PDF/A-3b, Dublin Core, und bei Factur-X das Erweiterungsschema mit den vier fx-Eigenschaften."""
    zeit = erstellt.strftime("%Y-%m-%dT%H:%M:%SZ")
    teile = [
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>',
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
        '<rdf:Description rdf:about="" xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"><pdfaid:part>3</pdfaid:part><pdfaid:conformance>B</pdfaid:conformance></rdf:Description>',
        f'<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title><rdf:Alt><rdf:li xml:lang="x-default">{_xml_text(titel)}</rdf:li></rdf:Alt></dc:title>'
        f'<dc:creator><rdf:Seq><rdf:li>{_xml_text(autor)}</rdf:li></rdf:Seq></dc:creator></rdf:Description>',
        f'<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/"><xmp:CreatorTool>{ERZEUGER}</xmp:CreatorTool><xmp:CreateDate>{zeit}</xmp:CreateDate><xmp:ModifyDate>{zeit}</xmp:ModifyDate></rdf:Description>',
        f'<rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/"><pdf:Producer>{ERZEUGER}</pdf:Producer></rdf:Description>',
    ]
    if faktur_x:
        eigenschaften = [("DocumentFileName", "Name der eingebetteten XML-Rechnung"), ("DocumentType", "Art des Dokuments (INVOICE)"),
                         ("Version", "Version des Factur-X-Schemas"), ("ConformanceLevel", "Profil der eingebetteten XML-Rechnung")]
        li = "".join(f'<rdf:li rdf:parseType="Resource"><pdfaProperty:name>{n}</pdfaProperty:name><pdfaProperty:valueType>Text</pdfaProperty:valueType>'
                     f'<pdfaProperty:category>external</pdfaProperty:category><pdfaProperty:description>{d}</pdfaProperty:description></rdf:li>' for n, d in eigenschaften)
        teile.append(
            '<rdf:Description rdf:about="" xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/" xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#" '
            'xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#"><pdfaExtension:schemas><rdf:Bag><rdf:li rdf:parseType="Resource">'
            '<pdfaSchema:schema>Factur-X PDFA Extension Schema</pdfaSchema:schema><pdfaSchema:namespaceURI>urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#</pdfaSchema:namespaceURI>'
            f'<pdfaSchema:prefix>fx</pdfaSchema:prefix><pdfaSchema:property><rdf:Seq>{li}</rdf:Seq></pdfaSchema:property></rdf:li></rdf:Bag></pdfaExtension:schemas></rdf:Description>')
        teile.append('<rdf:Description rdf:about="" xmlns:fx="urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"><fx:DocumentType>INVOICE</fx:DocumentType>'
                     '<fx:DocumentFileName>factur-x.xml</fx:DocumentFileName><fx:Version>1.0</fx:Version><fx:ConformanceLevel>EN 16931</fx:ConformanceLevel></rdf:Description>')
    teile.append('</rdf:RDF></x:xmpmeta>')
    teile.append('<?xpacket end="w"?>')
    return "\n".join(teile).encode("utf-8")


def pdfa3_mit_xml(pdf_bytes: bytes, xml_bytes: bytes | None, titel: str, autor: str) -> bytes:
    """PDF (reportlab, nur eingebettete Schriften) in PDF/A-3b umwandeln; mit XML wird daraus ein ZUGFeRD/Factur-X-Hybrid."""
    jetzt = datetime.now(timezone.utc).replace(microsecond=0)
    pdf = pikepdf.open(io.BytesIO(pdf_bytes))
    datum = jetzt.strftime("D:%Y%m%d%H%M%SZ")
    pdf.docinfo["/Title"] = titel
    pdf.docinfo["/Author"] = autor
    pdf.docinfo["/Creator"] = ERZEUGER
    pdf.docinfo["/Producer"] = ERZEUGER
    pdf.docinfo["/CreationDate"] = datum
    pdf.docinfo["/ModDate"] = datum

    if xml_bytes is not None:
        anhang = pikepdf.AttachedFileSpec(pdf, xml_bytes, description="Factur-X/ZUGFeRD-Rechnung (EN 16931)", filename="factur-x.xml", mime_type="text/xml")
        anhang.obj["/AFRelationship"] = pikepdf.Name("/Data")
        pdf.attachments["factur-x.xml"] = anhang
        datei = anhang.obj["/EF"]["/F"]
        datei["/Subtype"] = pikepdf.Name("/text#2Fxml")
        params = datei.get("/Params", pikepdf.Dictionary())
        params["/ModDate"] = pikepdf.String(datum)
        params["/Size"] = len(xml_bytes)
        datei["/Params"] = params
        pdf.Root["/AF"] = pikepdf.Array([anhang.obj])

    from PIL import ImageCms
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    profil = pdf.make_stream(icc)
    profil["/N"] = 3
    absicht = pikepdf.Dictionary({
        "/Type": pikepdf.Name("/OutputIntent"), "/S": pikepdf.Name("/GTS_PDFA1"),
        "/OutputConditionIdentifier": pikepdf.String("sRGB IEC61966-2.1"), "/Info": pikepdf.String("sRGB IEC61966-2.1"),
        "/RegistryName": pikepdf.String("http://www.color.org"), "/DestOutputProfile": profil,
    })
    pdf.Root["/OutputIntents"] = pikepdf.Array([pdf.make_indirect(absicht)])
    pdf.Root["/Metadata"] = pdf.make_stream(xmp_paket(titel, autor, jetzt, faktur_x=xml_bytes is not None),
                                            Type=pikepdf.Name("/Metadata"), Subtype=pikepdf.Name("/XML"))
    aus = io.BytesIO()
    pdf.save(aus, min_version="1.7", fix_metadata_version=False)
    return aus.getvalue()
