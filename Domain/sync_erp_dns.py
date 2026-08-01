#!/usr/bin/env python3
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = "https://api.cloudflare.com/client/v4"
CONFIG_PATH = Path(__file__).with_name("cloudflare_API.md")
PUBLIC_IP_URLS = [
    url.strip()
    for url in os.getenv(
        "PUBLIC_IP_URLS",
        "https://api64.ipify.org,https://ifconfig.me/ip,https://icanhazip.com,https://checkip.amazonaws.com,https://1.1.1.1/cdn-cgi/trace",
    ).split(",")
    if url.strip()
]
DEFAULT_TTL = int(os.getenv("CF_DNS_TTL", "120"))


def read_config(path):
    config = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*([A-Za-z_]+)\s*=\s*(.+?)\s*$", line)
        if match:
            config[match.group(1).lower()] = match.group(2).strip()
    return config


def api_request(token, method, path, payload=None, query=None):
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Cloudflare API {method} {path} failed: {error.code} {body}") from error

    result = json.loads(body)
    if not result.get("success"):
        raise RuntimeError(f"Cloudflare API {method} {path} failed: {result}")
    return result


def parse_public_ip(text):
    text = text.strip()
    if "\n" in text and "ip=" in text:
        for line in text.splitlines():
            if line.startswith("ip="):
                text = line.split("=", 1)[1].strip()
                break
    ipaddress.IPv4Address(text)
    return text


def get_public_ipv4():
    errors = []
    for url in PUBLIC_IP_URLS:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                ip_text = response.read().decode("utf-8").strip()
            ip_address = parse_public_ip(ip_text)
            print(f"public IPv4 {ip_address} from {url}")
            return ip_address
        except Exception as error:
            errors.append(f"{url}: {error}")

    raise RuntimeError("Could not detect public IPv4. Tried: " + "; ".join(errors))


def list_dns_records(token, zone_id):
    records = []
    page = 1
    while True:
        result = api_request(
            token,
            "GET",
            f"/zones/{zone_id}/dns_records",
            query={"per_page": 100, "page": page},
        )
        records.extend(result.get("result", []))
        info = result.get("result_info", {})
        if page >= int(info.get("total_pages") or 1):
            return records
        page += 1


def upsert_erp_record(token, zone_id, record_name, ip_address, records):
    target_records = [
        record
        for record in records
        if record.get("type") == "A" and record.get("name") == record_name
    ]

    payload = {
        "type": "A",
        "name": record_name,
        "content": ip_address,
        "ttl": DEFAULT_TTL,
        "proxied": False,
    }

    if not target_records:
        api_request(token, "POST", f"/zones/{zone_id}/dns_records", payload)
        print(f"created A {record_name} -> {ip_address} proxied=false")
        return

    current = target_records[0]
    if (
        current.get("content") != ip_address
        or current.get("proxied") is not False
        or int(current.get("ttl") or DEFAULT_TTL) != DEFAULT_TTL
    ):
        api_request(token, "PUT", f"/zones/{zone_id}/dns_records/{current['id']}", payload)
        print(f"updated A {record_name} -> {ip_address} proxied=false")
    else:
        print(f"ok A {record_name} -> {ip_address} proxied=false")


def main():
    config = read_config(CONFIG_PATH)
    zone_id = os.getenv("CF_ZONE_ID") or config.get("zone_id")
    token = os.getenv("CF_API_TOKEN") or config.get("token")
    domain = os.getenv("CF_DOMAIN") or config.get("domain") or "sengchong.com"
    record_name = os.getenv("CF_RECORD_NAME") or f"erp.{domain}"

    if not zone_id or not token:
        print("Missing Cloudflare zone id or API token.", file=sys.stderr)
        return 1

    ip_address = get_public_ipv4()
    records = list_dns_records(token, zone_id)
    upsert_erp_record(token, zone_id, record_name, ip_address, records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
