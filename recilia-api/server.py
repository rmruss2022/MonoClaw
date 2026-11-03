#!/usr/bin/env python3
"""
Recilia API — accounts + grove sync for the Nightbloom app.

Zero third-party deps (stdlib http.server + sqlite3), reboot-safe. Mirrors the
Lumen/rolodex auth pattern: pbkdf2 password hashing + random bearer tokens.
Stores each user's whole profile blob (grove / streak / achievements / tfi) so it
syncs across web + phone. CORS-open so the hosted web build can call it.

Env: PORT (Railway injects), RECILIA_HOST (0.0.0.0 in prod), RECILIA_DATA (volume).
"""
import os, json, sqlite3, hashlib, secrets, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT") or os.environ.get("RECILIA_PORT", "18846"))
HOST = os.environ.get("RECILIA_HOST", "127.0.0.1")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("RECILIA_DATA") or os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)
DB = os.path.join(DATA, "recilia.db")
_lock = threading.Lock()


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = db()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          salt TEXT NOT NULL,
          pw_hash TEXT NOT NULL,
          created REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tokens(
          token TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          created REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profiles(
          user_id INTEGER PRIMARY KEY,
          json TEXT NOT NULL,
          updated REAL NOT NULL
        );
        """
    )
    c.commit()
    c.close()


def hash_pw(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200000).hex()


def user_for_token(c, token):
    if not token:
        return None
    row = c.execute(
        "SELECT u.* FROM users u JOIN tokens t ON t.user_id=u.id WHERE t.token=?",
        (token,),
    ).fetchone()
    return row


def eleven_tts(text, voice, key):
    """Call ElevenLabs text-to-speech and return mp3 bytes. Raises on failure."""
    import urllib.request
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    payload = json.dumps({
        "text": text,
        "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5"),
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    # ---- helpers ----
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _token(self):
        h = self.headers.get("Authorization", "")
        return h[7:].strip() if h.startswith("Bearer ") else None

    def _serve_tts(self, text, voice):
        """Shared by GET /tts?text=… (easy to play by URL) and POST /tts {text}."""
        text = (text or "")[:5000]
        key = os.environ.get("ELEVENLABS_API_KEY")
        voice = voice or os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        if not key:
            self._send(503, {"error": "tts_unconfigured"})
            return
        if not text.strip():
            self._send(400, {"error": "empty text"})
            return
        # Cache by (voice, text): each unique narration costs one ElevenLabs call ever.
        import hashlib
        h = hashlib.sha1(f"{voice}:{text}".encode("utf-8")).hexdigest()
        cdir = os.path.join(DATA, "tts")
        cpath = os.path.join(cdir, h + ".mp3")
        audio = None
        if os.path.exists(cpath):
            try:
                with open(cpath, "rb") as f:
                    audio = f.read()
            except Exception:
                audio = None
        if audio is None:
            try:
                audio = eleven_tts(text, voice, key)
            except Exception:
                self._send(502, {"error": "tts_failed"})
                return
            try:
                os.makedirs(cdir, exist_ok=True)
                with open(cpath, "wb") as f:
                    f.write(audio)
            except Exception:
                pass
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(audio)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self._cors()
        self.end_headers()
        self.wfile.write(audio)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p in ("/health", "/healthz"):
            self._send(200, {"ok": True})
            return
        if p == "/tts":
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            self._serve_tts(q.get("text", [""])[0], q.get("voice", [None])[0])
            return
        if p == "/me":
            with _lock:
                c = db()
                try:
                    u = user_for_token(c, self._token())
                    if not u:
                        self._send(401, {"error": "sign in"})
                        return
                    row = c.execute("SELECT json FROM profiles WHERE user_id=?", (u["id"],)).fetchone()
                    prof = json.loads(row["json"]) if row else None
                    self._send(200, {"email": u["email"], "profile": prof})
                finally:
                    c.close()
            return
        self._send(404, {"error": "not found"})

    def do_PUT(self):
        p = self.path.split("?", 1)[0]
        if p == "/me/profile":
            data = self._body()
            prof = data.get("profile")
            if prof is None:
                self._send(400, {"error": "missing profile"})
                return
            with _lock:
                c = db()
                try:
                    u = user_for_token(c, self._token())
                    if not u:
                        self._send(401, {"error": "sign in"})
                        return
                    c.execute(
                        "INSERT INTO profiles(user_id,json,updated) VALUES(?,?,?) "
                        "ON CONFLICT(user_id) DO UPDATE SET json=excluded.json, updated=excluded.updated",
                        (u["id"], json.dumps(prof), time.time()),
                    )
                    c.commit()
                    self._send(200, {"ok": True})
                finally:
                    c.close()
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        # ElevenLabs narration proxy (POST {text, voice?}). Keeps the key server-side.
        if p == "/tts":
            d = self._body()
            self._serve_tts((d.get("text") or "").strip(), d.get("voice"))
            return
        data = self._body()
        if p in ("/auth/signup", "/auth/login"):
            email = str(data.get("email", "")).strip().lower()
            pw = str(data.get("password", ""))
            if "@" not in email or len(pw) < 6:
                self._send(400, {"error": "Enter a valid email and a password of at least 6 characters."})
                return
            with _lock:
                c = db()
                try:
                    if p == "/auth/signup":
                        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                            self._send(409, {"error": "That email already has an account — try signing in."})
                            return
                        salt = secrets.token_hex(16)
                        c.execute(
                            "INSERT INTO users(email,salt,pw_hash,created) VALUES(?,?,?,?)",
                            (email, salt, hash_pw(pw, salt), time.time()),
                        )
                        uid = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
                    else:
                        u = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                        if not u or hash_pw(pw, u["salt"]) != u["pw_hash"]:
                            self._send(401, {"error": "Wrong email or password."})
                            return
                        uid = u["id"]
                    token = secrets.token_hex(32)
                    c.execute("INSERT INTO tokens(token,user_id,created) VALUES(?,?,?)", (token, uid, time.time()))
                    c.commit()
                    self._send(200, {"token": token, "email": email})
                finally:
                    c.close()
            return
        if p == "/auth/logout":
            with _lock:
                c = db()
                try:
                    c.execute("DELETE FROM tokens WHERE token=?", (self._token(),))
                    c.commit()
                finally:
                    c.close()
            self._send(200, {"ok": True})
            return
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    init()
    print(f"Recilia API on {HOST}:{PORT} (data={DATA})", flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
