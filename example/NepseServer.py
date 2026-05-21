import glob
import json
import os
import threading
import time
from json import JSONDecodeError

import flask
from flask import Flask, request

try:
    from nepse import Nepse
except ImportError:
    import sys

    sys.path.append("../")
    from nepse import Nepse

app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True

nepse = Nepse()
nepse.setTLSVerification(False)

REFRESH_INTERVAL = 5  # seconds

_cache = {}
_cache_lock = threading.Lock()


def _safe_fetch(key, fn):
    try:
        data = fn()
        with _cache_lock:
            _cache[key] = data
    except Exception as e:
        print(f"[auto-refresh] failed to update {key}: {e}")


def _refresh_loop():
    fetchers = {
        "summary": nepse.getSummary,
        "nepseIndex": nepse.getNepseIndex,
        "nepseSubIndices": nepse.getNepseSubIndices,
        "topGainers": nepse.getTopGainers,
        "topLosers": nepse.getTopLosers,
        "topTenTrade": nepse.getTopTenTradeScrips,
        "topTenTransaction": nepse.getTopTenTransactionScrips,
        "topTenTurnover": nepse.getTopTenTurnoverScrips,
        "supplyDemand": nepse.getSupplyDemand,
        "isNepseOpen": nepse.isNepseOpen,
        "priceVolume": nepse.getPriceVolume,
        "liveMarket": nepse.getLiveMarket,
        "companyList": nepse.getCompanyList,
        "securityList": nepse.getSecurityList,
    }
    while True:
        print("[auto-refresh] refreshing data...")
        for key, fn in fetchers.items():
            _safe_fetch(key, fn)
        print("[auto-refresh] done.")
        time.sleep(REFRESH_INTERVAL)


def _get(key):
    with _cache_lock:
        return _cache.get(key)


_refresh_thread = threading.Thread(target=_refresh_loop, daemon=True)
_refresh_thread.start()

routes = {
    "PriceVolume": "/PriceVolume",
    "Summary": "/Summary",
    "SupplyDemand": "/SupplyDemand",
    "TopGainers": "/TopGainers",
    "TopLosers": "/TopLosers",
    "TopTenTradeScrips": "/TopTenTradeScrips",
    "TopTenTurnoverScrips": "/TopTenTurnoverScrips",
    "TopTenTransactionScrips": "/TopTenTransactionScrips",
    "IsNepseOpen": "/IsNepseOpen",
    "NepseIndex": "/NepseIndex",
    "NepseSubIndices": "/NepseSubIndices",
    "DailyNepseIndexGraph": "/DailyNepseIndexGraph",
    "DailyScripPriceGraph": "/DailyScripPriceGraph",
    "CompanyList": "/CompanyList",
    "SecurityList": "/SecurityList",
    "TradeTurnoverTransactionSubindices": "/TradeTurnoverTransactionSubindices",
    "LiveMarket": "/LiveMarket",
    "MarketDepth": "/MarketDepth",
}


@app.route("/")
def getIndex():
    content = "<BR>".join(
        [f"<a href={value}> {key} </a>" for key, value in routes.items()]
    )
    return f"Serving hot stock data <BR>{content}"


@app.route(routes["Summary"])
def getSummary():
    response = flask.jsonify(_getSummary())
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def _getSummary():
    data = _get("summary") or []
    return {obj["detail"]: obj["value"] for obj in data}


@app.route(routes["NepseIndex"])
def getNepseIndex():
    response = flask.jsonify(_getNepseIndex())
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def _getNepseIndex():
    data = _get("nepseIndex") or []
    return {obj["index"]: obj for obj in data}


@app.route(routes["NepseSubIndices"])
def getNepseSubIndices():
    response = flask.jsonify(_getNepseSubIndices())
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def _getNepseSubIndices():
    data = _get("nepseSubIndices") or []
    return {obj["index"]: obj for obj in data}


@app.route(routes["TopTenTradeScrips"])
def getTopTenTradeScrips():
    response = flask.jsonify(_get("topTenTrade") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["TopTenTransactionScrips"])
def getTopTenTransactionScrips():
    response = flask.jsonify(_get("topTenTransaction") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["TopTenTurnoverScrips"])
def getTopTenTurnoverScrips():
    response = flask.jsonify(_get("topTenTurnover") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["SupplyDemand"])
def getSupplyDemand():
    response = flask.jsonify(_get("supplyDemand") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["TopGainers"])
def getTopGainers():
    response = flask.jsonify(_get("topGainers") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["TopLosers"])
