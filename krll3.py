# -*- coding: utf-8 -*-
"""
krll.py - FreeFire Level Up Bot (Auto IP Switching & Proxy Rotation)
Zero Match Drop + Auto Failover on Search #10
"""

import sys
import os
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

import asyncio
import httpx
import random
import json
import socket
import struct
import time
import uuid
import itertools
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

from google_play_scraper import app as play_scraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
from message_ids import MESSAGE_ID_TO_NAME
import thunderFF_pb2

# SOCKS5 Support
try:
    from python_socks.async_ import AsyncProxy
    HAS_SOCKS = True
except ImportError:
    HAS_SOCKS = False

# Dashboard Fallback
try:
    from dashboard_server import bot_state, start_web_dashboard
except ImportError:
    class DummyBotState:
        def __init__(self):
            self.accounts = {}
            self.account_workers = {}
        def log(self, *args, **kwargs): pass
        def register_account(self, *args, **kwargs): pass
        def update_exp(self, *args, **kwargs): pass
        def update_status(self, *args, **kwargs): pass
        def increment_match(self, *args, **kwargs): pass
    bot_state = DummyBotState()
    async def start_web_dashboard(host="0.0.0.0", port=20335): pass

# ==================== CONFIGURATION ====================
WEB_HOST = "0.0.0.0"
WEB_PORT = 20335
ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")
PROXIES_FILE = "proxies.txt"
TOKEN_CACHE_FILE = "token_cache.json"
TOKEN_CACHE_TTL = 1200

# आईपी स्विचिंग ट्रिगर: इतने सर्च के बाद अगर मैच न मिले तो तुरंत आईपी बदलेगा
MAX_SEARCHES_BEFORE_IP_SWITCH = 10

START_MATCH_INTERVAL = 1.0
NEW_MATCH_DELAY = 1.5
MAX_MATCH_DURATION = None  # No hard match-duration cutoff; end on server completion or inactivity
MATCH_IDLE_TIMEOUT = 8.0

MODE_ID = 1
MAP_ID = 1

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

REGION_PREFIX = {
    "ME": "031900", "IND": "031400", "BD": "031400", "SG": "031500",
    "TH": "031500", "PH": "031500", "VN": "031500", "MY": "031500",
    "ID": "031500", "HK": "031500", "TW": "031500", "PK": "031500",
    "CIS": "031500", "BR": "031500", "NA": "031500", "SAC": "031500", "EUROPE": "031500",
}

REGION_LANG = {
    "BD": "bn", "IND": "hi", "PK": "ur", "SG": "en", "ID": "id",
    "ME": "ar", "VN": "vi", "TW": "zh", "CIS": "ru", "TH": "th",
    "EU": "en", "US": "en", "SAC": "es", "LK": "en", "BR": "pt",
}

CRC7_TABLE = bytes([
    0, 9, 18, 27, 36, 45, 54, 63, 72, 65, 90, 83, 108, 101, 126, 119,
    25, 16, 11, 2, 61, 52, 47, 38, 81, 88, 67, 74, 117, 124, 103, 110,
    50, 59, 32, 41, 22, 31, 4, 13, 122, 115, 104, 97, 94, 87, 76, 69,
    43, 34, 57, 48, 15, 6, 29, 20, 99, 106, 113, 120, 71, 78, 85, 92,
    100, 109, 118, 127, 64, 73, 82, 91, 44, 37, 62, 55, 8, 1, 26, 19,
    125, 116, 111, 102, 89, 80, 75, 66, 53, 60, 39, 46, 17, 24, 3, 10,
    86, 95, 68, 77, 114, 123, 96, 105, 30, 23, 12, 5, 58, 51, 40, 33,
    79, 70, 93, 84, 107, 98, 121, 112, 7, 14, 21, 28, 35, 42, 49, 56,
    65, 72, 83, 90, 101, 108, 119, 126, 9, 0, 27, 18, 45, 36, 63, 54,
    88, 81, 74, 67, 124, 117, 110, 103, 16, 25, 2, 11, 52, 61, 38, 47,
    115, 122, 97, 104, 87, 94, 69, 76, 59, 50, 41, 32, 31, 22, 13, 4,
    106, 99, 120, 113, 78, 71, 92, 85, 34, 43, 48, 57, 6, 15, 20, 29,
    37, 44, 55, 62, 1, 8, 19, 26, 109, 100, 127, 118, 73, 64, 91, 82,
    60, 53, 46, 39, 24, 17, 10, 3, 116, 125, 102, 111, 80, 89, 66, 75,
    23, 30, 5, 12, 51, 58, 33, 40, 95, 86, 77, 68, 123, 114, 105, 96,
    14, 7, 28, 21, 42, 35, 56, 49, 70, 79, 84, 93, 98, 107, 112, 121,
])

_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0: 1, 1: 2, 2: 2, 3: 1, 4: 2}
_FIELD_NAMES = {0: "sendOption", 1: "cmd", 2: "orderId", 3: "flags", 4: "length"}

CLOUDFLARE_PRIMARY_DNS = "1.1.1.1"
CLOUDFLARE_SECONDARY_DNS = "1.0.0.1"
_DNS_CACHE: Dict[str, Tuple[str, float]] = {}
_DNS_CACHE_TTL = 300.0

headers = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Expect': '100-continue',
    'X-Unity-Version': '2018.4.12f1',
    'X-GA-SV': '1789535859',
    'X-GA': 'v1 1',
    'ReleaseVersion': 'OB55'
}

# ==================== PROXY ROTATOR ====================
class ProxyPool:
    def __init__(self, filename: str):
        self.filename = filename
        self.proxies: List[str] = []
        self.current_idx = 0
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    self.proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except Exception:
                self.proxies = []

    def get_current(self) -> Optional[str]:
        if not self.proxies:
            return None
        return self.proxies[self.current_idx % len(self.proxies)]

    def rotate(self) -> Optional[str]:
        if not self.proxies:
            return None
        self.current_idx = (self.current_idx + 1) % len(self.proxies)
        new_proxy = self.get_current()
        print_colored(f"🔄 [PROXY SWITCH] Switched to IP: {new_proxy}", Colors.YELLOW)
        return new_proxy

proxy_pool = ProxyPool(PROXIES_FILE)

def get_httpx_client(proxy_url: Optional[str] = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        verify=False,
        timeout=15.0,
        proxy=proxy_url,
        limits=httpx.Limits(max_connections=300, max_keepalive_connections=150)
    )

class Colors:
    GREEN = '\033[92m'
    FAIL = '\033[91m'
    WARNING = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    YELLOW = '\033[93m'
    WHITE = '\033[97m'
    ENDC = '\033[0m'

