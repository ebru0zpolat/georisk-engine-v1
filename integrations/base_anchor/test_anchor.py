import hashlib
import json

from integrations.base_anchor.anchor import (
    SAMPLE_SNAPSHOT,
    canonical_json,
    snapshot_hash,
)


def test_hash_is_deterministic_across_key_order():
    reordered = json.loads(json.dumps(SAMPLE_SNAPSHOT))
    reordered = dict(reversed(list(reordered.items())))
    assert snapshot_hash(reordered) == snapshot_hash(SAMPLE_SNAPSHOT)


def test_hash_changes_when_payload_changes():
    tampered = {**SAMPLE_SNAPSHOT, "overall_score": SAMPLE_SNAPSHOT["overall_score"] + 1}
    assert snapshot_hash(tampered) != snapshot_hash(SAMPLE_SNAPSHOT)


def test_hash_matches_manual_sha256():
    expected = hashlib.sha256(canonical_json(SAMPLE_SNAPSHOT).encode()).hexdigest()
    assert snapshot_hash(SAMPLE_SNAPSHOT) == expected
