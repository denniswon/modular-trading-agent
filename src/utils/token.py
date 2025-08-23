from solana.rpc.async_api import AsyncClient
from solana.publickey import PublicKey
from solana.rpc.types import TokenAccountOpts
from base58 import b58decode
from typing import Optional

SPL_TOKEN_PROGRAM = PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")

async def get_token_decimals(client: AsyncClient, mint: str) -> int:
    resp = await client.get_token_supply(PublicKey(mint))
    return int(resp.value.decimals)

async def get_token_balance(client: AsyncClient, owner: str, mint: str) -> int:
    # returns raw amount (atomic units)
    opts = TokenAccountOpts(mint=mint, program_id=SPL_TOKEN_PROGRAM)
    resp = await client.get_token_accounts_by_owner(PublicKey(owner), opts)
    total = 0
    for acc in resp.value:
        ai = await client.get_token_account_balance(PublicKey(acc.pubkey))
        total += int(ai.value.amount)
    return total
