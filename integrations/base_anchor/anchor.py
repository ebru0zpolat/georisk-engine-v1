"""Anchor georisk asset-snapshot hashes on Base (Sepolia or Mainnet).

The anchor transaction is a 0-value self-transfer whose data field carries the
sha256 hash of the canonical snapshot JSON. That makes the snapshot content
tamper-evident: anyone with the snapshot payload and the tx hash can recompute
the hash and compare it against the on-chain data field.

Only ``hash`` operations run offline; ``anchor``/``verify`` need the ``web3``
package (see requirements.txt here) and these environment variables:

    BASE_ANCHOR_RPC_URL      Alchemy endpoint, e.g.
                             https://base-sepolia.g.alchemy.com/v2/<key>
    BASE_ANCHOR_PRIVATE_KEY  hex private key of a burner wallet with test ETH

Usage:
    python -m integrations.base_anchor.anchor hash --sample
    python -m integrations.base_anchor.anchor hash snapshot.json
    python -m integrations.base_anchor.anchor anchor snapshot.json
    python -m integrations.base_anchor.anchor verify <tx_hash> snapshot.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

SAMPLE_SNAPSHOT: dict[str, Any] = {
    "audit_id": "sample-audit-0001",
    "asset_name": "Sample Steel Plant",
    "latitude": 41.0082,
    "longitude": 28.9784,
    "radius_km": 5.0,
    "sector": "steel",
    "overall_score": 62,
    "components": {"flood": 40, "heat": 71, "wind": 55},
    "model_version": "risk-score-v0.1",
    "data_snapshot_id": "hazard_layers_2026_05",
    "asset_geometry_hash": "deadbeef",
    "uses_connector_fallback": True,
}


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic serialization: sorted keys, no whitespace, ASCII-safe."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def snapshot_hash(payload: dict[str, Any]) -> str:
    """sha256 hex digest of the canonical JSON form of a snapshot payload."""
    return hashlib.sha256(canonical_json(payload).encode("ascii")).hexdigest()


def _require_web3():
    try:
        from web3 import Web3
    except ImportError:
        sys.exit(
            "web3 is not installed. Run:\n"
            "  pip install -r integrations/base_anchor/requirements.txt"
        )
    return Web3


def _connect(Web3):
    rpc_url = os.environ.get("BASE_ANCHOR_RPC_URL")
    if not rpc_url:
        sys.exit("Set BASE_ANCHOR_RPC_URL to your Alchemy Base endpoint.")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        sys.exit(f"Could not reach RPC endpoint at {rpc_url}")
    return w3


def anchor_hash(digest_hex: str) -> str:
    """Publish a sha256 digest on-chain; returns the transaction hash."""
    Web3 = _require_web3()
    w3 = _connect(Web3)
    key = os.environ.get("BASE_ANCHOR_PRIVATE_KEY")
    if not key:
        sys.exit("Set BASE_ANCHOR_PRIVATE_KEY (use a burner wallet, never a real one).")
    account = w3.eth.account.from_key(key)

    tx = {
        "from": account.address,
        "to": account.address,
        "value": 0,
        "data": "0x" + digest_hex,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
    }
    tx["gas"] = w3.eth.estimate_gas(tx)
    fees = w3.eth.fee_history(1, "latest", [50])
    base_fee = fees["baseFeePerGas"][-1]
    priority = w3.to_wei(0.001, "gwei")
    tx["maxPriorityFeePerGas"] = priority
    tx["maxFeePerGas"] = base_fee * 2 + priority

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        sys.exit(f"Anchor transaction reverted: {tx_hash.hex()}")
    return "0x" + tx_hash.hex().removeprefix("0x")


def verify_anchor(tx_hash: str, expected_digest_hex: str) -> bool:
    """Check that the given transaction's data field matches the digest."""
    Web3 = _require_web3()
    w3 = _connect(Web3)
    tx = w3.eth.get_transaction(tx_hash)
    on_chain = tx["input"]
    on_chain_hex = on_chain.hex() if not isinstance(on_chain, str) else on_chain
    return on_chain_hex.removeprefix("0x").lower() == expected_digest_hex.lower()


def _load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "sample", False):
        return SAMPLE_SNAPSHOT
    if not args.snapshot:
        sys.exit("Provide a snapshot JSON file, or pass --sample.")
    return json.loads(Path(args.snapshot).read_text())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_hash = sub.add_parser("hash", help="print the canonical sha256 of a snapshot")
    p_hash.add_argument("snapshot", nargs="?", help="path to snapshot JSON")
    p_hash.add_argument("--sample", action="store_true", help="use built-in sample")

    p_anchor = sub.add_parser("anchor", help="hash a snapshot and anchor it on-chain")
    p_anchor.add_argument("snapshot", nargs="?", help="path to snapshot JSON")
    p_anchor.add_argument("--sample", action="store_true", help="use built-in sample")

    p_verify = sub.add_parser("verify", help="check an anchor tx against a snapshot")
    p_verify.add_argument("tx_hash", help="anchor transaction hash")
    p_verify.add_argument("snapshot", nargs="?", help="path to snapshot JSON")
    p_verify.add_argument("--sample", action="store_true", help="use built-in sample")

    args = parser.parse_args(argv)
    payload = _load_payload(args)
    digest = snapshot_hash(payload)

    if args.command == "hash":
        print(digest)
    elif args.command == "anchor":
        tx_hash = anchor_hash(digest)
        print(f"snapshot sha256: {digest}")
        print(f"anchor tx:       {tx_hash}")
        print(f"explorer:        https://sepolia.basescan.org/tx/{tx_hash}")
    elif args.command == "verify":
        if verify_anchor(args.tx_hash, digest):
            print(f"OK: on-chain data matches snapshot hash {digest}")
        else:
            sys.exit("MISMATCH: on-chain data does not match this snapshot")


if __name__ == "__main__":
    main()