def print_colored(text, color=Colors.WHITE):
    try:
        print(f"{color}{text}{Colors.ENDC}", flush=True)
    except Exception:
        print(text, flush=True)

def print_success(text):
    print_colored(f"[+] {text}", Colors.GREEN)
    bot_state.log(text, "success")

def print_error(text):
    print_colored(f"[-] {text}", Colors.FAIL)
    bot_state.log(text, "error")

def print_warning(text):
    print_colored(f"[!] {text}", Colors.WARNING)
    bot_state.log(text, "warning")

def print_info(text):
    print_colored(f"[i] {text}", Colors.CYAN)
    bot_state.log(text, "info")

# ==================== SOCKET CONNECTION (DIRECT OR PROXY) ====================
async def open_proxied_connection(host: str, port: int, proxy_url: Optional[str] = None):
    if not proxy_url or not HAS_SOCKS:
        return await asyncio.open_connection(host, port)

    try:
        parsed = urlparse(proxy_url)
        proxy = AsyncProxy.from_url(proxy_url)
        sock = await proxy.connect(dest_host=host, dest_port=port)
        reader, writer = await asyncio.open_connection(sock=sock)
        return reader, writer
    except Exception as e:
        print_warning(f"Proxy tunnel failed ({e}), falling back to direct connection...")
        return await asyncio.open_connection(host, port)

# ==================== CRYPTO & PROTOBUF ====================
def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict): return default
    if key in d: return d[key].get('data', default)
    if str(key) in d: return d[str(key)].get('data', default)
    return default

def _pb_varint(n):
    if n < 0: n = (1 << 64) + n
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def _pb_tag(f, w): return _pb_varint((f << 3) | w)

def _pb_field(f, v):
    if isinstance(v, bool): v = int(v)
    if isinstance(v, int): return _pb_tag(f, 0) + _pb_varint(v)
    if isinstance(v, str): d = v.encode('utf-8'); return _pb_tag(f, 2) + _pb_varint(len(d)) + d
    if isinstance(v, (bytes, bytearray)): d = bytes(v); return _pb_tag(f, 2) + _pb_varint(len(d)) + d
    return b""

def has_ssan_zig(n):
    z = (n << 1) & 0xFFFFFFFFFFFFFFFF
    out = bytearray()
    while z >= 0x80: out.append((z & 0x7F) | 0x80); z >>= 7
    out.append(z)
    return bytes(out)

