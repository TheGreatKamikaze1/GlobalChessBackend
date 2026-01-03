from tronpy import Tron
from tronpy.keys import PrivateKey
from app.core.config import settings

client = Tron()
private_key = PrivateKey(bytes.fromhex(settings.TRON_PRIVATE_KEY))

def send_usdt(to_address: str, amount: float):
    contract = client.get_contract(settings.TRON_USDT_CONTRACT)

    txn = (
        contract.functions.transfer(
            to_address,
            int(amount * 1_000_000)
        )
        .with_owner(private_key.public_key.to_base58check_address())
        .build()
        .sign(private_key)
        .broadcast()
    )

    return txn["txid"]