def getTopLosers():
    response = flask.jsonify(_get("topLosers") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["IsNepseOpen"])
def isNepseOpen():
    response = flask.jsonify(_get("isNepseOpen") or {})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["DailyNepseIndexGraph"])
def getDailyNepseIndexGraph():
    response = flask.jsonify(nepse.getDailyNepseIndexGraph())
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(f"{routes['DailyScripPriceGraph']}", defaults={"symbol": None})
@app.route(f"{routes['DailyScripPriceGraph']}/<string:symbol>")
def getDailyScripPriceGraph(symbol):
    if symbol:
        response = flask.jsonify(nepse.getDailyScripPriceGraph(symbol))
        response.headers.add("Access-Control-Allow-Origin", "*")
    else:
        symbols = nepse.getSecurityList()
        response = "<BR>".join(
            [
                f"<a href={routes['DailyScripPriceGraph']}/{symbol['symbol']}> {symbol['symbol']} </a>"
                for symbol in symbols
            ]
        )
    return response


@app.route(routes["CompanyList"])
def getCompanyList():
    response = flask.jsonify(_get("companyList") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["PriceVolume"])
def getPriceVolume():
    response = flask.jsonify(_get("priceVolume") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(routes["LiveMarket"])
def getLiveMarket():
    response = flask.jsonify(_get("liveMarket") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route(f"{routes['MarketDepth']}", defaults={"symbol": None})
@app.route(f"{routes['MarketDepth']}/<string:symbol>")
def getMarketDepth(symbol):
    if symbol:
        try:
            response = flask.jsonify(nepse.getSymbolMarketDepth(symbol))
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response
        except JSONDecodeError:
            return flask.jsonify(None)
    else:
        symbols = nepse.getSecurityList()
        response = "<BR>".join(
            [
                f"<a href={routes['MarketDepth']}/{symbol['symbol']}> {symbol['symbol']} </a>"
                for symbol in symbols
            ]
        )
        return response


@app.route(routes["TradeTurnoverTransactionSubindices"])
def getTradeTurnoverTransactionSubindices():
    companies = {company["symbol"]: company for company in (_get("companyList") or [])}
    turnover = {obj["symbol"]: obj for obj in (_get("topTenTurnover") or [])}
    transaction = {obj["symbol"]: obj for obj in (_get("topTenTransaction") or [])}
    trade = {obj["symbol"]: obj for obj in (_get("topTenTrade") or [])}

    gainers = {obj["symbol"]: obj for obj in (_get("topGainers") or [])}
    losers = {obj["symbol"]: obj for obj in (_get("topLosers") or [])}

    price_vol_info = {obj["symbol"]: obj for obj in (_get("priceVolume") or [])}

    sector_sub_indices = _getNepseSubIndices()
    # this is done since nepse sub indices and sector name are different
    sector_mapper = {
        "Commercial Banks": "Banking SubIndex",
        "Development Banks": "Development Bank Index",
        "Finance": "Finance Index",
        "Hotels And Tourism": "Hotels And Tourism Index",
        "Hydro Power": "HydroPower Index",
        "Investment": "Investment Index",
        "Life Insurance": "Life Insurance",
        "Manufacturing And Processing": "Manufacturing And Processing",
        "Microfinance": "Microfinance Index",
        "Mutual Fund": "Mutual Fund",
        "Non Life Insurance": "Non Life Insurance",
        "Others": "Others Index",
        "Tradings": "Trading Index",
    }

    scrips_details = dict()
    for symbol, company in companies.items():
        company_details = {}

        company_details["symbol"] = symbol
        company_details["sectorName"] = company["sectorName"]
        company_details["totalTurnover"] = (
            turnover[symbol]["turnover"] if symbol in turnover.keys() else 0
        )
        company_details["totalTrades"] = (
            transaction[symbol]["totalTrades"] if symbol in transaction.keys() else 0
        )
        company_details["totalTradeQuantity"] = (
            trade[symbol]["shareTraded"] if symbol in transaction.keys() else 0
        )

        if symbol in gainers.keys():
            (
                company_details["pointChange"],
                company_details["percentageChange"],
                company_details["ltp"],
            ) = (
                gainers[symbol]["pointChange"],
                gainers[symbol]["percentageChange"],
                gainers[symbol]["ltp"],
            )
        elif symbol in losers.keys():
            (
                company_details["pointChange"],
                company_details["percentageChange"],
                company_details["ltp"],
            ) = (
                losers[symbol]["pointChange"],
                losers[symbol]["percentageChange"],
                losers[symbol]["ltp"],
            )
        else:
            (
                company_details["pointChange"],
                company_details["percentageChange"],
                company_details["ltp"],
            ) = (0, 0, 0)

        scrips_details[symbol] = company_details

    sector_details = dict()
    sectors = {company["sectorName"] for company in companies.values()}
    for sector in sectors:
        total_trades, total_trade_quantity, total_turnover = 0, 0, 0
        for scrip_details in scrips_details.values():
            if scrip_details["sectorName"] == sector:
                total_trades += scrip_details["totalTrades"]
                total_trade_quantity += scrip_details["totalTradeQuantity"]
                total_turnover += scrip_details["totalTurnover"]

        sector_details[sector] = {
            "totalTrades": total_trades,
            "totalTradeQuantity": total_trade_quantity,
            "totalTurnover": total_turnover,
            "index": sector_sub_indices[sector_mapper[sector]],
            "sectorName": sector,
        }

    response = flask.jsonify(
        {"scripsDetails": scrips_details, "sectorsDetails": sector_details}
    )

    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


# ── Market Depth / Order Book endpoints ──────────────────────────────────────

_DEPTH_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "nepse", "nepse_depth-main", "files",
)


def _latest_depth_file():
    # find latest file that actually has order-book data
    files = sorted(glob.glob(os.path.join(_DEPTH_DIR, "**", "*.json"), recursive=True), reverse=True)
    for filepath in files:
        try:
            with open(filepath) as f:
                data = json.load(f)
            for snap in reversed(data):
                if any(v.get("totalBuyQty", 0) + v.get("totalSellQty", 0) > 0
                       for v in snap["data"].values()):
                    return filepath
        except Exception:
            continue
    return None


def _latest_nonempty_snapshot():
    """Return (filepath, snapshot_dict) for the most recent snapshot with real data."""
    files = sorted(glob.glob(os.path.join(_DEPTH_DIR, "**", "*.json"), recursive=True), reverse=True)
    for filepath in files:
        try:
            with open(filepath) as f:
                data = json.load(f)
            for snap in reversed(data):
                if any(v.get("totalBuyQty", 0) + v.get("totalSellQty", 0) > 0
                       for v in snap["data"].values()):
                    return filepath, snap
        except Exception:
            continue
    return None, None


def _imbalance(buy, sell):
    total = buy + sell
    return round((buy - sell) / total, 4) if total else 0


@app.route("/depth/today")
def getDepthToday():
    try:
        path, snap = _latest_nonempty_snapshot()
        if not path or not snap:
            return flask.jsonify([])
        result = []
        for symbol, info in snap["data"].items():
            buy = info.get("totalBuyQty", 0)
            sell = info.get("totalSellQty", 0)
            if buy == 0 and sell == 0:
                continue
            depth = info.get("marketDepth", {})
            buy_levels = depth.get("buyMarketDepthList", [])
            sell_levels = depth.get("sellMarketDepthList", [])
            best_bid = buy_levels[0]["orderBookOrderPrice"] if buy_levels else None
            best_ask = sell_levels[0]["orderBookOrderPrice"] if sell_levels else None
            result.append({
                "symbol": symbol,
                "totalBuyQty": buy,
                "totalSellQty": sell,
                "imbalance": _imbalance(buy, sell),
                "bestBid": best_bid,
                "bestAsk": best_ask,
                "spread": round(best_ask - best_bid, 2) if (best_bid and best_ask) else None,
                "timestamp": snap["timestamp"],
            })
        result.sort(key=lambda x: abs(x["imbalance"]), reverse=True)
        resp = flask.jsonify(result)
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@app.route("/depth/orderbook/<symbol>")
def getOrderBook(symbol):
    try:
        path = _latest_depth_file()
        if not path:
            return flask.jsonify(None)
        with open(path) as f:
            data = json.load(f)
        for snap in reversed(data):
            if symbol in snap["data"]:
                info = snap["data"][symbol]
                buy = info.get("totalBuyQty", 0)
                sell = info.get("totalSellQty", 0)
                depth = info.get("marketDepth", {})
                resp = flask.jsonify({
                    "symbol": symbol,
                    "timestamp": snap["timestamp"],
                    "totalBuyQty": buy,
                    "totalSellQty": sell,
                    "imbalance": _imbalance(buy, sell),
                    "buyLevels": depth.get("buyMarketDepthList", []),
                    "sellLevels": depth.get("sellMarketDepthList", []),
                })
                resp.headers.add("Access-Control-Allow-Origin", "*")
                return resp
        resp = flask.jsonify(None)
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@app.route("/depth/history/<symbol>")
def getDepthHistory(symbol):
    try:
        files = sorted(glob.glob(os.path.join(_DEPTH_DIR, "**", "*.json"), recursive=True))[-30:]
        result = []
        for filepath in files:
            date_str = os.path.basename(filepath).replace(".json", "")
            try:
                with open(filepath) as f:
                    data = json.load(f)
                for snap in reversed(data):
                    if symbol in snap["data"]:
                        info = snap["data"][symbol]
                        buy = info.get("totalBuyQty", 0)
                        sell = info.get("totalSellQty", 0)
                        if buy == 0 and sell == 0:
                            break
                        result.append({
                            "date": date_str,
                            "totalBuyQty": buy,
                            "totalSellQty": sell,
                            "imbalance": _imbalance(buy, sell),
                        })
                        break
            except Exception:
                continue
        resp = flask.jsonify(result)
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@app.route("/chart/<symbol>")
def getChart(symbol):
    try:
        data = nepse.getCompanyPriceVolumeHistory(symbol)
        content = data.get("content", []) if isinstance(data, dict) else (data or [])
        content = list(reversed(content))  # oldest first
        resp = flask.jsonify(content)
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@app.route("/SecurityList")
def getSecurityList():
    response = flask.jsonify(_get("securityList") or [])
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


# ── Floorsheet summary (accumulation / distribution) ──────────────────────────
_fs_cache = {"data": None, "ts": 0}
_FS_TTL   = 600  # 10 minutes


@app.route("/floorsheet/summary")
def getFloorsheetSummary():
    try:
        now = time.time()
        if _fs_cache["data"] and now - _fs_cache["ts"] < _FS_TTL:
            resp = flask.jsonify(_fs_cache["data"])
            resp.headers.add("Access-Control-Allow-Origin", "*")
            return resp

        base_url = nepse.api_end_points["floor_sheet"]
        url = f"{base_url}?size=500&sort=contractId,desc"

        first = nepse.requestPOSTAPI(url=url, payload_generator=nepse.getPOSTPayloadIDForFloorSheet)
        if not first or "floorsheets" not in first:
            raise ValueError("empty response")

        rows      = list(first["floorsheets"]["content"])
        total_pages = first["floorsheets"]["totalPages"]

        # Fetch ALL pages for complete accuracy (cached for 10 min)
        for page in range(1, total_pages):
            try:
                nxt = nepse.requestPOSTAPI(
                    url=f"{url}&page={page}",
                    payload_generator=nepse.getPOSTPayloadIDForFloorSheet,
                )
                rows.extend(nxt["floorsheets"]["content"])
            except Exception:
                break

        # Aggregate per (symbol, broker) pair — same stock can appear
        # multiple times if different brokers are buying/selling it
        buy_pairs  = {}   # {(symbol, broker): qty}
        sell_pairs = {}
        buy_amt    = {}
        sell_amt   = {}

        for row in rows:
            sym    = row.get("stockSymbol", "")
            buyer  = str(row.get("buyerMemberId", ""))
            seller = str(row.get("sellerMemberId", ""))
            qty    = row.get("contractQuantity", 0) or 0
            amt    = row.get("contractAmount", 0) or 0

            if not sym:
                continue

            bk = (sym, buyer)
            buy_pairs[bk]  = buy_pairs.get(bk,  0) + qty
            buy_amt[bk]    = buy_amt.get(bk,    0) + amt

            sk = (sym, seller)
            sell_pairs[sk] = sell_pairs.get(sk, 0) + qty
            sell_amt[sk]   = sell_amt.get(sk,   0) + amt

        def build_rows(pair_qty, pair_amt):
            out = []
            for (sym, broker), qty in pair_qty.items():
                total_amt = pair_amt.get((sym, broker), 0)
                avg_rate  = round(total_amt / qty, 2) if qty else 0
                out.append({
                    "symbol":   sym,
                    "totalQty": qty,
                    "broker":   broker,
                    "totalAmt": round(total_amt, 2),
                    "avgRate":  avg_rate,
                })
            out.sort(key=lambda x: x["totalQty"], reverse=True)
            return out[:50]

        result = {
            "accumulation": build_rows(buy_pairs,  buy_amt),
            "distribution": build_rows(sell_pairs, sell_amt),
            "totalRows":    len(rows),
        }

        _fs_cache["data"] = result
        _fs_cache["ts"]   = now

        resp = flask.jsonify(result)
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp

    except Exception as e:
        resp = flask.jsonify({"error": str(e), "accumulation": [], "distribution": [], "totalRows": 0})
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
