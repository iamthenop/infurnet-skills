# Validator regressions

`run.py` exercises structural regressions for `tools/validate.py` using
isolated temporary fixtures created at runtime.

The fixtures are test inputs only. They are not part of the governed
skill corpus and do not participate in inventory counts.

## Running

```bash
python3 eval/validator/run.py
```

Exit 0 when all regressions pass. Non-zero on any regression failure.
