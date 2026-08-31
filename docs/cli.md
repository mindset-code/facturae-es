# Command line

Installing the package puts `facturae-es` on your `PATH`. Everything also works
as `python -m facturae_es`.

Every command that reads an invoice accepts `-` for standard input, so they
compose.

## `plantilla` — somewhere to start

```console
$ facturae-es plantilla > factura.json
```

Writes a complete, valid invoice in JSON: two lines, one of them with VAT and
IRPF, both parties filled in. Edit it rather than building the shape from the
documentation.

With `-o` it writes to a file and reports on stderr, leaving stdout clean.

## `validar` — does it hold together?

```console
$ facturae-es validar factura.json
Factura A001 de 2026-01-15: válida.
  Emisor    Talleres Ejemplo SL (B12345674)
  Receptor  Cliente Ejemplo SA (A58818501)
  Líneas    2
  Base         1250.00
  + 01 al 21% sobre 1250.00:     262.50
  - 04 al 15% sobre 1000.00:     150.00
  TOTAL        1362.50 EUR
```

The `+` lines are taxes charged, the `-` lines withholdings. Note the two
different bases: VAT applies to both lines, IRPF only to the professional
service.

`--json` gives the same figures as an object.

## `totales` — just the numbers

```console
$ facturae-es totales factura.json
{
  "numero": "001",
  "serie": "A",
  "fecha": "2026-01-15",
  "lineas": 2,
  "total_bruto": "1250.00",
  "total_repercutido": "262.50",
  "total_retenido": "150.00",
  "total": "1362.50"
}
```

Amounts are strings so that no consumer can turn them into floats by accident.

## `generar` — the XML

```console
$ facturae-es generar factura.json -o factura.xml
Escrito factura.xml: Facturae 3.2.2, factura A001, total 1362.50 EUR
```

Without `-o` the XML goes to stdout and the report to stderr, so a redirect
gives you a clean file.

`--sin-declaracion` omits the `<?xml ...?>` declaration, for embedding the tree
in another document.

## `autocomprobar` — is the install sane?

```console
$ facturae-es autocomprobar
Autocomprobación correcta: Facturae 3.2.2, factura de ejemplo con total 1362.50 EUR y XML de 6154 bytes.
$ echo $?
0
```

It checks the sample invoice's totals against figures **written by hand** into
the source, that the XML declares the schema version, and that the JSON round
trip preserves the total. Exits `1` on any mismatch, so it gates a deployment:

```bash
facturae-es autocomprobar && ./desplegar.sh
```

## Composing

```bash
# straight from a template, no intermediate file
facturae-es plantilla | facturae-es totales -

# from your own system, through jq, into a signed pipeline
mi-erp exportar --factura 001 | facturae-es generar - > factura.xml
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | fine |
| `1` | `autocomprobar` found a mismatch |
| `2` | invalid invoice, malformed JSON, missing file, or bad arguments |

Invalid data prints one readable line to stderr — the same message the library
would raise — not a traceback:

```console
$ facturae-es validar incompleta.json
factura inválida: la factura necesita ['emisor', 'lineas', 'receptor']
```

## What the XML still needs

It is **unsigned**. Facturae requires XAdES before submission to FACe. See
[signing and FACe](signing.md).
