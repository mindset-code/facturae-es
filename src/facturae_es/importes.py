"""Dinero en Decimal, con dos decimales y redondeo al alza en el medio punto.

Dos decisiones que parecen menores y deciden si una factura la aceptan:

1. **Nunca ``float``.** ``0.1 + 0.2`` da ``0.30000000000000004``. Sobre cien
   lineas eso es un descuadre de centimos, y el receptor rechaza el fichero.
2. **``ROUND_HALF_UP``, no el redondeo de Python.** Python usa el de banquero
   por defecto: ``round(2.5)`` da ``2`` y ``round(3.5)`` da ``4``. En una
   factura, 2,5 son 3.

   Esto ultimo es la convencion comercial habitual, no una obligacion legal:
   ni la Ley 37/1992 del IVA ni el Reglamento de facturacion fijan un modo de
   redondeo para el importe de una factura. Lo exigible es el resultado --
   dos decimales y totales que cuadren con las lineas -- y ``ROUND_HALF_UP``
   es como se llega ahi sin que el redondeo de banquero meta diferencias de
   centimos frente a lo que calcula el receptor.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

__all__ = ["DOS_DECIMALES", "a_decimal", "formatear", "redondear"]

DOS_DECIMALES = Decimal("0.01")


def a_decimal(valor: Decimal | int | str | float) -> Decimal:
    """Convierte a ``Decimal`` sin colar la imprecision del binario.

    Un ``float`` se convierte pasando por ``str`` a proposito:
    ``Decimal(0.1)`` guarda ``0.1000000000000000055511151231257827``,
    mientras que ``Decimal(str(0.1))`` guarda ``0.1``.

    :raises TypeError: si el valor no representa un numero.
    """
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, bool):
        raise TypeError("un booleano no es un importe")
    if isinstance(valor, float):
        valor = str(valor)
    try:
        return Decimal(valor)
    except (InvalidOperation, ValueError, TypeError) as e:
        raise TypeError(f"{valor!r} no es un importe valido") from e


def redondear(valor: Decimal | int | str | float) -> Decimal:
    """Redondea a dos decimales con ``ROUND_HALF_UP``."""
    return a_decimal(valor).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def formatear(valor: Decimal | int | str | float) -> str:
    """Importe tal y como va en el XML: punto decimal y dos cifras.

    El esquema espera notacion inglesa. Una coma decimal invalida el fichero, y
    es el error mas repetido cuando el importe se compone concatenando texto.
    """
    return f"{redondear(valor):.2f}"
