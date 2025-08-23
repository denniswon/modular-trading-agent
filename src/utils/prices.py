import aiohttp, os, asyncio

COINGECKO = os.getenv("COINGECKO_URL", "https://api.coingecko.com/api/v3")

async def fetch_json(session, url):
    async with session.get(url, timeout=20) as r:
        r.raise_for_status()
        return await r.json()

async def get_sol_price_usd(session=None) -> float:
    close = False
    if session is None:
        session = aiohttp.ClientSession()
        close = True
    try:
        url = f"{COINGECKO}/simple/price?ids=solana&vs_currencies=usd"
        js = await fetch_json(session, url)
        return float(js.get("solana", {}).get("usd", 0.0))
    finally:
        if close:
            await session.close()
