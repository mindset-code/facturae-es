# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`desde_dict`, `desde_json` and `a_dict`**: build a `Factura` from plain
  data and dump it back. Most integrations have a dict from an API or a
  database row, not model objects, and every one of them was writing the same
  loop of `.get()` calls. An unknown key raises rather than being ignored —
  a misspelled `precio_unitraio` used to produce a zero-euro invoice in
  silence. The round trip regenerates byte-identical XML, which is what makes
  it worth archiving the JSON next to the document.
- **Command-line interface** (`facturae-es`, also `python -m facturae_es`).
  `plantilla` writes a filled-in JSON to start from, `validar` shows the tax
  breakdown, `totales` emits the figures as JSON, `generar` writes the XML, and
  `autocomprobar` is a smoke test. Every command reads `-` from standard input,
  so they compose with whatever produces the data.
- **`autocomprobar`**: checks the sample invoice's totals against figures
  written **by hand** into the source, that the XML declares the schema
  version, and that the JSON round trip preserves the total. Exits non-zero on
  mismatch, so it can gate a deployment.
- **`examples/facturacion_completa.py`**: a runnable end-to-end example —
  build, verify totals, generate, re-parse the XML to check what was written,
  round-trip through JSON, and walk through five rejected inputs. The test
  suite executes it, so it cannot drift from the API.
- **Documentation** in `docs/`: getting started, the invoice model with the
  reason behind each validation, the JSON format, the CLI reference with real
  output, signing and FACe, and an FAQ.
- **`py.typed`**: the package now ships its type information; `mypy` and
  `pyright` were falling back to `Any` on the installed package.
- **English README** as the primary one, with the Spanish text complete in
  `README.es.md`.
- `CONTRIBUTING.md`, including the request to pseudonymise invoices in bug
  reports.

### Fixed

- **The README stated the wrong legal deadlines.** It said mandatory B2B
  e-invoicing arrives in "October 2027" for turnover above 8 million euros and
  "October 2028" for the rest. Royal Decree 238/2026, of 25 March
  ([BOE-A-2026-7295](https://www.boe.es/buscar/act.php?id=BOE-A-2026-7295)),
  fixes no such dates: its fourth final provision counts twelve and
  twenty-four months **from the entry into force of the ministerial order**
  developing the public invoicing solution. Until that order is published no
  calendar date exists, so the README now states the rule and links the BOE
  instead of quoting dates it cannot support.

## [0.1.0]

### Added

- Facturae 3.2.2 generation with no dependencies.
- Invoice model — parties, addresses, lines and taxes — validating itself at
  construction against what the schema requires.
- Totals derived from the lines, computed with `Decimal` and rounded at each
  amount, so the detail and the totals cannot disagree.
- IRPF subtracted and other taxes added, grouped by rate.
