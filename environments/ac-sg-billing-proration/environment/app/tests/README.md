# Tests

`python -m unittest discover -s tests` runs everything; the release job runs the same command.

## Quarantine

Tests that are flaky in CI can be quarantined by listing their id in `tests/quarantine.txt`
(one per line, with the incident ticket in a comment). Quarantined tests are reported as skipped.
Remove the entry once the flake is fixed.
