#!/usr/bin/env python3

"""
Skyvora:
- скачать 13 уникальных geo-профилей через CF-IPCountry
- проверить region
- сгенерировать VLESS Reality для всех endpoints × ports
- сохранить результаты
- обновить GitHub Gist
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urlencode


# ============================================================
# НАСТРОЙКИ
# ============================================================

URL = "https://d.irhgiuj.live/sub/2a2fd40b4f429240933c078a43862344"

GIST_TOKEN = os.environ["GIST_TOKEN"]
GIST_ID = os.environ["GIST_ID"]

# Все 13 уникальных auto_order-профилей
PROFILES = {
    "EU_DE": "DE",
    "EU_FR": "ZA",
    "AMERICAS": "US",
    "EAST_ASIA": "JP",
    "MENA": "TR",
    "SOUTH_ASIA": "IN",
    "OCEANIA": "AU",
    "IR_TM": "TM",
    "AF_SPECIAL": "AF",
    "BY_EMPTY": "BY",
    "CN_SPECIAL": "CN",
    "RU": "RU",
    "UA": "UA",
}

OUT_DIR = "skyvora_out"


# ============================================================
# СКАЧИВАНИЕ ПРОФИЛЯ
# ============================================================

def fetch(country: str) -> dict:

    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Skyvora/1.0 (Android)",
            "Accept": "application/json",
            "CF-IPCountry": country,
        },
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(
            r.read().decode("utf-8")
        )


# ============================================================
# ГЕНЕРАЦИЯ VLESS REALITY
# ============================================================

def servers_to_vless(
    data: dict,
    profile_name: str,
) -> list[str]:

    links: list[str] = []

    for s in data.get("servers") or []:

        sid = s.get("id", "?")

        uuid = s.get("uuid")
        if not uuid:
            print(f"  skip {sid}: no uuid")
            continue

        sni = s.get("sni") or ""
        flow = s.get("flow") or ""

        pbk = s.get("public_key") or ""
        fp = s.get("fingerprint") or "chrome"
        short_id = s.get("short_id") or ""

        endpoints = s.get("endpoints") or []

        # ----------------------------------------------------
        # PORTS
        # ----------------------------------------------------

        ports = s.get("ports")

        if not ports:

            if s.get("port"):
                ports = [s["port"]]

            else:
                print(
                    f"  skip {sid}: no port/ports"
                )
                continue

        # ----------------------------------------------------
        # RELAY / DIRECT
        # ----------------------------------------------------

        if s.get("relayed"):
            route_type = "relay"
        else:
            route_type = "direct"

        hop = s.get("hop") or ""

        # ----------------------------------------------------
        # ENDPOINTS × PORTS
        # ----------------------------------------------------

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

                # ------------------------------------------------
                # REMARK
                # ------------------------------------------------

                parts = [
                    "Skyvora",
                    profile_name,
                    sid,
                    str(ip),
                    str(port),
                    route_type,
                ]

                if hop:
                    parts.append(str(hop))

                remark = "-".join(parts)

                # ------------------------------------------------
                # VLESS
                # ------------------------------------------------

                link = (
                    f"vless://{uuid}@{ip}:{port}"
                    f"?{urlencode(params)}"
                    f"#{quote(remark)}"
                )

                links.append(link)

    return links


# ============================================================
# GIST UPDATE
# ============================================================

def update_gist(
    text: str,
    encoded: str,
    combined_json: dict,
    summary: str,
    profile_files: dict[str, str],
) -> dict:

    files = {
        "skyvora.txt": {
            "content": text
        },

        "skyvora_base64.txt": {
            "content": encoded
        },

        "skyvora.json": {
            "content": json.dumps(
                combined_json,
                ensure_ascii=False,
                indent=2,
            )
        },

        "skyvora_summary.txt": {
            "content": summary
        },
    }

    # --------------------------------------------------------
    # Добавляем отдельные профили
    # --------------------------------------------------------

    for filename, content in profile_files.items():

        files[filename] = {
            "content": content
        }

    payload = json.dumps({
        "files": files
    }).encode("utf-8")

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
# MAIN
# ============================================================

def main() -> None:

    os.makedirs(
        OUT_DIR,
        exist_ok=True,
    )

    results: dict[str, dict] = {}

    errors: list[tuple[str, str]] = []

    # ========================================================
    # DOWNLOAD 13 PROFILES
    # ========================================================

    print("=" * 70)
    print("Skyvora — 13 geo profiles")
    print("=" * 70)

    def job(
        name: str,
        country: str,
    ):
        data = fetch(country)
        return name, country, data

    with ThreadPoolExecutor(
        max_workers=8
    ) as executor:

        futures = [
            executor.submit(
                job,
                name,
                country,
            )
            for name, country in PROFILES.items()
        ]

        for future in as_completed(futures):

            try:

                name, country, data = (
                    future.result()
                )

                results[name] = {
                    "cc": country,
                    "data": data,
                }

            except Exception as e:

                errors.append(
                    (
                        str(e),
                        "",
                    )
                )

    # ========================================================
    # PROCESS
    # ========================================================

    all_links: list[str] = []

    summary_rows: list[str] = []

    combined_profiles: dict = {}

    seen_orders: set[tuple] = set()

    # ========================================================
    # СТАБИЛЬНЫЙ ПОРЯДОК
    # ========================================================

    for name, country in PROFILES.items():

        if name not in results:

            print(
                f"[FAIL] {name} ({country})"
            )

            continue

        data = results[name]["data"]

        region = data.get("region")

        recommended = data.get(
            "recommended"
        )

        config = data.get("config") or {}

        order = list(
            config.get("auto_order") or []
        )

        servers = data.get(
            "servers"
        ) or []

        # ----------------------------------------------------
        # AUTO ORDER
        # ----------------------------------------------------

        seen_orders.add(
            tuple(order)
        )

        # ----------------------------------------------------
        # REGION CHECK
        # ----------------------------------------------------

        if region != country:

            raise RuntimeError(
                f"{name}: API returned "
                f"region={region}, "
                f"expected={country}. "
                f"Gist НЕ будет обновлён."
            )

        # ----------------------------------------------------
        # VLESS
        # ----------------------------------------------------

        links = servers_to_vless(
            data,
            name,
        )

        all_links.extend(
            links
        )

        # ----------------------------------------------------
        # Сохраняем JSON профиля
        # ----------------------------------------------------

        base = os.path.join(
            OUT_DIR,
            f"{name}_{country}",
        )

        with open(
            base + ".json",
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2,
            )

        # ----------------------------------------------------
        # TXT
        # ----------------------------------------------------

        profile_text = (
            "\n".join(links)
            + ("\n" if links else "")
        )

        with open(
            base + ".txt",
            "w",
            encoding="utf-8",
        ) as f:

            f.write(profile_text)

        # ----------------------------------------------------
        # BASE64
        # ----------------------------------------------------

        profile_b64 = base64.b64encode(
            "\n".join(links).encode("utf-8")
        ).decode("ascii")

        with open(
            base + ".b64.txt",
            "w",
            encoding="utf-8",
        ) as f:

            f.write(profile_b64)

        # ----------------------------------------------------
        # COMBINED JSON
        # ----------------------------------------------------

        combined_profiles[name] = {
            "country": country,
            "region": region,
            "recommended": recommended,
            "auto_order": order,
            "servers": servers,
            "vless_count": len(links),
        }

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        relay = sum(
            1
            for s in servers
            if s.get("relayed")
        )

        direct = (
            len(servers)
            - relay
        )

        row = (
            f"{name:12} "
            f"cc={country:2} "
            f"region={str(region):3} "
            f"rec={str(recommended):5} "
            f"servers={len(servers):2} "
            f"vless={len(links):4} "
            f"direct={direct:2} "
            f"relay={relay:2} "
            f"order={order}"
        )

        print(row)

        summary_rows.append(row)

    # ========================================================
    # УНИКАЛЬНЫЕ VLESS
    # ========================================================

    unique_links = list(
        dict.fromkeys(all_links)
    )

    # ========================================================
    # ОБЩИЙ TXT
    # ========================================================

    all_text = (
        "\n".join(unique_links)
        + ("\n" if unique_links else "")
    )

    with open(
        os.path.join(
            OUT_DIR,
            "all.txt",
        ),
        "w",
        encoding="utf-8",
    ) as f:

        f.write(all_text)

    # ========================================================
    # ОБЩИЙ BASE64
    # ========================================================

    all_b64 = base64.b64encode(
        "\n".join(unique_links).encode(
            "utf-8"
        )
    ).decode("ascii")

    with open(
        os.path.join(
            OUT_DIR,
            "all.b64.txt",
        ),
        "w",
        encoding="utf-8",
    ) as f:

        f.write(all_b64)

    # ========================================================
    # COMBINED JSON
    # ========================================================

    combined_json = {
        "source": URL,
        "profiles": combined_profiles,
        "unique_auto_order_patterns": len(
            seen_orders
        ),
        "total_vless": len(all_links),
        "unique_vless": len(unique_links),
    }

    with open(
        os.path.join(
            OUT_DIR,
            "all.json",
        ),
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            combined_json,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    summary_lines = list(
        summary_rows
    )

    summary_lines.append("")
    summary_lines.append(
        f"unique auto_order patterns: "
        f"{len(seen_orders)}"
    )

    summary_lines.append(
        f"total vless "
        f"(with duplicates across profiles): "
        f"{len(all_links)}"
    )

    summary_lines.append(
        f"unique vless: "
        f"{len(unique_links)}"
    )

    summary = (
        "\n".join(summary_lines)
        + "\n"
    )

    with open(
        os.path.join(
            OUT_DIR,
            "summary.txt",
        ),
        "w",
        encoding="utf-8",
    ) as f:

        f.write(summary)

    # ========================================================
    # GIST FILES
    # ========================================================

    profile_files: dict[str, str] = {}

    for name, country in PROFILES.items():

        if name not in results:
            continue

        base = os.path.join(
            OUT_DIR,
            f"{name}_{country}",
        )

        # TXT
        with open(
            base + ".txt",
            "r",
            encoding="utf-8",
        ) as f:

            profile_files[
                f"skyvora_{name.lower()}.txt"
            ] = f.read()

        # BASE64
        with open(
            base + ".b64.txt",
            "r",
            encoding="utf-8",
        ) as f:

            profile_files[
                f"skyvora_{name.lower()}_base64.txt"
            ] = f.read()

    # ========================================================
    # GIST UPDATE
    # ========================================================

    print()
    print("=" * 70)
    print("Updating GitHub Gist...")
    print("=" * 70)

    result = update_gist(
        all_text,
        all_b64,
        combined_json,
        summary,
        profile_files,
    )

    # ========================================================
    # FINAL
    # ========================================================

    print()
    print("=" * 70)
    print("ГОТОВО")
    print("=" * 70)

    print(
        f"Профилей обработано: "
        f"{len(results)}/{len(PROFILES)}"
    )

    print(
        f"Уникальных auto_order: "
        f"{len(seen_orders)}"
    )

    print(
        f"Всего VLESS: "
        f"{len(all_links)}"
    )

    print(
        f"Уникальных VLESS: "
        f"{len(unique_links)}"
    )

    print(
        "Gist:",
        result.get("html_url"),
    )

    print(
        f"Локальные файлы: "
        f"{OUT_DIR}/"
    )

    if errors:

        print()
        print("Ошибки:")

        for error, _ in errors:
            print(
                " -",
                error,
            )


if __name__ == "__main__":
    main()
