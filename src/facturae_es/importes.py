"""Dinero en Decimal, redondeado como manda Hacienda.

Dos decisiones que parecen menores y deciden si una factura la aceptan:

1. **Nunca ``float``.** ``0.1 + 0.2`` da ``0.30000000000000004``. Sobre cien
   lineas eso es un descuadre de centimos, y el receptor rechaza el fichero.
2. **``ROUND_HALF_UP``, no el redondeo de Python.** Python usa banquero por
   defecto: ``round(2.5)`` da ``2``. En una factura, 2,5 son 3. El articulo
   11 de la Ley 37/1992 (IVA) manda redondear al alza en el medio punto.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

__all__ = ["DOS_DECIMALES", "a_decimal", "redondear", "formatear"]

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
