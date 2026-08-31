"""Facturae 3.2.2 en Python puro, sin dependencias.

Genera el XML del formato oficial de factura electronica espanola calculando
los totales a partir de las lineas, para que no puedan descuadrar.
"""

from .carga import a_dict, desde_dict, desde_json
from .generador import NS, VERSION_ESQUEMA, generar, generar_arbol
from .importes import a_decimal, formatear, redondear
from .modelo import (
    IGIC,
    IPSI,
    IRPF,
    IVA,
    ClaseFactura,
    Direccion,
    Emisor,
    Factura,
    FacturaInvalida,
    Impuesto,
    Linea,
    Receptor,
    TipoDocumento,
    TipoPersona,
    TipoResidencia,
)

__version__ = "0.1.0"

__all__ = [
    "IGIC",
    "IPSI",
    "IRPF",
    "IVA",
    "NS",
    "VERSION_ESQUEMA",
    "ClaseFactura",
    "Direccion",
    "Emisor",
    "Factura",
    "FacturaInvalida",
    "Impuesto",
    "Linea",
    "Receptor",
    "TipoDocumento",
    "TipoPersona",
    "TipoResidencia",
    "__version__",
    "a_decimal",
    "a_dict",
    "desde_dict",
    "desde_json",
    "formatear",
    "generar",
    "generar_arbol",
    "redondear",
]
