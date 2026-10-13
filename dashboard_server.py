# -*- coding: utf-8 -*-
"""Local dashboard for KR Level Up. Account actions are delegated to krll3.py."""
import asyncio
import json
import os
import re
import time
from typing import Dict, List, Any, Optional
from aiohttp import web

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.json")
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "index.html")
BATCH_SETTINGS_FILE = os.path.join(BASE_DIR, "batch_settings.json")

class BotState:
    def __init__(self):
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = 200
        self.total_matches = 0
        self.total_gained_exp = 0
        self.start_time = time.time()
        self.account_workers: Dict[str, asyncio.Task] = {}  # keyed by login UID
        self.refresh_callbacks: Dict[str, Any] = {}
        self.account_credentials: Dict[str, Dict[str, Any]] = {}  # keyed by in-game account ID
        self.match_tasks: Dict[str, set] = {}  # keyed by in-game account ID
        # Bulk/batch scheduler state (keyed by login UID)
        self.batch_queue: List[str] = []
        self.batch_active: set = set()
        self.batch_results: Dict[str, str] = {}
        self.batch_settings: Dict[str, Any] = {"concurrency": 10, "search_timeout_min": 5}

    def log(self, message: str, level: str = "info", uid: Optional[str] = None):
        self.logs.append({"time": time.strftime("%H:%M:%S"), "level": level, "message": message, "uid": uid})
        self.logs = self.logs[-self.max_logs:]

    def register_account(self, uid: str, nickname: str, region: str, level: int, exp: int, likes: int = 0):
        uid = str(uid)
        if uid not in self.accounts:
            self.accounts[uid] = {"uid": uid, "nickname": nickname or f"Player_{uid[:6]}", "region": region or "ME",
                "level": level or 1, "initial_exp": exp, "current_exp": exp, "gained_exp": 0, "likes": likes or 0,
                "status": "ONLINE", "matches_played": 0, "active_matches": 0, "max_parallel_matches": 1, "target_level": 8, "level_stop_requested": False, "last_match_time": None,
                "last_updated": time.strftime("%H:%M:%S")}
        else:
            a = self.accounts[uid]
            if nickname: a["nickname"] = nickname
            if region: a["region"] = region
            if level: a["level"] = level
            a["current_exp"] = exp
            a["gained_exp"] = max(0, exp - a["initial_exp"])
            a["likes"] = likes or 0
            a["status"] = "ONLINE"
            a["last_updated"] = time.strftime("%H:%M:%S")
        self.recalc_totals()

    def update_exp(self, uid: str, current_exp: int, level: Optional[int] = None):
        uid = str(uid)
        if uid not in self.accounts: return
        a = self.accounts[uid]
        old = a["current_exp"]
        a["current_exp"] = current_exp
        if level is not None and level > 0: a["level"] = level
        a["gained_exp"] = max(0, current_exp - a["initial_exp"])
        a["last_updated"] = time.strftime("%H:%M:%S")
        if current_exp > old: self.log(f"{a['nickname']} ({uid}) +{current_exp-old} EXP | Total +{a['gained_exp']}", "success", uid)
        self.recalc_totals()

    def update_status(self, uid: str, status: str, active_matches: Optional[int] = None):
        uid = str(uid)
        if uid in self.accounts:
            self.accounts[uid]["status"] = status
            if active_matches is not None: self.accounts[uid]["active_matches"] = active_matches
            self.accounts[uid]["last_updated"] = time.strftime("%H:%M:%S")

    def increment_match(self, uid: str):
        uid = str(uid); self.total_matches += 1
        if uid in self.accounts:
            a = self.accounts[uid]; a["matches_played"] += 1
            a["last_match_time"] = time.strftime("%H:%M:%S")
            a["last_updated"] = time.strftime("%H:%M:%S")
            self.log(f"{a['nickname']} finished Match #{a['matches_played']}", "info", uid)

    def recalc_totals(self):
        self.total_gained_exp = sum(a.get("gained_exp", 0) for a in self.accounts.values())

bot_state = BotState()


