# JSON format

`desde_dict` and `desde_json` build a `Factura` from plain data, which is what
most integrations actually have: a row from a database, a payload from an API,
a file on disk.

```python
from facturae_es import desde_dict, desde_json, a_dict
```

## The shape

```json
{
  "numero": "001",
  "serie": "A",
  "fecha": "2026-01-15",
  "descripcion": "Servicios de consultoría de enero",
  "emisor": {
    "nif": "B12345674",
    "nombre": "Talleres Ejemplo SL",
    "direccion": {
      "calle": "Calle Mayor 1",
      "codigo_postal": "08001",
      "poblacion": "Barcelona",
      "provincia": "Barcelona"
    }
  },
  "receptor": { "...": "same shape as emisor" },
  "lineas": [
    {
      "descripcion": "Consultoría técnica",
      "cantidad": 10,
      "precio_unitario": 100,
      "impuestos": [{"codigo": "01", "tipo": 21}, {"codigo": "04", "tipo": 15}]
    },
    { "descripcion": "Licencia", "cantidad": 1, "precio_unitario": 250 }
  ]
}
```

`facturae-es plantilla` writes exactly this, filled in and ready to edit.

## Fields

| Object | Required | Optional |
|---|---|---|
| invoice | `numero`, `emisor`, `receptor`, `lineas` | `fecha`, `serie`, `moneda`, `idioma`, `clase`, `tipo_documento`, `descripcion` |
| `emisor` / `receptor` | `nif`, `nombre`, `direccion` | `tipo_persona`, `tipo_residencia`, `apellido1`, `apellido2` |
| `direccion` | `calle`, `codigo_postal`, `poblacion`, `provincia` | `pais` (default `ESP`) |
| line | `descripcion` | `cantidad`, `precio_unitario`, `impuestos`, `unidad` |
| tax | — | `codigo` (default `"01"`), `tipo` (default `21`) |

`fecha` is ISO 8601, `AAAA-MM-DD`. `15/01/2026` is rejected — an ambiguous
date format is not something to guess at.

## An unknown key is an error, not noise

```python
desde_dict({..., "lineas": [{"descripcion": "X", "precio_unitraio": 100}]})
# FacturaInvalida: lineas[0]: campo(s) desconocido(s) ['precio_unitraio'].
#   Los admitidos son ['cantidad', 'descripcion', 'impuestos', ...]
```

The alternative — ignoring what you do not recognise — produces an invoice for
zero euros and says nothing. The typo is caught at the boundary, where it is
still cheap.

## Numbers

Amounts may arrive as string, `int` or `float`:

- **string and `int`** pass through unchanged.
- **`float`** goes through `repr()` first, which gives the shortest string that
  reconstructs the same float, and that string becomes the `Decimal`. It is the
  most faithful recovery available from a value that has already lost
  precision.

If you control the producer, emit strings: `"precio_unitario": "100.00"`. JSON
has no decimal type, and a string is the only way to say exactly what you mean.

## The round trip

`a_dict` produces a dict that `desde_dict` accepts, and the round trip
reproduces the same XML byte for byte:

```python
original = desde_dict(datos)
assert generar(desde_dict(a_dict(original))) == generar(original)
```

That is tested, and it is what makes it worth archiving both files: the XML is
what you deliver, the JSON is what lets you regenerate it later without keeping
the code that built it.

`a_dict` writes every amount as a string, because `Decimal` is not JSON
serialisable and going through `float` would defeat the point.

## Errors

Everything raises `FacturaInvalida`, which subclasses `ValueError`, with the
path to the offending field:

```
la factura necesita ['emisor', 'lineas', 'receptor']
lineas[1]: campo(s) desconocido(s) ['precio']
direccion necesita ['codigo_postal']
la fecha '15/01/2026' no esta en formato ISO (AAAA-MM-DD)
el JSON no es valido: Expecting value: line 1 column 1 (char 0)
```
