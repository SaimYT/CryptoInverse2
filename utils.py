import aiohttp
from decimal import Decimal


COINGECKO_IDS = {
    "SOL": "solana",
    "TRX": "tron",
    "USDT_TRC20": "tether",
    "TON": "the-open-network",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "HYPE": "hyperliquid",
    "ARB": "arbitrum",
    "MATIC": "matic-network",
}


async def get_crypto_prices():
    prices = {k: {"usd": Decimal("0"), "rub": Decimal("0")} for k in [
        "SOL", "TRX", "USDT_TRC20", "TON", "ETH", "BNB", "HYPE", "BASE", "ARB", "MATIC"
    ]}

    ids = ",".join(COINGECKO_IDS.values())
    try:
        async with aiohttp.ClientSession() as session:
            url = (
                f"https://api.coingecko.com/api/v3/simple/price"
                f"?ids={ids}&vs_currencies=usd,rub"
            )
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()

                for coin, cg_id in COINGECKO_IDS.items():
                    if cg_id in data:
                        prices[coin]["usd"] = Decimal(str(data[cg_id]["usd"]))
                        prices[coin]["rub"] = Decimal(str(data[cg_id]["rub"]))

                if "ethereum" in data:
                    prices["BASE"]["usd"] = Decimal(str(data["ethereum"]["usd"]))
                    prices["BASE"]["rub"] = Decimal(str(data["ethereum"]["rub"]))

    except Exception as e:
        print(f"Ошибка получения курсов: {e}")

    return prices


async def get_sol_balance(address: str) -> Decimal:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.mainnet-beta.solana.com", json=payload, timeout=10
            ) as resp:
                data = await resp.json()
                lamports = data.get("result", {}).get("value", 0)
                return Decimal(lamports) / Decimal(10**9)
    except Exception as e:
        print(f"Ошибка Solana RPC: {e}")
        return Decimal("0")


async def get_trc20_balance(address: str) -> Decimal:
    try:
        url = f"https://api.trongrid.io/v1/accounts/{address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                trx_balance = data.get("data", [{}])[0].get("balance", 0)
                return Decimal(trx_balance) / Decimal(10**6)
    except Exception as e:
        print(f"Ошибка TronGrid: {e}")
        return Decimal("0")


async def get_ton_balance(address: str) -> Decimal:
    try:
        url = f"https://toncenter.com/api/v2/getAddressBalance?address={address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return Decimal(data["result"]) / Decimal(10**9)
                return Decimal("0")
    except Exception as e:
        print(f"Ошибка TON API: {e}")
        return Decimal("0")