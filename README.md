# facturae-es

**Spain's official e-invoice format, generated from Python with zero dependencies.**

[![tests](https://github.com/mindset-code/facturae-es/actions/workflows/tests.yml/badge.svg)](https://github.com/mindset-code/facturae-es/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](pyproject.toml)

> 🇬🇧 English · 🇪🇸 [Versión en español](README.es.md)

![facturae-es](docs/portada.png)

Royal Decree 238/2026, of 25 March
([BOE-A-2026-7295](https://www.boe.es/buscar/act.php?id=BOE-A-2026-7295)),
develops mandatory e-invoicing between Spanish businesses and professionals.
The deadlines are not counted from that decree: its fourth final provision ties
them to the entry into force of the ministerial order developing the public
invoicing solution — **twelve months** afterwards for businesses whose turnover
exceeded 8 million euros the previous year, **twenty-four** for everyone else.
Whenever that clock starts, a lot of people will need to emit Facturae XML.
This library emits it.

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

factura.total          # Decimal('1210.00')
print(generar(factura))
```

## Install

```bash
pip install git+https://github.com/mindset-code/facturae-es
```

Python 3.9+. Zero dependencies — `xml.etree.ElementTree` for the document,
`decimal` for the arithmetic. Check the install with:

```bash
facturae-es autocomprobar
```

## Totals are derived, never supplied

There is no `total=` parameter. The total comes from the lines, the lines from
quantity times price, the tax from the base:

```
total = Σ lines + Σ taxes charged − Σ withholdings
```

An invoice whose stated total disagrees with its detail is not a rounding
problem to fix later; it is a document that gets rejected. Making it
underivable removes the failure mode entirely.

Everything is `Decimal`, rounded at each amount rather than once at the end, so
`Σ lines == total_bruto` holds exactly.

## From the command line

```console
$ facturae-es plantilla > factura.json     # a filled-in starting point
$ facturae-es validar factura.json
Factura A001 de 2026-01-15: válida.
  Base         1250.00
  + 01 al 21% sobre 1250.00:     262.50
  - 04 al 15% sobre 1000.00:     150.00
  TOTAL        1362.50 EUR
$ facturae-es generar factura.json -o factura.xml
```

Reads `-` from standard input, so it composes:
`mi-erp exportar | facturae-es generar - > factura.xml`.
Full reference: [docs/cli.md](docs/cli.md).

## From a dict or JSON

Most integrations do not have model objects; they have a row or a payload:

```python
from facturae_es import desde_dict, desde_json, a_dict

factura = desde_json(texto)
datos = a_dict(factura)      # round-trips to the identical XML
```

**A misspelled key raises instead of being ignored.** A `precio_unitraio` that
gets quietly dropped produces an invoice for zero euros and says nothing; this
is the single most valuable thing the loader does. See [docs/json.md](docs/json.md).

## What it catches before you emit

Each of these is enforced at construction, with a message that says what the
schema expects:

- **A Spanish postcode of four digits.** `"8001"` is what a spreadsheet does to
  Barcelona's `"08001"`, and it is the most common data error of all.
- **A country in alpha-2.** `ESP`, not `ES` — the schema wants ISO 3166-1
  alpha-3.
- **A line with no tax block.** If the operation is exempt, that is
  `Impuesto(IVA, 0)` explicitly: the schema needs the block, and 0 % is a
  different statement from silence.
- **The same tax code twice on a line.** That is not two rates, it is a
  double-count.
- **A natural person with no surname.** Facturae keeps `Name` and
  `FirstSurname` in separate elements; there is no full-name field.

## Not signed

The XML this produces is **valid and unsigned**. Facturae requires an XAdES
signature before submission to FACe, and signing needs a certificate and a
crypto library — neither of which belongs in a zero-dependency formatter.
[docs/signing.md](docs/signing.md) explains the division of labour and what not
to do to the bytes in between.

## Documentation

| Page | What is in it |
|---|---|
| [Getting started](docs/getting-started.md) | install, first invoice, why totals are derived |
| [The invoice model](docs/invoice-model.md) | parties, lines, taxes, every validation and its reason |
| [JSON format](docs/json.md) | every field, floats, the round trip |
| [Command line](docs/cli.md) | each subcommand with real output |
| [Signing and FACe](docs/signing.md) | what is missing to submit, and why |
| [FAQ](docs/faq.md) | rounding, NIF check digits, the legal calendar |

A runnable end-to-end example is in
[`examples/facturacion_completa.py`](examples/facturacion_completa.py): build
an invoice, check the totals, emit the XML, read it back to verify what was
written, round-trip through JSON, and walk through five rejected inputs. The
test suite runs it, so it cannot rot.

## Scope

It generates the **document**. It does not sign it, does not submit it, and
does not validate against the official XSD at runtime — that would mean
vendoring or fetching the schema. For the chained hash VERI\*FACTU requires of
billing systems, a separate obligation, see
[pyverifactu-huella](https://github.com/mindset-code/pyverifactu-huella).

**This is not legal or tax advice.** Check the official sources before resting
a real obligation on it.

## Sources

- [Facturae](https://www.facturae.gob.es/) — official format, schemas and documentation
- [Real Decreto 238/2026, de 25 de marzo](https://www.boe.es/buscar/act.php?id=BOE-A-2026-7295) — mandatory B2B e-invoicing
- Ley 18/2022 (Crea y Crece), which the decree develops

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/mindset-code/facturae-es
cd facturae-es
pip install -e ".[dev]"
pytest -v
```

## License

MIT — see [LICENSE](LICENSE).

---

<sub>Maintained by <a href="https://github.com/mindset-code">Mindset &amp; Code</a>. If you need
e-invoicing wired into a system that is already running, write to
contacto@mindset-code.com.</sub>
