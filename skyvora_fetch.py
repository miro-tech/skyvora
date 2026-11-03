#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Skyvora subscription → VLESS links
(Reality + CDN WS/TLS + CDN Reality)

Получение подписок из нескольких регионов.
Перебор доменов и резервных IP.
Сохранение результатов локально и в GitHub Gist.

Переменные окружения:
    GIST_TOKEN
    GIST_ID

Примеры:

    python3 skyvora_fetch_configs.py

    python3 skyvora_fetch_configs.py --device-id 7f3a9c21-6e48-4b72-a5d1-91c8e7b4f260

    python3 skyvora_fetch_configs.py --cf-country TM

    python3 skyvora_fetch_configs.py --cf-country TM AF

    python3 skyvora_fetch_configs.py --cf-country ""

    python3 skyvora_fetch_configs.py --out skyvora_out
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from pathlib import Path


# ============================================================
# SKYVORA SETTINGS
# ============================================================

TOKEN = "2a2fd40b4f429240933c078a43862344"
PATH = f"/sub/{TOKEN}"

APP_VERSION = "52"

HOSTS = [
    "d.irhgiuj.live",
    "d.vrask.fit",
    "d.irhgi.lol",
    "d.vrask.world",
    "d.skyvora.app",
    "sub.skyvora.app",
    "skyvora.app",
]

FALLBACK_IPS = [
    "31.214.157.41",
    "31.214.157.118",
    "80.77.25.249",
]

USER_AGENT = (
    "Dalvik/2.1.0 "
    "(Linux; U; Android 13; Pixel 7 "
    "Build/TQ3A.230805.001)"
)

TIMEOUT = 15

CTX = ssl.create_default_context()


# ============================================================
# GITHUB GIST
# ============================================================

GIST_TOKEN = os.environ.get("GIST_TOKEN")
GIST_ID = os.environ.get("GIST_ID")


# ============================================================
# HTTP FETCH
# ============================================================

def fetch(
    url: str,
    headers: dict,
    timeout: int = TIMEOUT,
) -> tuple[int, bytes]:

    req = urllib.request.Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            req,
            context=CTX,
            timeout=timeout,
        ) as r:

            return r.status, r.read()

    except urllib.error.HTTPError as e:

        body = (
            e.read()
            if hasattr(e, "read")
            else b""
        )

        return e.code, body


# ============================================================
# SKYVORA HOSTS
# ============================================================

def try_hosts(
    device_id: str,
    cf_country: str | None,
) -> tuple[str, dict]:

    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    if (
        cf_country is not None
        and str(cf_country).strip()
    ):

        headers["CF-IPCountry"] = (
            str(cf_country).strip().upper()
        )

    encoded_device = urllib.parse.quote(
        device_id,
        safe="",
    )

    candidates = []

    # --------------------------------------------------------
    # DOMAINS
    # --------------------------------------------------------

    for host in HOSTS:

        candidates.append(
            f"https://{host}{PATH}"
            f"?d={encoded_device}"
            f"&v={APP_VERSION}"
        )

    # --------------------------------------------------------
    # FALLBACK IPs
    # --------------------------------------------------------

    for ip in FALLBACK_IPS:

        candidates.append(
            f"https://{ip}{PATH}"
            f"?d={encoded_device}"
            f"&v={APP_VERSION}"
        )

    last_err = None

    for url in candidates:

        try:

            code, raw = fetch(
                url,
                headers,
            )

            if code != 200:

                print(
                    f"  [{code}] "
                    f"{url[:90]}..."
                )

                last_err = f"HTTP {code}"
                continue

            data = json.loads(raw)

            if (
                not isinstance(data, dict)
                or "servers" not in data
                or not isinstance(data.get("servers"), list)
            ):

                print(
                    f"  [bad JSON] "
                    f"{url[:90]}..."
                )

                last_err = "invalid response"
                continue

            print(f"  [OK] {url}")

            return url, data

        except Exception as e:

            print(
                f"  [FAIL] "
                f"{url[:90]}... → {e}"
            )

            last_err = str(e)

    raise RuntimeError(
        f"All hosts failed: {last_err}"
    )