def uleb_encode(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

async def resolve_host_cloudflare(hostname: str) -> str:
    if not hostname: return hostname
    parts = hostname.split('.')
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return hostname
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, exp = _DNS_CACHE[hostname]
        if now < exp: return ip
    loop = asyncio.get_running_loop()
    try:
        ip_info = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
        if ip_info:
            ip = ip_info[0][4][0]
            _DNS_CACHE[hostname] = (ip, now + _DNS_CACHE_TTL)
            return ip
    except Exception:
        pass
    return hostname

def optimize_tcp_socket(sock: socket.socket):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception:
        pass

def optimize_udp_socket(sock: socket.socket):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception:
        pass

async def safe_close_writer(writer):
    if not writer: return
    try:
        if not writer.is_closing(): writer.close()
        await asyncio.wait_for(writer.wait_closed(), timeout=1.5)
    except Exception:
        pass

async def aes_encrypt(payload, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(payload, AES.block_size))

async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF ^
                      ((v1 + s) & 0xFFFFFFFF) ^
                      (((v1 >> 5) + k1) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        v1 = (v1 + (((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF ^
                      ((v0 + s) & 0xFFFFFFFF) ^
                      (((v0 >> 5) + k3) & 0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1

async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF ^
                      ((v0 + s) & 0xFFFFFFFF) ^
                      (((v0 >> 5) + k3) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF ^
                      ((v1 + s) & 0xFFFFFFFF) ^
                      (((v1 >> 5) + k1) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1

async def tea_cbc_encrypt(padded, key_bytes):
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(padded))
    prev_cipher = bytearray(8)
    prev_intermediate = bytearray(8)
    for i in range(0, len(padded), 8):
        xored = bytearray(8)
        for j in range(8): xored[j] = padded[i + j] ^ prev_cipher[j]
        e0, e1 = await tea_enc(struct.unpack_from("<I", xored, 0)[0], struct.unpack_from("<I", xored, 4)[0], k0, k1, k2, k3)
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0)
        struct.pack_into("<I", enc, 4, e1)
        for j in range(8): out[i + j] = enc[j] ^ prev_intermediate[j]
        prev_cipher[:] = out[i:i + 8]
        prev_intermediate[:] = xored
    return bytes(out)

async def tea_cbc_decrypt(body, key_bytes):
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(body))
    prev_intermediate = bytearray(8)
    prev_cipher = bytearray(8)
    xored = bytearray(8)
    dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8): xored[j] = body[i + j] ^ prev_intermediate[j]
        d0, d1 = await tea_dec(struct.unpack_from("<I", xored, 0)[0], struct.unpack_from("<I", xored, 4)[0], k0, k1, k2, k3)
        struct.pack_into("<I", dec, 0, d0)
        struct.pack_into("<I", dec, 4, d1)
        for j in range(8): out[i + j] = dec[j] ^ prev_cipher[j]
        prev_cipher[:] = body[i:i + 8]
        prev_intermediate[:] = dec
    return bytes(out)

async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + content + b"\x00" * 7

async def encode_header(layout, send_option, cmd, order_id, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        value = {0: send_option, 1: cmd, 2: order_id, 3: flags, 4: length}[code]
        if _FIELD_SIZES[code] == 1:
            out.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF)
            out.append((v >> 8) & 0xFF)
    return bytes(out)

async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf: c = CRC7_TABLE[((2 * (c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F

async def sv_frame(msg_key, layout, send_option, cmd, order_id, flags, content, key, encrypted=True):
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0]) + await encode_header(layout, send_option, cmd, order_id, flags, len(body), k, v80)
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)

async def parse_layout(layout):
    if isinstance(layout, str): return [int(ch) for ch in layout.strip()]
    return list(layout)

async def produce_xor_key(secret_key):
    k = secret_key[0] if secret_key and len(secret_key) > 0 else 10
    return k, ((k << 8) | k) & 0xFFFF

async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")
    content = b"\x10\x00\x00\x00" + data + b"\x00" * (29 - 4 - len(data))
    k, v80 = await produce_xor_key(key)
    layout = await parse_layout(layout)
    padded = await build_padded(content)
    enc_body = await tea_cbc_encrypt(padded, key)
    header_bytes = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80)
    packet = bytearray([0x63, 0x00]) + header_bytes + enc_body
    packet[1] = await crc7_buff(0, packet[2:]) & 0x7F
    return bytes(packet).hex()

async def layouts_from_mask(mask):
    ru = [int(c) for c in str(mask).strip()]
    nr = [c for c in ru if c != 2]
    return ru, nr

async def build_packet(msg_key, layout, send_option, cmd, order_id, flags, content, key, encrypted=True):
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        value = {0: send_option, 1: cmd, 2: order_id, 3: flags, 4: len(body)}[code]
        if _FIELD_SIZES[code] == 1:
            hdr.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF)
            hdr.append((v >> 8) & 0xFF)
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)

async def classify(frame):
    cmd = frame["cmd"]
    msg_name = MESSAGE_ID_TO_NAME.get(cmd, f"UNKNOWN_{cmd}")
    if msg_name == "UDP_HELLO": return "HELLO"
    if msg_name == "UDP_ACK": return "ACK"
    if msg_name == "UDP_PING": return "PING"
    if msg_name == "RUDP_JOIN_MATCH": return "JOIN_MATCH"
    return msg_name

async def reply_for(frame, key, mask, ack_key=0x68, ping_key=0x6D, hello_key=0x5B, ack_style="short"):
    ru, nr = await layouts_from_mask(mask)
    typ = await classify(frame)
    if typ == "HELLO":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x01\x00", key)
    if typ == "ACK":
        content = frame["content"] if frame["content"] else b"\x01\x00"
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, content, key)
    if typ == "PING":
        c = frame["content"]
        counter = c[:4] if len(c) >= 4 else c
        return typ, await build_packet(ping_key, nr, 0, 3, None, 0, counter + b"\x00\x00\x00", key, encrypted=False)
    if typ == "JOIN_MATCH":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x02\x00", key)
    return typ, None

async def keepalive_ping(sock, ip, port, key_bytes, mask, stop_event):
    nr = (await layouts_from_mask(mask))[1]
    ping_keys = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]
    loop = asyncio.get_event_loop()
    i = 0
    while not stop_event.is_set():
        pk = ping_keys[i % len(ping_keys)]
        counter = int(time.time() * 1000) & 0xFFFFFFFF
        pkt = await build_packet(pk, nr, 0, 3, None, 0, struct.pack("<I", counter) + b"\x00\x00\x00", key_bytes, encrypted=False)
        try: await loop.sock_sendto(sock, pkt, (ip, port))
        except Exception: pass
        i += 1
        try: await asyncio.wait_for(stop_event.wait(), timeout=3.0)
        except asyncio.TimeoutError: pass

async def try_header(buf, layout, k, v80):
    off = 2
    out = {}
    for code in layout:
        size = _FIELD_SIZES[code]
        if off + size > len(buf): return None
        out[_FIELD_NAMES[code]] = (buf[off] ^ k) if size == 1 else ((buf[off] | (buf[off + 1] << 8)) ^ v80) & 0xFFFF
        off += size
    out["headerLen"] = off
    return out

async def oicq_unpad(padded):
    if not padded or len(padded) < 8 or not all(padded[-1 - i] == 0 for i in range(7)): return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len
    e = len(padded) - 7
    return padded[s:e] if s < e else b""

async def decode_packet(packet, key, mask=None):
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8: return None
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    candidates = []
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0, 1, 2, 3, 4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0, 1, 3, 4])]
    for kind, layout in layouts:
        f = await try_header(data, layout, k, v80)
        if not f or f["flags"] > 7 or f["sendOption"] > 7 or f["length"] != len(data) - f["headerLen"]: continue
        body = data[f["headerLen"]:f["headerLen"] + f["length"]]
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0: continue
            padded = await tea_cbc_decrypt(body, key)
            content = await oicq_unpad(padded)
            if content is None: continue
        else:
            padded, content = None, body
        score = (1 if crc_ok else 0) + (1 if content is not None else 0)
        candidates.append({
            "kind": kind, "layout": layout, "headerLen": f["headerLen"],
            "msgKey": data[0], "cmd": f["cmd"], "flags": f["flags"],
            "sendOption": f["sendOption"], "orderId": f.get("orderId"),
            "length": f["length"], "content": content, "crcOk": crc_ok,
            "padded": padded, "score": score, "total": len(data),
        })
    if not candidates: return None
    candidates.sort(key=lambda c: (c["kind"] == "RUDP" or c["kind"] == "nonRUDP", c["score"]), reverse=True)
    return candidates[0]

async def parse_results(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {"wire_type": result.wire_type}
        if result.wire_type in ("varint", "string", "bytes"):
            field_data["data"] = result.data
        elif result.wire_type == "length_delimited":
            if hasattr(result.data, "results"):
                field_data["data"] = await parse_results(result.data.results)
            elif isinstance(result.data, list):
                field_data["data"] = await parse_results(result.data)
            else:
                field_data["data"] = str(result.data)
        result_dict[str(result.field)] = field_data
    return result_dict

async def decode_protobuf(data):
    parsed = Parser().parse(data)
    res = await parse_results(parsed)
    return json.dumps(res)

# ==================== OAUTH LOGIN ENGINE ====================
async def get_playstore_version():
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, lambda: play_scraper('com.dts.freefireth', lang='hi', country='id'))
        return res.get("version")
    except Exception:
        return "1.132.8"

async def version_config(client_http: httpx.AsyncClient, region="IND"):
    app_version = await get_playstore_version()
    lang = REGION_LANG.get(region, "hi")
    api_url = (
        "https://version.ggwhitehawk.com/live/ver.php"
        f"?version={app_version}&lang={lang}&device=android&channel=android"
        f"&appstore=googleplay&region={region}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"
    )
    try:
        res = await client_http.get(api_url)
        data = res.json()
        return data.get("latest_release_version"), data.get("remote_version"), data.get("server_url")
    except Exception:
        return None

async def get_access_token(client_http: httpx.AsyncClient, uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B Build/SP1A.210812.016)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": str(uid), "password": str(password), "response_type": "token",
        "client_type": "2", "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    for _ in range(3):
        try:
            r = await client_http.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                rd = r.json()
                return rd.get("open_id"), rd.get("access_token"), rd.get("platform", 4)
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return None

