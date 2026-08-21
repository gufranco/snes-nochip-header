## What this changes

One or two sentences. What is different afterwards, and why it needed to be.

## How it was checked

Paste the output rather than describing it. A claim that the tests pass is not
evidence that they did.

```text
```

- [ ] `ruff format --check .` and `ruff check .` are clean
- [ ] `mypy` reports nothing
- [ ] Every test file runs, and coverage is 100% of statements and branches
- [ ] `conformance/hardware.test.py` still holds every constant to the specification

## If this changes the checksum, the offsets, or the size rule

Read page 1-2-20 of the development manual and not page 1-2-9. The two describe
different sums and only one of them is in the header.

A change here is not checked by the tests alone. Run the census over a library
you own and paste the two lines that matter:

```text
  properties held on N of N
  carried     true of N of N images with a self-consistent header
```

A change that moves the second number down is a regression even when every test
still passes, because the four properties only ask whether the code agrees with
itself.

## What it does not carry

- [ ] No cartridge, no fragment of one, and no digest fine enough to rebuild one
- [ ] Nothing that says where to obtain them
