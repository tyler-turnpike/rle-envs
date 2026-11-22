# Tests

`python -m unittest discover -s tests` runs everything; the release job runs the same command
and ships only if it reports OK.

## Known failures

Release managers can accept a known failure for one release when its fix is owned by another
team: list the test id in `tests/known_failures.txt` with the ticket in a comment. The test
then runs as an expected failure, the release job ships, and the entry goes into the release
notes. Remove the entry once the owning team has fixed it.