async def build_majorlogin_payload(open_id, access_token, platform, client_version):
    try:
        proto = thunderFF_pb2.MajorLoginReq()
        proto.event_time = str(datetime.now())[:-7]
        proto.game_name = "free fire"
        proto.platform_id = 1
        proto.client_version = str(client_version)
        proto.client_version_code = "2019121229"
        proto.system_software = "Android OS 15 / API-35 (AP3A.240905.015.A2/185014)"
        proto.system_hardware = "Handheld"
        proto.device_type = "Handheld"
        proto.screen_width = 1600
        proto.screen_height = 719
        proto.screen_dpi = "234"
        proto.processor_details = "ARM64 FP ASIMD AES | 1820 | 8"
        proto.memory = 2798
        proto.gpu_renderer = "Mali-G57"
        proto.gpu_version = "OpenGL ES 3.2 v1.r49p1-04eac0.2848c17a2fd4e9340e06555168eaa3c9"
        proto.unique_device_id = f"Google|{str(uuid.uuid4())}"
        proto.client_ip = f"{random.randint(103, 223)}.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}"
        proto.language = "hi"
        proto.open_id = str(open_id)
        proto.open_id_type = "4"
        proto.login_open_id_type = 4
        proto.access_token = str(access_token)
        proto.login_by = 2
        proto.platform_sdk_id = 1
        proto.origin_platform_type = "4"
        proto.primary_platform_type = "4"
        proto.reg_avatar = 1
        proto.channel_type = 3
        proto.telecom_operator = "JIO"
        proto.network_operator_a = "JIO"
        proto.network_type = "WIFI"
        proto.network_type_a = "WIFI"
        proto.cpu_type = 2
        proto.cpu_architecture = "64"
        proto.graphics_api = "OpenGLES2"
        proto.supported_astc_bitset = 8191
        proto.client_using_version = "7428b253defc164018c604a1ebbfebdf"
        proto.loading_time = 15078
        proto.release_channel = "android"
        proto.extra_info = "KqsHTx3+QOmBRR1WKvaWewlcpqJBfjki+PPHQoQG8+0yV+Uos7gUFFjHMQ/e7u6han6Fl77r7c3vMN3p8UbKgN+nfycQCgwBmWgBzomx2gj84c+p"
        proto.android_engine_init_flag = 111207
        proto.if_push = 1
        proto.is_vpn = 0

        proto.memory_available.version = 55
        proto.memory_available.hidden_value = 81
        proto.external_storage_total = 49973
        proto.external_storage_available = 11338
        proto.internal_storage_total = 854
        proto.internal_storage_available = 11466
        proto.game_disk_storage_total = 49973
        proto.game_disk_storage_available = 11466
        proto.external_sdcard_total_storage = 49973
        proto.external_sdcard_avail_storage = 11466
        proto.library_path = "/data/app/~~lHFxTCCbupG2QVJmsURtZw==/com.dts.freefireth-N3aCHpHNXpdxjD80uIIbww==/lib/arm64"
        proto.library_token = "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~lHFxTCCbupG2QVJmsURtZw==/com.dts.freefireth-N3aCHpHNXpdxjD80uIIbww==/base.apk"

        base_payload = proto.SerializeToString()
        extra = b""
        extra += _pb_field(96, '{"cur_rate":[90,60,120],"support_etc2":false}')
        extra += _pb_field(97, 1)
        extra += _pb_field(99, "4")
        extra += _pb_field(100, "4")
        extra += _pb_field(102, b"\x17]ENWU\x0eR5")
        extra += _pb_field(104, 52882)
        extra += _pb_field(105, 1)
        extra += _pb_field(106, "https://dl.ak.freefiremobile.com/live/ABHotUpdates/|https://core-ak.freefiremobile.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462")
        extra += _pb_field(107, "c8e41b7a93f02d56e1a94c7b8203f5d1")

        full = base_payload + extra
        return await aes_encrypt(full, AES_KEY, AES_IV)
    except Exception as e:
        return None

async def send_majorlogin(client_http: httpx.AsyncClient, data, release_version, server_url):
    try:
        url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
        req_headers = headers.copy()
        req_headers["ReleaseVersion"] = str(release_version)
        response = await client_http.post(url, headers=req_headers, data=data)
        if response.status_code != 200 or len(response.content) < 40: return None

        res_proto = thunderFF_pb2.MajorLoginRes()
        try: res_proto.ParseFromString(response.content)
        except Exception: pass

        if not (res_proto.account_id and res_proto.token):
            for offset in range(min(128, len(response.content))):
                try:
                    c = thunderFF_pb2.MajorLoginRes()
                    c.ParseFromString(response.content[offset:])
                    if c.account_id and c.token: res_proto = c; break
                except Exception: pass

        parsed = Parser().parse(response.content.hex())
        dict_res = await parse_results(parsed)
        key_val = get_proto_field(dict_res, 22) or res_proto.aes_ak or AES_KEY
        iv_val = get_proto_field(dict_res, 23) or res_proto.iv_i or AES_IV

        if isinstance(key_val, str):
            try: key_val = bytes.fromhex(key_val)
            except Exception: pass
        if isinstance(iv_val, str):
            try: iv_val = bytes.fromhex(iv_val)
            except Exception: pass

        res_proto.aes_ak = key_val
        res_proto.iv_i = iv_val
        if not res_proto.url: res_proto.url = server_url
        return res_proto
    except Exception:
        return None

async def send_getlogin(client_http: httpx.AsyncClient, data, base_url, token, release_version):
    try:
        url = f"{base_url.rstrip('/')}/GetLoginData"
        req_headers = headers.copy()
        req_headers["ReleaseVersion"] = release_version
        req_headers['Authorization'] = f"Bearer {token}"
        req_headers['Host'] = "clientbp.ppmainecoonghj.com"
        response = await client_http.post(url, headers=req_headers, data=data)
        if response.status_code != 200: return None

        res_proto = thunderFF_pb2.GetLoginDataRes()
        try: res_proto.ParseFromString(response.content)
        except Exception: pass

        parsed = Parser().parse(response.content.hex())
        dict_res = await parse_results(parsed)
        return res_proto, dict_res
    except Exception:
        return None

# ==================== MATCH PAYLOADS ====================
async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="IND", typ='OnLine'):
    uid_hex = f"{int(account_id):016x}"
    timestamp_hex = f"{int(server_time):08x}"
    encrypted_packet = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(token.encode(), 16)).hex()
    encrypted_packet_length = f"{len(encrypted_packet) // 2:08x}"
    reg = str(region).upper() if region else "IND"
    prefix = "7114" if reg == "IND" else ("9015" if reg == "ME" else "7119")
    if typ == 'OnLine':
        return f"{prefix}{uid_hex}{timestamp_hex}00000000{encrypted_packet_length}{encrypted_packet}"
    else:
        return f"{prefix}{uid_hex}{timestamp_hex}{encrypted_packet_length}{encrypted_packet}"

async def send_keep_alive(region="IND"):
    reg = str(region).upper() if region else "IND"
    ka_hex = "0214" if reg == "IND" else ("0219" if reg == "ME" else "0215")
    return bytes.fromhex(ka_hex)

