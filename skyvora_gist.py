import json
import base64
import urllib.request
from urllib.parse import urlencode, quote
import os

# =========================
# НАСТРОЙКИ
# =========================

URL = "https://d.irhgiuj.live/sub/2a2fd40b4f429240933c078a43862344"

# Нужный регион
COUNTRY = "TM"

GIST_TOKEN = os.environ["GIST_TOKEN"]
GIST_ID = os.environ["GIST_ID"]

# =========================
# СКАЧИВАНИЕ JSON
# =========================

req = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "CF-IPCountry": COUNTRY,
    }
)

with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(
        r.read().decode("utf-8")
    )

# =========================
# ПРОВЕРКА РЕГИОНА
# =========================

if data.get("region") != COUNTRY:
    raise RuntimeError(
        f"API вернул регион {data.get('region')}, "
        f"а ожидался {COUNTRY}. Gist НЕ будет обновлён."
    )

# =========================
# ГЕНЕРАЦИЯ VLESS REALITY
# =========================

out = []

for s in data.get("servers", []):

    sid = s["id"]
    name = s.get("name", sid)

    uuid = s["uuid"]

    sni = s.get("sni", "")
    flow = s.get("flow", "")

    pbk = s["public_key"]
    fp = s.get("fingerprint", "chrome")
    short_id = s["short_id"]

    endpoints = s.get("endpoints", [])

    ports = s.get("ports")

    if not ports:
        if "port" in s:
            ports = [s["port"]]
        else:
            print(f"Пропуск {sid}: нет port/ports")
            continue

    # =========================
    # RELAY / DIRECT
    # =========================

    relayed = s.get("relayed", False)
    hop = s.get("hop", "")

    if relayed:
        route_type = "relay"
    else:
        route_type = "direct"

    # =========================
    # ГЕНЕРАЦИЯ
    # =========================

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
            }

            if flow:
                params["flow"] = flow

            parts = [
                "Skyvora",
                sid,
                ip,
                str(port),
                route_type,
            ]

            if hop:
                parts.append(hop)

            remark = "-".join(parts)

            link = (
                f"vless://{uuid}@{ip}:{port}"
                f"?{urlencode(params)}"
                f"#{quote(remark)}"
            )

            out.append(link)

# =========================
# ТЕКСТ
# =========================

text = "\n".join(out) + "\n"

# =========================
# BASE64
# =========================

encoded = base64.b64encode(
    text.encode("utf-8")
).decode("ascii")

# =========================
# СТАТИСТИКА
# =========================

relay_count = sum(
    1
    for s in data.get("servers", [])
    if s.get("relayed", False)
)

direct_count = len(data.get("servers", [])) - relay_count

print("================================")
print("Skyvora")
print("================================")
print("Запрошенный регион:", COUNTRY)
print("Полученный регион:", data.get("region"))
print("Config version:", data.get("config", {}).get("version"))
print("Серверов:", len(data.get("servers", [])))
print("Direct:", direct_count)
print("Relay:", relay_count)
print("VLESS конфигов:", len(out))
print("================================")

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

print()
print("Готово!")
print("Gist обновлён:", result.get("html_url"))
