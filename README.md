# Solana Memecoin Bot (v2)
- Fixed slippage & priority fee added (configurable)
- GMGN & Photon executors wired to forward slippage/priority fee and also inject a ComputeBudget ix if remote API doesn't support it
- DexScreener websocket stream, Rugcheck + BubbleMaps validation, token-decimals/SOL price fetcher, AES-encrypted secret storage

## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.tools.secure_init --key-name SOL_PRIVATE_KEY   # will prompt for AES password and your base58 private key
python -m src.main --config config.yaml
```
Set `auto_execute: true` in `config.yaml` to place real trades.