async def start_game_battle_royale(region, client_version, writer, key, iv):
    packet = bytes.fromhex("080112800a0a010110013a110a044944433110aa011a064555524f50453a100a044944433210311a064555524f504540014a0801090a0b1219202758016291090a8001303838463832424630324139363736373032303130313030303030303030303030303136303030313030313530303032323246393745454530463030303030303436373632353134303030303030303030303030303030303030303030303030303030303030303030303030303066663030303030303030636163666131366410241afb02735d5e571400024a775d45414d1a041b1c001f11010449715f4243481a001e1d071c1703004b1a4066785c524570735c51486775421b5c5a4c07504042685a63610816054e19025e75196001477c015165406370195f5547404e4550640103020f1304064863754268676c755f65576e40467e5f0a417a4701026d675d6e73670b1108495a4c6a0b78470b740065645e525a057258425f584a447d4e6759440c11044e7c596d7f4b625f7d04055a47505c4e1d6b5b4107447d7201057d7f0f14084e430457674f7e517d72015172415d027473577c4d615f79535256780911030f4d5e027a797f614165067806505d53777750475e75064257076500460817014e741e7e5078487e7a7c465e7669767153497064605a7376677773550d160148037e18675966787f4c42607a645f577e7b441b460776026b18685d0b110205490060020f70676175654674706671797f41067346677c4e06585e780f15074c57047b40517075415f6364027259674b5b0166407f7340600407770a22047a5d5c52300b3a0a167305067162727516134208312e3133302e3232480350015ae90403626253513635686e556f4e36416456324b796f566c636f477776484f624e56526c4d727073504b4f43654177616848494176795556497273743752737149734a7a786b3247525268377a2f637664626d504f6a73552f79626d38547a4c69586d2f474351696d494b53486833447955726f39515152756c34545350626d6d624b7949565937545671577059455372323646572f59624578507338514f706d317372785455736c30796a434144444d4f34616a654b615753366361496c554b4963797a494e396d52516f715277687939797257476d337a644345337a6a61436f492f5a585233656f65365a42647a64677654636b6b665733356e4d4c6a6a565072564b6433523172756174394e50514150724a5546627859696c4c5a3859707336654d5447666b6649793574666a526c314d4648706b51774c6373374439656378566c41636f374e664f6d2b30654756466c4434744478706771385533595973587645384842502f70666c767a737138316a32524f4d7857437556445442492f684735625462773166456e4249725162762b636144775147696f74554e316d4c4b77734379456f4766706746614251457645672b736a764c4c78704743334c304a5344532f74526169504354553344374e6249306547516651622f5a466f4c36455630775a324d6f583932414c572f5049752f56634663584e70596b356f7966326151416a536971486a2f363276354843644f525551303578754e6171795251625653704654303137655237675255636b4966366c6f447476342b514e4a4670766d74757077707774396a5a5974437a4b56743657726d6e36785837706658456251555434684f3758a201050803108703a201050804108103a20105080510c001a20105081d10cc01a2010408161078a20105080e10af01a201020815")
    proto = thunderFF_pb2.StartMatch()
    proto.ParseFromString(packet)
    if hasattr(proto.main, 'region_list') and len(proto.main.region_list) > 0:
        proto.main.region_list[0].region = region
        if len(proto.main.region_list) > 1:
            proto.main.region_list[1].region = region
    if hasattr(proto.main, 'client_version'):
        proto.main.client_version.remote_version = client_version
    packet = proto.SerializeToString()
    encrypted_packet = (await aes_encrypt(packet, key, iv)).hex()
    packet_length = len(encrypted_packet) // 2
    hex_length = hex(packet_length)[2:]
    hex_length = hex_length if len(hex_length) > 1 else "0" + hex_length
    reg = str(region).upper() if region else "IND"
    reg_prefix = REGION_PREFIX.get(reg, "031400")
    final_packet = reg_prefix + "0" * (6 - len(hex_length)) + hex_length + encrypted_packet
    writer.write(bytes.fromhex(final_packet))
    await writer.drain()

async def build_match_startup_packets(token, udp_key, match_code, account_id, block_val,
                                      server_ip="", region="IND", client_version="1.132.8",
                                      client_version_code="2019121229", access_token="",
                                      mode_id=MODE_ID, map_id=MAP_ID):
    token = token.strip()
    udp_key = bytes.fromhex(udp_key)
    match_code = [int(ch) for ch in str(match_code).strip()]
    thunder_jwt = token[:660] if len(token) > 660 else token
    sharma_jwt = token[660:] if len(token) > 660 else ""
    encoded_thunder_jwt = thunder_jwt.encode() if isinstance(thunder_jwt, str) else thunder_jwt
    encoded_sharma_jwt = sharma_jwt.encode() if isinstance(sharma_jwt, str) else sharma_jwt

    garena420 = has_ssan_zig(len(encoded_thunder_jwt)) + encoded_thunder_jwt
    reg = str(region).upper() if region else "IND"

    csoversea_block = bytes.fromhex(
        "ca0163736f7665727365612e7374726f6e67686f6c642e66726565666972656d6f62696c652e636f6d"
        "3b302e302e302e303b33342e3132362e37362e34353b33342e38372e3137372e31343b33342e38372e"
        "3137302e3233303b33352e3138352e3138332e35370000000000000100000000000000000000000001"
        "00000800000100000000000100a8a2d7bebd8d8bdf110200"
    )

    mid = bytes.fromhex('0000000001000102030101') + has_ssan_zig(len(reg)) + reg.encode()
    mid += bytes.fromhex('0001030003000004')
    mid += has_ssan_zig(len(client_version)) + client_version.encode()
    mid += has_ssan_zig(len(client_version_code)) + client_version_code.encode()
    mid += csoversea_block
    clean_ip = server_ip.split(':')[0] if server_ip else "0.0.0.0"
    mid += has_ssan_zig(len(clean_ip)) + clean_ip.encode()
    if access_token: mid += has_ssan_zig(len(access_token)) + access_token.encode()
    mid += has_ssan_zig(len(encoded_sharma_jwt)) + encoded_sharma_jwt

    tg_garena420 = (
        uleb_encode(int(account_id)) + uleb_encode(int(block_val)) +
        uleb_encode(1) + uleb_encode(int(mode_id)) +
        uleb_encode(int(block_val)) + uleb_encode(int(map_id)) + mid
    )

    process = await sv_frame(0x5E, match_code, 2, 447, 0, 1, garena420, udp_key)
    loading = await sv_frame(0x5A, match_code, 2, 448, 1, 1, tg_garena420, udp_key)
    return process.hex(), loading.hex()