def read_accounts():
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def write_accounts(accounts):
    tmp = ACCOUNTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(accounts, f, indent=2)
    os.replace(tmp, ACCOUNTS_FILE)

def set_batch_state(login_uid, state):
    """Persist a bulk account's state (pending / active / done / skipped) into accounts.json."""
    saved = read_accounts()
    for account in saved:
        if str(account.get("uid", "")) == str(login_uid):
            account["batch_state"] = state
            write_accounts(saved)
            return

def load_batch_settings():
    try:
        with open(BATCH_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            bot_state.batch_settings["concurrency"] = max(1, int(data.get("concurrency", 10)))
            bot_state.batch_settings["search_timeout_min"] = max(0, float(data.get("search_timeout_min", 5)))
    except (OSError, ValueError, TypeError):
        pass

def save_batch_settings():
    try:
        with open(BATCH_SETTINGS_FILE, "w", encoding="utf-8") as f: json.dump(bot_state.batch_settings, f)
    except OSError:
        pass

load_batch_settings()

# Accepts one account per line or a whole paragraph: "UID:PASSWORD", "UID PASSWORD", "UID|PASSWORD", "UID,PASSWORD".
BULK_ACCOUNT_RE = re.compile(r"(\d{4,})[\s:|,;]+(\S+)")

def parse_bulk_accounts(text):
    pairs, seen = [], set()
    for uid, password in BULK_ACCOUNT_RE.findall(text or ""):
        if uid in seen: continue
        seen.add(uid); pairs.append((uid, password))
    return pairs

async def handle_index(request):
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f: content = f.read()
    except OSError:
        content = "<h1>Dashboard template missing: templates/index.html</h1>"
    return web.Response(text=content, content_type="text/html", charset="utf-8")

def batch_summary():
    states = [str(a.get("batch_state", "")) for a in read_accounts() if a.get("batch")]
    return {"pending": len(bot_state.batch_queue), "active": len(bot_state.batch_active),
        "done": states.count("done"), "skipped": states.count("skipped"),
        "concurrency": bot_state.batch_settings.get("concurrency", 10),
        "search_timeout_min": bot_state.batch_settings.get("search_timeout_min", 5)}

async def handle_stats(request):
    accounts = sorted(bot_state.accounts.values(), key=lambda a: a.get("gained_exp", 0), reverse=True)
    return web.json_response({"total_accounts": len(read_accounts()), "total_matches": bot_state.total_matches,
        "total_gained_exp": bot_state.total_gained_exp, "accounts": accounts, "logs": bot_state.logs[-60:],
        "uptime": int(time.time() - bot_state.start_time), "batch": batch_summary()})

async def handle_add_account(request):
    try:
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        password = str(data.get("password", "")).strip()
        try: max_parallel = max(0, int(data.get("max_parallel_matches", 1)))
        except (TypeError, ValueError): max_parallel = 1
        try: target_level = max(0, int(data.get("target_level", 8)))
        except (TypeError, ValueError): target_level = 8
        if not uid or not password:
            return web.json_response({"status":"error", "error":"UID and Password are required"}, status=400)
        accounts = read_accounts()
        if any(str(a.get("uid", "")) == uid for a in accounts):
            return web.json_response({"status":"error", "error":"That UID is already added"}, status=409)
        accounts.append({"uid": uid, "password": password, "max_parallel_matches": max_parallel, "target_level": target_level})
        write_accounts(accounts)
        bot_state.log(f"Account {uid} added from dashboard", "success", uid)
        callback = bot_state.refresh_callbacks.get("on_account_added")
        if callback: await callback({"uid": uid, "password": password, "max_parallel_matches": max_parallel, "target_level": target_level})
        return web.json_response({"status":"ok"})
    except Exception as e:
        return web.json_response({"status":"error", "error":str(e)}, status=500)

async def handle_bulk_add(request):
    try:
        data = await request.json()
        pairs = parse_bulk_accounts(str(data.get("text", "")))
        if not pairs:
            return web.json_response({"status":"error", "error":"No UID/password pairs found in the pasted text"}, status=400)
        try: max_parallel = max(0, int(data.get("max_parallel_matches", 1)))
        except (TypeError, ValueError): max_parallel = 1
        try: target_level = max(0, int(data.get("target_level", 8)))
        except (TypeError, ValueError): target_level = 8
        try: bot_state.batch_settings["concurrency"] = max(1, int(data.get("concurrency", bot_state.batch_settings["concurrency"])))
        except (TypeError, ValueError): pass
        try: bot_state.batch_settings["search_timeout_min"] = max(0, float(data.get("search_timeout_min", bot_state.batch_settings["search_timeout_min"])))
        except (TypeError, ValueError): pass
        save_batch_settings()
        accounts = read_accounts()
        existing = {str(a.get("uid", "")) for a in accounts}
        added = duplicates = 0
        for uid, password in pairs:
            if uid in existing:
                duplicates += 1; continue
            accounts.append({"uid": uid, "password": password, "max_parallel_matches": max_parallel,
                "target_level": target_level, "batch": True, "batch_state": "pending"})
            existing.add(uid); bot_state.batch_queue.append(uid); added += 1
        write_accounts(accounts)
        bot_state.log(f"Bulk add: {added} account(s) queued, {duplicates} duplicate(s) skipped | {bot_state.batch_settings['concurrency']} at once", "success")
        return web.json_response({"status":"ok", "added":added, "duplicates":duplicates})
    except Exception as e:
        return web.json_response({"status":"error", "error":str(e)}, status=500)

async def handle_batch_settings(request):
    try:
        data = await request.json()
        try: bot_state.batch_settings["concurrency"] = max(1, int(data.get("concurrency", bot_state.batch_settings["concurrency"])))
        except (TypeError, ValueError):
            return web.json_response({"status":"error", "error":"Accounts at once must be a whole number"}, status=400)
        try: bot_state.batch_settings["search_timeout_min"] = max(0, float(data.get("search_timeout_min", bot_state.batch_settings["search_timeout_min"])))
        except (TypeError, ValueError):
            return web.json_response({"status":"error", "error":"Search timeout must be a number"}, status=400)
        save_batch_settings()
        bot_state.log(f"Batch settings: {bot_state.batch_settings['concurrency']} at once, skip after {bot_state.batch_settings['search_timeout_min']:g} min without a match", "info")
        return web.json_response({"status":"ok", **batch_summary()})
    except Exception as e:
        return web.json_response({"status":"error", "error":str(e)}, status=500)

async def handle_delete_account(request):
    try:
        data = await request.json(); requested = str(data.get("uid", "")).strip()
        # The card uses the in-game account ID; also accept the login UID.
        login_uid = requested
        for acc_id, credentials in list(bot_state.account_credentials.items()):
            if acc_id == requested:
                login_uid = str(credentials.get("uid", requested)); break
        accounts = [a for a in read_accounts() if str(a.get("uid", "")) != login_uid]
        write_accounts(accounts)
        if login_uid in bot_state.batch_queue: bot_state.batch_queue.remove(login_uid)
        bot_state.batch_active.discard(login_uid)
        task = bot_state.account_workers.pop(login_uid, None)
        if task and not task.done():
            task.cancel()
        # Cancel every detached UDP match task belonging to this account.
        account_ids = [acc_id for acc_id, credentials in list(bot_state.account_credentials.items())
                       if str(credentials.get("uid", "")) == login_uid or acc_id == requested]
        account_ids.append(requested)
        for acc_id in set(account_ids):
            for match_task in list(bot_state.match_tasks.get(str(acc_id), set())):
                if not match_task.done(): match_task.cancel()
            bot_state.match_tasks.pop(str(acc_id), None)
            bot_state.account_credentials.pop(str(acc_id), None)
            bot_state.accounts.pop(str(acc_id), None)
        bot_state.log(f"Account {login_uid} removed from dashboard rotation", "warning", login_uid)
        return web.json_response({"status":"ok"})
    except Exception as e:
        return web.json_response({"status":"error", "error":str(e)}, status=500)

async def handle_parallel_limit(request):
    try:
        data = await request.json()
        requested = str(data.get("uid", "")).strip()
        try: limit = max(0, int(data.get("max_parallel_matches", 0)))
        except (TypeError, ValueError):
            return web.json_response({"status":"error", "error":"Limit must be a non-negative integer"}, status=400)
        login_uid = requested
        for acc_id, credentials in list(bot_state.account_credentials.items()):
            if acc_id == requested:
                login_uid = str(credentials.get("uid", requested)); break
        saved = read_accounts()
        found = False
        for account in saved:
            if str(account.get("uid", "")) == login_uid:
                account["max_parallel_matches"] = limit
                found = True
                break
        if not found:
            return web.json_response({"status":"error", "error":"Account not found"}, status=404)
        write_accounts(saved)
        for acc_id, credentials in list(bot_state.account_credentials.items()):
            if str(credentials.get("uid", "")) == login_uid or acc_id == requested:
                if acc_id in bot_state.accounts:
                    bot_state.accounts[acc_id]["max_parallel_matches"] = limit
        if requested in bot_state.accounts:
            bot_state.accounts[requested]["max_parallel_matches"] = limit
        bot_state.log(f"Parallel match limit for {login_uid} set to {'unlimited' if limit == 0 else limit}", "info", login_uid)
        return web.json_response({"status":"ok", "max_parallel_matches":limit})
    except Exception as e:
        return web.json_response({"status":"error", "error":str(e)}, status=500)

async def handle_target_level(request):
    try:
        data = await request.json()
        requested = str(data.get("uid", "")).strip()
        try: target = max(0, int(data.get("target_level", 0)))
        except (TypeError, ValueError):
            return web.json_response({"status":"error", "error":"Target level must be a non-negative integer"}, status=400)
        login_uid = requested
        for acc_id, credentials in list(bot_state.account_credentials.items()):
            if acc_id == requested:
                login_uid = str(credentials.get("uid", requested)); break
        saved = read_accounts(); found = False
        for account in saved:
            if str(account.get("uid", "")) == login_uid:
                account["target_level"] = target; found = True; break
        if not found: return web.json_response({"status":"error", "error":"Account not found"}, status=404)
        write_accounts(saved)
        for acc_id, credentials in list(bot_state.account_credentials.items()):
            if str(credentials.get("uid", "")) == login_uid or acc_id == requested:
                if acc_id in bot_state.accounts: bot_state.accounts[acc_id]["target_level"] = target
        if requested in bot_state.accounts: bot_state.accounts[requested]["target_level"] = target
        bot_state.log(f"Target level for {login_uid} set to {target or 'disabled'}", "info", login_uid)
        return web.json_response({"status":"ok", "target_level":target})
    except Exception as e:
        return web.json_response({"status":"error", "error":str(e)}, status=500)

async def handle_refresh_account(request):
    try:
        data = await request.json(); requested = str(data.get("uid", "")).strip()
        login_uid = requested
        for acc_id, credentials in list(bot_state.account_credentials.items()):
            if acc_id == requested:
                login_uid = str(credentials.get("uid", requested)); break
        acc = next((a for a in read_accounts() if str(a.get("uid", "")) == login_uid), None)
        if not acc: return web.json_response({"status":"error", "error":"Account not found"}, status=404)
        callback = bot_state.refresh_callbacks.get("on_account_added")
        if callback: await callback(acc)
        return web.json_response({"status":"ok"})
    except Exception as e:
        return web.json_response({"status":"error", "error":str(e)}, status=500)

async def start_web_dashboard(host="0.0.0.0", port=20335):
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_post("/api/account/add", handle_add_account)
    app.router.add_post("/api/account/delete", handle_delete_account)
    app.router.add_post("/api/account/refresh", handle_refresh_account)
    app.router.add_post("/api/account/parallel-limit", handle_parallel_limit)
    app.router.add_post("/api/account/target-level", handle_target_level)
    app.router.add_post("/api/account/bulk-add", handle_bulk_add)
    app.router.add_post("/api/batch/settings", handle_batch_settings)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    print(f"[+] KR Level Up dashboard: http://127.0.0.1:{port}")
