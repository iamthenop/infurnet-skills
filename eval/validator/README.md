# Validator regression fixtures

Static test cases for `tools/validate.py` structural checks.
Each subdirectory contains a minimal fixture demonstrating one
validator invariant.

These fixtures are not part of the governed skill/role corpus and
do not participate in inventory counts.

## Running

```bash
python3 eval/validator/run.py
```

Exit 0 when all regressions pass. Non-zero on any failure.
