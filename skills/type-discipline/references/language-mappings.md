# Type discipline — language mappings

Lookup reference for canonical language-specific type mappings.
`skills/type-discipline/SKILL.md` governs the rules; this file carries
the per-language detail.

The rule is the value class, not the library. Other languages map by
analogy to the same value classes.

## Java and Python mappings

| Value class | Java | Python |
| --- | --- | --- |
| UUID identifier | `java.util.UUID` or value object | `uuid.UUID` or value object |
| Closed vocabulary | enum | enum or literal-backed type |
| Confusable identifiers | distinct value objects | distinct value objects |
| Cross-process timestamp | `java.time.Instant` | timezone-aware UTC `datetime.datetime` |
| Filesystem path | `java.nio.file.Path` | `pathlib.Path` |
| Hash / digest | byte array or typed wrapper | fixed-width `bytes` |
| Exact decimal | `java.math.BigDecimal` | `decimal.Decimal` |