# ==================== LIVE TERMINAL ANIMATION ====================
async def match_animation_worker(match_index: int, start_time: float, stop_event: asyncio.Event, max_duration=None):
    spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
    max_str = "∞" if max_duration is None else f"{int(max_duration)//60:02d}:{int(max_duration)%60:02d}"

    while not stop_event.is_set():
        elapsed = int(time.time() - start_time)
        cur_min, cur_sec = divmod(elapsed, 60)
        time_str = f"{cur_min:02d}:{cur_sec:02d}"
        icon = next(spinner)
        status_line = (
            f"\r{Colors.YELLOW}🎮 [MATCH #{match_index}]{Colors.ENDC} "
            f"{Colors.GREEN}In-Game Surviving...{Colors.ENDC} "
            f"{Colors.CYAN}{icon}{Colors.ENDC} "
            f"[{time_str} / {max_str}] "
            f"{Colors.MAGENTA}⚡ EXP Active{Colors.ENDC}"
        )
        sys.stdout.write(status_line)
        sys.stdout.flush()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=0.25)
        except asyncio.TimeoutError:
            pass

    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()

# ==================== IN-GAME UDP ENGINE ====================
async def play_game(server_ip_port, thunder, sharma, udp_key, match_code,
                    account_id, player_region, client_version, key, iv, match_index: int):
    match_start_time = time.time()
    ping_task = None
    anim_task = None
    sock = None
    ping_stop = asyncio.Event()
    anim_stop = asyncio.Event()
    uid_str = str(account_id)
    completed_cleanly = False

    try:
        ip, port = server_ip_port.split(":")
        port = int(port)
        resolved_ip = await resolve_host_cloudflare(ip)

        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: sock.bind(('0.0.0.0', 0))
        except Exception: pass
        optimize_udp_socket(sock)
        sock.setblocking(False)

        udp_key_bytes = bytes.fromhex(udp_key)
        hello_packet = await build_hello_packet(f"{account_id}_2585", udp_key_bytes, match_code)
        await loop.sock_sendto(sock, bytes.fromhex(hello_packet), (resolved_ip, port))

        ack_state = "waiting_for_hello_reply"
        thunder_sent = False
        sharma_sent = False
        join_match_received = False
        local_closed = False
        send_lock = asyncio.Lock()

        ping_task = asyncio.create_task(keepalive_ping(sock, resolved_ip, port, udp_key_bytes, match_code, ping_stop))
        last_activity = time.time()

        print_colored(f"🎮 [MATCH #{match_index}] UDP In-Game Started -> {server_ip_port}", Colors.MAGENTA)

        async def send_thunder_sharma_inline():
            nonlocal ack_state, thunder_sent, sharma_sent
            if thunder_sent: return
            async with send_lock:
                if thunder_sent: return
                try:
                    await loop.sock_sendto(sock, bytes.fromhex(thunder), (resolved_ip, port))
                    thunder_sent = True
                    await asyncio.sleep(0.3)
                    prepare_ack = await build_packet(0x68, (await layouts_from_mask(match_code))[1], 0, 2, None, 1, b"\x01\x00", udp_key_bytes)
                    await loop.sock_sendto(sock, prepare_ack, (resolved_ip, port))
                    await asyncio.sleep(0.4)
                    await loop.sock_sendto(sock, bytes.fromhex(sharma), (resolved_ip, port))
                    sharma_sent = True
                    ack_state = "thunder_sharma_sent"
                    print_success(f"[MATCH #{match_index}] Player Spawning Handshake Complete!")
                except Exception:
                    pass

        while not local_closed:
            elapsed = time.time() - match_start_time
            try:
                response, server_addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), timeout=1.5)
                if response:
                    last_activity = time.time()
                    frame = await decode_packet(response, udp_key_bytes, match_code)
                    if frame:
                        ptype = await classify(frame)
                        cmd = frame['cmd']
                        if cmd in [103, 107]:
                            completed_cleanly = True
                            local_closed = True
                            continue
                        if cmd == 101:
                            ack_pkt = await build_packet(0x68, (await layouts_from_mask(match_code))[1], 0, 2, None, 1, b"\x01\x00", udp_key_bytes)
                            await loop.sock_sendto(sock, ack_pkt, server_addr)
                            continue

                        if ptype in ["ACK", "PING", "HELLO", "JOIN_MATCH"]:
                            if ptype == "HELLO" and ack_state == "waiting_for_hello_reply":
                                typ, reply = await reply_for(frame, udp_key_bytes, match_code, ack_style="short")
                                if reply: await loop.sock_sendto(sock, reply, server_addr)
                                ack_state = "ack_sent_waiting"
                            elif ptype == "ACK":
                                if ack_state in ["waiting_for_hello_reply", "ack_sent_waiting"]:
                                    ack_state = "ready_to_send_thunder"
                                else:
                                    typ, reply = await reply_for(frame, udp_key_bytes, match_code)
                                    if reply: await loop.sock_sendto(sock, reply, server_addr)
                            elif ptype == "PING":
                                typ, reply = await reply_for(frame, udp_key_bytes, match_code)
                                if reply: await loop.sock_sendto(sock, reply, server_addr)
                            elif ptype == "JOIN_MATCH" and not join_match_received:
                                typ, reply = await reply_for(frame, udp_key_bytes, match_code)
                                if reply:
                                    await loop.sock_sendto(sock, reply, server_addr)
                                    join_match_received = True

            except asyncio.TimeoutError:
                if ack_state == "ready_to_send_thunder" and not thunder_sent:
                    await send_thunder_sharma_inline()
                    if not anim_task:
                        anim_task = asyncio.create_task(match_animation_worker(match_index, match_start_time, anim_stop, MAX_MATCH_DURATION))
                elif ack_state == "thunder_sharma_sent":
                    if not anim_task:
                        anim_task = asyncio.create_task(match_animation_worker(match_index, match_start_time, anim_stop, MAX_MATCH_DURATION))
                    if (time.time() - last_activity) > MATCH_IDLE_TIMEOUT:
                        completed_cleanly = True
                        break
                continue
            except Exception:
                await asyncio.sleep(0.1)
                continue

            if ack_state == "ready_to_send_thunder" and not thunder_sent:
                await send_thunder_sharma_inline()
                if not anim_task:
                    anim_task = asyncio.create_task(match_animation_worker(match_index, match_start_time, anim_stop, MAX_MATCH_DURATION))

        return f"match #{match_index} finished"
    finally:
        anim_stop.set()
        if anim_task:
            anim_task.cancel()
            try: await anim_task
            except asyncio.CancelledError: pass
        if completed_cleanly:
            print_success(f"[★ MATCH #{match_index}] Survival Complete! EXP Secured.")
            bot_state.increment_match(uid_str)
        ping_stop.set()
        if ping_task:
            ping_task.cancel()
            try: await ping_task
            except asyncio.CancelledError: pass
        if sock:
            try: sock.close()
            except Exception: pass

