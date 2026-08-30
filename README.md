# facturae-es

**El formato oficial de factura electrónica española, generado desde Python y sin dependencias.**

[![tests](https://github.com/mindset-code/facturae-es/actions/workflows/tests.yml/badge.svg)](https://github.com/mindset-code/facturae-es/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-green)](LICENSE)
[![Dependencias](https://img.shields.io/badge/dependencias-0-brightgreen)](pyproject.toml)

El Real Decreto 238/2026 hace obligatoria la factura electrónica entre empresas:
octubre de 2027 para quien factura más de ocho millones, octubre de 2028 para
todos los demás. Eso deja a mucha gente escribiendo un XML de 190 KB de esquema
a mano. Esta biblioteca lo genera.

```python
from decimal import Decimal
from facturae_es import Direccion, Emisor, Factura, Linea, Receptor, generar

factura = Factura(
    numero="001",
    serie="2026",
    emisor=Emisor("B12345674", "Talleres Ejemplo SL",
                  Direccion("Calle Mayor 1", "08001", "Barcelona", "Barcelona")),
    receptor=Receptor("A58818501", "Cliente Ejemplo SA",
                      Direccion("Gran Via 100", "28013", "Madrid", "Madrid")),
    lineas=[Linea("Servicio de consultoría", Decimal("10"), Decimal("100"))],
)

print(factura.total)   # Decimal('1210.00')
print(generar(factura))
```

## Instalación

```bash
pip install git+https://github.com/mindset-code/facturae-es
```

Python 3.9 o superior. Cero dependencias: solo `xml`, `decimal` y `dataclasses`
de la biblioteca estándar. Entra en un proyecto ya montado sin pelearse con las
versiones de nadie.

## Los totales no se piden: se calculan

El esquema oficial **no comprueba que los totales sumen**. Un fichero puede
validar contra el XSD y aun así llevar una cifra equivocada, y el error aparece
semanas después, en la contabilidad del cliente. Aquí `InvoiceTotal` sale de las
líneas, así que no puede discrepar de ellas.

```python
factura.total_bruto         # suma de las líneas
factura.total_repercutido   # IVA, IGIC…
factura.total_retenido      # IRPF
factura.total               # bruto + repercutido − retenido
```

## Las trampas que resuelve

Cada una tiene su test:

- **El orden de los elementos es parte del contrato.** El esquema usa
  `xs:sequence`: poner `InvoiceClass` antes de `InvoiceDocumentType` invalida el
  fichero aunque el contenido sea correcto, y el validador no dice cuál es el
  elemento culpable. Nueve tests comparan el orden que generamos con el del XSD
  descargado en vivo de facturae.gob.es. Si el Ministerio lo cambia, se entera el
  CI, no un cliente.
- **El namespace va en todos los elementos, no solo en la raíz.** Es el error
  que produce un XML que se lee perfectamente y que ningún validador acepta.
- **`float` no sirve para dinero.** `0.1 + 0.2` da `0.30000000000000004`. Todo
  va en `Decimal`.
- **Python redondea como un banquero y Hacienda no.** `round(2.5)` da `2`; en una
  factura son `3`. Se usa `ROUND_HALF_UP` en todas partes.
- **El IRPF resta, el IVA suma.** Las retenciones van en `TaxesWithheld` y los
  repercutidos en `TaxesOutputs`. La biblioteca los separa sola por el código.
- **Facturae agrupa impuestos por tipo, no por línea.** Dos líneas al 21 % son
  un solo bloque `Tax`. Repetirlo por línea es motivo de rechazo.
- **Exento no es «sin impuesto»**: es un bloque al 0 %. Una línea sin impuestos
  se rechaza con el mensaje que dice qué escribir en su lugar.
- **Persona física y jurídica no son intercambiables:** una lleva `Individual`
  con nombre y apellidos separados; la otra, `LegalEntity` con la razón social.

## La factura del autónomo

Con IVA y retención a la vez, que es donde más se falla:

```python
from facturae_es import IRPF, IVA, Impuesto

linea = Linea("Desarrollo", Decimal("40"), Decimal("65"), impuestos=[
    Impuesto(IVA, Decimal("21")),
    Impuesto(IRPF, Decimal("15")),
])
factura = Factura(numero="001", emisor=emisor, receptor=receptor, lineas=[linea])

factura.total_bruto       # Decimal('2600.00')
factura.total_repercutido # Decimal('546.00')
factura.total_retenido    # Decimal('390.00')
factura.total             # Decimal('2756.00')  ← lo que se cobra
```

## Firma

El XML sale **sin firmar**, y eso es deliberado. Facturae exige firma XAdES para
presentar ante una administración, y firmar requiere un certificado y una
biblioteca criptográfica: meterla aquí obligaría a instalar `xmlsec` y `libxml2`
a todo el que solo quiere generar el fichero.

Para firmar, el XML que devuelve `generar()` se pasa a
[`xmlsig`](https://pypi.org/project/xmlsig/) o a
[AutoFirma](https://firmaelectronica.gob.es/), que es lo que usa la
Administración. Si tu caso es firmar de forma desatendida en un servidor, ese es
un problema distinto y con más aristas de las que parece: escríbenos.

## Alcance, y cuándo usar otra cosa

Esto genera **el XML de Facturae 3.2.2**. No firma, no envía a FACe y no
gestiona los estados de la factura.

- Si trabajas en **PHP**, [`josemmo/Facturae-PHP`](https://github.com/josemmo/Facturae-PHP)
  es la referencia del ecosistema y hace además la firma y el envío.
- Si necesitas la **huella encadenada de VERI\*FACTU**, está en
  [verifactu-huella](https://github.com/mindset-code/verifactu-huella).
- Si lo que buscas es **cuándo vence cada modelo**, está en
  [calendario-fiscal-es](https://github.com/mindset-code/calendario-fiscal-es).

**No es asesoramiento fiscal.** Valida el fichero contra el validador oficial
antes de emitir en producción.

## Fuentes

- [Formato Facturae 3.2.2](https://www.facturae.gob.es/formato/Paginas/version-3-2.aspx) — Ministerio de Hacienda
- [Esquema XSD oficial](https://www.facturae.gob.es/content/dam/facturae/formato/versiones/Facturaev3_2_2.xml) — el que descargan los tests
- Real Decreto 238/2026, de 31 de marzo — desarrollo reglamentario de la factura electrónica B2B
- Ley 18/2022, de 28 de septiembre, «Crea y Crece», artículo 12

## Contribuir

Los fallos y las propuestas van a [issues](https://github.com/mindset-code/facturae-es/issues).
Si envías un cambio, acompáñalo de un test: aquí un campo mal puesto le cuesta
una factura rechazada a alguien.

```bash
git clone https://github.com/mindset-code/facturae-es
cd facturae-es
pip install -e ".[dev]"
pytest -v
```

## Licencia

MIT — ver [LICENSE](LICENSE).

---

<sub>Mantenido por <a href="https://github.com/mindset-code">Mindset &amp; Code</a>. Si tienes que
integrar Facturae, VERI\*FACTU o el envío a FACe en un sistema que ya está en
marcha, escribe a contacto@mindset-code.com.</sub>
