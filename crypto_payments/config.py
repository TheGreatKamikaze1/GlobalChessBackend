from __future__ import annotations

import os
import string
from dataclasses import dataclass
from decimal import Decimal

DEFAULT_BASE_RPC_URL = "https://mainnet.base.org"
DEFAULT_BASE_EXPLORER_URL = "https://basescan.org"
DEFAULT_BASE_CHAIN_ID = 8453
DEFAULT_BASE_USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


@dataclass(frozen=True)
class AssetConfig:
    symbol: str
    name: str
    contract_address: str
    decimals: int
    usd_price: Decimal


@dataclass(frozen=True)
class NetworkConfig:
    key: str
    name: str
    chain_id: int
    chain_id_hex: str
    currency_symbol: str
    public_rpc_url: str
    explorer_url: str
    treasury_address: str
    assets: dict[str, AssetConfig]


def normalize_address(address: str | None) -> str:
    if not address:
        raise ValueError("Wallet address is required")

    candidate = address.strip()
    if candidate.startswith("0x"):
        candidate = candidate[2:]

    if len(candidate) != 40 or any(ch not in string.hexdigits for ch in candidate):
        raise ValueError("Invalid wallet address")

    return f"0x{candidate.lower()}"


def get_supported_networks() -> dict[str, NetworkConfig]:
    base_treasury_address = os.getenv("BASE_TREASURY_ADDRESS", "").strip()

    assets = {
        "USDC": AssetConfig(
            symbol="USDC",
            name="USD Coin",
            contract_address=normalize_address(
                os.getenv("BASE_USDC_CONTRACT", DEFAULT_BASE_USDC_CONTRACT)
            ),
            decimals=int(os.getenv("BASE_USDC_DECIMALS", "6")),
            usd_price=Decimal("1.00"),
        )
    }

    return {
        "BASE": NetworkConfig(
            key="BASE",
            name="Base Mainnet",
            chain_id=DEFAULT_BASE_CHAIN_ID,
            chain_id_hex=hex(DEFAULT_BASE_CHAIN_ID),
            currency_symbol="ETH",
            public_rpc_url=os.getenv("BASE_RPC_URL", DEFAULT_BASE_RPC_URL),
            explorer_url=os.getenv("BASE_EXPLORER_URL", DEFAULT_BASE_EXPLORER_URL),
            treasury_address=normalize_address(base_treasury_address) if base_treasury_address else "",
            assets=assets,
        )
    }


def get_network_config(network_key: str) -> NetworkConfig:
    network = get_supported_networks().get((network_key or "").upper())
    if not network:
        raise ValueError("Unsupported crypto network")
    return network


def get_asset_config(network_key: str, asset_symbol: str) -> AssetConfig:
    network = get_network_config(network_key)
    asset = network.assets.get((asset_symbol or "").upper())
    if not asset:
        raise ValueError("Unsupported crypto asset")
    return asset
