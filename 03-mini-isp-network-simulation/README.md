# Mini ISP Network Simulation

**MetroLink ISP** — a small regional Internet Service Provider simulation demonstrating core networking fundamentals through documented topology, Cisco IOS configs, and a runnable Python validation layer.

## What This Project Shows

| Area | Demonstration |
|------|---------------|
| **IP subnetting** | /30 WAN links, /27 service VLAN, /24 customer networks |
| **Switching** | VLAN segmentation (infra, services, two customers) |
| **Routing** | Static routes, default gateway, hop-by-hop path validation |
| **DHCP** | Centralized pools with excluded ranges and relay (helper-address) |
| **DNS** | Internal zone `metrolink.local` for ISP services |
| **NAT** | PAT at CPE and core for outbound internet access |
| **Troubleshooting** | Layered diagnostic approach with verification commands |

## Quick Start

### Option A — Run the Python Simulator (no lab hardware)

```powershell
cd D:\08.coding\telecom-portfolio-evan\01-network-fundamentals\01-mini-isp-network-simulation
python simulator/run_simulation.py
```

Trace a specific path:

```powershell
python simulator/run_simulation.py --trace 10.0.0.36 R-ACME
```

### Option B — Build in Cisco Packet Tracer

1. Open Packet Tracer and recreate the topology from [`docs/topology.md`](docs/topology.md).
2. Apply device configs from [`configs/`](configs/) via CLI.
3. Configure DHCP/DNS services on Server-PT devices per [`configs/srv-dhcp-dns.cfg`](configs/srv-dhcp-dns.cfg).
4. Run verification commands from [`verification/validation-commands.txt`](verification/validation-commands.txt).

## Project Structure

```
01-mini-isp-network-simulation/
├── README.md                 ← You are here
├── docs/
│   ├── topology.md           ← Network diagram and design
│   ├── ip-addressing-plan.md ← Subnets, interfaces, DHCP/DNS tables
│   └── troubleshooting-guide.md
├── configs/
│   ├── r-isp-core.cfg        ← Core router (NAT, static routes)
│   ├── sw-dist.cfg           ← L3 switch (VLANs, SVIs, DHCP relay)
│   ├── r-acme-cpe.cfg        ← Customer A edge router
│   ├── r-beta-cpe.cfg        ← Customer B edge router
│   └── srv-dhcp-dns.cfg      ← DHCP pools and DNS zone reference
├── verification/
│   └── validation-commands.txt
└── simulator/
    ├── network_model.py      ← Routing, DHCP, DNS logic
    └── run_simulation.py     ← CLI demo runner
```

## Network at a Glance

```
Internet (203.0.113.0/30)
        │
   R-ISP-CORE (10.0.0.1)
        │
   SW-DIST ──┬── VLAN 20: DHCP / DNS / Portal (10.0.0.32/27)
             ├── VLAN 100: Acme Corp (192.168.100.0/24)
             └── VLAN 101: Beta LLC (192.168.101.0/24)
```

Two business customers connect through CPE routers. The ISP provides IP connectivity, centralized DHCP/DNS, and a customer portal at `portal.metrolink.local`.

## Verification Checklist

- [ ] Customer PC receives DHCP address in `.50–.200` range
- [ ] Gateway and DNS server reachable from each customer LAN
- [ ] `portal.metrolink.local` resolves to `10.0.0.36`
- [ ] Upstream peer `203.0.113.2` reachable (simulated internet)
- [ ] Python simulator reports 7/7 connectivity tests passing

## Skills Demonstrated

- IP subnetting and address planning
- Router-to-switch hierarchical design
- VLAN configuration and inter-VLAN routing
- DHCP and DNS service integration
- Static routing and NAT/PAT concepts
- Systematic connectivity troubleshooting

## Requirements

- **Packet Tracer:** Cisco Packet Tracer 8.x (optional, for hands-on lab)
- **Simulator:** Python 3.9+ (stdlib only, no pip install needed)
