# Xray VLESS+Reality VPN Server

Self-hosted VPN server using [Xray-core](https://github.com/XTLS/Xray-core) with VLESS+Reality — designed for users in countries with heavy internet censorship (Iran, China, Russia). Traffic is indistinguishable from normal HTTPS to a real site.

## Requirements

- A VPS outside the censored country with a public IP
- Ubuntu 20.04+ (or any Linux with kernel 5.4+)
- Docker + Docker Compose plugin
- Python 3.8+
- Port 443 open inbound (TCP) in your provider's firewall/security group

---

## 1. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
newgrp docker
```

---

## 2. Kernel Tuning (run once)

Enables BBR congestion control and tunes TCP buffers for high-throughput VPN traffic.

```bash
# Load BBR and fair-queue modules
sudo modprobe tcp_bbr && sudo modprobe sch_fq

# Persist modules across reboots
printf "tcp_bbr\nsch_fq\n" | sudo tee /etc/modules-load.d/bbr.conf

# Write performance sysctl config
sudo tee /etc/sysctl.d/99-xray-perf.conf <<'EOF'
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.core.rmem_default = 1048576
net.core.wmem_default = 1048576
net.ipv4.tcp_rmem = 8192 1048576 67108864
net.ipv4.tcp_wmem = 8192 1048576 67108864
net.ipv4.tcp_mem = 262144 1048576 786432
net.core.netdev_max_backlog = 16384
net.core.somaxconn = 8192
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535
net.netfilter.nf_conntrack_max = 524288
net.netfilter.nf_conntrack_tcp_timeout_established = 21600
net.netfilter.nf_conntrack_tcp_timeout_time_wait = 30
net.ipv4.tcp_mtu_probing = 1
net.ipv4.tcp_no_metrics_save = 1
EOF

# Apply immediately (no reboot needed)
sudo sysctl -p /etc/sysctl.d/99-xray-perf.conf

# Verify BBR is active
sysctl net.ipv4.tcp_congestion_control
# Expected output: net.ipv4.tcp_congestion_control = bbr
```

---

## 3. Clone and Set Up

```bash
git clone git@github.com:amirsadraabdollahi/v2ray.git ~/v2ray
cd ~/v2ray
```

> **Important:** Before running setup, open `setup.py` and replace the IP address in `get_server_ip()` with your server's actual public IP:
>
> ```python
> def get_server_ip():
>     return "YOUR_SERVER_IP"  # <-- replace this
> ```
>
> You can find your public IP by running: `curl -s https://api.ipify.org`

```bash
python3 setup.py
```

`setup.py` will:
1. Pull the Xray Docker image
2. Generate a UUID and X25519 keypair
3. Write `config/config.json`
4. Print the `vless://` share link and all client parameters

---

## 4. Start the Server

```bash
docker compose up -d
```

Verify it started correctly:

```bash
docker compose ps
docker compose logs
```

The logs should show:

```
xray  | Xray x.x.x started
```

---

## 5. Connect — Client Apps

Import the `vless://` link printed by `setup.py` into any of these apps:

| Platform | App |
|---|---|
| Android | [v2rayNG](https://github.com/2dust/v2rayNG/releases) |
| iOS | Shadowrocket, Streisand |
| Windows | [v2rayN](https://github.com/2dust/v2rayN/releases) (v7+), Nekoray |
| macOS | Nekoray, V2Box |
| Linux | Nekoray |

---

## Maintenance

```bash
# View live logs
docker compose logs -f

# Restart
docker compose restart

# Update Xray to latest version
docker compose pull && docker compose up -d

# Stop
docker compose down
```

---

## Troubleshooting

**Port 443 reachable check** (run from your local machine):
```bash
nc -zv YOUR_SERVER_IP 443
# Expected: Connection succeeded
```

**BBR active on live connections:**
```bash
ss -tin dst :443 | grep ccalgo
# Expected: ccalgo:bbr
```

**Container not starting — check logs:**
```bash
docker compose logs xray
```

**Client times out but port is open:**
- Check your VPS provider's control panel for a network-level firewall (Security Groups, Firewall Rules) and ensure TCP 443 inbound is allowed from `0.0.0.0/0`

---

## Adding More Users

Edit `config/config.json` and add another entry to the `clients` array:

```json
"clients": [
  { "id": "existing-uuid", "flow": "xtls-rprx-vision" },
  { "id": "new-uuid-here", "flow": "xtls-rprx-vision" }
]
```

Generate a new UUID with:
```bash
docker run --rm ghcr.io/xtls/xray-core:latest uuid
```

Then restart:
```bash
docker compose restart
```

Each user gets a unique UUID but shares the same server address, port, and keys. Give them a `vless://` link with their UUID substituted in.
