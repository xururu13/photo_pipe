# ── Генерация XMP-сайдкаров ───────────────────────────────────────────────────

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


# Регистрация пространств имён (чтобы ET не генерировал ns0: ns1: ...)
ET.register_namespace("x", "adobe:ns:meta/")
ET.register_namespace("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
ET.register_namespace("xmp", "http://ns.adobe.com/xap/1.0/")


def generate_xmp(rating: int) -> str:
    """Генерирует XML-строку XMP с рейтингом для Capture One."""
    rating = max(1, min(5, rating))

    xmpmeta = ET.Element("x:xmpmeta", {"xmlns:x": "adobe:ns:meta/"})
    rdf = ET.SubElement(xmpmeta, "rdf:RDF", {
        "xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    })
    ET.SubElement(rdf, "rdf:Description", {
        "rdf:about": "",
        "xmlns:xmp": "http://ns.adobe.com/xap/1.0/",
        "xmp:Rating": str(rating),
    })

    ET.indent(xmpmeta, space="  ")
    xml_str = ET.tostring(xmpmeta, encoding="unicode", xml_declaration=True)
    return xml_str + "\n"


def write_xmp(photo_path: Path, rating: int, dry_run: bool = False) -> Path | None:
    """Записывает XMP-сайдкар рядом с фото. Возвращает путь к файлу или None."""
    xmp_path = photo_path.parent / f"{photo_path.stem}.xmp"

    if dry_run:
        return xmp_path

    xml_content = generate_xmp(rating)
    xmp_path.write_text(xml_content, encoding="utf-8")
    return xmp_path
