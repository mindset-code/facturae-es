# Getting started

## Install

```bash
pip install git+https://github.com/mindset-code/facturae-es
```

Python 3.9+. **Zero dependencies** — the XML is built with
`xml.etree.ElementTree` and the arithmetic with `decimal`, both from the
standard library.

Check the install without writing code:

```bash
facturae-es autocomprobar
```

It builds a sample invoice, checks its totals against figures written by hand
into the code, generates the XML and exits `1` if anything disagrees.

## The shortest complete invoice

```python
from decimal import Decimal
from facturae_es import Direccion, Emisor, Factura, Linea, Receptor, generar

factura = Factura(
    numero="001",
    emisor=Emisor(
        nif="B12345674",
        nombre="Talleres Ejemplo SL",
        direccion=Direccion("Calle Mayor 1", "08001", "Barcelona", "Barcelona"),
    ),
    receptor=Receptor(
        nif="A58818501",
        nombre="Cliente Ejemplo SA",
        direccion=Direccion("Gran Via 100", "28013", "Madrid", "Madrid"),
    ),
    lineas=[Linea("Consultoría", cantidad=Decimal("10"), precio_unitario=Decimal("100"))],
)

factura.total          # Decimal('1210.00') — 1000 + 21 % VAT
print(generar(factura))
```

Every line carries 21 % VAT unless you say otherwise. That default is a
convenience, not an opinion: pass `impuestos=` to change it.

## Totals are derived, never supplied

There is no `total=` parameter, on purpose. The total comes from the lines,
the lines from quantity times price, and the tax from the base:

```
line.bruto        = cantidad × precio_unitario          (rounded to 2 dp)
total_bruto       = Σ line.bruto
total_repercutido = Σ tax due, grouped by rate           (VAT, IGIC, IPSI…)
total_retenido    = Σ withholdings, grouped by rate      (IRPF)
total             = total_bruto + total_repercutido − total_retenido
```

An invoice whose stated total disagrees with its lines is not a rounding
problem you fix later; it is a document that will be rejected. Making it
underivable removes the failure mode.

## Money is `Decimal`, never `float`

```python
Linea("X", cantidad=Decimal("3"), precio_unitario=Decimal("0.1")).bruto
# Decimal('0.30')  — not 0.30000000000000004
```

If a value reaches the library as a `float` (which happens when it comes from
JSON), it is converted through its shortest faithful string representation
before becoming a `Decimal`. That recovers as much as can be recovered from a
number that has already been degraded — but pass strings or `Decimal` if you
control the source.

## Building from a dict or JSON

Most integrations do not have model objects; they have a dict from an API or a
database row:

```python
from facturae_es import desde_dict, desde_json

factura = desde_dict({"numero": "001", "emisor": {...}, "receptor": {...},
                      "lineas": [...]})
factura = desde_json(texto)
```

A misspelled key raises instead of being ignored. See [JSON format](json.md).

## From the command line

```bash
facturae-es plantilla > factura.json     # a filled-in starting point
facturae-es validar factura.json         # totals and breakdown
facturae-es generar factura.json -o factura.xml
```

Full reference: [command line](cli.md).

## What you still need

The XML this produces is **not signed**. Facturae requires an XAdES signature
before it can be submitted to FACe. See [signing and FACe](signing.md) for what
that involves and why it is not in this library.

## Next

- [The invoice model](invoice-model.md) — parties, lines, taxes, validation
- [JSON format](json.md) — every field, and the round trip
- [Command line](cli.md)
- [Signing and FACe](signing.md) — what is missing to submit
- [FAQ](faq.md)
