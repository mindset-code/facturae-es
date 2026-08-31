# Signing and FACe

> **The short version.** This library produces a valid, unsigned Facturae
> document. Facturae requires an **XAdES** electronic signature before it can be
> submitted. Signing is not in this library, and this page explains why and what
> to reach for instead.

## Why signing is not here

Signing an XML document needs three things this library deliberately does not
touch:

1. **A private key and a certificate.** Handling either means deciding where
   they live, how they are unlocked, and who can use them. That belongs in your
   application's security model, not in a formatting library.
2. **A cryptography dependency.** The whole design here is zero dependencies,
   which is what lets it drop into an existing system. A signature library
   would bring OpenSSL bindings with it.
3. **XAdES specifically**, not plain XML-DSig — an enveloped signature with a
   signing certificate, signing time and a signature policy. Getting it subtly
   wrong produces a document that parses and is rejected.

A library that generated *almost* a signature would be worse than one that is
clear about stopping at the document.

## The division of labour

```
  your data  ──▶  facturae-es  ──▶  unsigned XML
                                          │
                                          ▼
                                   XAdES signature        ← a signing library
                                          │                 + your certificate
                                          ▼
                                    .xsig file
                                          │
                                          ▼
                                        FACe               ← submission
```

## Practical route

The Spanish public administration publishes free desktop tools for signing
(AutoFirma is the usual one), and there are libraries for XAdES in most
ecosystems. Which to use depends on your platform and on where your certificate
lives, so this page will not recommend one it has not verified for your case.

What matters for using this library correctly:

- **Sign the bytes this library produces, unchanged.** Do not reformat,
  re-indent or re-serialise the XML before signing. An enveloped signature
  covers the document as it stands; any later change invalidates it.
- **Write the file, then sign the file.** `facturae-es generar factura.json -o
  factura.xml` gives you a clean artefact with nothing else on stdout.
- **Archive the JSON alongside.** `a_dict`/`desde_dict` round-trip to the same
  XML byte for byte, so the JSON is a reproducible record of what was signed.

## Naming

A signed Facturae file conventionally carries the `.xsig` extension. The
unsigned document this library writes is a plain `.xml`; renaming it does not
make it signed, and FACe will say so.

## What this library does guarantee

- The document is Facturae **3.2.2**, declared in `SchemaVersion` and in the
  namespace.
- The totals in the XML are derived from the lines, so `TotalGrossAmount`,
  `TotalTaxOutputs`, `TotalTaxesWithheld` and `InvoiceTotal` cannot disagree
  with the detail.
- Amounts are formatted to two decimals as strings, computed with `Decimal`.
- Structural constraints the schema imposes — a tax block on every line, a
  surname for a natural person, alpha-3 country codes, five-digit Spanish
  postcodes — are enforced at construction rather than discovered at
  submission.

It does **not** validate against the official XSD at runtime. That would mean
either vendoring the schema or fetching it over the network, and neither
belongs in a dependency-free library. If you need XSD validation in your
pipeline, run it as a separate step against the file this produces.

## Related

For the chained hash that VERI\*FACTU requires of billing systems — a different
obligation from the invoice format itself — see
[pyverifactu-huella](https://github.com/mindset-code/pyverifactu-huella).
