# Network Troubleshooting Lab

**Broken Network Fix Simulation** — intentionally broken network scenarios that demonstrate systematic troubleshooting from symptom to verified fix.

This project simulates common network failures and documents the full troubleshooting workflow: **Problem → Diagnosis → Fix → Verification**.

## Issues Resolved

- Incorrect default gateway configuration
- DNS resolution failure (client and server)
- IP address conflict on a shared LAN
- Missing static route on a core router

## Tools Used

- **Packet Tracer** — hands-on topology with broken/fixed configs
- **CLI diagnostics** — `ping`, `tracert` / `traceroute`, `ipconfig`, `nslookup`, `arp`
- **Python simulator** — interactive lab without hardware

## Quick Start

### Option A — Python Simulator

```powershell
cd D:\08.coding\telecom-portfolio-evan\01-network-fundamentals\03-broken-network-simulation
python simulator/run_lab.py
```

```
lab> scenarios
lab> load wrong-gateway
lab> ipconfig
lab> ping 192.168.2.10
lab> set gateway 192.168.1.1
lab> verify

lab> load dns-misconfig
lab> nslookup app.internal
lab> set dns 192.168.1.35
lab> set dns-record app.internal 192.168.2.10
lab> verify

lab> load missing-route
lab> tracert 192.168.2.10
lab> show ip route
lab> ip route 192.168.2.0 255.255.255.0 10.0.0.6
lab> verify
```

### Option B — Packet Tracer Lab

1. Build topology from [`docs/topology.md`](docs/topology.md)
2. Apply baseline configs from [`configs/baseline/`](configs/baseline/)
3. Confirm connectivity with [`verification/diagnostic-commands.txt`](verification/diagnostic-commands.txt)
4. Swap in a broken config from [`configs/broken/`](configs/broken/)
5. Follow the matching guide in [`scenarios/`](scenarios/)

## Scenarios

| ID | Issue | Symptom |
|----|-------|---------|
| `wrong-gateway` | Bad default gateway on PC | Off-subnet traffic fails |
| `dns-misconfig` | Wrong DNS server / bad A record | IP works; hostname fails |
| `ip-conflict` | Duplicate 192.168.1.10 | Intermittent connectivity |
| `missing-route` | No route to 192.168.2.0/24 | Traceroute stops at R-CORE |

Each scenario document includes:

- **Problem** — user-visible symptoms
- **Diagnosis** — commands and expected output
- **Fix** — configuration change
- **Verification** — ping / traceroute / nslookup proof

## Network at a Glance

```
PC-USER (192.168.1.10)
    |
 R-GW (192.168.1.1)
    |
 R-CORE (10.0.0.2)
    |
 R-ENG (192.168.2.1)
    |
 SRV-APP (192.168.2.10)    SRV-DNS (192.168.1.35)
```

## Project Structure

```
03-broken-network-simulation/
├── README.md
├── docs/
│   ├── topology.md
│   └── ip-addressing-plan.md
├── scenarios/
│   ├── 01-wrong-gateway.md
│   ├── 02-dns-misconfiguration.md
│   ├── 03-ip-conflict.md
│   └── 04-missing-route.md
├── configs/
│   ├── baseline/          Working configs
│   └── broken/            Intentional misconfigs
├── verification/
│   └── diagnostic-commands.txt
└── simulator/
    ├── network_state.py
    └── run_lab.py
```

## Troubleshooting Method

Work in OSI order:

1. **Local** — `ipconfig`, ping gateway
2. **Same subnet** — ping DNS / local servers
3. **Remote** — ping app server by IP
4. **Name resolution** — `nslookup` before blaming routing
5. **Path** — `tracert` to find where packets stop
6. **Router** — `show ip route` on the last responding hop

## Skills Demonstrated

- Systematic fault isolation (layer-by-layer)
- Default gateway and subnet mask troubleshooting
- DNS client vs. server diagnosis
- Duplicate IP / ARP conflict detection
- Static routing and traceroute analysis
- Documented verification with CLI tools

## Requirements

- Python 3.9+ (stdlib only)
- Cisco Packet Tracer 8.x (optional)
