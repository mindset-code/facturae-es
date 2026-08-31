#!/usr/bin/env python3
"""Una factura de principio a fin, como la emitiría un despacho.

Recorre el caso real completo: construir la factura desde objetos, comprobar
que los totales cuadran, generar el XML, volver a leerlo para verificar lo
emitido, y guardar el JSON junto al XML para poder regenerarlo idéntico más
adelante.

Se ejecuta tal cual, sin argumentos y sin dependencias::

    python examples/facturacion_completa.py
"""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from pathlib import Path

from facturae_es import (
    IRPF,
    IVA,
    VERSION_ESQUEMA,
    Direccion,
    Emisor,
    Factura,
    FacturaInvalida,
    Impuesto,
    Linea,
    Receptor,
    a_dict,
    desde_dict,
    generar,
)

NS = {"f": "http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xml"}
SALIDA = Path(tempfile.gettempdir())


def separador(titulo: str) -> None:
    print()
    print(titulo)
    print("-" * len(titulo))


# --------------------------------------------------------------------------- #
# 1. La factura                                                                 #
# --------------------------------------------------------------------------- #
separador("1. Construir la factura")

emisor = Emisor(
    nif="B12345674",
    nombre="Talleres Ejemplo SL",
    direccion=Direccion(
        calle="Calle Mayor 1",
        codigo_postal="08001",
        poblacion="Barcelona",
        provincia="Barcelona",
    ),
)

receptor = Receptor(
    nif="A58818501",
    nombre="Cliente Ejemplo SA",
    direccion=Direccion(
        calle="Gran Via 100",
        codigo_postal="28013",
        poblacion="Madrid",
        provincia="Madrid",
    ),
)

factura = Factura(
    numero="001",
    serie="A",
    fecha=date(2026, 1, 15),
    descripcion="Servicios de consultoría de enero",
    emisor=emisor,
    receptor=receptor,
    lineas=[
        # Un servicio profesional: lleva IVA repercutido y IRPF retenido.
        Linea(
            descripcion="Consultoría técnica",
            cantidad=Decimal("10"),
            precio_unitario=Decimal("100"),
            unidad="horas",
            impuestos=[Impuesto(IVA, Decimal("21")), Impuesto(IRPF, Decimal("15"))],
        ),
        # Una licencia: solo IVA. Sin `impuestos` se aplica el 21 % por defecto.
        Linea(
            descripcion="Licencia de mantenimiento",
            precio_unitario=Decimal("250"),
        ),
    ],
)

print(f"  Factura {factura.serie}{factura.numero} de {factura.fecha}")
print(f"  {factura.emisor.nombre} -> {factura.receptor.nombre}")

# --------------------------------------------------------------------------- #
# 2. Los totales salen de las líneas, no se piden                               #
# --------------------------------------------------------------------------- #
separador("2. Totales derivados")

for linea in factura.lineas:
    print(f"  {linea.descripcion:<28} {linea.cantidad:>5} x {linea.precio_unitario:>8}"
          f" = {linea.bruto:>9}")

print(f"\n  Base imponible                              {factura.total_bruto:>9}")
for impuesto, base, cuota in factura.impuestos_repercutidos():
    print(f"  + impuesto {impuesto.codigo} al {impuesto.tipo}% sobre {base:>9} "
          f"= {cuota:>9}")
for impuesto, base, cuota in factura.impuestos_retenidos():
    print(f"  - impuesto {impuesto.codigo} al {impuesto.tipo}% sobre {base:>9} "
          f"= {cuota:>9}")
print(f"  {'=' * 52}")
print(f"  TOTAL                                       {factura.total:>9} "
      f"{factura.moneda}")

# Comprobación explícita: el IRPF se RESTA, los demás se suman.
assert factura.total == (
    factura.total_bruto + factura.total_repercutido - factura.total_retenido
)
print("\n  El IRPF se resta y el IVA se suma. Cuadra por construcción:")
print("  no hay forma de pasar un total que no se derive de las líneas.")

