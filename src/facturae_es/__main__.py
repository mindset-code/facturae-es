"""Interfaz de línea de órdenes de ``facturae-es``.

Genera el XML de Facturae 3.2.2 a partir de un JSON, sin escribir Python. Está
pensada para el sitio donde suele hacer falta: un proceso que ya tiene los
datos de la factura en JSON y necesita el fichero que se sube a FACe.

    facturae-es plantilla > factura.json
    facturae-es generar factura.json -o factura.xsig.xml

Se ejecuta como ``facturae-es`` (el guion que instala pip) o como
``python -m facturae_es``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import VERSION_ESQUEMA, Factura, FacturaInvalida, generar
from .carga import a_dict, desde_dict, desde_json

# Factura de ejemplo con la que arranca `plantilla` y contra la que se compara
# `autocomprobar`. Los NIF son de prueba con dígito de control correcto.
PLANTILLA: dict[str, Any] = {
    "numero": "001",
    "serie": "A",
    "fecha": "2026-01-15",
    "descripcion": "Servicios de consultoría de enero",
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
    "lineas": [
        {
            "descripcion": "Consultoría técnica",
            "cantidad": 10,
            "precio_unitario": 100,
            "impuestos": [{"codigo": "01", "tipo": 21}, {"codigo": "04", "tipo": 15}],
        },
        {
            "descripcion": "Licencia de mantenimiento",
            "cantidad": 1,
            "precio_unitario": 250,
        },
    ],
}

# Totales de esa factura, escritos A MANO. Si se leyeran de la biblioteca,
# `autocomprobar` no comprobaría nada: sería una tautología.
#   línea 1: 10 x 100 = 1000,00   IVA 21 % = 210,00   IRPF 15 % = 150,00
#   línea 2:  1 x 250 =  250,00   IVA 21 % =  52,50
#   bruto 1250,00 + repercutido 262,50 - retenido 150,00 = 1362,50
TOTALES_CONOCIDOS = {
    "total_bruto": "1250.00",
    "total_repercutido": "262.50",
    "total_retenido": "150.00",
    "total": "1362.50",
}


def _leer(ruta: str) -> Factura:
    """Lee una factura de un fichero JSON, o de la entrada estándar con ``-``."""
    texto = sys.stdin.read() if ruta == "-" else Path(ruta).read_text(encoding="utf-8")
    return desde_json(texto)


def _resumen(f: Factura) -> dict[str, Any]:
    """Los totales derivados, como cadenas para no perder precisión."""
    return {
        "numero": f.numero,
        "serie": f.serie,
        "fecha": f.fecha.isoformat(),
        "lineas": len(f.lineas),
        "total_bruto": str(f.total_bruto),
        "total_repercutido": str(f.total_repercutido),
        "total_retenido": str(f.total_retenido),
        "total": str(f.total),
    }


# --------------------------------------------------------------------------- #
# Subordenes                                                                    #
# --------------------------------------------------------------------------- #
def _cmd_plantilla(args: argparse.Namespace) -> int:
    texto = json.dumps(PLANTILLA, indent=2, ensure_ascii=False) + "\n"
    if args.salida:
        Path(args.salida).write_text(texto, encoding="utf-8")
        print(f"Escrita la plantilla en {args.salida}", file=sys.stderr)
    else:
        sys.stdout.write(texto)
    return 0


def _cmd_validar(args: argparse.Namespace) -> int:
    f = _leer(args.fichero)
    if args.json:
        print(json.dumps(_resumen(f), indent=2, ensure_ascii=False))
        return 0
    print(f"Factura {f.serie}{f.numero} de {f.fecha}: válida.")
    print(f"  Emisor    {f.emisor.nombre} ({f.emisor.nif})")
    print(f"  Receptor  {f.receptor.nombre} ({f.receptor.nif})")
    print(f"  Líneas    {len(f.lineas)}")
    print(f"  Base      {f.total_bruto:>10}")
    # Los desgloses son métodos, no propiedades: devuelven una lista agrupando
    # por tipo, no un escalar ya calculado. Los totales sí son propiedades.
    for impuesto, base, cuota in f.impuestos_repercutidos():
        print(f"  + {impuesto.codigo} al {impuesto.tipo}% sobre {base}: {cuota:>10}")
    for impuesto, base, cuota in f.impuestos_retenidos():
        print(f"  - {impuesto.codigo} al {impuesto.tipo}% sobre {base}: {cuota:>10}")
    print(f"  TOTAL     {f.total:>10} {f.moneda}")
    return 0


def _cmd_totales(args: argparse.Namespace) -> int:
    f = _leer(args.fichero)
    print(json.dumps(_resumen(f), indent=2, ensure_ascii=False))
    return 0


def _cmd_generar(args: argparse.Namespace) -> int:
    f = _leer(args.fichero)
    xml = generar(f, declaracion=not args.sin_declaracion)
    if args.salida:
        Path(args.salida).write_text(xml, encoding="utf-8")
        print(
            f"Escrito {args.salida}: Facturae {VERSION_ESQUEMA}, "
            f"factura {f.serie}{f.numero}, total {f.total} {f.moneda}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(xml)
    return 0


def _cmd_autocomprobar(args: argparse.Namespace) -> int:
    """Prueba de humo: construye la plantilla y comprueba sus totales.

    Sale con 0 si cuadra y con 1 si no, para poder encadenarlo tras desplegar.
    """
    fallos: list[str] = []
    try:
        f = desde_dict(PLANTILLA)
    except FacturaInvalida as e:
        print(f"AUTOCOMPROBACIÓN FALLIDA: la plantilla no valida: {e}", file=sys.stderr)
        return 1

    obtenidos = {
        "total_bruto": f.total_bruto,
        "total_repercutido": f.total_repercutido,
        "total_retenido": f.total_retenido,
        "total": f.total,
    }
    for campo, esperado in TOTALES_CONOCIDOS.items():
        if obtenidos[campo] != Decimal(esperado):
            fallos.append(f"{campo}: se esperaba {esperado} y salió {obtenidos[campo]}")

    xml = generar(f)
    if VERSION_ESQUEMA not in xml:
        fallos.append(f"el XML no declara la versión {VERSION_ESQUEMA} del esquema")
    # La vuelta completa tiene que reconstruir la misma factura: es lo que
    # permite guardar la entrada junto al XML y volver a generarlo igual.
    if desde_dict(a_dict(f)).total != f.total:
        fallos.append("la ida y vuelta por a_dict/desde_dict no conserva el total")

    if fallos:
        print("AUTOCOMPROBACIÓN FALLIDA", file=sys.stderr)
        for x in fallos:
            print(f"  {x}", file=sys.stderr)
        return 1
    print(
        f"Autocomprobación correcta: Facturae {VERSION_ESQUEMA}, "
        f"factura de ejemplo con total {f.total} EUR y XML de {len(xml)} bytes."
    )
    return 0


# --------------------------------------------------------------------------- #
# Analizador                                                                    #
# --------------------------------------------------------------------------- #
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="facturae-es",
        description=(
            "Genera Facturae 3.2.2, el formato oficial de factura electrónica "
            "española, a partir de un JSON. Sin dependencias."
        ),
        epilog=(
            "El XML que sale NO está firmado. Facturae exige XAdES para "
            "presentarlo en FACe; la firma se aplica aparte."
        ),
    )
    subs = parser.add_subparsers(dest="orden", required=True, metavar="ORDEN")

    p = subs.add_parser(
        "plantilla",
        help="escribe un JSON de ejemplo, relleno, del que partir",
    )
    p.add_argument("-o", "--salida", help="fichero destino; por defecto, la salida estándar")
    p.set_defaults(func=_cmd_plantilla)

    p = subs.add_parser("validar", help="comprueba el JSON y muestra los totales")
    p.add_argument("fichero", help="JSON de la factura; «-» para la entrada estándar")
    p.add_argument("--json", action="store_true", help="emite el resumen en JSON")
    p.set_defaults(func=_cmd_validar)

    p = subs.add_parser("totales", help="solo los totales, en JSON")
    p.add_argument("fichero", help="JSON de la factura; «-» para la entrada estándar")
    p.set_defaults(func=_cmd_totales)

    p = subs.add_parser("generar", help="produce el XML de Facturae")
    p.add_argument("fichero", help="JSON de la factura; «-» para la entrada estándar")
    p.add_argument("-o", "--salida", help="fichero destino; por defecto, la salida estándar")
    p.add_argument(
        "--sin-declaracion",
        action="store_true",
        help="omite la declaración <?xml ...?>, para empotrar el árbol en otro documento",
    )
    p.set_defaults(func=_cmd_generar)

    p = subs.add_parser(
        "autocomprobar",
        help="prueba de humo: sale con 0 si la instalación produce los totales esperados",
    )
    p.set_defaults(func=_cmd_autocomprobar)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except FacturaInvalida as e:
        # El mensaje de FacturaInvalida ya está escrito para leerse y dice qué
        # campo falla. Un rastro de pila encima no añadiría nada.
        print(f"factura inválida: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error de fichero: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
