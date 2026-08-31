"""Pruebas de facturae-es.

El anclaje fuerte de esta suite es ``TestOrdenContraElEsquema``: descarga el
XSD oficial de facturae.gob.es y comprueba que el orden de los elementos que
generamos coincide con el que exige ``xs:sequence``. Si el Ministerio cambia el
esquema, el test se entera; no depende de lo que recordemos.

Los tests que necesitan red se saltan solos cuando no la hay, para que la suite
siga siendo util sin conexion.
"""

from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import pytest

from facturae_es import (
    IRPF,
    IVA,
    NS,
    ClaseFactura,
    Direccion,
    Emisor,
    Factura,
    FacturaInvalida,
    Impuesto,
    Linea,
    Receptor,
    TipoPersona,
    formatear,
    generar,
    generar_arbol,
    redondear,
)

XS = "{http://www.w3.org/2001/XMLSchema}"
URL_XSD = ("https://www.facturae.gob.es/content/dam/facturae/formato/"
           "versiones/Facturaev3_2_2.xml")


# --- Material de prueba -----------------------------------------------------

def emisor_ejemplo() -> Emisor:
    return Emisor(
        nif="B12345674",
        nombre="Talleres Ejemplo SL",
        direccion=Direccion("Calle Mayor 1", "08001", "Barcelona", "Barcelona"),
    )


def receptor_ejemplo() -> Receptor:
    return Receptor(
        nif="A58818501",
        nombre="Cliente Ejemplo SA",
        direccion=Direccion("Gran Via 100", "28013", "Madrid", "Madrid"),
    )


def factura_ejemplo(lineas=None, **extra) -> Factura:
    # Ojo con "lineas or [...]": una lista vacia es falsy y quedaria sustituida
    # por la linea por defecto, dejando sin probar el caso de la factura vacia.
    if lineas is None:
        lineas = [Linea("Servicio de consultoria", Decimal("10"), Decimal("100"))]
    return Factura(
        numero=extra.pop("numero", "2026-001"),
        emisor=emisor_ejemplo(),
        receptor=receptor_ejemplo(),
        lineas=lineas,
        fecha=extra.pop("fecha", date(2026, 3, 15)),
        **extra,
    )


def texto(raiz: ET.Element, ruta: str) -> str:
    """Texto de un elemento, con el namespace ya puesto."""
    ruta_ns = "/".join(f"{{{NS}}}{p}" for p in ruta.split("/"))
    el = raiz.find(ruta_ns)
    assert el is not None, f"no existe el elemento {ruta}"
    return el.text or ""


# --- Importes ---------------------------------------------------------------

class TestImportes:
    def test_el_medio_centimo_sube(self):
        """Python redondea 2.5 a 2 (banquero). En una factura son 3."""
        assert redondear("2.005") == Decimal("2.01")
        assert redondear("0.125") == Decimal("0.13")
        assert round(Decimal("2.5")) == 2  # el de Python, para contraste
        assert redondear("2.5") == Decimal("2.50")

    def test_un_float_no_arrastra_su_basura_binaria(self):
        assert redondear(0.1 + 0.2) == Decimal("0.30")
        assert formatear(0.615) == "0.62"

    def test_el_xml_lleva_punto_decimal(self):
        assert formatear(Decimal("1234.5")) == "1234.50"
        assert "," not in formatear(Decimal("1234.5"))

    def test_un_texto_que_no_es_numero_falla(self):
        with pytest.raises(TypeError):
            redondear("veinte euros")

    def test_un_booleano_no_es_un_importe(self):
        with pytest.raises(TypeError):
            redondear(True)


# --- Totales ----------------------------------------------------------------

