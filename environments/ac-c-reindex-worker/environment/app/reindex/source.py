"""Source corpus: the documents table the search index is built from.

The corpus lives in data/docs.db (SQLite).  Ids are increasing but not contiguous
(deleted rows are purged now and then), and soft-deleted rows are skipped.
`generate_corpus` builds the fixture corpus used in dev images and tests.
"""
import random
import sqlite3
from collections import namedtuple

Doc = namedtuple("Doc", "id title body lang")

DEFAULT_SEED = 20240611
DEFAULT_COUNT = 6000

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    lang TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""

_ACCENTED = ["café", "naïve", "résumé", "über", "façade", "Ångström", "smörgåsbord",
             "jalapeño", "Zürich", "déjà", "crème", "señor", "Straße", "coöperate"]
_STOP = ["the", "of", "and", "to", "in", "is", "for", "with", "on", "as", "by", "at"]


def _vocabulary(rng, size=700):
    onsets = ["b", "c", "d", "f", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t",
              "v", "w", "z", "br", "ch", "cl", "dr", "gr", "pl", "qu", "sh", "st", "th", "tr"]
    vowels = ["a", "e", "i", "o", "u", "ai", "ea", "io", "ou", "y"]
    codas = ["", "", "n", "r", "s", "t", "l", "m", "ck", "nd", "st", "x"]
    words = set()
    while len(words) < size:
        syllables = rng.randint(1, 3)
        words.add("".join(rng.choice(onsets) + rng.choice(vowels) + rng.choice(codas)
                          for _ in range(syllables)))
    return sorted(words) + _ACCENTED + _STOP * 6


def generate_corpus(path, count=DEFAULT_COUNT, seed=DEFAULT_SEED):
    """Write a deterministic corpus of `count` documents to the SQLite file at `path`."""
    rng = random.Random(seed)
    vocab = _vocabulary(rng)
    rows, doc_id = [], 0
    for _ in range(count):
        doc_id += rng.choice((1, 1, 1, 2, 3))
        title = " ".join(rng.choice(vocab) for _ in range(rng.randint(2, 7))).title()
        sentences = []
        for _ in range(rng.randint(0, 9)):
            words = [rng.choice(vocab) for _ in range(rng.randint(4, 18))]
            if rng.random() < 0.15:
                words[0] = words[0].upper()
            sentences.append(" ".join(words).capitalize() + rng.choice((".", "!", "?", "...", ";")))
        body = " ".join(sentences)
        lang = rng.choice(("en", "en", "en", "de", "fr"))
        deleted = 1 if rng.random() < 0.04 else 0
        updated = "2024-%02d-%02d" % (rng.randint(1, 12), rng.randint(1, 28))
        rows.append((doc_id, title, body, lang, deleted, updated))
    conn = sqlite3.connect(path)
    with conn:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM docs")
        conn.executemany("INSERT INTO docs VALUES (?, ?, ?, ?, ?, ?)", rows)
    conn.close()
    return len(rows)


class Source:
    """Read-only access to the live (not soft-deleted) documents, in id order."""

    def __init__(self, path):
        self.conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM docs WHERE deleted = 0").fetchone()[0]

    def batches(self, start_id=0, size=25):
        """Yield lists of Docs with id >= start_id, `size` at a time, in id order."""
        next_id = start_id
        while True:
            rows = self.conn.execute(
                "SELECT id, title, body, lang FROM docs WHERE deleted = 0 AND id >= ? "
                "ORDER BY id LIMIT ?", (next_id, size)).fetchall()
            if not rows:
                return
            yield [Doc(*row) for row in rows]
            next_id = rows[-1][0] + 1

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "data/docs.db"
    print("wrote %d docs to %s" % (generate_corpus(out), out))