# ============================================================
# PORT
# ============================================================

def port_of(
    s: dict,
) -> int | None:

    p = s.get("port")

    if isinstance(p, int) and p > 0:
        return p

    ports = s.get("ports") or []

    if ports:

        try:
            p = int(ports[0])

            if p > 0:
                return p

        except (TypeError, ValueError, IndexError):
            pass

    return None


# ============================================================
# ENDPOINT
# ============================================================

def endpoint_of(
    s: dict,
) -> str | None:

    eps = s.get("endpoints") or []

    if eps:
        return str(eps[0])

    return None


# ============================================================
# VLESS REALITY
# ============================================================

def reality_uri(
    s: dict,
    address: str,
    port: int,
) -> str:

    uid = s["uuid"]

    pbk = (
        s.get("public_key")
        or s.get("publicKey")
        or ""
    )

    sid = (
        s.get("short_id")
        or s.get("shortId")
        or ""
    )

    sni = (
        s.get("sni")
        or "www.apple.com"
    )

    flow = (
        s.get("flow")
        or "xtls-rprx-vision"
    )

    fp = (
        s.get("fingerprint")
        or "chrome"
    )

    name = urllib.parse.quote(
        f"{s.get('name') or s.get('id') or 'node'} "
        f"Reality {address}:{port}"
    )

    q = urllib.parse.urlencode(
        {
            "encryption": "none",
            "flow": flow,
            "fp": fp,
            "pbk": pbk,
            "security": "reality",
            "sid": sid,
            "sni": sni,
            "type": "tcp",
        },
        safe="",
    )

    return (
        f"vless://{uid}@{address}:{port}"
        f"?{q}#{name}"
    )


# ============================================================
# CDN WS / TLS
# ============================================================

def cdn_ws_uri(
    s: dict,
) -> str | None:

    cdn = s.get("cdn")

    if (
        not cdn
        or not isinstance(cdn, dict)
    ):
        return None

    host = cdn.get("host") or ""

    path = (
        cdn.get("path")
        or "/"
    )

    try:

        port = int(
            cdn.get("port")
            or 443
        )

    except (TypeError, ValueError):

        return None

    ips = cdn.get("ips") or []

    addr = (
        str(ips[0])
        if ips
        else host
    )

    if not addr:
        return None

    uid = s["uuid"]

    sni = host or addr

    name = urllib.parse.quote(
        f"{s.get('name') or s.get('id') or 'node'} "
        f"CDN {addr}"
    )

    q = urllib.parse.urlencode(
        {
            "encryption": "none",
            "fp": "chrome",
            "host": host or addr,
            "path": path,
            "security": "tls",
            "sni": sni,
            "type": "ws",
        },
        doseq=False,
    )

    return (
        f"vless://{uid}@{addr}:{port}"
        f"?{q}#{name}"
    )


# ============================================================
# CDN IP + REALITY PORT
# ============================================================

def cdn_reality_port_uri(
    s: dict,
) -> str | None:

    cdn = s.get("cdn")

    if (
        not cdn
        or not isinstance(cdn, dict)
    ):
        return None

    ips = cdn.get("ips") or []

    if not ips:
        return None

    port = port_of(s)

    if not port:
        return None

    return reality_uri(
        s,
        str(ips[0]),
        port,
    )


# ============================================================
# BUILD ALL LINKS
# ============================================================