class TestTotales:
    def test_el_caso_sencillo(self):
        f = factura_ejemplo()
        assert f.total_bruto == Decimal("1000.00")
        assert f.total_repercutido == Decimal("210.00")
        assert f.total_retenido == Decimal("0.00")
        assert f.total == Decimal("1210.00")

    def test_el_irpf_resta_en_vez_de_sumar(self):
        """La factura del autonomo: 21 % de IVA y 15 % de retencion."""
        linea = Linea("Servicio", Decimal("1"), Decimal("1000"),
                      impuestos=[Impuesto(IVA, Decimal("21")),
                                 Impuesto(IRPF, Decimal("15"))])
        f = factura_ejemplo([linea])
        assert f.total_repercutido == Decimal("210.00")
        assert f.total_retenido == Decimal("150.00")
        assert f.total == Decimal("1060.00")

    def test_dos_lineas_al_mismo_tipo_van_en_un_solo_bloque(self):
        f = factura_ejemplo([
            Linea("Uno", Decimal("1"), Decimal("100")),
            Linea("Dos", Decimal("2"), Decimal("50")),
        ])
        bloques = f.impuestos_repercutidos()
        assert len(bloques) == 1, "Facturae agrupa por codigo y tipo, no por linea"
        _, base, cuota = bloques[0]
        assert base == Decimal("200.00")
        assert cuota == Decimal("42.00")

    def test_tipos_distintos_van_en_bloques_distintos(self):
        f = factura_ejemplo([
            Linea("General", Decimal("1"), Decimal("100")),
            Linea("Reducido", Decimal("1"), Decimal("100"),
                  impuestos=[Impuesto(IVA, Decimal("10"))]),
        ])
        assert len(f.impuestos_repercutidos()) == 2
        assert f.total_repercutido == Decimal("31.00")

    def test_una_linea_exenta_declara_el_cero(self):
        """Exento no es «sin impuesto»: es un bloque al 0 %."""
        f = factura_ejemplo([Linea("Formacion exenta", Decimal("1"), Decimal("500"),
                                   impuestos=[Impuesto(IVA, Decimal("0"))])])
        assert f.total_repercutido == Decimal("0.00")
        assert f.total == Decimal("500.00")
        assert len(f.impuestos_repercutidos()) == 1

    def test_los_totales_cuadran_siempre(self):
        """Propiedad general sobre cantidades y precios variados."""
        for cantidad in ("1", "3", "7.5", "0.25"):
            for precio in ("0.01", "9.99", "133.33", "1000"):
                f = factura_ejemplo([Linea("X", Decimal(cantidad), Decimal(precio))])
                assert f.total == f.total_bruto + f.total_repercutido - f.total_retenido


# --- Validaciones -----------------------------------------------------------

class TestValidaciones:
    def test_una_factura_sin_lineas_no_es_una_factura(self):
        with pytest.raises(FacturaInvalida, match="sin lineas"):
            factura_ejemplo([])

    def test_el_numero_no_pasa_de_veinte_caracteres(self):
        with pytest.raises(FacturaInvalida, match="20 caracteres"):
            factura_ejemplo(numero="X" * 21)

    def test_una_clase_inventada_falla(self):
        with pytest.raises(FacturaInvalida, match="InvoiceClassType"):
            factura_ejemplo(clase="ZZ")

    def test_el_codigo_postal_espanol_lleva_cinco_digitos(self):
        with pytest.raises(FacturaInvalida, match="cinco digitos"):
            Direccion("Calle", "8001", "Barcelona", "Barcelona")

    def test_el_pais_va_en_alfa_3(self):
        with pytest.raises(FacturaInvalida, match="alfa-3"):
            Direccion("Rue", "75001", "Paris", "Paris", pais="FR")

    def test_una_persona_fisica_necesita_apellido(self):
        with pytest.raises(FacturaInvalida, match="apellido1"):
            Emisor(nif="12345678Z", nombre="Ana",
                   direccion=Direccion("Calle", "08001", "Barcelona", "Barcelona"),
                   tipo_persona=TipoPersona.FISICA)

    def test_una_linea_sin_impuestos_se_rechaza_con_instrucciones(self):
        with pytest.raises(FacturaInvalida, match="Impuesto\\(IVA, 0\\)"):
            Linea("Algo", Decimal("1"), Decimal("100"), impuestos=[])

    def test_un_codigo_de_impuesto_que_no_es_de_dos_digitos(self):
        with pytest.raises(FacturaInvalida, match="dos digitos"):
            Impuesto("IVA", Decimal("21"))

    def test_no_se_puede_repetir_el_mismo_impuesto_en_una_linea(self):
        with pytest.raises(FacturaInvalida, match="repite"):
            Linea("Algo", Decimal("1"), Decimal("100"),
                  impuestos=[Impuesto(IVA, Decimal("21")), Impuesto(IVA, Decimal("10"))])


# --- XML --------------------------------------------------------------------

