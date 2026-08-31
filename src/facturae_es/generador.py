"""Genera el XML Facturae 3.2.2.

Dos cosas que este modulo trata con cuidado porque son las que invalidan un
fichero sin decir por que:

1. **El orden.** El esquema oficial usa ``xs:sequence`` en todas partes, asi
   que el orden de los elementos forma parte del contrato. Un ``InvoiceClass``
   escrito antes de ``InvoiceDocumentType`` invalida el fichero aunque el
   contenido sea correcto. Aqui cada bloque se escribe en la secuencia exacta
   del XSD, y un test lo compara contra el esquema descargado de
   facturae.gob.es.

2. **El espacio de nombres.** TODOS los elementos van en el namespace de
   Facturae, no solo la raiz. Poner el prefijo a mano en la raiz y olvidarlo en
   los hijos produce un XML que parece correcto al leerlo y que ningun
   validador acepta.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from decimal import Decimal

from .importes import formatear
from .modelo import Direccion, Factura, TipoPersona, _Parte

__all__ = ["NS", "VERSION_ESQUEMA", "generar", "generar_arbol"]

VERSION_ESQUEMA = "3.2.2"
NS = "http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xml"

ET.register_namespace("fe", NS)

#: Emision individual. El esquema admite tambien "L" (lote); aqui cada llamada
#: genera un fichero con una factura.
_MODALIDAD = "I"
#: "EM": el emisor de la factura es el propio vendedor.
_EMISOR_ES_VENDEDOR = "EM"


def _q(etiqueta: str) -> str:
    """Nombre cualificado: todo elemento vive en el namespace de Facturae."""
    return f"{{{NS}}}{etiqueta}"


def _hijo(padre: ET.Element, etiqueta: str, texto: str | None = None) -> ET.Element:
    el = ET.SubElement(padre, _q(etiqueta))
    if texto is not None:
        el.text = texto
    return el


def _importe(padre: ET.Element, etiqueta: str, valor: Decimal) -> None:
    """Los tipos ``AmountType`` del esquema envuelven la cifra en TotalAmount."""
    _hijo(_hijo(padre, etiqueta), "TotalAmount", formatear(valor))


def _escribir_direccion(padre: ET.Element, d: Direccion) -> None:
    """``AddressInSpain`` u ``OverseasAddress``: el esquema los distingue."""
    if d.es_espanola:
        nodo = _hijo(padre, "AddressInSpain")
        _hijo(nodo, "Address", d.calle)
        _hijo(nodo, "PostCode", d.codigo_postal)
        _hijo(nodo, "Town", d.poblacion)
        _hijo(nodo, "Province", d.provincia)
        _hijo(nodo, "CountryCode", d.pais)
    else:
        nodo = _hijo(padre, "OverseasAddress")
        _hijo(nodo, "Address", d.calle)
        _hijo(nodo, "PostCodeAndTown", f"{d.codigo_postal} {d.poblacion}".strip())
        _hijo(nodo, "Province", d.provincia)
        _hijo(nodo, "CountryCode", d.pais)


def _escribir_parte(padre: ET.Element, etiqueta: str, p: _Parte) -> None:
    """``SellerParty`` o ``BuyerParty``.

    Orden del esquema: ``TaxIdentification`` y luego la eleccion entre
    ``LegalEntity`` (juridica) e ``Individual`` (fisica). No son
    intercambiables: una persona fisica lleva nombre y apellidos separados.
    """
    parte = _hijo(padre, etiqueta)

    ident = _hijo(parte, "TaxIdentification")
    _hijo(ident, "PersonTypeCode", p.tipo_persona)
    _hijo(ident, "ResidenceTypeCode", p.tipo_residencia)
    _hijo(ident, "TaxIdentificationNumber", p.nif)

    if p.tipo_persona == TipoPersona.JURIDICA:
        entidad = _hijo(parte, "LegalEntity")
        _hijo(entidad, "CorporateName", p.nombre)
        _escribir_direccion(entidad, p.direccion)
    else:
        persona = _hijo(parte, "Individual")
        _hijo(persona, "Name", p.nombre)
        _hijo(persona, "FirstSurname", p.apellido1)
        if p.apellido2:
            _hijo(persona, "SecondSurname", p.apellido2)
        _escribir_direccion(persona, p.direccion)


def _escribir_impuestos(
    padre: ET.Element,
    etiqueta: str,
    bloques: Iterable[tuple[object, Decimal, Decimal]],
) -> None:
    """``TaxesOutputs`` o ``TaxesWithheld``: un ``Tax`` por codigo y tipo."""
    nodo = _hijo(padre, etiqueta)
    for imp, base, cuota in bloques:
        t = _hijo(nodo, "Tax")
        _hijo(t, "TaxTypeCode", imp.codigo)
        _hijo(t, "TaxRate", formatear(imp.tipo))
        _importe(t, "TaxableBase", base)
        _importe(t, "TaxAmount", cuota)


def _escribir_cabecera_fichero(raiz: ET.Element, f: Factura) -> None:
    cab = _hijo(raiz, "FileHeader")
    _hijo(cab, "SchemaVersion", VERSION_ESQUEMA)
    _hijo(cab, "Modality", _MODALIDAD)
    _hijo(cab, "InvoiceIssuerType", _EMISOR_ES_VENDEDOR)

    lote = _hijo(cab, "Batch")
    _hijo(lote, "BatchIdentifier", f"{f.serie}{f.numero}")
    _hijo(lote, "InvoicesCount", "1")
    _importe(lote, "TotalInvoicesAmount", f.total)
    _importe(lote, "TotalOutstandingAmount", f.total)
    _importe(lote, "TotalExecutableAmount", f.total)
    _hijo(lote, "InvoiceCurrencyCode", f.moneda)


def _escribir_totales(padre: ET.Element, f: Factura) -> None:
    """``InvoiceTotals``, en el orden del esquema.

    ``TotalGrossAmountBeforeTaxes`` coincide con el bruto porque esta version
    no aplica descuentos ni cargos generales. Si se anaden, se restan aqui.
    """
    t = _hijo(padre, "InvoiceTotals")
    _hijo(t, "TotalGrossAmount", formatear(f.total_bruto))
    _hijo(t, "TotalGrossAmountBeforeTaxes", formatear(f.total_bruto))
    _hijo(t, "TotalTaxOutputs", formatear(f.total_repercutido))
    _hijo(t, "TotalTaxesWithheld", formatear(f.total_retenido))
    _hijo(t, "InvoiceTotal", formatear(f.total))
    _hijo(t, "TotalOutstandingAmount", formatear(f.total))
    _hijo(t, "TotalExecutableAmount", formatear(f.total))


def _escribir_lineas(padre: ET.Element, f: Factura) -> None:
    items = _hijo(padre, "Items")
    for linea in f.lineas:
        el = _hijo(items, "InvoiceLine")
        _hijo(el, "ItemDescription", linea.descripcion)
        _hijo(el, "Quantity", formatear(linea.cantidad))
        if linea.unidad:
            _hijo(el, "UnitOfMeasure", linea.unidad)
        _hijo(el, "UnitPriceWithoutTax", formatear(linea.precio_unitario))
        _hijo(el, "TotalCost", formatear(linea.bruto))
        _hijo(el, "GrossAmount", formatear(linea.bruto))

        retenidos = [(i, linea.bruto, i.cuota(linea.bruto))
                     for i in linea.impuestos if i.se_retiene]
        if retenidos:
            _escribir_impuestos(el, "TaxesWithheld", retenidos)
        repercutidos = [(i, linea.bruto, i.cuota(linea.bruto))
                        for i in linea.impuestos if not i.se_retiene]
        _escribir_impuestos(el, "TaxesOutputs", repercutidos)


def generar_arbol(factura: Factura) -> ET.Element:
    """Construye el arbol XML de la factura y devuelve su raiz."""
    raiz = ET.Element(_q("Facturae"))

    _escribir_cabecera_fichero(raiz, factura)

    partes = _hijo(raiz, "Parties")
    _escribir_parte(partes, "SellerParty", factura.emisor)
    _escribir_parte(partes, "BuyerParty", factura.receptor)

    facturas = _hijo(raiz, "Invoices")
    inv = _hijo(facturas, "Invoice")

    cab = _hijo(inv, "InvoiceHeader")
    _hijo(cab, "InvoiceNumber", factura.numero)
    if factura.serie:
        _hijo(cab, "InvoiceSeriesCode", factura.serie)
    _hijo(cab, "InvoiceDocumentType", factura.tipo_documento)
    _hijo(cab, "InvoiceClass", factura.clase)

    emision = _hijo(inv, "InvoiceIssueData")
    _hijo(emision, "IssueDate", factura.fecha.isoformat())
    _hijo(emision, "InvoiceCurrencyCode", factura.moneda)
    _hijo(emision, "TaxCurrencyCode", factura.moneda)
    _hijo(emision, "LanguageName", factura.idioma)
    if factura.descripcion:
        _hijo(emision, "InvoiceDescription", factura.descripcion)

    _escribir_impuestos(inv, "TaxesOutputs", factura.impuestos_repercutidos())
    retenidos = factura.impuestos_retenidos()
    if retenidos:
        _escribir_impuestos(inv, "TaxesWithheld", retenidos)

    _escribir_totales(inv, factura)
    _escribir_lineas(inv, factura)

    return raiz


def generar(factura: Factura, *, declaracion: bool = True) -> str:
    """Devuelve el XML Facturae 3.2.2 de la factura, listo para firmar.

    :param declaracion: incluir la cabecera ``<?xml ...?>``. Se puede quitar
        para incrustar el fragmento en otro documento.

    El fichero sale **sin firmar**: Facturae exige firma XAdES para presentar
    ante una administracion. Ver la seccion «Firma» del README.
    """
    raiz = generar_arbol(factura)
    ET.indent(raiz, space="  ")
    cuerpo = ET.tostring(raiz, encoding="unicode")
    if declaracion:
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + cuerpo + "\n"
    return cuerpo
