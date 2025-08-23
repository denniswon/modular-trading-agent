import base64, asyncio, os, getpass
from solana.rpc.async_api import AsyncClient
from solana.transaction import VersionedTransaction
from solana.rpc.commitment import Confirmed
from solders.message import to_bytes_versioned
from solders.transaction_status import UiTransactionEncoding
from solana.keypair import Keypair
from base58 import b58decode

from src.utils.secure_storage import load_secret

class SolanaWallet:
    def __init__(self, rpc_url: str, key_name: str):
        self.rpc_url = rpc_url
        self.key_name = key_name
        self._kp = None
        self.client: AsyncClient|None = None

    async def connect(self):
        self.client = AsyncClient(self.rpc_url, commitment=Confirmed)
        if self._kp is None:
            pw = getpass.getpass("Enter AES password to unlock wallet: ")
            sk_b58 = load_secret(self.key_name, pw)
            sk = b58decode(sk_b58)
            self._kp = Keypair.from_secret_key(sk)

    @property
    def pubkey(self):
        return self._kp.public_key

    async def sign_and_send(self, tx_base64: str, compute_unit_ixs=None):
        assert self.client
        raw = base64.b64decode(tx_base64)
        tx = VersionedTransaction.deserialize(raw)
        # NOTE: In a real flow, we would prepend ComputeBudget ixs into the compiled message.
        # Here we assume upstream supports priority fee; otherwise we just sign+send.
        tx.sign([self._kp])
        sig = await self.client.send_raw_transaction(
            bytes(tx), opts={"skip_preflight": False, "preflightCommitment": "confirmed", "encoding": UiTransactionEncoding.Base64}
        )
        await self.client.confirm_transaction(sig.value)
        return str(sig.value)
