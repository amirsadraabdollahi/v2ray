#!/usr/bin/env python3
"""
Xray VLESS+Reality server setup.
Run once on the server to generate keys and write config/config.json.
Then start the server with: docker compose up -d
"""
import json
import os
import re
import secrets
import subprocess
import sys

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
XRAY_IMAGE = "ghcr.io/xtls/xray-core:latest"
PORT = 443
# The legitimate TLS site Xray will impersonate for active-probe resistance.
DEST = "www.google.com:443"
SERVER_NAMES = ["www.google.com"]


def run_xray(*args):
    result = subprocess.run(
        ["docker", "run", "--rm", XRAY_IMAGE, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def generate_uuid():
    return run_xray("uuid")


def generate_keypair():
    output = run_xray("x25519")
    private_match = re.search(r"PrivateKey:\s*(\S+)", output)
    public_match = re.search(r"Password \(PublicKey\):\s*(\S+)", output)
    if not private_match or not public_match:
        raise RuntimeError(f"Could not parse x25519 output:\n{output}")
    return private_match.group(1), public_match.group(1)


def get_server_ip():
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", "https://api.ipify.org"],
            capture_output=True,
            text=True,
        )
        ip = result.stdout.strip()
        if ip:
            return ip
    except Exception:
        pass
    return "YOUR_SERVER_IP"


def build_config(uuid, private_key, short_id):
    return {
        "log": {"loglevel": "warning"},
        "policy": {
            "levels": {
                "0": {
                    "uplinkOnly": 0,
                    "downlinkOnly": 0,
                    "connIdle": 300,
                    "handshakeSecs": 8,
                }
            },
            "system": {
                "statsInboundUplink": False,
                "statsInboundDownlink": False,
                "statsOutboundUplink": False,
                "statsOutboundDownlink": False,
            },
        },
        "inbounds": [
            {
                "port": PORT,
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": uuid, "flow": "xtls-rprx-vision"}],
                    "decryption": "none",
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "dest": DEST,
                        "serverNames": SERVER_NAMES,
                        "privateKey": private_key,
                        "shortIds": [short_id],
                    },
                    "sockopt": {
                        "tcpFastOpen": True,
                        "tcpKeepAliveInterval": 60,
                        "tcpKeepAliveIdle": 120,
                    },
                },
                "sniffing": {"enabled": False},
            }
        ],
        "outbounds": [
            {
                "protocol": "freedom",
                "tag": "direct",
                "settings": {"domainStrategy": "UseIPv4"},
                "streamSettings": {
                    "sockopt": {
                        "tcpFastOpen": True,
                        "tcpKeepAliveInterval": 60,
                    }
                },
            }
        ],
    }


def vless_uri(uuid, server_ip, public_key, short_id):
    sni = SERVER_NAMES[0]
    params = (
        f"encryption=none"
        f"&flow=xtls-rprx-vision"
        f"&security=reality"
        f"&sni={sni}"
        f"&fp=chrome"
        f"&pbk={public_key}"
        f"&sid={short_id}"
        f"&type=tcp"
        f"&headerType=none"
    )
    return f"vless://{uuid}@{server_ip}:{PORT}?{params}#MyVPN"


def print_section(title):
    bar = "=" * 60
    print(f"\n{bar}\n{title}\n{bar}")


def main():
    print("Pulling Xray image (first run may take a minute)...")
    subprocess.run(["docker", "pull", XRAY_IMAGE], check=True)

    print("Generating UUID...")
    uuid = generate_uuid()

    print("Generating X25519 keypair...")
    private_key, public_key = generate_keypair()

    short_id = secrets.token_hex(8)

    print("Detecting server IP...")
    server_ip = get_server_ip()

    config = build_config(uuid, private_key, short_id)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Config written to {CONFIG_PATH}")

    uri = vless_uri(uuid, server_ip, public_key, short_id)

    print_section("NEXT STEP")
    print("  docker compose up -d")

    print_section("CLIENT SHARE LINK")
    print("Import this into v2rayN / Nekoray / Shadowrocket / v2rayNG:\n")
    print(uri)

    print_section("CLIENT PARAMETERS (manual entry)")
    print(f"  Address:     {server_ip}")
    print(f"  Port:        {PORT}")
    print(f"  UUID:        {uuid}")
    print(f"  Flow:        xtls-rprx-vision")
    print(f"  Transport:   TCP")
    print(f"  Security:    reality")
    print(f"  SNI:         {SERVER_NAMES[0]}")
    print(f"  Fingerprint: chrome")
    print(f"  Public key:  {public_key}")
    print(f"  Short ID:    {short_id}")
    print()


if __name__ == "__main__":
    main()