# --------------------------------------------------------------------------- #
# 3. El XML                                                                     #
# --------------------------------------------------------------------------- #
separador("3. Generar el XML de Facturae")

xml = generar(factura)
destino_xml = SALIDA / "factura-A001.xml"
destino_xml.write_text(xml, encoding="utf-8")

print(f"  Escrito {destino_xml} ({len(xml)} bytes, esquema {VERSION_ESQUEMA})")

# --------------------------------------------------------------------------- #
# 4. Verificar lo emitido leyéndolo de vuelta                                   #
# --------------------------------------------------------------------------- #
separador("4. Releer el XML y comprobar los importes")

raiz = ET.fromstring(xml)
print(f"  Raíz: {raiz.tag.split('}')[-1]}")
for etiqueta in ("TotalGrossAmount", "TotalTaxOutputs", "TotalTaxesWithheld",
                 "InvoiceTotal"):
    nodo = raiz.find(f".//f:{etiqueta}", NS)
    print(f"  {etiqueta:<20} {nodo.text}")

assert raiz.find(".//f:InvoiceTotal", NS).text == str(factura.total)
print("\n  Lo que dice el XML es lo que calculó el modelo.")

# --------------------------------------------------------------------------- #
# 5. Guardar la entrada junto a la salida                                       #
# --------------------------------------------------------------------------- #
separador("5. Ida y vuelta por JSON")

import json  # noqa: E402  (aquí, para que se vea dónde entra en juego)

datos = a_dict(factura)
destino_json = SALIDA / "factura-A001.json"
destino_json.write_text(
    json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(f"  Escrito {destino_json}")

reconstruida = desde_dict(json.loads(destino_json.read_text(encoding="utf-8")))
assert generar(reconstruida) == xml
print("  Regenerar el XML desde ese JSON da EXACTAMENTE el mismo fichero.")
print("  Por eso merece la pena archivar los dos: el XML es lo que se entrega,")
print("  y el JSON es lo que permite reproducirlo sin conservar el código.")

# --------------------------------------------------------------------------- #
# 6. Lo que la biblioteca rechaza                                               #
# --------------------------------------------------------------------------- #
separador("6. Errores que se detectan antes de emitir")

casos = [
    (
        "código postal de cuatro dígitos",
        lambda: Direccion("Calle Mayor 1", "8001", "Barcelona", "Barcelona"),
    ),
    (
        "país en alfa-2 en vez de alfa-3",
        lambda: Direccion("Rue 1", "75001", "Paris", "Paris", pais="FR"),
    ),
    (
        "línea sin impuestos",
        lambda: Linea(descripcion="Algo", impuestos=[]),
    ),
    (
        "el mismo impuesto dos veces en una línea",
        lambda: Linea(
            descripcion="Algo",
            impuestos=[Impuesto(IVA, Decimal("21")), Impuesto(IVA, Decimal("10"))],
        ),
    ),
    (
        "persona física sin apellido",
        lambda: Emisor(
            nif="12345678Z",
            nombre="Juan",
            direccion=Direccion("Calle 1", "28001", "Madrid", "Madrid"),
            tipo_persona="F",
        ),
    ),
]

for etiqueta, construir in casos:
    try:
        construir()
    except FacturaInvalida as e:
        print(f"  {etiqueta}:")
        print(f"      {e}")
    else:
        raise AssertionError(f"se esperaba que fallara: {etiqueta}")

# --------------------------------------------------------------------------- #
# 7. Lo que falta para presentarla                                              #
# --------------------------------------------------------------------------- #
separador("7. Lo que esto NO hace")

print("  El XML no va firmado. Facturae exige una firma XAdES para presentarlo")
print("  en FACe, y firmar necesita un certificado y una biblioteca de firma:")
print("  queda fuera del alcance de esta, que genera el documento.")
print()
print("  Tampoco calcula la huella encadenada que VERI*FACTU exige a los")
print("  sistemas de facturación. Eso es pyverifactu-huella.")

print()
print("Listo.")
