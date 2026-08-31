"""Pruebas de la carga desde JSON y de la interfaz de línea de órdenes.

Lo que se vigila aquí, sobre todo, es que un dato mal escrito NO pase en
silencio: una factura que sale por cero euros porque alguien escribió
``precio_unitraio`` es peor que una que falla.
"""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

import pytest

from facturae_es import FacturaInvalida, a_dict, desde_dict, desde_json, generar
from facturae_es.__main__ import PLANTILLA, TOTALES_CONOCIDOS, main

RAIZ = Path(__file__).resolve().parent.parent
NS = {"f": "http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xml"}


@pytest.fixture
def minima() -> dict:
    return {
        "numero": "001",
        "emisor": {
            "nif": "B12345674",
            "nombre": "Talleres Ejemplo SL",
            "direccion": {
                "calle": "Calle Mayor 1",
                "codigo_postal": "08001",
                "poblacion": "Barcelona",
                "provincia": "Barcelona",
            },
        },
        "receptor": {
            "nif": "A58818501",
            "nombre": "Cliente Ejemplo SA",
            "direccion": {
                "calle": "Gran Via 100",
                "codigo_postal": "28013",
                "poblacion": "Madrid",
                "provincia": "Madrid",
            },
        },
        "lineas": [{"descripcion": "Consultoria", "cantidad": 10, "precio_unitario": 100}],
    }


class TestCarga:
    def test_una_factura_minima_cuadra(self, minima):
        f = desde_dict(minima)
        assert f.total_bruto == Decimal("1000.00")
        assert f.total == Decimal("1210.00")  # 21 % de IVA por defecto

    def test_un_campo_mal_escrito_falla_en_vez_de_ignorarse(self, minima):
        """El fallo silencioso que esto evita: una factura por 0 euros."""
        minima["lineas"][0]["precio_unitraio"] = 100
        del minima["lineas"][0]["precio_unitario"]
        with pytest.raises(FacturaInvalida, match="desconocido"):
            desde_dict(minima)

    def test_dice_que_campos_faltan(self):
        with pytest.raises(FacturaInvalida, match=r"emisor.*lineas.*receptor"):
            desde_dict({"numero": "1"})

    def test_los_float_no_pierden_precision(self, minima):
        """0.1 + 0.2 en float da 0.30000000000000004; aqui no puede pasar."""
        minima["lineas"][0]["cantidad"] = 3
        minima["lineas"][0]["precio_unitario"] = 0.1
        f = desde_dict(minima)
        assert f.lineas[0].bruto == Decimal("0.30")

    def test_las_fechas_iso_se_leen(self, minima):
        minima["fecha"] = "2026-01-15"
        assert desde_dict(minima).fecha.isoformat() == "2026-01-15"

    def test_una_fecha_mal_formada_no_pasa(self, minima):
        minima["fecha"] = "15/01/2026"
        with pytest.raises(FacturaInvalida, match="ISO"):
            desde_dict(minima)

    def test_json_roto_da_un_error_legible(self):
        with pytest.raises(FacturaInvalida, match="no es valido"):
            desde_json("{esto no es json")

    def test_la_ida_y_vuelta_conserva_la_factura(self, minima):
        original = desde_dict(minima)
        vuelta = desde_dict(a_dict(original))
        assert vuelta.total == original.total
        assert vuelta.numero == original.numero
        assert len(vuelta.lineas) == len(original.lineas)

    def test_la_ida_y_vuelta_produce_el_mismo_xml(self, minima):
        """Es lo que permite guardar el JSON junto al XML y regenerarlo igual."""
        original = desde_dict(minima)
        assert generar(desde_dict(a_dict(original))) == generar(original)

    def test_a_dict_serializa_a_json_sin_quejarse(self, minima):
        """Decimal no es serializable: por eso los importes salen como cadena."""
        json.dumps(a_dict(desde_dict(minima)))


class TestAutocomprobar:
    def test_sale_con_cero(self, capsys):
        assert main(["autocomprobar"]) == 0
        assert "correcta" in capsys.readouterr().out.lower()

    def test_los_totales_conocidos_estan_escritos_a_mano(self):
        """Si se leyeran de la biblioteca, autocomprobar seria una tautologia.

        Estos numeros salen de la aritmetica de la plantilla:
          linea 1: 10 x 100 = 1000,00  IVA 21 % = 210,00  IRPF 15 % = 150,00
          linea 2:  1 x 250 =  250,00  IVA 21 % =  52,50
          bruto 1250,00 + 262,50 - 150,00 = 1362,50
        """
        assert TOTALES_CONOCIDOS == {
            "total_bruto": "1250.00",
            "total_repercutido": "262.50",
            "total_retenido": "150.00",
            "total": "1362.50",
        }

    def test_la_plantilla_produce_esos_totales(self):
        f = desde_dict(PLANTILLA)
        assert f.total_bruto == Decimal("1250.00")
        assert f.total_repercutido == Decimal("262.50")
        assert f.total_retenido == Decimal("150.00")
        assert f.total == Decimal("1362.50")


