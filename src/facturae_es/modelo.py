"""Los datos de una factura, con los importes ya cuadrados.

El esquema oficial de Facturae no comprueba que los totales sumen: un fichero
puede validar contra el XSD y aun asi llevar una cifra equivocada. Aqui los
totales NO se piden: se calculan a partir de las lineas, y por eso no pueden
discrepar.

Todo el dinero se maneja con ``Decimal``. Un ``float`` como 0.1 + 0.2 no vale
para una factura: la diferencia acaba en un descuadre de centimos que hace
saltar la validacion del receptor.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .importes import a_decimal, redondear

__all__ = [
    "IGIC",
    "IPSI",
    "IRPF",
    "IVA",
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
]


class FacturaInvalida(ValueError):
    """La factura no se puede emitir tal y como esta."""


# --- Valores tasados por el esquema (no son texto libre) --------------------

class TipoPersona:
    """``PersonTypeCodeType`` del esquema."""

    FISICA = "F"
    JURIDICA = "J"
    TODOS = frozenset({"F", "J"})


class TipoResidencia:
    """``ResidenceTypeCodeType``: extranjero, residente o Union Europea."""

    EXTRANJERO = "E"
    RESIDENTE = "R"
    UNION_EUROPEA = "U"
    TODOS = frozenset({"E", "R", "U"})


class ClaseFactura:
    """``InvoiceClassType``. OO es el caso normal: original individual."""

    ORIGINAL = "OO"
    ORIGINAL_RECTIFICATIVA = "OR"
    ORIGINAL_RECAPITULATIVA = "OC"
    COPIA = "CO"
    COPIA_RECTIFICATIVA = "CR"
    COPIA_RECAPITULATIVA = "CC"
    TODOS = frozenset({"OO", "OR", "OC", "CO", "CR", "CC"})


class TipoDocumento:
    """``InvoiceDocumentTypeType``: factura completa, abono o autofactura."""

    COMPLETA = "FC"
    ABONO = "FA"
    AUTOFACTURA = "AF"
    TODOS = frozenset({"FC", "FA", "AF"})


#: Codigos de ``TaxTypeCodeType`` de uso corriente. El esquema admite mas: se
#: pueden pasar como cadena de dos digitos.
IVA = "01"
IPSI = "02"
IGIC = "03"
IRPF = "04"


@dataclass(frozen=True)
class Impuesto:
    """Un tipo impositivo aplicado a una base.

    :param codigo: ``TaxTypeCode`` de dos digitos. El IVA es ``"01"``.
    :param tipo: porcentaje, no fraccion. El 21 % se escribe ``21``, no ``0.21``.
    """

    codigo: str = IVA
    tipo: Decimal = Decimal("21")

    def __post_init__(self) -> None:
        object.__setattr__(self, "tipo", a_decimal(self.tipo))
        dos_digitos = (
            isinstance(self.codigo, str)
            and len(self.codigo) == 2
            and self.codigo.isdigit()
        )
        if not dos_digitos:
            raise FacturaInvalida(
                f"el codigo de impuesto {self.codigo!r} no es de dos digitos; "
                f"el IVA es '01' y el IRPF '04'"
            )
        if self.tipo < 0:
            raise FacturaInvalida("un tipo impositivo no puede ser negativo")

    @property
    def se_retiene(self) -> bool:
        """El IRPF se resta del total; los demas se suman."""
        return self.codigo == IRPF

    def cuota(self, base: Decimal) -> Decimal:
        """Cuota sobre la base, redondeada a dos decimales."""
        return redondear(a_decimal(base) * self.tipo / Decimal(100))


@dataclass(frozen=True)
class Direccion:
    """Domicilio. ``pais`` va en ISO 3166-1 alfa-3: España es ``ESP``."""

    calle: str
    codigo_postal: str
    poblacion: str
    provincia: str
    pais: str = "ESP"

    def __post_init__(self) -> None:
        if self.pais == "ESP" and not (
            len(self.codigo_postal) == 5 and self.codigo_postal.isdigit()
        ):
            raise FacturaInvalida(
                f"el codigo postal espanol {self.codigo_postal!r} tiene que ser de "
                f"cinco digitos, con los ceros a la izquierda incluidos ('08001')"
            )
        if len(self.pais) != 3:
            raise FacturaInvalida(
                f"el pais {self.pais!r} va en ISO 3166-1 alfa-3 (ESP, FRA, PRT), no alfa-2"
            )

    @property
    def es_espanola(self) -> bool:
        """Decide entre ``AddressInSpain`` y ``OverseasAddress`` del esquema."""
        return self.pais == "ESP"


@dataclass(frozen=True)
class _Parte:
    """Comun a emisor y receptor."""

    nif: str
    nombre: str
    direccion: Direccion
    tipo_persona: str = TipoPersona.JURIDICA
    tipo_residencia: str = TipoResidencia.RESIDENTE
    apellido1: str = ""
    apellido2: str = ""

    def __post_init__(self) -> None:
        if self.tipo_persona not in TipoPersona.TODOS:
            raise FacturaInvalida(
                f"tipo_persona {self.tipo_persona!r}: solo 'F' (fisica) o 'J' (juridica)"
            )
        if self.tipo_residencia not in TipoResidencia.TODOS:
            raise FacturaInvalida(
                f"tipo_residencia {self.tipo_residencia!r}: 'R' residente, "
                f"'U' Union Europea, 'E' extranjero"
            )
        if not self.nif.strip():
            raise FacturaInvalida("el NIF no puede ir vacio")
        if not self.nombre.strip():
            raise FacturaInvalida("el nombre no puede ir vacio")
        if self.tipo_persona == TipoPersona.FISICA and not self.apellido1.strip():
            raise FacturaInvalida(
                "una persona fisica necesita apellido1: el esquema exige Name y "
                "FirstSurname en elementos separados, no un nombre completo"
            )


@dataclass(frozen=True)
class Emisor(_Parte):
    """Quien emite la factura."""


@dataclass(frozen=True)
class Receptor(_Parte):
    """Quien la recibe."""


@dataclass(frozen=True)
class Linea:
    """Una linea de detalle.

    El importe bruto sale de multiplicar cantidad por precio; no se pide, para
    que no pueda venir mal.
    """

    descripcion: str
    cantidad: Decimal = Decimal("1")
    precio_unitario: Decimal = Decimal("0")
    impuestos: Sequence[Impuesto] = field(default_factory=lambda: (Impuesto(),))
    unidad: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "cantidad", a_decimal(self.cantidad))
        object.__setattr__(self, "precio_unitario", a_decimal(self.precio_unitario))
        object.__setattr__(self, "impuestos", tuple(self.impuestos))
        if not self.descripcion.strip():
            raise FacturaInvalida("cada linea necesita una descripcion")
        if not self.impuestos:
            raise FacturaInvalida(
                f"la linea {self.descripcion!r} no lleva impuestos. Si esta exenta, "
                f"pasa Impuesto(IVA, 0) explicitamente: el esquema exige el bloque"
            )
        vistos = [i.codigo for i in self.impuestos]
        if len(vistos) != len(set(vistos)):
            raise FacturaInvalida(
                f"la linea {self.descripcion!r} repite un codigo de impuesto: {vistos}"
            )

    @property
    def bruto(self) -> Decimal:
        """Cantidad por precio, a dos decimales."""
        return redondear(self.cantidad * self.precio_unitario)


@dataclass(frozen=True)
class Factura:
    """Una factura completa, con los totales derivados de sus lineas."""

    numero: str
    emisor: Emisor
    receptor: Receptor
    lineas: Sequence[Linea]
    fecha: date = field(default_factory=date.today)
    serie: str = ""
    moneda: str = "EUR"
    idioma: str = "es"
    clase: str = ClaseFactura.ORIGINAL
    tipo_documento: str = TipoDocumento.COMPLETA
    descripcion: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "lineas", tuple(self.lineas))
        if not self.lineas:
            raise FacturaInvalida("una factura sin lineas no es una factura")
        if not self.numero.strip():
            raise FacturaInvalida("la factura necesita numero")
        if len(self.numero) > 20:
            raise FacturaInvalida(
                f"InvoiceNumber admite 20 caracteres y {self.numero!r} "
                f"tiene {len(self.numero)}"
            )
        if len(self.serie) > 20:
            raise FacturaInvalida("InvoiceSeriesCode admite 20 caracteres")
        if self.clase not in ClaseFactura.TODOS:
            raise FacturaInvalida(f"clase {self.clase!r} fuera de InvoiceClassType")
        if self.tipo_documento not in TipoDocumento.TODOS:
            raise FacturaInvalida(
                f"tipo_documento {self.tipo_documento!r}: 'FC' completa, "
                f"'FA' abono, 'AF' autofactura"
            )
        if len(self.moneda) != 3:
            raise FacturaInvalida(f"la moneda {self.moneda!r} va en ISO 4217: EUR, USD")

    # --- Totales, todos derivados ----------------------------------------

    @property
    def total_bruto(self) -> Decimal:
        """``TotalGrossAmount``: suma de las lineas antes de impuestos."""
        return redondear(sum((x.bruto for x in self.lineas), Decimal(0)))

    def _agrupar(self, retenidos: bool) -> list[tuple[Impuesto, Decimal, Decimal]]:
        """Impuestos agregados por codigo y tipo, con base y cuota sumadas.

        Facturae declara un bloque por combinacion de codigo y tipo, no uno por
        linea: dos lineas al 21 % van juntas en un solo bloque.
        """
        cajas: dict[tuple[str, str], list] = {}
        for linea in self.lineas:
            for imp in linea.impuestos:
                if imp.se_retiene != retenidos:
                    continue
                clave = (imp.codigo, str(imp.tipo))
                if clave not in cajas:
                    cajas[clave] = [imp, Decimal(0), Decimal(0)]
                cajas[clave][1] += linea.bruto
                cajas[clave][2] += imp.cuota(linea.bruto)
        return [
            (imp, redondear(base), redondear(cuota))
            for imp, base, cuota in (cajas[k] for k in sorted(cajas))
        ]

    def impuestos_repercutidos(self) -> list[tuple[Impuesto, Decimal, Decimal]]:
        """``TaxesOutputs``: IVA, IGIC y demas, que se suman al total."""
        return self._agrupar(retenidos=False)

    def impuestos_retenidos(self) -> list[tuple[Impuesto, Decimal, Decimal]]:
        """``TaxesWithheld``: el IRPF, que se resta."""
        return self._agrupar(retenidos=True)

    @property
    def total_repercutido(self) -> Decimal:
        """``TotalTaxOutputs``."""
        return redondear(sum((c for _, _, c in self.impuestos_repercutidos()), Decimal(0)))

    @property
    def total_retenido(self) -> Decimal:
        """``TotalTaxesWithheld``."""
        return redondear(sum((c for _, _, c in self.impuestos_retenidos()), Decimal(0)))

    @property
    def total(self) -> Decimal:
        """``InvoiceTotal``: bruto mas repercutidos menos retenidos."""
        return redondear(self.total_bruto + self.total_repercutido - self.total_retenido)
