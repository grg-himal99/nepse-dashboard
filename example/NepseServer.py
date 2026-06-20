import glob
import json
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date
from datetime import timedelta
from json import JSONDecodeError

import flask
from flask import Flask, Response, request, stream_with_context

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


_FETCHERS = {
    "summary": lambda: nepse.getSummary(),
    "nepseIndex": lambda: nepse.getNepseIndex(),
    "nepseSubIndices": lambda: nepse.getNepseSubIndices(),
    "topGainers": lambda: nepse.getTopGainers(),
    "topLosers": lambda: nepse.getTopLosers(),
    "topTenTrade": lambda: nepse.getTopTenTradeScrips(),
    "topTenTransaction": lambda: nepse.getTopTenTransactionScrips(),
    "topTenTurnover": lambda: nepse.getTopTenTurnoverScrips(),
    "supplyDemand": lambda: nepse.getSupplyDemand(),
    "isNepseOpen": lambda: nepse.isNepseOpen(),
    "priceVolume": lambda: nepse.getPriceVolume(),
    "liveMarket": lambda: nepse.getLiveMarket(),
    "companyList": lambda: nepse.getCompanyList(),
    "securityList": lambda: nepse.getSecurityList(),
}

# Priority keys fetched in parallel at startup so the cache is warm before the
# first HTTP request arrives.
_WARMUP_KEYS = [
    "summary",
    "nepseIndex",
    "isNepseOpen",
    "topGainers",
    "topLosers",
    "priceVolume",
]


def _warmup_cache():
    print("[warmup] pre-populating cache in parallel…")
    with ThreadPoolExecutor(max_workers=len(_WARMUP_KEYS)) as ex:
        futures = {ex.submit(_safe_fetch, k, _FETCHERS[k]): k for k in _WARMUP_KEYS}
        for f in as_completed(futures):
            pass  # errors already logged in _safe_fetch
    print("[warmup] done.")


def _refresh_loop():
    while True:
        print("[auto-refresh] refreshing data...")
        for key, fn in _FETCHERS.items():
            _safe_fetch(key, fn)
        print("[auto-refresh] done.")
        time.sleep(REFRESH_INTERVAL)


def _get(key):
    with _cache_lock:
        return _cache.get(key)


_warmup_cache()
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
    html_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../frontend/index.html"
    )
    if os.path.exists(html_path):
        return flask.send_file(html_path)
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
    "..",
    "nepse",
    "nepse_depth-main",
    "files",
)


def _latest_depth_file():
    # find latest file that actually has order-book data
    files = sorted(
        glob.glob(os.path.join(_DEPTH_DIR, "**", "*.json"), recursive=True),
        reverse=True,
    )
    for filepath in files:
        try:
            with open(filepath) as f:
                data = json.load(f)
            for snap in reversed(data):
                if any(
                    v.get("totalBuyQty", 0) + v.get("totalSellQty", 0) > 0
                    for v in snap["data"].values()
                ):
                    return filepath
        except Exception:
            continue
    return None


def _latest_nonempty_snapshot():
    """Return (filepath, snapshot_dict) for the most recent snapshot with real data."""
    files = sorted(
        glob.glob(os.path.join(_DEPTH_DIR, "**", "*.json"), recursive=True),
        reverse=True,
    )
    for filepath in files:
        try:
            with open(filepath) as f:
                data = json.load(f)
            for snap in reversed(data):
                if any(
                    v.get("totalBuyQty", 0) + v.get("totalSellQty", 0) > 0
                    for v in snap["data"].values()
                ):
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
            result.append(
                {
                    "symbol": symbol,
                    "totalBuyQty": buy,
                    "totalSellQty": sell,
                    "imbalance": _imbalance(buy, sell),
                    "bestBid": best_bid,
                    "bestAsk": best_ask,
                    "spread": (
                        round(best_ask - best_bid, 2)
                        if (best_bid and best_ask)
                        else None
                    ),
                    "timestamp": snap["timestamp"],
                }
            )
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
                resp = flask.jsonify(
                    {
                        "symbol": symbol,
                        "timestamp": snap["timestamp"],
                        "totalBuyQty": buy,
                        "totalSellQty": sell,
                        "imbalance": _imbalance(buy, sell),
                        "buyLevels": depth.get("buyMarketDepthList", []),
                        "sellLevels": depth.get("sellMarketDepthList", []),
                    }
                )
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
        files = sorted(
            glob.glob(os.path.join(_DEPTH_DIR, "**", "*.json"), recursive=True)
        )[-30:]
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
                        result.append(
                            {
                                "date": date_str,
                                "totalBuyQty": buy,
                                "totalSellQty": sell,
                                "imbalance": _imbalance(buy, sell),
                            }
                        )
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


