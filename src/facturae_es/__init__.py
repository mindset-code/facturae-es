"""Facturae 3.2.2 en Python puro, sin dependencias.

Genera el XML del formato oficial de factura electronica espanola calculando
los totales a partir de las lineas, para que no puedan descuadrar.
"""

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
    "ClaseFactura",
    "Direccion",
    "Emisor",
    "Factura",
    "FacturaInvalida",
    "IGIC",
    "IPSI",
    "IRPF",
    "IVA",
    "Impuesto",
    "Linea",
    "NS",
    "Receptor",
    "TipoDocumento",
    "TipoPersona",
    "TipoResidencia",
    "VERSION_ESQUEMA",
    "__version__",
    "a_decimal",
    "formatear",
    "generar",
    "generar_arbol",
    "redondear",
]
