# Contributing

## Setup

```bash
git clone https://github.com/mindset-code/facturae-es
cd facturae-es
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check .
```

## The rules that shape this library

Before proposing a change, these are the decisions it is built on. They are not
accidents, and a change that reverses one needs to argue against the reason:

1. **Zero runtime dependencies.** It is what lets this drop into a system that
   already exists. A pull request that adds one has to show the job cannot be
   done with the standard library.
2. **Totals are derived, never accepted.** No `total=` parameter, ever. An
   invoice whose total disagrees with its lines is a rejected document.
3. **`Decimal` everywhere, `float` nowhere.** Amounts are money.
4. **Validation at construction, not at generation.** An invalid invoice should
   be impossible to build, so it cannot reach the XML writer.
5. **An unknown JSON key is an error.** Ignoring it produces a zero-euro
   invoice and says nothing.
6. **No signing.** See [docs/signing.md](docs/signing.md).

## Tests

Every change needs a test that fails before it and passes after. Two things get
extra attention because they have been wrong in real systems:

- **Amounts.** Assert the exact `Decimal`, never `pytest.approx`. If the
  expected value took arithmetic to work out, write the arithmetic in a comment
  the way `TOTALES_CONOCIDOS` does — a test that recomputes the expectation
  from the code under test proves nothing.
- **The XML.** Parse what was generated and assert on the parsed tree, not on a
  substring of the text. A substring match passes on malformed XML.

## Adding a field to the schema

Facturae 3.2.2 is large, and this library covers the part a normal invoice
needs. If you add an element:

1. Cite the schema. Say which element, in which block, and whether it is
   optional.
2. Add it to the model **and** to `carga.py`, or the JSON path silently loses
   it.
3. Add it to `a_dict`, or the round trip stops being a round trip. There is a
   test asserting the round trip regenerates identical XML; it should catch you.
4. Keep it optional unless the schema makes it mandatory.

## Style

Spanish for identifiers, docstrings and comments — the domain is Spanish and so
are the words (`factura`, `emisor`, `retenido`). English for user-facing
documentation. Comments explain *why*; the code already says what.

Line length 95, enforced by ruff.

## Reporting a bug

An [issue](https://github.com/mindset-code/facturae-es/issues) with the input
that reproduces it. **Pseudonymise it first** — replace real NIFs, names and
addresses with the ones from `facturae-es plantilla`. A bug report should not
contain somebody's tax data, and an invoice with a fake NIF reproduces a
formatting bug just as well as a real one.