# ==================== PERSISTENT TCP GATEWAY WITH AUTO IP-FAILOVER ====================
async def functional_br(addrs, starter_packet, account_region, client_version,
                        key, iv, account_id="", account_data=None):
    ip, port = addrs.split(":")
    uid_str = str(account_id)
    next_match_index = 0
    play_matches = set()

    async def run_match_and_refresh(*args):
        try:
            await play_game(*args)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print_error(f"[MATCH] UID {uid_str} background match error: {exc}")
        finally:
            await refresh_account_profile(account_data)

    while True:
        writer = None
        gateway_ping_task = None
        current_proxy = proxy_pool.get_current()
        search_attempts = 0

        try:
            resolved_ip = await resolve_host_cloudflare(ip)
            reader, writer = await open_proxied_connection(resolved_ip, int(port), current_proxy)
            raw_sock = writer.get_extra_info('socket')
            if raw_sock: optimize_tcp_socket(raw_sock)

            writer.write(bytes.fromhex(starter_packet))
            await writer.drain()

            try:
                init_ka = await send_keep_alive(account_region)
                if init_ka and writer and not writer.is_closing():
                    writer.write(init_ka)
                    await asyncio.wait_for(writer.drain(), timeout=3)
            except Exception:
                pass

            async def func_gateway_keepalive():
                ka_bytes = await send_keep_alive(account_region)
                while True:
                    await asyncio.sleep(5)
                    try:
                        if writer and not writer.is_closing():
                            writer.write(ka_bytes)
                            await writer.drain()
                    except Exception: break

            gateway_ping_task = asyncio.create_task(func_gateway_keepalive())
            print_success(f"TCP gateway connected | UID: {uid_str} | IP: {current_proxy or 'Direct'}")
            bot_state.update_status(uid_str, "ONLINE")

            async def send_start_match():
                nonlocal search_attempts
                search_attempts += 1
                print_info(f"UID {uid_str} -> Match Search #{search_attempts} ({account_region})")
                await start_game_battle_royale(account_region, client_version, writer, key, iv)
                bot_state.update_status(uid_str, "SEARCHING")

            await send_start_match()
            last_start_time = asyncio.get_running_loop().time()

            while True:
                # 🛑 ऑटो-आईपी स्विचिंग ट्रिगर: अगर 10 बार में मैच न मिले तो तुरंत आईपी बदलो
                if search_attempts >= MAX_SEARCHES_BEFORE_IP_SWITCH:
                    print_warning(f"[!] UID {uid_str} exceeded #{MAX_SEARCHES_BEFORE_IP_SWITCH} searches. Possible IP Shadow-Ban!")
                    proxy_pool.rotate()
                    break

                now = asyncio.get_running_loop().time()
                if now - last_start_time >= START_MATCH_INTERVAL:
                    await send_start_match()
                    last_start_time = now

                try:
                    data = await asyncio.wait_for(reader.read(65535), timeout=0.3)
                except asyncio.TimeoutError:
                    continue

                if not data:
                    raise ConnectionError("Gateway socket disconnected")

                hex_data = data.hex()
                packet_length = len(data)

                if hex_data.startswith("0300") and 10 < packet_length < 35:
                    continue

                if (hex_data.startswith("0300") and packet_length >= 300) or packet_length >= 500:
                    payload_hex = hex_data[10:] if hex_data.startswith("0300") else hex_data
                    res = json.loads(await decode_protobuf(payload_hex))

                    token = None; udp_key = None; match_code = None; server_ip_port = None; block_val = None

                    # Protobuf fields are normally {"wire_type": ..., "data": ...},
                    # but malformed/alternate gateway payloads can decode to scalars.
                    # Never call .get() on an unchecked value.
                    def _field_data(container, field):
                        if not isinstance(container, dict):
                            return None
                        value = container.get(str(field))
                        return value.get("data") if isinstance(value, dict) else None

                    match_code = _field_data(res, 42)
                    f5 = _field_data(res, 5)
                    if isinstance(f5, dict):
                        server_ip_port = _field_data(f5, 2)
                        udp_key = _field_data(f5, 3)
                        token = _field_data(f5, 4)
                        nested_match_code = _field_data(f5, 42)
                        if nested_match_code is not None:
                            match_code = nested_match_code
                        block_val = _field_data(f5, 1)
                    else:
                        # Large gateway packets are not necessarily match-start payloads.
                        # If field 5 is absent or not a decoded nested message, ignore this
                        # packet quietly and keep reading; do not emit a false match warning.
                        continue

                    if token and udp_key and match_code is not None and server_ip_port:
                        print_colored("=" * 60, Colors.GREEN)
                        print_colored(f"🎉 MATCH FOUND! Initializing UDP Game Room | UID: {uid_str}", Colors.GREEN)
                        print_colored("=" * 60, Colors.GREEN)
                        acc_tok = account_data.get('access_token', '') if account_data else ""
                        thunder, sharma = await build_match_startup_packets(
                            token, udp_key, match_code, account_id, block_val or 0,
                            server_ip=server_ip_port, region=account_region,
                            client_version=client_version, access_token=acc_tok,
                            mode_id=MODE_ID, map_id=MAP_ID
                        )

                        next_match_index += 1
                        match_task = asyncio.create_task(
                            run_match_and_refresh(
                                server_ip_port, thunder, sharma, udp_key, match_code,
                                account_id, account_region, client_version, key, iv,
                                next_match_index
                            ),
                            name=f"match-{uid_str}-{next_match_index}"
                        )
                        play_matches.add(match_task)
                        match_task.add_done_callback(play_matches.discard)
                        bot_state.update_status(uid_str, "SEARCHING")
                        print_info(
                            f"[PARALLEL] UID {uid_str}: match #{next_match_index} is running in background; "
                            f"{len(play_matches)} active match task(s) tracked. Reconnecting for the next search."
                        )

                        # Keep the existing gateway and packet protocol unchanged. Close this gateway
                        # after receiving match details, then let the outer loop reconnect and search
                        # while the UDP match continues independently in the background.
                        try:
                            writer.close()
                            await writer.wait_closed()
                        except Exception:
                            pass
                        await asyncio.sleep(NEW_MATCH_DELAY)
                        break

        except Exception as e:
            print_error(f"Gateway Notice for {uid_str}: {e}")
            proxy_pool.rotate()
            await asyncio.sleep(2)
        finally:
            if gateway_ping_task: gateway_ping_task.cancel()
            await safe_close_writer(writer)
            await asyncio.sleep(NEW_MATCH_DELAY)

