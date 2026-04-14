from __future__ import annotations

from pacifica.client import PacificaClient, sf

MIN_BASIS_BPS = 5.0


class BasisArbStrategy:
    @staticmethod
    async def scan_basis_opportunities(client: PacificaClient) -> list[dict]:
        prices = await client.get_prices()
        results = []

        for item in prices:
            sym = item.symbol
            if not sym:
                continue

            mark = sf(item.mark)
            oracle = sf(item.oracle)

            if oracle == 0 or mark == 0:
                continue

            basis_bps = ((mark - oracle) / oracle) * 10_000

            if abs(basis_bps) < MIN_BASIS_BPS:
                continue

            direction = "short_perp" if basis_bps > 0 else "long_perp"

            results.append({
                "symbol": sym,
                "mark": mark,
                "oracle": oracle,
                "basis_bps": round(basis_bps, 4),
                "direction": direction,
            })

        return sorted(results, key=lambda x: abs(x["basis_bps"]), reverse=True)
