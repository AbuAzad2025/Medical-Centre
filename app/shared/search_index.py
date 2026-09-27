"""
Blind trigram index: the only way to do substring search over encrypted PHI.

Why this exists
---------------
AES-SIV makes ``=`` and B-tree indexes work on an encrypted column, but it
cannot make ``LIKE '%term%'`` work: a plaintext substring has no relationship
to the ciphertext. A search term has to become a *keyed* value the database can
match, so the standard answer is to index overlapping character n-grams.

For each searchable column we store one row per distinct trigram, with the
trigram itself replaced by an HMAC-SHA256 digest. Searching means digesting the
query's trigrams, finding patients that have *all* of them, and only then
decrypting those few candidates to confirm the substring really is there. The
final check is what makes results exact: trigram overlap alone produces false
positives (the trigrams may not be contiguous), and a candidate that fails the
check is discarded.

Security trade-off, stated plainly
----------------------------------
An HMAC digest is not reversible, but the *set* of digests is stable, so an
attacker holding the database can tell that two rows share a trigram, and can
count how often a given trigram occurs. That is frequency analysis, and it is
the accepted cost of making encrypted PHI searchable at all. The exposure is
bounded by RLS: every row is tenant-scoped, so an attacker needs write access
to another tenant's digests to learn anything about it. The key is
domain-separated from the blind index (label ``search-ngram-v1``), so a digest
leaked from one subsystem cannot be used to confirm a value in the other.

A full-field digest is still preferred where it is enough: trigrams only come
into play for substring queries, and a term shorter than :data:`NGRAM` has no
trigrams to match on, so it falls back to exact matching.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Length of the indexed n-grams. Three is the standard minimum that keeps the
#: row count tolerable while still being selective for names.
NGRAM = 3

#: Domain separation for this subsystem, so these digests are useless for
#: confirming a value through the plain blind index (and vice versa).
NGRAM_LABEL = b'search-ngram-v1'

#: Upper bound on candidates fetched before the exact re-check. Bounds the work
#: an over-broad trigram set (for example a single space) can cause, and keeps
#: the decrypted candidate set small.
DEFAULT_CANDIDATE_LIMIT = 200


def ngrams(value, size: int = NGRAM) -> list[str]:
    """Return the distinct n-grams of *value*, in a stable order.

    The value is expected to already be normalised (see
    :func:`app.shared.encrypted_type.normalize_for_index`) so that both the
    stored rows and the query term are built from the same alphabet.
    """
    if not value:
        return []
    text = str(value)
    if len(text) < size:
        # Too short to have an n-gram; callers must handle this case explicitly
        # rather than silently matching nothing.
        return []
    seen: dict[str, None] = {}
    for i in range(len(text) - size + 1):
        seen.setdefault(text[i : i + size], None)
    return list(seen)


def _service():
    from services.field_encryption_service import FieldEncryptionService

    return FieldEncryptionService.get_service()


def is_available() -> bool:
    """True when n-gram digests can actually be produced."""
    return _service() is not None


def ngram_digest(gram: str) -> str | None:
    """HMAC a single n-gram under the search-specific label."""
    if not gram:
        return None
    svc = _service()
    if svc is None:
        return None
    # Prefix the label so a digest here can never collide with a blind index
    # digest over the same characters.
    return svc.blind_index(NGRAM_LABEL + b':' + gram.encode('utf-8'))


def digests_for(value, size: int = NGRAM) -> list[str]:
    """Digests for every n-gram of *value*.

    Returns an empty list when encryption is not configured, so callers can tell
    "cannot search" apart from "no match" instead of silently matching nothing.
    """
    svc = _service()
    if svc is None:
        return []
    out: dict[str, None] = {}
    for gram in ngrams(value, size):
        d = svc.blind_index(NGRAM_LABEL + b':' + gram.encode('utf-8'))
        if d:
            out.setdefault(d, None)
    return list(out)


def term_digests(term, size: int = NGRAM) -> list[str]:
    """Alias of :func:`digests_for` that reads better at query sites."""
    return digests_for(term, size)


def is_indexable(term, size: int = NGRAM) -> bool:
    """Whether *term* is long enough to be searched as an n-gram query."""
    return bool(term) and len(str(term)) >= size
