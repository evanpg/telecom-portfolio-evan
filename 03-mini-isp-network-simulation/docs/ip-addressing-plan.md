# IP Addressing Plan — MetroLink ISP

## Address Space Summary

| Network | CIDR | Usable Hosts | Assignment |
|---------|------|--------------|------------|
| Upstream link | 203.0.113.0/30 | 2 | ISP ↔ peer router |
| ISP backbone | 10.0.0.0/24 | 254 | Core, switch SVIs, gateways |
| Infrastructure | 10.0.0.0/28 | 14 | VLAN 10 management |
| Services | 10.0.0.32/27 | 30 | VLAN 20 DHCP/DNS/portal |
| Customer A | 192.168.100.0/24 | 254 | VLAN 100 Acme Corp |
| Customer B | 192.168.101.0/24 | 254 | VLAN 101 Beta LLC |

## Interface Assignments

### R-ISP-CORE (Core Router)

| Interface | IP Address | Description |
|-----------|------------|-------------|
| GigabitEthernet0/0 | 203.0.113.1/30 | Upstream to peer |
| GigabitEthernet0/1 | 10.0.0.1/24 | ISP backbone |
| Loopback0 | 10.255.0.1/32 | Router ID / management |

### SW-DIST (Distribution Switch — L3 SVIs)

| VLAN | SVI IP | Description |
|------|--------|-------------|
| 10 | 10.0.0.2/28 | Infrastructure |
| 20 | 10.0.0.33/27 | Services gateway |
| 100 | 192.168.100.254/24 | Customer A gateway (ISP side) |
| 101 | 192.168.101.254/24 | Customer B gateway (ISP side) |

### R-ACME (Customer A CPE)

| Interface | IP Address | Description |
|-----------|------------|-------------|
| GigabitEthernet0/0 | 192.168.100.1/24 | LAN — Acme workstations |
| GigabitEthernet0/1 | 192.168.100.253/24 | WAN — toward ISP (static) |

### R-BETA (Customer B CPE)

| Interface | IP Address | Description |
|-----------|------------|-------------|
| GigabitEthernet0/0 | 192.168.101.1/24 | LAN — Beta workstations |
| GigabitEthernet0/1 | 192.168.101.253/24 | WAN — toward ISP (static) |

## Services (VLAN 20)

| Host | IP | Service |
|------|-----|---------|
| SRV-DHCP | 10.0.0.34/27 | DHCP pools for customers |
| SRV-DNS | 10.0.0.35/27 | Internal zone `metrolink.local` |
| SRV-PORTAL | 10.0.0.36/27 | HTTP customer portal |

## DHCP Pools

| Pool Name | Network | Gateway | DNS | Lease Range |
|-----------|---------|---------|-----|-------------|
| ACME-LAN | 192.168.100.0/24 | 192.168.100.1 | 10.0.0.35 | .50 – .200 |
| BETA-LAN | 192.168.101.0/24 | 192.168.101.1 | 10.0.0.35 | .50 – .200 |

Excluded addresses: network, broadcast, gateway (.1), ISP-side (.253–.254), static servers (.10).

## DNS Records (metrolink.local zone)

| Record | Type | Value |
|--------|------|-------|
| portal | A | 10.0.0.36 |
| dns | A | 10.0.0.35 |
| dhcp | A | 10.0.0.34 |
| acme-gw | A | 192.168.100.1 |
| beta-gw | A | 192.168.101.1 |

## Routing Table (R-ISP-CORE)

| Destination | Next Hop | Type |
|-------------|----------|------|
| 203.0.113.0/30 | Connected (Gi0/0) | Direct |
| 10.0.0.0/24 | Connected (Gi0/1) | Direct |
| 10.255.0.1/32 | Connected (Lo0) | Direct |
| 192.168.100.0/24 | 10.0.0.2 (SW-DIST) | Static |
| 192.168.101.0/24 | 10.0.0.2 (SW-DIST) | Static |
| 0.0.0.0/0 | 203.0.113.2 | Default static |

## Subnetting Walkthrough

**VLAN 20 Services — 10.0.0.32/27**

```
Network:   10.0.0.32
Mask:      255.255.255.224 (/27)
Block size: 32 addresses

Range:     10.0.0.32 – 10.0.0.63
Usable:    10.0.0.33 – 10.0.0.62
Broadcast: 10.0.0.63
```

This /27 carves 30 usable hosts from the /24 backbone block without overlapping VLAN 10 (/28 uses 10.0.0.0–10.0.0.15).

**Upstream /30 — 203.0.113.0/30**

```
Network:   203.0.113.0
Usable:    203.0.113.1 (ISP), 203.0.113.2 (peer)
Broadcast: 203.0.113.3
```

Classic point-to-point WAN — only two host addresses, no waste.
