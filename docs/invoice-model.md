# The invoice model

Five frozen dataclasses, each validating itself on construction. An invalid
invoice cannot be built, so it cannot be generated.

```
Factura
├── Emisor    ──┐
├── Receptor  ──┴── Direccion
└── Linea[]   ───── Impuesto[]
```

Everything raises `FacturaInvalida` (a `ValueError`) with a message that says
which field is wrong and what the schema expects.

## `Direccion`

```python
Direccion(calle, codigo_postal, poblacion, provincia, pais="ESP")
```

- `pais` is **ISO 3166-1 alpha-3** — `ESP`, `FRA`, `PRT`. Alpha-2 is rejected,
  because `ES` and `ESP` look similar enough to be pasted by mistake.
- A Spanish postcode must be five digits **including leading zeros**. `"8001"`
  is rejected; Barcelona is `"08001"`. This is the single most common data
  error when postcodes have passed through a spreadsheet, which strips the
  zero.
- `es_espanola` decides between the schema's `AddressInSpain` and
  `OverseasAddress` blocks.

## `Emisor` and `Receptor`

Same fields; two classes so the XML writer knows which side it is on.

```python
Emisor(nif, nombre, direccion, tipo_persona="J", tipo_residencia="R",
       apellido1="", apellido2="")
```

- `tipo_persona`: `"J"` legal entity, `"F"` natural person.
- `tipo_residencia`: `"R"` resident, `"U"` EU, `"E"` foreign.
- **A natural person needs `apellido1`.** Facturae stores `Name` and
  `FirstSurname` in separate elements; it has no field for a full name. If you
  hold "Juan Pérez García" in one column, you have to split it before you can
  emit a valid document, and the library says so rather than silently emitting
  a person with no surname.

The NIF is checked for being non-empty, not for its check digit. Validating
Spanish tax IDs is a separate problem with its own edge cases (NIE, CIF, other
EU VAT numbers), and a half-correct validator that rejects a valid ID is worse
than none.

## `Linea`

```python
Linea(descripcion, cantidad=1, precio_unitario=0, impuestos=(Impuesto(),), unidad="")
```

`bruto` is `cantidad × precio_unitario`, rounded to two decimals. It is not a
parameter — an amount that disagrees with its own quantity and price is exactly
the error this design removes.

Two rules that exist because the schema demands them:

- **A line must carry at least one tax.** If the operation is exempt, pass
  `Impuesto(IVA, 0)` explicitly. The schema requires the tax block; an exempt
  line at 0 % is a different statement from a line with no tax block at all,
  and only you know which one you mean.
- **No repeated tax codes in one line.** Two VAT entries on the same line is
  not "two rates", it is a bug — and the totals would double-count.

## `Impuesto`

```python
Impuesto(codigo=IVA, tipo=Decimal("21"))
```

- `codigo` is the two-digit `TaxTypeCode`. The constants exported are `IVA`
  (`"01"`), `IPSI` (`"02"`), `IGIC` (`"03"`) and `IRPF` (`"04"`).
- `tipo` is a **percentage, not a fraction**: 21 % is `21`, never `0.21`.
  A `0.21` would silently produce an invoice with 0.21 % VAT, so the number
  being a percentage is documented on the field itself.
- `se_retiene` is true for IRPF only. Withholdings are **subtracted** from the
  total; everything else is added.

## `Factura`

```python
Factura(numero, emisor, receptor, lineas, fecha=today, serie="",
        moneda="EUR", idioma="es", clase="OO", tipo_documento="FC",
        descripcion="")
```

- `numero` and `serie` are capped at 20 characters, which is what
  `InvoiceNumber` and `InvoiceSeriesCode` admit.
- An invoice with no lines is rejected.
- `clase` and `tipo_documento` come from `ClaseFactura` and `TipoDocumento`.

### Derived values

| Property | What it is |
|---|---|
| `total_bruto` | sum of line `bruto` |
| `total_repercutido` | sum of taxes charged |
| `total_retenido` | sum of withholdings |
| `total` | `bruto + repercutido − retenido` |

| Method | What it returns |
|---|---|
| `impuestos_repercutidos()` | `[(Impuesto, base, cuota), …]` grouped by rate |
| `impuestos_retenidos()` | the same, for withholdings |

The scalars are properties; the breakdowns are methods, because they group and
return a list rather than reading a value.

## Rounding

Every amount is rounded to two decimals with `redondear`, at the point where it
becomes an amount — line by line, and rate by rate — not once at the end.
That is what makes `Σ lines == total_bruto` hold exactly, instead of drifting
by a cent on long invoices.

`a_decimal` and `formatear` are exported if you need the same conversion and
the same two-decimal string formatting elsewhere in your own code.