class TestXml:
    def test_todo_elemento_esta_en_el_namespace(self):
        """El fallo clasico: prefijo en la raiz y los hijos sin namespace."""
        raiz = generar_arbol(factura_ejemplo())
        for el in raiz.iter():
            assert el.tag.startswith(f"{{{NS}}}"), f"{el.tag} se quedo fuera del namespace"

    def test_es_xml_bien_formado_y_se_puede_releer(self):
        xml = generar(factura_ejemplo())
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        ET.fromstring(xml)

    def test_los_totales_del_xml_son_los_calculados(self):
        f = factura_ejemplo()
        raiz = generar_arbol(f)
        ruta = "Invoices/Invoice/InvoiceTotals"
        assert texto(raiz, ruta + "/TotalGrossAmount") == "1000.00"
        assert texto(raiz, ruta + "/TotalTaxOutputs") == "210.00"
        assert texto(raiz, ruta + "/InvoiceTotal") == "1210.00"
        assert texto(raiz, ruta + "/TotalExecutableAmount") == "1210.00"

    def test_la_version_del_esquema_es_la_declarada(self):
        raiz = generar_arbol(factura_ejemplo())
        assert texto(raiz, "FileHeader/SchemaVersion") == "3.2.2"

    def test_la_fecha_va_en_iso(self):
        raiz = generar_arbol(factura_ejemplo(fecha=date(2026, 12, 3)))
        assert texto(raiz, "Invoices/Invoice/InvoiceIssueData/IssueDate") == "2026-12-03"

    def test_una_persona_fisica_usa_individual_y_no_legalentity(self):
        emisor = Emisor(nif="12345678Z", nombre="Ana", apellido1="Ruiz",
                        apellido2="Soler", tipo_persona=TipoPersona.FISICA,
                        direccion=Direccion("Calle", "08001", "Barcelona", "Barcelona"))
        f = Factura(numero="1", emisor=emisor, receptor=receptor_ejemplo(),
                    lineas=[Linea("X", Decimal("1"), Decimal("10"))])
        raiz = generar_arbol(f)
        assert raiz.find(f"{{{NS}}}Parties/{{{NS}}}SellerParty/{{{NS}}}Individual") is not None
        assert raiz.find(f"{{{NS}}}Parties/{{{NS}}}SellerParty/{{{NS}}}LegalEntity") is None
        assert texto(raiz, "Parties/SellerParty/Individual/FirstSurname") == "Ruiz"

    def test_una_direccion_extranjera_usa_overseasaddress(self):
        receptor = Receptor(nif="FR123", nombre="Client SARL",
                            direccion=Direccion("Rue de Paris 1", "75001",
                                                "Paris", "Paris", pais="FRA"))
        f = Factura(numero="1", emisor=emisor_ejemplo(), receptor=receptor,
                    lineas=[Linea("X", Decimal("1"), Decimal("10"))])
        raiz = generar_arbol(f)
        base = f"{{{NS}}}Parties/{{{NS}}}BuyerParty/{{{NS}}}LegalEntity/"
        assert raiz.find(base + f"{{{NS}}}OverseasAddress") is not None
        assert raiz.find(base + f"{{{NS}}}AddressInSpain") is None

    def test_sin_irpf_no_se_escribe_el_bloque_de_retenciones(self):
        raiz = generar_arbol(factura_ejemplo())
        assert raiz.find(f"{{{NS}}}Invoices/{{{NS}}}Invoice/{{{NS}}}TaxesWithheld") is None

    def test_con_irpf_si_se_escribe(self):
        linea = Linea("Servicio", Decimal("1"), Decimal("1000"),
                      impuestos=[Impuesto(IVA, Decimal("21")),
                                 Impuesto(IRPF, Decimal("15"))])
        raiz = generar_arbol(factura_ejemplo([linea]))
        nodo = raiz.find(f"{{{NS}}}Invoices/{{{NS}}}Invoice/{{{NS}}}TaxesWithheld")
        assert nodo is not None
        assert texto(raiz, "Invoices/Invoice/InvoiceTotals/TotalTaxesWithheld") == "150.00"

    def test_la_serie_solo_aparece_si_la_hay(self):
        sin = generar_arbol(factura_ejemplo())
        assert sin.find(f"{{{NS}}}Invoices/{{{NS}}}Invoice/{{{NS}}}InvoiceHeader/"
                        f"{{{NS}}}InvoiceSeriesCode") is None
        con = generar_arbol(factura_ejemplo(serie="A"))
        assert texto(con, "Invoices/Invoice/InvoiceHeader/InvoiceSeriesCode") == "A"

    def test_hay_una_linea_por_cada_linea(self):
        f = factura_ejemplo([
            Linea("Uno", Decimal("1"), Decimal("10")),
            Linea("Dos", Decimal("2"), Decimal("20")),
            Linea("Tres", Decimal("3"), Decimal("30")),
        ])
        raiz = generar_arbol(f)
        items = raiz.findall(f"{{{NS}}}Invoices/{{{NS}}}Invoice/{{{NS}}}Items/"
                             f"{{{NS}}}InvoiceLine")
        assert len(items) == 3

    def test_los_caracteres_especiales_se_escapan(self):
        f = factura_ejemplo([Linea("Tornillos & tuercas <10mm>", Decimal("1"),
                                   Decimal("5"))])
        xml = generar(f)
        assert "&amp;" in xml and "&lt;" in xml
        ET.fromstring(xml)  # si el escapado fallara, esto reventaria