class TestOrdenes:
    def test_plantilla_produce_un_json_que_la_biblioteca_acepta(self, capsys):
        assert main(["plantilla"]) == 0
        desde_json(capsys.readouterr().out)

    def test_plantilla_escribe_al_fichero_pedido(self, tmp_path, capsys):
        destino = tmp_path / "f.json"
        assert main(["plantilla", "-o", str(destino)]) == 0
        desde_json(destino.read_text(encoding="utf-8"))

    def test_validar_muestra_el_desglose(self, tmp_path, capsys):
        destino = tmp_path / "f.json"
        destino.write_text(json.dumps(PLANTILLA), encoding="utf-8")
        assert main(["validar", str(destino)]) == 0
        salida = capsys.readouterr().out
        assert "1362.50" in salida
        assert "+ 01" in salida  # IVA repercutido
        assert "- 04" in salida  # IRPF retenido

    def test_totales_emite_json_valido(self, tmp_path, capsys):
        destino = tmp_path / "f.json"
        destino.write_text(json.dumps(PLANTILLA), encoding="utf-8")
        assert main(["totales", str(destino)]) == 0
        d = json.loads(capsys.readouterr().out)
        assert d["total"] == "1362.50"

    def test_generar_produce_un_xml_que_se_parsea(self, tmp_path, capsys):
        entrada = tmp_path / "f.json"
        entrada.write_text(json.dumps(PLANTILLA), encoding="utf-8")
        salida = tmp_path / "f.xml"
        assert main(["generar", str(entrada), "-o", str(salida)]) == 0

        raiz = ET.parse(salida).getroot()
        assert raiz.tag.endswith("Facturae")
        assert raiz.find(".//f:InvoiceTotal", NS).text == "1362.50"
        assert raiz.find(".//f:TotalGrossAmount", NS).text == "1250.00"

    def test_sin_declaracion_omite_la_cabecera_xml(self, tmp_path, capsys):
        entrada = tmp_path / "f.json"
        entrada.write_text(json.dumps(PLANTILLA), encoding="utf-8")
        assert main(["generar", str(entrada), "--sin-declaracion"]) == 0
        assert not capsys.readouterr().out.startswith("<?xml")

    def test_lee_de_la_entrada_estandar(self, capsys, monkeypatch):
        import io

        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(PLANTILLA)))
        assert main(["totales", "-"]) == 0
        assert json.loads(capsys.readouterr().out)["total"] == "1362.50"


class TestErrores:
    def test_una_factura_incompleta_sale_con_2(self, tmp_path, capsys):
        malo = tmp_path / "malo.json"
        malo.write_text('{"numero": "1"}', encoding="utf-8")
        assert main(["validar", str(malo)]) == 2
        assert "inválida" in capsys.readouterr().err

    def test_json_roto_sale_con_2(self, tmp_path, capsys):
        malo = tmp_path / "malo.json"
        malo.write_text("no soy json", encoding="utf-8")
        assert main(["validar", str(malo)]) == 2

    def test_fichero_inexistente_sale_con_2_y_lo_dice(self, tmp_path, capsys):
        assert main(["validar", str(tmp_path / "no-existe.json")]) == 2
        assert "error de fichero" in capsys.readouterr().err


class TestArranqueReal:
    """Que main() devuelva 0 no prueba que el paquete arranque por su cuenta."""

    def test_python_m_funciona(self):
        r = subprocess.run(
            [sys.executable, "-m", "facturae_es", "autocomprobar"],
            capture_output=True,
            text=True,
            cwd=RAIZ,
            env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        )
        assert r.returncode == 0, r.stderr

    def test_el_ejemplo_del_repositorio_se_ejecuta(self):
        ejemplo = RAIZ / "examples" / "facturacion_completa.py"
        assert ejemplo.exists(), "el ejemplo que enlaza el README tiene que existir"
        r = subprocess.run(
            [sys.executable, str(ejemplo)],
            capture_output=True,
            text=True,
            cwd=RAIZ,
            env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        )
        assert r.returncode == 0, r.stderr
