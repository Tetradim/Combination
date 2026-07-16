# Updating Source Pins

Combination does not follow source branches automatically. An upgrade is an explicit experiment change.

## Procedure

1. Review the upstream Chain or Iron changes.
2. Update the relevant submodule to the desired commit.
3. Update the same SHA in `combination.lock.json`.
4. Update the same SHA in `src/sentinel_combination/components.py`.
5. Run:

```bash
combination doctor --strict
combination test-all
```

6. Record which experiments changed behavior.
7. Commit the gitlink, lock, and pin constant together.

## Required invariant

The following values must match:

- the gitlink SHA;
- the lock-file SHA;
- the `ComponentPin.commit` SHA;
- the checked-out submodule HEAD.

Do not update a pin by branch name alone.