# --- El anclaje: el propio esquema oficial -----------------------------------

class TestOrdenContraElEsquema:
    """Compara lo que generamos con el orden que exige el XSD del Ministerio."""

    @staticmethod
    def _descargar_xsd():
        try:
            pet = urllib.request.Request(URL_XSD, headers={"User-Agent": "facturae-es-tests"})
            with urllib.request.urlopen(pet, timeout=30) as r:
                return ET.fromstring(r.read())
        except (urllib.error.URLError, OSError) as e:
            pytest.skip(f"sin acceso al esquema oficial: {e}")

    @staticmethod
    def _secuencia(esquema, nombre_tipo):
        for t in esquema.findall(XS + "complexType"):
            if t.get("name") != nombre_tipo:
                continue
            for seq in t.iter(XS + "sequence"):
                return [e.get("name") for e in seq.findall(XS + "element") if e.get("name")]
        return []

    def _hijos(self, raiz, ruta):
        el = raiz.find("/".join(f"{{{NS}}}{p}" for p in ruta.split("/"))) if ruta else raiz
        assert el is not None, f"no existe {ruta}"
        return [h.tag.replace(f"{{{NS}}}", "") for h in el]

    @pytest.mark.parametrize(
        "ruta, tipo",
        [
            ("", "FacturaeType"),
            ("FileHeader", "FileHeaderType"),
            ("FileHeader/Batch", "BatchType"),
            ("Parties", "PartiesType"),
            ("Invoices/Invoice", "InvoiceType"),
            ("Invoices/Invoice/InvoiceHeader", "InvoiceHeaderType"),
            ("Invoices/Invoice/InvoiceIssueData", "InvoiceIssueDataType"),
            ("Invoices/Invoice/InvoiceTotals", "InvoiceTotalsType"),
            ("Invoices/Invoice/Items/InvoiceLine", "InvoiceLineType"),
        ],
    )
    def test_el_orden_es_el_del_esquema(self, ruta, tipo):
        esquema = self._descargar_xsd()
        if ruta == "":
            nodo = esquema.find(XS + 'element[@name="Facturae"]')
            esperado = [e.get("name") for seq in nodo.iter(XS + "sequence")
                        for e in seq.findall(XS + "element") if e.get("name")]
        else:
            esperado = self._secuencia(esquema, tipo)
        assert esperado, f"el esquema no declara {tipo}"

        generado = self._hijos(generar_arbol(self._factura_completa()), ruta)
        posiciones = [esperado.index(n) for n in generado if n in esperado]
        assert posiciones == sorted(posiciones), (
            f"en {ruta or 'Facturae'} el orden generado {generado} no sigue "
            f"la secuencia del esquema {esperado}"
        )
        assert all(n in esperado for n in generado), (
            f"en {ruta or 'Facturae'} generamos elementos que el esquema no declara: "
            f"{[n for n in generado if n not in esperado]}"
        )

    @staticmethod
    def _factura_completa() -> Factura:
        """Una factura que ejercita todos los bloques opcionales."""
        return Factura(
            numero="001",
            serie="A",
            descripcion="Trabajos de marzo",
            emisor=emisor_ejemplo(),
            receptor=receptor_ejemplo(),
            clase=ClaseFactura.ORIGINAL,
            lineas=[Linea("Servicio", Decimal("2"), Decimal("300"), unidad="01",
                          impuestos=[Impuesto(IVA, Decimal("21")),
                                     Impuesto(IRPF, Decimal("15"))])],
        )
