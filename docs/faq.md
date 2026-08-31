# FAQ

### Does it sign the invoice?

No, and that is deliberate. See [signing and FACe](signing.md). The document is
valid Facturae 3.2.2; the XAdES signature is a separate step with your own
certificate.

### Can I submit what it produces to FACe?

Not directly — it needs to be signed first. Everything else about the document
is ready.

### Why can't I set the total?

Because a total that disagrees with the lines is a document that gets rejected,
and the only way to make that impossible is to derive it. `total` comes from
the lines, the lines from quantity times price. If your source system already
has a total, compare it against `factura.total` and investigate any difference
— that comparison is worth more than copying the number across.

### The total is one cent off from my ERP. Which is right?

Check where each one rounds. This library rounds **at every amount** — line by
line, and rate by rate — rather than once at the end. Rounding only at the end
lets fractions of a cent accumulate and then land in one place. Both are
defensible arithmetic; they are not the same arithmetic, and on a long invoice
they differ.

### Why is 21 % written as `21` and not `0.21`?

Because the XML schema stores it as a percentage, and translating in the
library would mean everyone has to remember which side of the boundary they are
on. `0.21` is accepted as a *number* and would produce an invoice with 0.21 %
VAT — so it is documented on the field and covered by a test.

### Why does an exempt line still need a tax block?

Because the schema requires one. An exempt operation is `Impuesto(IVA, 0)` — a
statement that VAT applies at 0 % — which is a different claim from a line with
no tax block, and only you know which one the operation is. The library will
not choose for you.

### A natural person as issuer fails. Why?

Facturae keeps `Name` and `FirstSurname` in separate elements; it has no field
for a full name. If your database has one `nombre_completo` column, you have to
split it before you can emit a valid document. The library raises at
construction rather than emitting a person with no surname.

### Does it validate the NIF check digit?

No. Validating Spanish tax IDs correctly means handling NIF, NIE and CIF, each
with its own algorithm, plus foreign VAT numbers for non-resident parties. A
validator that is 95 % right rejects real customers, which is worse than not
validating. Only emptiness is checked.

### Why not `float` for amounts?

Because `0.1 + 0.2` is not `0.3` in binary floating point, and an invoice is
one of the places where that matters. Everything is `Decimal`. A `float` that
arrives from JSON is converted through its shortest faithful string
representation, which recovers as much as can be recovered — but pass strings
if you control the producer.

### Does it read Facturae XML back?

No. It generates. Reading arbitrary Facturae — including versions other than
3.2.2, signed documents and the extension mechanism — is a much larger problem
than writing one well-defined shape. `a_dict` gives you a round trip through
*your own* JSON, which covers archiving and regeneration.

### Which version of Facturae?

3.2.2, declared in `VERSION_ESQUEMA` and in the namespace, and asserted by
`autocomprobar`.

### Why zero dependencies?

So it drops into a system that already exists without a version negotiation.
`xml.etree.ElementTree` and `decimal` are enough for this job.

### When does mandatory B2B e-invoicing actually start?

Royal Decree 238/2026, of 25 March
([BOE-A-2026-7295](https://www.boe.es/buscar/act.php?id=BOE-A-2026-7295)),
develops the regime, and its fourth final provision counts the deadlines **from
the entry into force of the ministerial order** that develops the public
invoicing solution: twelve months for businesses whose turnover exceeded 8
million euros in the previous calendar year, twenty-four months for everyone
else. Until that order is published, no calendar date is fixed — so treat any
specific date you read elsewhere with suspicion, including one in an older
version of this repository.

**This is not legal or tax advice.** Check the official source before planning
around it.