# ── Shared floorsheet helpers (used by both A/D and Broker Summary) ───────────
_BROKER_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "broker_data.db")
_BROKER_LOCK = threading.Lock()
_PERIOD_DAYS = {"1d": 1, "1w": 5, "2w": 10, "1m": 22}

# In-memory broker cache for 1D (populated whenever full floorsheet is fetched)
_broker_live = {"data": None, "date": None}


def _init_broker_db():
    conn = sqlite3.connect(_BROKER_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS broker_daily (
            business_date TEXT NOT NULL,
            broker_id     TEXT NOT NULL,
            buy_qty       INTEGER DEFAULT 0,
            buy_amt       REAL    DEFAULT 0.0,
            sell_qty      INTEGER DEFAULT 0,
            sell_amt      REAL    DEFAULT 0.0,
            PRIMARY KEY (business_date, broker_id)
        )
    """)
    conn.commit()
    conn.close()


def _nepse_trading_days(n):
    """Return last n Nepal trading dates (Sun–Thu). Newest first."""
    days, cur = [], _date.today()
    while len(days) < n:
        wd = cur.weekday()  # Mon=0 … Sun=6
        if wd not in (4, 5):  # skip Fri(4) and Sat(5)
            days.append(cur.strftime("%Y-%m-%d"))
        cur -= timedelta(days=1)
        if (_date.today() - cur).days > 90:
            break
    return days


def _store_broker_day(date_str, broker_data):
    with _BROKER_LOCK:
        conn = sqlite3.connect(_BROKER_DB)
        conn.execute("DELETE FROM broker_daily WHERE business_date=?", (date_str,))
        for bid, d in broker_data.items():
            conn.execute(
                "INSERT INTO broker_daily VALUES (?,?,?,?,?,?)",
                (
                    date_str,
                    bid,
                    d["buy_qty"],
                    d["buy_amt"],
                    d["sell_qty"],
                    d["sell_amt"],
                ),
            )
        conn.commit()
        conn.close()


def _rows_to_broker_data(rows):
    """Aggregate raw floorsheet rows into per-broker buy/sell totals."""
    broker_data = {}
    for row in rows:
        buyer = str(row.get("buyerMemberId", "") or "").strip()
        seller = str(row.get("sellerMemberId", "") or "").strip()
        qty = row.get("contractQuantity", 0) or 0
        amt = row.get("contractAmount", 0) or 0
        if buyer:
            d = broker_data.setdefault(
                buyer, {"buy_qty": 0, "buy_amt": 0.0, "sell_qty": 0, "sell_amt": 0.0}
            )
            d["buy_qty"] += qty
            d["buy_amt"] += amt
        if seller:
            d = broker_data.setdefault(
                seller, {"buy_qty": 0, "buy_amt": 0.0, "sell_qty": 0, "sell_amt": 0.0}
            )
            d["sell_qty"] += qty
            d["sell_amt"] += amt
    return broker_data


_init_broker_db()


# ── Historical floorsheet backfill from GitHub CSV repo ───────────────────────
_FS_REPO_RAW = "https://raw.githubusercontent.com/madhuko/temp/main/fs/2026/{date}.csv"
_FS_REPO_API = "https://api.github.com/repos/madhuko/temp/contents/fs/2026"


def _db_existing_dates():
    conn = sqlite3.connect(_BROKER_DB)
    rows = conn.execute("SELECT DISTINCT business_date FROM broker_daily").fetchall()
    conn.close()
    return {r[0] for r in rows}


def _parse_csv_to_broker(text):
    """Parse floorsheet CSV (contract,symbol,buyer,seller,qty,rate,amt) into broker data dict."""
    import csv
    import io

    broker_data = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        buyer = str(row.get("buyer", "") or "").strip()
        seller = str(row.get("seller", "") or "").strip()
        try:
            qty = float(row.get("qty", 0) or 0)
        except:
            qty = 0
        try:
            amt = float(row.get("amt", 0) or 0)
        except:
            amt = 0
        if buyer:
            d = broker_data.setdefault(
                buyer, {"buy_qty": 0, "buy_amt": 0.0, "sell_qty": 0, "sell_amt": 0.0}
            )
            d["buy_qty"] += qty
            d["buy_amt"] += amt
        if seller:
            d = broker_data.setdefault(
                seller, {"buy_qty": 0, "buy_amt": 0.0, "sell_qty": 0, "sell_amt": 0.0}
            )
            d["sell_qty"] += qty
            d["sell_amt"] += amt
    return broker_data


def _backfill_from_github():
    """Download missing daily floorsheet CSVs from GitHub and import into broker DB."""
    import httpx

    time.sleep(5)  # let server fully start first

    try:
        # Get list of available files from GitHub API
        resp = httpx.get(
            _FS_REPO_API,
            timeout=15,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        files = [
            f["name"].replace(".csv", "")
            for f in resp.json()
            if f["name"].endswith(".csv")
        ]
    except Exception as e:
        print(f"[backfill] failed to list repo files: {e}")
        return

    existing = _db_existing_dates()
    missing = sorted(d for d in files if d not in existing)

    if not missing:
        print(f"[backfill] all {len(files)} dates already in DB — nothing to do")
        return

    print(f"[backfill] importing {len(missing)} missing dates from GitHub…")

    ok = 0
    for date_str in missing:
        try:
            url = _FS_REPO_RAW.format(date=date_str)
            resp = httpx.get(url, timeout=30)
            if resp.status_code != 200:
                continue
            broker_data = _parse_csv_to_broker(resp.text)
            if broker_data:
                _store_broker_day(date_str, broker_data)
                ok += 1
                if ok % 10 == 0:
                    print(f"[backfill] {ok}/{len(missing)} done…")
        except Exception as e:
            print(f"[backfill] error on {date_str}: {e}")

    print(f"[backfill] done — imported {ok}/{len(missing)} dates")


threading.Thread(target=_backfill_from_github, daemon=True).start()


# ── Floorsheet fetch (shared by A/D view + Broker Summary) ────────────────────
_fs_cache = {"data": None, "ts": 0}
_FS_TTL = 600  # 10 minutes


def _fetch_full_floorsheet():
    """Fetch all floorsheet pages. Returns raw rows list or raises."""
    base_url = nepse.api_end_points["floor_sheet"]
    url = f"{base_url}?size=500&sort=contractId,desc"

    first = nepse.requestPOSTAPI(
        url=url, payload_generator=nepse.getPOSTPayloadIDForFloorSheet
    )
    if not first or "floorsheets" not in first:
        raise ValueError("empty floorsheet response")

    rows = list(first["floorsheets"]["content"])
    total_pages = first["floorsheets"]["totalPages"]

    for page in range(1, total_pages):
        try:
            nxt = nepse.requestPOSTAPI(
                url=f"{url}&page={page}",
                payload_generator=nepse.getPOSTPayloadIDForFloorSheet,
            )
            rows.extend(nxt["floorsheets"]["content"])
        except Exception:
            break

    return rows


@app.route("/floorsheet/summary")
def getFloorsheetSummary():
    try:
        now = time.time()
        if _fs_cache["data"] and now - _fs_cache["ts"] < _FS_TTL:
            resp = flask.jsonify(_fs_cache["data"])
            resp.headers.add("Access-Control-Allow-Origin", "*")
            return resp

        rows = _fetch_full_floorsheet()

        # ── A/D aggregation (symbol + broker pairs) ──
        buy_pairs = {}
        sell_pairs = {}
        buy_amt = {}
        sell_amt = {}

        for row in rows:
            sym = row.get("stockSymbol", "")
            buyer = str(row.get("buyerMemberId", ""))
            seller = str(row.get("sellerMemberId", ""))
            qty = row.get("contractQuantity", 0) or 0
            amt = row.get("contractAmount", 0) or 0
            if not sym:
                continue
            bk = (sym, buyer)
            buy_pairs[bk] = buy_pairs.get(bk, 0) + qty
            buy_amt[bk] = buy_amt.get(bk, 0) + amt
            sk = (sym, seller)
            sell_pairs[sk] = sell_pairs.get(sk, 0) + qty
            sell_amt[sk] = sell_amt.get(sk, 0) + amt

        def build_rows(pair_qty, pair_amt):
            out = []
            for (sym, broker), qty in pair_qty.items():
                total_amt = pair_amt.get((sym, broker), 0)
                out.append(
                    {
                        "symbol": sym,
                        "totalQty": qty,
                        "broker": broker,
                        "totalAmt": round(total_amt, 2),
                        "avgRate": round(total_amt / qty, 2) if qty else 0,
                    }
                )
            out.sort(key=lambda x: x["totalQty"], reverse=True)
            return out[:50]

        result = {
            "accumulation": build_rows(buy_pairs, buy_amt),
            "distribution": build_rows(sell_pairs, sell_amt),
            "totalRows": len(rows),
        }
        _fs_cache["data"] = result
        _fs_cache["ts"] = now

        # ── Also build broker-level aggregate and persist ──
        broker_data = _rows_to_broker_data(rows)
        trade_date = (_nepse_trading_days(1) or [_date.today().strftime("%Y-%m-%d")])[0]
        _store_broker_day(trade_date, broker_data)
        _broker_live["data"] = broker_data
        _broker_live["date"] = trade_date
        print(
            f"[floorsheet] {len(rows)} rows · {len(broker_data)} brokers stored for {trade_date}"
        )

        resp = flask.jsonify(result)
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp

    except Exception as e:
        resp = flask.jsonify(
            {"error": str(e), "accumulation": [], "distribution": [], "totalRows": 0}
        )
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp


# ── Broker Summary (multi-period, SQLite-backed) ──────────────────────────────


@app.route("/broker/summary")
def getBrokerSummary():
    period = request.args.get("period", "1d")
    n_days = _PERIOD_DAYS.get(period, 1)
    dates = _nepse_trading_days(n_days)

    # For 1D: if live cache has today's data, use it directly (no DB needed)
    if period == "1d" and _broker_live["data"] and _broker_live["date"] in dates:
        broker_data = _broker_live["data"]
        brokers = _broker_data_to_list(broker_data)
        resp = flask.jsonify(
            {
                "period": period,
                "requestedDates": dates,
                "availableDates": [_broker_live["date"]],
                "fetching": False,
                "brokers": brokers,
            }
        )
        resp.headers.add("Access-Control-Allow-Origin", "*")
        return resp

    # Multi-day: query SQLite
    conn = sqlite3.connect(_BROKER_DB)
    ph = ",".join("?" * len(dates))
    rows = conn.execute(
        f"""SELECT broker_id, SUM(buy_qty), SUM(buy_amt), SUM(sell_qty), SUM(sell_amt)
            FROM broker_daily WHERE business_date IN ({ph}) GROUP BY broker_id""",
        dates,
    ).fetchall()
    avail = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT business_date FROM broker_daily WHERE business_date IN ({ph}) ORDER BY business_date DESC",
            dates,
        ).fetchall()
    ]
    conn.close()

    broker_list = []
    for bid, bq, ba, sq, sa in rows:
        bq = bq or 0
        ba = ba or 0.0
        sq = sq or 0
        sa = sa or 0.0
        net_qty = bq - sq
        net_amt = ba - sa
        broker_list.append(
            {
                "brokerId": bid,
                "buyQty": bq,
                "buyAmt": round(ba, 2),
                "sellQty": sq,
                "sellAmt": round(sa, 2),
                "netQty": net_qty,
                "netAmt": round(net_amt, 2),
                "bias": (
                    "bull" if net_qty > 0 else ("bear" if net_qty < 0 else "neutral")
                ),
            }
        )
    broker_list.sort(key=lambda x: x["netQty"], reverse=True)

    resp = flask.jsonify(
        {
            "period": period,
            "requestedDates": dates,
            "availableDates": avail,
            "fetching": False,
            "brokers": broker_list,
        }
    )
    resp.headers.add("Access-Control-Allow-Origin", "*")
    return resp


def _broker_data_to_list(broker_data):
    out = []
    for bid, d in broker_data.items():
        bq = d["buy_qty"]
        ba = d["buy_amt"]
        sq = d["sell_qty"]
        sa = d["sell_amt"]
        net_qty = bq - sq
        net_amt = ba - sa
        out.append(
            {
                "brokerId": bid,
                "buyQty": bq,
                "buyAmt": round(ba, 2),
                "sellQty": sq,
                "sellAmt": round(sa, 2),
                "netQty": net_qty,
                "netAmt": round(net_amt, 2),
                "bias": (
                    "bull" if net_qty > 0 else ("bear" if net_qty < 0 else "neutral")
                ),
            }
        )
    out.sort(key=lambda x: x["netQty"], reverse=True)
    return out


def _auto_floorsheet_loop():
    """Try to fetch full floorsheet every 30 min. Populates broker + A/D caches when market has data."""
    time.sleep(15)  # let refresh loop initialize tokens first
    while True:
        print("[auto-floorsheet] attempting fetch...", flush=True)
        try:
            rows = _fetch_full_floorsheet()
            if rows:
                broker_data = _rows_to_broker_data(rows)
                trade_date = (
                    _nepse_trading_days(1) or [_date.today().strftime("%Y-%m-%d")]
                )[0]
                _store_broker_day(trade_date, broker_data)
                _broker_live["data"] = broker_data
                _broker_live["date"] = trade_date

                buy_pairs = {}
                sell_pairs = {}
                buy_amt = {}
                sell_amt = {}
                for row in rows:
                    sym = row.get("stockSymbol", "")
                    buyer = str(row.get("buyerMemberId", ""))
                    seller = str(row.get("sellerMemberId", ""))
                    qty = row.get("contractQuantity", 0) or 0
                    amt = row.get("contractAmount", 0) or 0
                    if not sym:
                        continue
                    bk = (sym, buyer)
                    buy_pairs[bk] = buy_pairs.get(bk, 0) + qty
                    buy_amt[bk] = buy_amt.get(bk, 0) + amt
                    sk = (sym, seller)
                    sell_pairs[sk] = sell_pairs.get(sk, 0) + qty
                    sell_amt[sk] = sell_amt.get(sk, 0) + amt

                def _build(pq, pa):
                    out = []
                    for (s, b), q in pq.items():
                        a = pa.get((s, b), 0)
                        out.append(
                            {
                                "symbol": s,
                                "totalQty": q,
                                "broker": b,
                                "totalAmt": round(a, 2),
                                "avgRate": round(a / q, 2) if q else 0,
                            }
                        )
                    out.sort(key=lambda x: x["totalQty"], reverse=True)
                    return out[:50]

                _fs_cache["data"] = {
                    "accumulation": _build(buy_pairs, buy_amt),
                    "distribution": _build(sell_pairs, sell_amt),
                    "totalRows": len(rows),
                }
                _fs_cache["ts"] = time.time()
                print(
                    f"[auto-floorsheet] {len(rows)} rows · {len(broker_data)} brokers · date={trade_date}",
                    flush=True,
                )
            else:
                print("[auto-floorsheet] no data (market closed)", flush=True)
        except Exception as e:
            print(f"[auto-floorsheet] error: {e}", flush=True)
        time.sleep(1800)  # retry every 30 minutes


threading.Thread(target=_auto_floorsheet_loop, daemon=True).start()


# ── AI Stock Reports (Claude API) ─────────────────────────────────────────────


def _collect_report_data(report_type, symbol=""):
    """Gather relevant market data for the requested report type."""
    data = {}

    summary = _getSummary()
    if summary:
        data["market_summary"] = summary

    indices = _getNepseIndex()
    if indices:
        idx = indices.get("NEPSE Index") or next(iter(indices.values()), None)
        if idx:
            data["nepse_index"] = {
                "current": idx.get("currentValue"),
                "change": idx.get("change"),
                "pct_change": idx.get("perChange"),
            }

    if report_type in ("market_summary", "top_movers"):
        gainers = _get("topGainers") or []
        losers = _get("topLosers") or []
        data["top_gainers"] = [
            {
                "symbol": g.get("symbol"),
                "ltp": g.get("ltp"),
                "pct": g.get("percentageChange"),
            }
            for g in gainers[:10]
        ]
        data["top_losers"] = [
            {
                "symbol": l.get("symbol"),
                "ltp": l.get("ltp"),
                "pct": l.get("percentageChange"),
            }
            for l in losers[:10]
        ]
        top_trade = _get("topTenTrade") or []
        data["top_traded"] = [
            {"symbol": s.get("symbol"), "shares": s.get("shareTraded")}
            for s in top_trade[:10]
        ]

    if report_type == "broker_analysis":
        broker_live = _broker_live.get("data") or {}
        if broker_live:
            broker_list = _broker_data_to_list(broker_live)
            broker_list.sort(key=lambda x: x["netQty"], reverse=True)
            data["top_buyers"] = [b for b in broker_list if b["netQty"] > 0][:10]
            data["top_sellers"] = [b for b in reversed(broker_list) if b["netQty"] < 0][
                :10
            ]

    if report_type == "stock_analysis" and symbol:
        # Today's live market data (available during trading hours)
        live = _get("liveMarket") or []
        stock = next(
            (s for s in live if s.get("symbol", "").upper() == symbol.upper()), None
        )
        if stock:
            data["today"] = {
                "symbol": stock.get("symbol"),
                "ltp": stock.get("ltp"),
                "open": stock.get("openPrice"),
                "high": stock.get("highPrice"),
                "low": stock.get("lowPrice"),
                "volume": stock.get("totalTradeQuantity"),
                "pct_change": stock.get("percentageChange"),
                "turnover": stock.get("totalTradeValue"),
            }

        # Historical price/volume — last 30 trading days (via internal chart route)
        try:
            hist_raw = nepse.getCompanyPriceVolumeHistory(symbol)
            content = (
                hist_raw.get("content", [])
                if isinstance(hist_raw, dict)
                else (hist_raw or [])
            )
            content = [r for r in content if r.get("closePrice")]
            content = list(reversed(content))[-30:]
            data["price_history"] = [
                {
                    "date": r.get("businessDate"),
                    "high": r.get("highPrice"),
                    "low": r.get("lowPrice"),
                    "close": r.get("closePrice"),
                    "volume": r.get("totalTradedQuantity"),
                    "trades": r.get("totalTrades"),
                }
                for r in content
            ]
            if data["price_history"]:
                closes = [r["close"] for r in data["price_history"]]
                data["price_stats"] = {
                    "days": len(closes),
                    "latest": closes[-1],
                    "30d_high": max(r["high"] for r in data["price_history"]),
                    "30d_low": min(r["low"] for r in data["price_history"]),
                    "avg_volume": round(
                        sum(r["volume"] or 0 for r in data["price_history"])
                        / len(closes)
                    ),
                    "trend": "UP" if closes[-1] > closes[0] else "DOWN",
                    "pct_30d": (
                        round((closes[-1] - closes[0]) / closes[0] * 100, 2)
                        if closes[0]
                        else 0
                    ),
                }
        except Exception as e:
            print(f"[ai/report] price history error for {symbol}: {e}")

    return data


def _build_report_prompt(report_type, symbol, data):
    today = _date.today().strftime("%B %d, %Y")
    ctx = json.dumps(data, indent=2)

    if report_type == "market_summary":
        return (
            f"Today is {today}. Below is live data from the Nepal Stock Exchange (NEPSE):\n\n{ctx}\n\n"
            "Write a concise Daily Market Summary for NEPSE investors. Include:\n"
            "1. Overall market direction and NEPSE index movement\n"
            "2. Sector highlights (if data available)\n"
            "3. Notable gainers and losers with brief reasons\n"
            "4. Trading activity (volume/turnover trend)\n"
            "5. Key takeaways for retail investors\n"
            "Use plain language. Format with markdown headers. Keep it under 400 words."
        )
    elif report_type == "top_movers":
        return (
            f"Today is {today}. Below is NEPSE top movers data:\n\n{ctx}\n\n"
            "Analyze today's top gainers and losers on NEPSE. For each group:\n"
            "- Identify any sector patterns among the movers\n"
            "- Highlight the most significant moves and possible catalysts\n"
            "- Note any stocks showing unusual volume\n"
            "- Suggest what investors should watch\n"
            "Use markdown. Keep under 350 words."
        )
    elif report_type == "broker_analysis":
        return (
            f"Today is {today}. Below is NEPSE broker net position data (broker ID, buy qty, sell qty, net qty):\n\n{ctx}\n\n"
            "Analyze institutional broker activity on NEPSE:\n"
            "- Which brokers are aggressively buying vs selling?\n"
            "- What does this broker positioning signal for market direction?\n"
            "- Are there any concentration risks or dominant players?\n"
            "- What should retail investors infer from this pattern?\n"
            "Use markdown. Keep under 350 words."
        )
    elif report_type == "stock_analysis":
        return (
            f"Today is {today}. Below is real market data for {symbol} on NEPSE:\n\n{ctx}\n\n"
            f"Write a technical analysis of {symbol} using ONLY the numbers from the data above. Include:\n"
            f"- **30-day trend**: Use price_stats.trend and pct_30d. Quote actual open/close prices.\n"
            f"- **Support & Resistance**: Derive from 30d_high, 30d_low, and recent price_history closes.\n"
            f"- **Volume analysis**: Compare recent volume to avg_volume. Is smart money buying or selling?\n"
            f"- **Most recent session**: Quote the last row in price_history (high, low, close, volume).\n"
            f"- **Outlook**: Give a specific price range to watch for the next 1-2 weeks.\n"
            "Never say data is missing — it is all in the JSON above. Use markdown. Under 350 words."
        )
    return f"Analyze this NEPSE market data and provide insights:\n\n{ctx}"


@app.route("/ai/report", methods=["POST", "OPTIONS"])
def getAIReport():
    if request.method == "OPTIONS":
        resp = Response("", status=200)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    body = request.json or {}
    report_type = body.get("type", "market_summary")
    symbol = body.get("symbol", "").upper().strip()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        resp = flask.jsonify(
            {
                "error": "GEMINI_API_KEY not set. Get a free key at aistudio.google.com, then: export GEMINI_API_KEY=your-key"
            }
        )
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 500

    try:
        from google import genai as _genai
    except ImportError:
        resp = flask.jsonify(
            {"error": "google-genai not installed. Run: pip3 install google-genai"}
        )
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 500

    market_data = _collect_report_data(report_type, symbol)
    system_prompt = (
        "You are an expert NEPSE (Nepal Stock Exchange) market analyst with deep knowledge of "
        "Nepali financial markets, listed companies, and investor behaviour. "
        "Provide insightful, actionable analysis. Use Rs for currency. "
        "Be direct and specific. Never make up data — only analyse what is provided."
    )
    prompt = (
        system_prompt + "\n\n" + _build_report_prompt(report_type, symbol, market_data)
    )

    def generate():
        try:
            client = _genai.Client(api_key=api_key)
            stream = client.models.generate_content_stream(
                model="gemini-flash-latest",
                contents=prompt,
            )
            for chunk in stream:
                text = chunk.text
                if text:
                    yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=8000)
