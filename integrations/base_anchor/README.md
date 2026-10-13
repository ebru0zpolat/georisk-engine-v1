# Base anchor — tamper-evident snapshot hashes

Anchors the sha256 hash of a georisk `AssetSnapshot` payload on Base, so a risk
assessment made at a point in time can be proven unmodified later. The anchor
is a 0-value self-transfer whose `data` field carries the hash — no smart
contract, no tokens, cost is a fraction of a cent (free on testnet).

## One-time setup

1. **Enable Base Sepolia** on your Alchemy app ("Enable networks" on the app
   dashboard) and copy the Base Sepolia endpoint URL.
2. **Create a burner wallet** — never reuse a wallet that holds real funds:
   ```bash
   pip install -r integrations/base_anchor/requirements.txt
   python -c "from eth_account import Account; a = Account.create(); print('address:', a.address); print('key:', a.key.hex())"
   ```
3. **Fund it with test ETH** from a Base Sepolia faucet (e.g. the Alchemy
   faucet at https://www.alchemy.com/faucets/base-sepolia). A tiny amount
   covers thousands of anchors.
4. **Export the environment variables** (or put them in a local `.env` you do
   not commit):
   ```bash
   export BASE_ANCHOR_RPC_URL="https://base-sepolia.g.alchemy.com/v2/<your-key>"
   export BASE_ANCHOR_PRIVATE_KEY="0x<burner-key>"
   ```

## Usage

```bash
# Hash only (offline, no web3 needed) — using the built-in sample payload
python -m integrations.base_anchor.anchor hash --sample

# Anchor a real snapshot (JSON export of an AssetSnapshot, e.g. model_dump())
python -m integrations.base_anchor.anchor anchor snapshot.json

# Later: prove the snapshot is unchanged
python -m integrations.base_anchor.anchor verify 0x<tx_hash> snapshot.json
```

`anchor` prints the transaction hash and a Basescan link. Store the tx hash
alongside the snapshot (an `anchor_tx` column on the case store is the natural
home) — the pair (snapshot JSON, tx hash) is the verifiable artifact.

## Going to mainnet

Point `BASE_ANCHOR_RPC_URL` at your Base Mainnet endpoint and fund the burner
with a few dollars of real ETH on Base. Nothing else changes, except the
explorer domain is `basescan.org` instead of `sepolia.basescan.org`.

## Notes

- Hashing is canonical (sorted keys, compact separators), so the same payload
  always yields the same digest regardless of key order or whitespace.
- The private key is read from the environment only; nothing here writes or
  logs it. Treat the burner as disposable.