def build_links(
    data: dict,
) -> list[str]:

    links = []

    servers = (
        data.get("servers")
        or []
    )

    for s in servers:

        if (
            not isinstance(s, dict)
            or not s.get("uuid")
        ):
            continue

        ep = endpoint_of(s)
        port = port_of(s)

        # ----------------------------------------------------
        # DIRECT REALITY
        # ----------------------------------------------------

        if ep and port:

            links.append(
                reality_uri(
                    s,
                    ep,
                    port,
                )
            )

        # ----------------------------------------------------
        # OTHER ENDPOINTS
        # ----------------------------------------------------

        for extra in (
            s.get("endpoints") or []
        )[1:]:

            if port:

                links.append(
                    reality_uri(
                        s,
                        str(extra),
                        port,
                    )
                )

        # ----------------------------------------------------
        # CDN WS/TLS
        # ----------------------------------------------------

        ws = cdn_ws_uri(s)

        if ws:
            links.append(ws)

        # ----------------------------------------------------
        # CDN IP + REALITY PORT
        # ----------------------------------------------------

        alt = cdn_reality_port_uri(s)

        if alt:
            links.append(alt)

    # --------------------------------------------------------
    # UNIQUE
    # --------------------------------------------------------

    seen = set()
    out = []

    for u in links:

        if u not in seen:

            seen.add(u)
            out.append(u)

    return out


# ============================================================
# GITHUB GIST UPDATE
# ============================================================

def update_gist(
    request_url: str,
    raw_json: str,
    all_text: str,
    reality_text: str,
    cdn_ws_text: str,
    all_b64: str,
) -> dict:

    if not GIST_TOKEN:

        raise RuntimeError(
            "GIST_TOKEN is not set"
        )

    if not GIST_ID:

        raise RuntimeError(
            "GIST_ID is not set"
        )

    files = {

        "skyvora.txt": {
            "content": all_text
        },

        "skyvora_reality.txt": {
            "content": reality_text
        },

        "skyvora_cdn_ws.txt": {
            "content": cdn_ws_text
        },

        "skyvora_base64.txt": {
            "content": all_b64
        },

        "skyvora_raw.json": {
            "content": raw_json
        },

        "skyvora_request_url.txt": {
            "content": request_url + "\n"
        },

    }

    payload = json.dumps(
        {
            "files": files
        },
        ensure_ascii=False,
    ).encode("utf-8")

    gist_url = (
        "https://api.github.com/gists/"
        + GIST_ID
    )

    req = urllib.request.Request(
        gist_url,
        data=payload,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {GIST_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "skyvora-gist-updater",
        },
    )

    with urllib.request.urlopen(
        req,
        timeout=30,
    ) as r:

        return json.loads(
            r.read().decode("utf-8")
        )


# ============================================================
# COUNTRY NORMALIZATION
# ============================================================

