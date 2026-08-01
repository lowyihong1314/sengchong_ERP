import ipaddress
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


GUARD_DIR = Path("/mnt/c/ProgramData/WSLGuard")
CONFIG_PATH = GUARD_DIR / "rdp-allow-ips.json"
LAUNCHER_LOG_PATH = GUARD_DIR / "wsl-guard-launcher.log"
SCHTASKS_EXE = "/mnt/c/Windows/System32/schtasks.exe"
POWERSHELL_EXE = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
WATCHDOG_TASK_NAME = "WSL Guard Watchdog"
DEFAULT_LAN_CIDRS = ("192.168.0.0/16",)
DEFAULT_EXTERNAL_IPS = ("180.74.224.155",)


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _validate_external_ip(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("IP address is required.")
    if "/" in text:
        raise ValueError("Use a single public IPv4 address, not a CIDR range.")
    ip = ipaddress.ip_address(text)
    if ip.version != 4:
        raise ValueError("Only IPv4 addresses are supported for RDP allow-list entries.")
    return str(ip)


def _validate_lan_cidr(value):
    text = str(value or "").strip()
    network = ipaddress.ip_network(text, strict=False)
    if network.version != 4:
        raise ValueError("Only IPv4 CIDR ranges are supported.")
    return str(network)


def _dedupe(values):
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _default_config():
    return {
        "lanCidrs": list(DEFAULT_LAN_CIDRS),
        "externalIps": list(DEFAULT_EXTERNAL_IPS),
        "updatedAt": _utc_now(),
    }


def _read_json_file():
    if not CONFIG_PATH.exists():
        return _default_config()

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
    except (json.JSONDecodeError, OSError):
        return _default_config()

    if not isinstance(data, dict):
        return _default_config()
    return data


def read_config():
    data = _read_json_file()
    lan_cidrs = []
    external_ips = []

    for cidr in data.get("lanCidrs", DEFAULT_LAN_CIDRS):
        try:
            lan_cidrs.append(_validate_lan_cidr(cidr))
        except ValueError:
            continue

    for ip in data.get("externalIps", DEFAULT_EXTERNAL_IPS):
        try:
            external_ips.append(_validate_external_ip(ip))
        except ValueError:
            continue

    if not lan_cidrs:
        lan_cidrs = list(DEFAULT_LAN_CIDRS)

    if not external_ips:
        external_ips = list(DEFAULT_EXTERNAL_IPS)

    return {
        "lanCidrs": _dedupe(lan_cidrs),
        "externalIps": _dedupe(external_ips),
        "updatedAt": data.get("updatedAt") or "",
        "configPath": str(CONFIG_PATH),
    }


def write_config(*, external_ips, lan_cidrs=None):
    normalized_external_ips = _dedupe(_validate_external_ip(ip) for ip in external_ips)
    if not normalized_external_ips:
        raise ValueError("At least one public IPv4 address is required.")

    normalized_lan_cidrs = _dedupe(
        _validate_lan_cidr(cidr) for cidr in (lan_cidrs or DEFAULT_LAN_CIDRS)
    )

    GUARD_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "lanCidrs": normalized_lan_cidrs,
        "externalIps": normalized_external_ips,
        "updatedAt": _utc_now(),
    }
    tmp_path = CONFIG_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as config_file:
        json.dump(data, config_file, indent=2)
        config_file.write("\n")
    tmp_path.replace(CONFIG_PATH)
    return read_config()


def add_external_ip(ip):
    config = read_config()
    next_ips = _dedupe([*config["externalIps"], _validate_external_ip(ip)])
    return write_config(external_ips=next_ips, lan_cidrs=config["lanCidrs"])


def remove_external_ip(ip):
    target = _validate_external_ip(ip)
    config = read_config()
    next_ips = [existing for existing in config["externalIps"] if existing != target]
    return write_config(external_ips=next_ips, lan_cidrs=config["lanCidrs"])


def effective_remote_ips(config=None):
    source = config or read_config()
    return [*source["lanCidrs"], *source["externalIps"]]


def _run(command, timeout=8):
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    return {
        "ok": completed.returncode == 0,
        "returnCode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def trigger_apply():
    if not Path(SCHTASKS_EXE).exists():
        return {
            "ok": False,
            "returnCode": -1,
            "stdout": "",
            "stderr": "schtasks.exe was not found.",
        }
    return _run([SCHTASKS_EXE, "/Run", "/TN", WATCHDOG_TASK_NAME], timeout=12)


def current_rdp_remote_ip():
    if not Path(POWERSHELL_EXE).exists():
        return ""

    command = [
        POWERSHELL_EXE,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "Get-NetTCPConnection -LocalPort 3389 -State Established "
            "| Select-Object -First 1 -ExpandProperty RemoteAddress"
        ),
    ]
    result = _run(command, timeout=8)
    if not result["ok"]:
        return ""
    try:
        return _validate_external_ip(result["stdout"].splitlines()[0])
    except (IndexError, ValueError):
        return ""


def recent_launcher_log(lines=18):
    if not LAUNCHER_LOG_PATH.exists():
        return []

    try:
        with LAUNCHER_LOG_PATH.open("r", encoding="utf-8", errors="replace") as log_file:
            return [
                line.replace("\x00", "").rstrip("\n")
                for line in log_file.readlines()[-lines:]
                if line.replace("\x00", "").strip()
            ]
    except OSError:
        return []


def status_payload():
    config = read_config()
    return {
        **config,
        "effectiveRemoteIps": effective_remote_ips(config),
        "currentRdpRemoteIp": current_rdp_remote_ip(),
        "watchdogTaskName": WATCHDOG_TASK_NAME,
        "recentLog": recent_launcher_log(),
    }
