"""Document -> index row.

Row format (consumed by the search service; do not change without a format bump):
  id        source doc id
  slug      url slug from the title
  lang      language code
  length    number of index tokens (stopwords removed)
  terms     up to 8 most frequent tokens, ties broken alphabetically
  checksum  sha256 prefix over the normalised title + body (change detection)
  minhash   64 x 32-bit minhash values over character 5-grams (near-duplicate detection)
"""
import hashlib
import re
import unicodedata
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset("a an and are as at be by for from has in is it of on or that the to was "
                      "were will with".split())
TOP_TERMS = 8
NUM_PERM = 64
SHINGLE = 5
_SALTS = [b"perm-%04d" % i for i in range(NUM_PERM)]


def normalize(text):
    """NFKD-fold accents away and lowercase."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def tokenize(text):
    return [tok for tok in TOKEN_RE.findall(normalize(text)) if tok not in STOPWORDS]


def slugify(title):
    return "-".join(TOKEN_RE.findall(normalize(title)))[:64] or "untitled"


def checksum(title, body):
    digest = hashlib.sha256()
    digest.update(normalize(title).encode("utf-8"))
    digest.update(b"\x00")
    digest.update(normalize(body).encode("utf-8"))
    return digest.hexdigest()[:32]


def minhash(tokens):
    text = " ".join(tokens)
    shingles = {text[i:i + SHINGLE] for i in range(max(1, len(text) - SHINGLE + 1))}
    encoded = [s.encode("utf-8") for s in sorted(shingles)]
    blake = hashlib.blake2b
    signature = []
    for salt in _SALTS:
        signature.append(min(int.from_bytes(blake(s, digest_size=4, salt=salt).digest(), "big")
                             for s in encoded))
    return signature


def transform_doc(doc):
    tokens = tokenize(doc.title + " " + doc.body)
    top = sorted(Counter(tokens).items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_TERMS]
    return {
        "id": doc.id,
        "slug": slugify(doc.title),
        "lang": doc.lang,
        "length": len(tokens),
        "terms": [term for term, _ in top],
        "checksum": checksum(doc.title, doc.body),
        "minhash": minhash(tokens),
    }