def normalize_countries(
    values: list[str] | None,
) -> list[str | None]:

    if values is None:
        return ["TM"]

    # --cf-country без аргументов отключает заголовок.
    if not values:
        return [None]

    result = []

    for value in values:

        value = str(value).strip().upper()

        if not value:
            result.append(None)
        else:
            result.append(value)

    # Удаляем повторяющиеся регионы.
    unique = []

    for country in result:

        if country not in unique:
            unique.append(country)

    return unique


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    ap = argparse.ArgumentParser(
        description=(
            "Skyvora → VLESS configs "
            "+ GitHub Gist"
        )
    )

    ap.add_argument(
        "--device-id",
        default=None,
        help=(
            "Device ID (UUID). "
            "Random if omitted."
        ),
    )

    ap.add_argument(
        "--cf-country",
        nargs="*",
        default=None,
        help=(
            "CF-IPCountry codes. "
            "Default: TM. "
            "Example: --cf-country TM AF. "
            'Disable: --cf-country ""'
        ),
    )

    ap.add_argument(
        "--out",
        type=Path,
        default=Path("skyvora_out"),
        help="Output directory",
    )

    args = ap.parse_args()

    # ========================================================
    # DEVICE ID
    # ========================================================

    device_id = (
        args.device_id
        or str(uuid.uuid4())
    )

    countries = normalize_countries(
        args.cf_country
    )

    print()
    print("=" * 70)
    print("SKYVORA SUBSCRIPTION FETCHER")
    print("=" * 70)

    print(
        f"device_id: {device_id}"
    )

    print(
        f"version: {APP_VERSION}"
    )

    print(
        f"User-Agent: Android 13"
    )

    print(
        "CF-IPCountry: "
        + ", ".join(
            c if c else "(not set)"
            for c in countries
        )
    )

    # ========================================================
    # FETCH ALL COUNTRIES
    # ========================================================

    country_results = []

    all_servers = []
    seen_servers = set()

    for country in countries:

        print()
        print("=" * 60)

        print(
            "Fetching country: "
            f"{country or '(not set)'}"
        )

        print("=" * 60)

        try:

            url, country_data = try_hosts(
                device_id,
                country,
            )

        except Exception as e:

            print(
                f"[ERROR] Country "
                f"{country or '(not set)'}: {e}",
                file=sys.stderr,
            )

            continue

        country_name = country or "DEFAULT"

        country_results.append(
            {
                "country": country_name,
                "url": url,
                "data": country_data,
            }
        )

        # ----------------------------------------------------
        # MERGE SERVERS
        # ----------------------------------------------------

        for server in (
            country_data.get("servers") or []
        ):

            if not isinstance(server, dict):
                continue

            key = json.dumps(
                server,
                sort_keys=True,
                ensure_ascii=False,
            )

            if key not in seen_servers:

                seen_servers.add(key)
                all_servers.append(server)

    if not country_results:

        print(
            "ERROR: all country requests failed",
            file=sys.stderr,
        )

        return 1

    # ========================================================
    # MERGE DATA
    # ========================================================

    # Основные поля первого успешного ответа.
    data = dict(
        country_results[0]["data"]
    )

    # Объединённый список серверов.
    data["servers"] = all_servers

    # Какой регион использован для основных метаданных.
    data["primary_country"] = (
        country_results[0]["country"]
    )

    # Полные исходные ответы всех регионов.
    data["region_results"] = [
        {
            "country": item["country"],
            "request_url": item["url"],
            "data": item["data"],
        }
        for item in country_results
    ]

    # Краткая информация о регионах.
    data["regions"] = {
        item["country"]: {
            "region": item["data"].get("region"),

            "updated_at": (
                item["data"].get("updated_at")
                or item["data"].get("updatedAt")
            ),

            "servers": len(
                item["data"].get("servers") or []
            ),

            "request_url": item["url"],
        }
        for item in country_results
    }

    # Первый URL — для совместимости с прежним форматом.
    url = country_results[0]["url"]

    # ========================================================
    # COUNTRY SUMMARY
    # ========================================================

    print()
    print("Country summary:")

    for item in country_results:

        print(
            f"  {item['country']}: "
            f"{len(item['data'].get('servers') or [])} servers"
        )

    print(
        f"Unique combined servers: {len(all_servers)}"
    )

    # ========================================================
    # OUTPUT DIRECTORY
    # ========================================================

    args.out.mkdir(
        parents=True,
        exist_ok=True,
    )

    regions_dir = (
        args.out / "regions"
    )

    regions_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # SAVE INDIVIDUAL REGION JSON
    # ========================================================

    for item in country_results:

        country_name = item["country"]

        region_json = json.dumps(
            item["data"],
            indent=2,
            ensure_ascii=False,
        )

        region_file = (
            regions_dir
            / f"{country_name.lower()}.json"
        )

        region_file.write_text(
            region_json,
            encoding="utf-8",
        )

    # ========================================================
    # RAW JSON
    # ========================================================

    raw_json = json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
    )

    (
        args.out / "raw.json"
    ).write_text(
        raw_json,
        encoding="utf-8",
    )

    # ========================================================
    # REQUEST URL
    # ========================================================

    (
        args.out / "request_url.txt"
    ).write_text(
        url + "\n",
        encoding="utf-8",
    )

    all_request_urls = "\n".join(
        f"{item['country']}\t{item['url']}"
        for item in country_results
    )

    (
        args.out / "regions_request_urls.txt"
    ).write_text(
        all_request_urls + "\n",
        encoding="utf-8",
    )

    # ========================================================
    # INFO
    # ========================================================

    region = data.get("region")

    updated = (
        data.get("updated_at")
        or data.get("updatedAt")
    )

    servers = (
        data.get("servers")
        or []
    )

    print()
    print(
        f"primary_country={data.get('primary_country')}"
    )

    print(
        f"region={region}"
    )

    print(
        f"updated_at={updated}"
    )

    print(
        f"servers={len(servers)}"
    )

    # ========================================================
    # BUILD LINKS
    # ========================================================

    links = build_links(data)

    # ========================================================
    # ALL
    # ========================================================

    all_text = (
        "\n".join(links)
        + ("\n" if links else "")
    )

    (
        args.out / "all.txt"
    ).write_text(
        all_text,
        encoding="utf-8",
    )

    # ========================================================
    # REALITY
    # ========================================================

    reality = [
        u
        for u in links
        if "security=reality" in u
    ]

    reality_text = (
        "\n".join(reality)
        + ("\n" if reality else "")
    )

    (
        args.out / "reality.txt"
    ).write_text(
        reality_text,
        encoding="utf-8",
    )

    # ========================================================
    # CDN WS
    # ========================================================

    cdn_ws = [
        u
        for u in links
        if "type=ws" in u
    ]

    cdn_ws_text = (
        "\n".join(cdn_ws)
        + ("\n" if cdn_ws else "")
    )

    (
        args.out / "cdn_ws.txt"
    ).write_text(
        cdn_ws_text,
        encoding="utf-8",
    )

    # ========================================================
    # BASE64
    # ========================================================

    all_b64 = base64.b64encode(
        "\n".join(links).encode("utf-8")
    ).decode("ascii")

    (
        args.out / "all.b64.txt"
    ).write_text(
        all_b64,
        encoding="utf-8",
    )

    # ========================================================
    # STATISTICS
    # ========================================================

    print()
    print(
        f"links total={len(links)}"
    )

    print(
        f"reality={len(reality)}"
    )

    print(
        f"cdn_ws={len(cdn_ws)}"
    )

    # ========================================================
    # GITHUB GIST
    # ========================================================

    print()
    print("=" * 70)
    print("Updating GitHub Gist...")
    print("=" * 70)

    try:

        result = update_gist(
            request_url=url,
            raw_json=raw_json,
            all_text=all_text,
            reality_text=reality_text,
            cdn_ws_text=cdn_ws_text,
            all_b64=all_b64,
        )

        print(
            "Gist updated successfully."
        )

        html_url = result.get(
            "html_url"
        )

        if html_url:

            print(
                "Gist:",
                html_url,
            )

    except Exception as e:

        print(
            "GIST ERROR:",
            e,
            file=sys.stderr,
        )

        # Локальные файлы уже сохранены.
        return 1

    # ========================================================
    # FINAL
    # ========================================================

    print()
    print("=" * 70)
    print("ГОТОВО")
    print("=" * 70)

    print(
        f"primary region: {region}"
    )

    print(
        f"countries: {len(country_results)}"
    )

    print(
        f"servers: {len(servers)}"
    )

    print(
        f"VLESS total: {len(links)}"
    )

    print(
        f"Reality: {len(reality)}"
    )

    print(
        f"CDN WS/TLS: {len(cdn_ws)}"
    )

    print(
        f"Локальные файлы: {args.out}/"
    )

    print()
    print("Файлы Gist:")

    print("  skyvora.txt")
    print("  skyvora_reality.txt")
    print("  skyvora_cdn_ws.txt")
    print("  skyvora_base64.txt")
    print("  skyvora_raw.json")
    print("  skyvora_request_url.txt")

    print()
    print("--- sample ---")

    for u in links[:6]:
        print(u)

    return 0


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
