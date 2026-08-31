"""Construir una :class:`~facturae_es.modelo.Factura` desde un diccionario.

La mayoria de integraciones no tienen objetos de este modelo: tienen un dict
que viene de un JSON, de una API o de una fila de base de datos. Este modulo
hace esa conversion en un solo sitio, validando por el camino, en vez de
dejar que cada proyecto reescriba el mismo bucle de `.get()`.

    >>> from facturae_es import desde_dict
    >>> factura = desde_dict({
    ...     "numero": "001",
    ...     "emisor": {"nif": "B12345674", "nombre": "Talleres Ejemplo SL",
    ...                "direccion": {"calle": "Calle Mayor 1", "codigo_postal": "08001",
    ...                              "poblacion": "Barcelona", "provincia": "Barcelona"}},
    ...     "receptor": {"nif": "A58818501", "nombre": "Cliente Ejemplo SA",
    ...                  "direccion": {"calle": "Gran Via 100", "codigo_postal": "28013",
    ...                                "poblacion": "Madrid", "provincia": "Madrid"}},
    ...     "lineas": [{"descripcion": "Consultoria", "cantidad": 10, "precio_unitario": 100}],
    ... })
    >>> factura.total
    Decimal('1210.00')

Los importes se leen como cadena o numero y se convierten a ``Decimal``: un
``float`` que venga de un JSON pasa por ``str()`` antes, para que ``0.1`` no
se convierta en ``0.1000000000000000055511151231257827``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from .modelo import (
    Direccion,
    Emisor,
    Factura,
    FacturaInvalida,
    Impuesto,
    Linea,
    Receptor,
)

__all__ = ["a_dict", "desde_dict", "desde_json"]

_CAMPOS_FACTURA = {
    "numero", "emisor", "receptor", "lineas", "fecha", "serie", "moneda",
    "idioma", "clase", "tipo_documento", "descripcion",
}
_CAMPOS_PARTE = {
    "nif", "nombre", "direccion", "tipo_persona", "tipo_residencia",
    "apellido1", "apellido2",
}
_CAMPOS_DIRECCION = {"calle", "codigo_postal", "poblacion", "provincia", "pais"}
_CAMPOS_LINEA = {"descripcion", "cantidad", "precio_unitario", "impuestos", "unidad"}
_CAMPOS_IMPUESTO = {"codigo", "tipo"}


def _exigir_dict(valor: Any, donde: str) -> Mapping[str, Any]:
    if not isinstance(valor, Mapping):
        raise FacturaInvalida(f"{donde} debe ser un objeto, y es {type(valor).__name__}")
    return valor


def _sobrantes(datos: Mapping[str, Any], validos: set[str], donde: str) -> None:
    """Un campo mal escrito se ignoraria en silencio; mejor decirlo."""
    extra = set(datos) - validos
    if extra:
        raise FacturaInvalida(
            f"{donde}: campo(s) desconocido(s) {sorted(extra)}. "
            f"Los admitidos son {sorted(validos)}"
        )


def _fecha(valor: Any) -> date:
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor.strip())
        except ValueError:
            raise FacturaInvalida(
                f"la fecha {valor!r} no esta en formato ISO (AAAA-MM-DD)"
            ) from None
    raise FacturaInvalida(f"no se puede leer {valor!r} como fecha")


def _numero(valor: Any, donde: str) -> str:
    """Devuelve el importe como cadena, sin pasar nunca por float."""
    if isinstance(valor, float):
        # repr() de un float da la representacion mas corta que lo reconstruye,
        # que es lo mas fiel que se puede recuperar de algo ya degradado.
        return repr(valor)
    if isinstance(valor, (int, str)):
        return str(valor)
    raise FacturaInvalida(f"{donde}: {valor!r} no es un importe")


def _direccion(datos: Any) -> Direccion:
    d = _exigir_dict(datos, "direccion")
    _sobrantes(d, _CAMPOS_DIRECCION, "direccion")
    faltan = {"calle", "codigo_postal", "poblacion", "provincia"} - set(d)
    if faltan:
        raise FacturaInvalida(f"la direccion necesita {sorted(faltan)}")
    return Direccion(
        calle=str(d["calle"]),
        codigo_postal=str(d["codigo_postal"]),
        poblacion=str(d["poblacion"]),
        provincia=str(d["provincia"]),
        pais=str(d.get("pais", "ESP")),
    )


def _parte(datos: Any, clase: type, donde: str):
    d = _exigir_dict(datos, donde)
    _sobrantes(d, _CAMPOS_PARTE, donde)
    faltan = {"nif", "nombre", "direccion"} - set(d)
    if faltan:
        raise FacturaInvalida(f"{donde} necesita {sorted(faltan)}")
    campos = {k: v for k, v in d.items() if k != "direccion"}
    campos = {k: str(v) for k, v in campos.items()}
    return clase(direccion=_direccion(d["direccion"]), **campos)


def _impuesto(datos: Any) -> Impuesto:
    d = _exigir_dict(datos, "impuesto")
    _sobrantes(d, _CAMPOS_IMPUESTO, "impuesto")
    argumentos: dict[str, Any] = {}
    if "codigo" in d:
        argumentos["codigo"] = str(d["codigo"])
    if "tipo" in d:
        argumentos["tipo"] = _numero(d["tipo"], "impuesto.tipo")
    return Impuesto(**argumentos)


def _linea(datos: Any, indice: int) -> Linea:
    d = _exigir_dict(datos, f"lineas[{indice}]")
    _sobrantes(d, _CAMPOS_LINEA, f"lineas[{indice}]")
    if "descripcion" not in d:
        raise FacturaInvalida(f"lineas[{indice}] necesita descripcion")
    argumentos: dict[str, Any] = {"descripcion": str(d["descripcion"])}
    if "cantidad" in d:
        argumentos["cantidad"] = _numero(d["cantidad"], f"lineas[{indice}].cantidad")
    if "precio_unitario" in d:
        argumentos["precio_unitario"] = _numero(
            d["precio_unitario"], f"lineas[{indice}].precio_unitario"
        )
    if "unidad" in d:
        argumentos["unidad"] = str(d["unidad"])
    if "impuestos" in d:
        impuestos = d["impuestos"]
        if not isinstance(impuestos, Sequence) or isinstance(impuestos, (str, bytes)):
            raise FacturaInvalida(f"lineas[{indice}].impuestos debe ser una lista")
        argumentos["impuestos"] = [_impuesto(i) for i in impuestos]
    return Linea(**argumentos)


def desde_dict(datos: Mapping[str, Any]) -> Factura:
    """Construye una :class:`Factura` desde un diccionario.

    Los campos son los de la clase. Se rechaza cualquier clave que no exista,
    en lugar de ignorarla: un ``precio_unitraio`` mal escrito produciria una
    factura por cero euros sin decir nada.

    :raises FacturaInvalida: si falta un campo obligatorio, sobra alguno, o
        un valor no se puede convertir.
    """
    d = _exigir_dict(datos, "la factura")
    _sobrantes(d, _CAMPOS_FACTURA, "la factura")
    faltan = {"numero", "emisor", "receptor", "lineas"} - set(d)
    if faltan:
        raise FacturaInvalida(f"la factura necesita {sorted(faltan)}")

    lineas = d["lineas"]
    if not isinstance(lineas, Sequence) or isinstance(lineas, (str, bytes)):
        raise FacturaInvalida("«lineas» debe ser una lista")

    argumentos: dict[str, Any] = {
        "numero": str(d["numero"]),
        "emisor": _parte(d["emisor"], Emisor, "emisor"),
        "receptor": _parte(d["receptor"], Receptor, "receptor"),
        "lineas": [_linea(x, i) for i, x in enumerate(lineas)],
    }
    if "fecha" in d:
        argumentos["fecha"] = _fecha(d["fecha"])
    for campo in ("serie", "moneda", "idioma", "clase", "tipo_documento", "descripcion"):
        if campo in d:
            argumentos[campo] = str(d[campo])
    return Factura(**argumentos)


def desde_json(texto: str) -> Factura:
    """Como :func:`desde_dict`, partiendo del texto JSON.

    :raises FacturaInvalida: si el texto no es JSON valido.
    """
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as error:
        raise FacturaInvalida(f"el JSON no es valido: {error}") from None
    return desde_dict(datos)


def a_dict(factura: Factura) -> dict[str, Any]:
    """Vuelca una factura al diccionario que :func:`desde_dict` acepta.

    La vuelta completa (``desde_dict(a_dict(f))``) reconstruye una factura
    equivalente, lo que permite guardar la entrada junto al XML emitido.
    Los importes salen como cadena para no perder precision al serializar.
    """

    def parte(p) -> dict[str, Any]:
        return {
            "nif": p.nif,
            "nombre": p.nombre,
            "direccion": {
                "calle": p.direccion.calle,
                "codigo_postal": p.direccion.codigo_postal,
                "poblacion": p.direccion.poblacion,
                "provincia": p.direccion.provincia,
                "pais": p.direccion.pais,
            },
            "tipo_persona": p.tipo_persona,
            "tipo_residencia": p.tipo_residencia,
            "apellido1": p.apellido1,
            "apellido2": p.apellido2,
        }

    return {
        "numero": factura.numero,
        "serie": factura.serie,
        "fecha": factura.fecha.isoformat(),
        "moneda": factura.moneda,
        "idioma": factura.idioma,
        "clase": factura.clase,
        "tipo_documento": factura.tipo_documento,
        "descripcion": factura.descripcion,
        "emisor": parte(factura.emisor),
        "receptor": parte(factura.receptor),
        "lineas": [
            {
                "descripcion": linea.descripcion,
                "cantidad": str(linea.cantidad),
                "precio_unitario": str(linea.precio_unitario),
                "unidad": linea.unidad,
                "impuestos": [
                    {"codigo": i.codigo, "tipo": str(i.tipo)} for i in linea.impuestos
                ],
            }
            for linea in factura.lineas
        ],
    }
