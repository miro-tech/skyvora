
import json
import base64
import urllib.request
from urllib.parse import urlencode, quote
import os

# =========================
# НАСТРОЙКИ
# =========================

URL = "https://skyvora.app/sub/2a2fd40b4f429240933c078a43862344"

GIST_TOKEN = os.environ["GIST_TOKEN"]
GIST_ID = os.environ["GIST_ID"]

# =========================
# СКАЧИВАНИЕ JSON
# =========================

req = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(
        r.read().decode("utf-8")
    )

# =========================
# ГЕНЕРАЦИЯ VLESS
# =========================

out = []

for s in data["servers"]:

    sid = s["id"]
    uuid = s["uuid"]

    sni = s.get("sni", "")
    flow = s.get("flow", "")

    pbk = s["public_key"]
    fp = s.get("fingerprint", "chrome")
    short_id = s["short_id"]

    endpoints = s["endpoints"]

    ports = s.get(
        "ports",
        [s["port"]]
    )

    for ip in endpoints:

        for port in ports:

            params = {
                "encryption": "none",
                "security": "reality",
                "sni": sni,
                "fp": fp,
                "pbk": pbk,
                "sid": short_id,
                "type": "tcp",
                "flow": flow,
            }

            link = (
                f"vless://{uuid}@{ip}:{port}"
                f"?{urlencode(params)}"
                f"#{quote('Skyvora-' + sid + '-' + ip + '-' + str(port))}"
            )

            out.append(link)

text = "\n".join(out) + "\n"

# =========================
# BASE64
# =========================

encoded = base64.b64encode(
    text.encode()
).decode()

# =========================
# GITHUB GIST UPDATE
# =========================

gist_url = (
    "https://api.github.com/gists/"
    + GIST_ID
)

payload = json.dumps({
    "files": {
        "skyvora.txt": {
            "content": text
        },
        "skyvora_base64.txt": {
            "content": encoded
        },
        "skyvora.json": {
            "content": json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            )
        }
    }
}).encode("utf-8")

req = urllib.request.Request(
    gist_url,
    data=payload,
    method="PATCH",
    headers={
        "Authorization": f"Bearer {GIST_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "skyvora-gist-updater",
    }
)

with urllib.request.urlopen(req, timeout=30) as r:
    result = json.loads(
        r.read().decode("utf-8")
    )

print("Готово!")
print("Серверов:", len(data["servers"]))
print("Конфигов:", len(out))
print("Gist обновлён:", result.get("html_url"))