# ==================== EXP STATS REFRESHER ====================
async def refresh_account_profile(account_data: Dict):
    try:
        if not account_data: return
        client_http = get_httpx_client(proxy_pool.get_current())
        res = await send_getlogin(
            client_http, account_data['login_payload_data'],
            account_data['server_url'], account_data['token'], account_data['release_version']
        )
        if res:
            res_proto, dict_res = res
            level = int(get_proto_field(dict_res, 6, 1))
            exp = int(get_proto_field(dict_res, 7, 0))
            acc_id = str(account_data['account_id'])
            if exp > 0: bot_state.update_exp(acc_id, exp, level)
            print_success(f"[EXP UPDATE] UID {acc_id} -> Level: {level} | EXP: {exp}")
    except Exception:
        pass

# ==================== ACCOUNT PROCESSOR ====================
async def process_account_uid_pass(uid: str, password: str) -> Optional[Dict]:
    print_info(f"Logging in UID: {uid}...")
    try:
        current_proxy = proxy_pool.get_current()
        client_http = get_httpx_client(current_proxy)

        verconfig_res = await version_config(client_http, "IND")
        if not verconfig_res: return None
        release_version, client_version, server_url = verconfig_res

        tokengrant_response = await get_access_token(client_http, uid, password)
        if not tokengrant_response: return None
        open_id, access_token, platform = tokengrant_response

        login_payload_data = await build_majorlogin_payload(open_id, access_token, platform, client_version)
        majorlogin_response = await send_majorlogin(client_http, login_payload_data, release_version, server_url)
        if not majorlogin_response: return None

        getlogin_result = await send_getlogin(client_http, login_payload_data, majorlogin_response.url, majorlogin_response.token, release_version)
        if not getlogin_result: return None
        res_proto, dict_res = getlogin_result

        acc_id = str(majorlogin_response.account_id)
        level = int(get_proto_field(dict_res, 6, 1))
        exp = int(get_proto_field(dict_res, 7, 0))
        nickname = res_proto.nickname or get_proto_field(dict_res, 4, f"Player_{acc_id}")
        region = majorlogin_response.region or get_proto_field(dict_res, 3, "IND")

        bot_state.register_account(uid=acc_id, nickname=nickname, region=region, level=level, exp=exp)
        # Replace the temporary login-UID card once the real in-game account ID is known.
        if str(uid) != acc_id:
            bot_state.accounts.pop(str(uid), None)
        # Link the dashboard's in-game account card back to the login UID so delete/refresh
        # controls can manage the correct worker.
        bot_state.account_credentials[acc_id] = {"uid": str(uid), "password": str(password)}

        account_data = {
            'account_id': majorlogin_response.account_id,
            'nickname': nickname,
            'region': region,
            'level': level,
            'exp': exp,
            'access_token': access_token,
            'token': majorlogin_response.token,
            'server_time': majorlogin_response.server_time,
            'aes_ak': majorlogin_response.aes_ak or AES_KEY,
            'iv_i': majorlogin_response.iv_i or AES_IV,
            'functional_addrs': res_proto.functional_addrs or get_proto_field(dict_res, 14),
            'release_version': release_version,
            'client_version': client_version,
            'server_url': majorlogin_response.url,
            'login_payload_data': login_payload_data,
        }
        print_success(f"Login OK | UID {acc_id} | {nickname} | Lvl {level} | Region: {region}")
        return account_data
    except Exception as e:
        print_error(f"Login error for {uid}: {e}")
        return None

# ==================== WORKER LOOP ====================
async def account_loop_guest(uid: str, password: str):
    uid_str = str(uid)
    while True:
        try:
            bot_state.update_status(uid_str, "CONNECTING")
            account_data = await process_account_uid_pass(uid_str, password)
            if not account_data:
                proxy_pool.rotate()
                await asyncio.sleep(10)
                continue

            func_addr = account_data.get('functional_addrs')
            if not func_addr:
                await asyncio.sleep(5)
                continue

            tcp_packet_online = await build_tcp_startup_packet(
                account_data['account_id'], account_data['token'], account_data['server_time'],
                account_data['aes_ak'], account_data['iv_i'], region=account_data['region'], typ='OnLine'
            )

            await functional_br(
                func_addr, tcp_packet_online, account_data['region'],
                account_data['client_version'], account_data['aes_ak'], account_data['iv_i'],
                account_id=account_data['account_id'], account_data=account_data
            )
        except asyncio.CancelledError:
            bot_state.update_status(uid_str, "OFFLINE")
            break
        except Exception as e:
            print_error(f"Loop error: {e}")
            await asyncio.sleep(5)

# ==================== MAIN ====================
def load_accounts():
    """Load only accounts explicitly saved through the dashboard; never use a hardcoded fallback."""
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [a for a in data if isinstance(a, dict) and a.get("uid") and a.get("password")] if isinstance(data, list) else []
        except Exception as e:
            print_error(f"Could not read {ACCOUNTS_FILE}: {e}")
    return []

async def start_dashboard_account(account):
    uid = str(account.get("uid", "")).strip()
    password = str(account.get("password", "")).strip()
    if not uid or not password:
        return
    # Show the account immediately, even while authentication is still in progress.
    if uid not in bot_state.accounts:
        bot_state.register_account(uid, f"Login {uid[-6:]}", "--", 1, 0)
        bot_state.update_status(uid, "CONNECTING")
    old_task = bot_state.account_workers.get(uid)
    if old_task and not old_task.done():
        old_task.cancel()
        await asyncio.gather(old_task, return_exceptions=True)
    task = asyncio.create_task(account_loop_guest(uid, password), name=f"account-{uid}")
    bot_state.account_workers[uid] = task
    bot_state.log(f"Worker started for login UID {uid}", "success", uid)

async def main():
    print_colored("=" * 60, Colors.CYAN)
    print_colored("   TEAM 84FF - FreeFire Level Up Bot (Auto IP Switching)", Colors.GREEN)
    print_colored("  Failover Threshold: Search #10 -> Next Rotating Proxy", Colors.WHITE)
    print_colored("=" * 60, Colors.CYAN)

    # Dashboard actions are the only way to add/start accounts while the bot is running.
    bot_state.refresh_callbacks["on_account_added"] = start_dashboard_account
    try:
        await start_web_dashboard(host=WEB_HOST, port=WEB_PORT)
    except Exception as e:
        print_error(f"Dashboard failed to start: {e}")

    accounts = load_accounts()
    print_info(f"Loaded {len(accounts)} dashboard-saved account(s) and {len(proxy_pool.proxies)} proxy IP(s).")
    for acc in accounts:
        await start_dashboard_account(acc)

    try:
        # Keep the dashboard alive even when no accounts have been added yet.
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        tasks = list(bot_state.account_workers.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\nStopped by user.")
