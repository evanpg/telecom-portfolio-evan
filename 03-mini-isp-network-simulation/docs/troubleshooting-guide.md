# Troubleshooting Guide

Systematic approach for validating and fixing connectivity in the MetroLink ISP simulation.

## Layer 1 — Physical

| Symptom | Check | Fix |
|---------|-------|-----|
| Interface down | `show ip interface brief` | Verify cable, `no shutdown` |
| Wrong speed/duplex | `show interfaces` | Match both ends (auto or forced) |
| No link on trunk | LED / `show interfaces trunk` | Use crossover or auto-MDIX ports |

## Layer 2 — Switching

| Symptom | Check | Fix |
|---------|-------|-----|
| PC in wrong VLAN | `show vlan brief`, `show mac address-table` | Move port to correct access VLAN |
| Trunk not carrying VLANs | `show interfaces trunk` | Add VLAN to `switchport trunk allowed` |
| Native VLAN mismatch | Both ends of trunk | Align `switchport trunk native vlan` |

## Layer 3 — IP & Routing

| Symptom | Check | Fix |
|---------|-------|-----|
| Cannot ping gateway | `show ip route`, verify IP/mask on interface | Correct IP, enable routing |
| Remote subnet unreachable | `show ip route` on each hop | Add missing static route |
| Asymmetric routing | Trace path both directions | Ensure return route exists |

### Diagnostic Commands

```text
! On any router
show ip interface brief
show ip route
show running-config | section ip route
ping <destination>
traceroute <destination>

! On switch
show ip route
show vlan brief
show interfaces status
```

## DHCP Issues

| Symptom | Check | Fix |
|---------|-------|-----|
| APIPA address (169.254.x.x) | DHCP server reachability, pool config | Verify pool, relay, or L3 path to 10.0.0.34 |
| Wrong gateway/DNS | `ipconfig /all` or `show ip dhcp binding` | Update pool options |
| Pool exhausted | `show ip dhcp pool` | Expand range or shorten lease |

**Relay scenario:** If DHCP server is on VLAN 20 and clients on VLAN 100, configure `ip helper-address 10.0.0.34` on the VLAN 100 SVI.

## DNS Issues

| Symptom | Check | Fix |
|---------|-------|-----|
| Name does not resolve | `nslookup portal.metrolink.local 10.0.0.35` | Add A record on SRV-DNS |
| Resolves but no connectivity | Ping resolved IP | Fix routing/firewall, not DNS |
| Wrong IP returned | DNS zone file / server config | Correct A record |

## NAT / Internet Access

| Symptom | Check | Fix |
|---------|-------|-----|
| Internal OK, no internet | `show ip nat translations` on core | Verify NAT overload (PAT) config |
| NAT pool empty | ACL matching inside traffic | Fix `access-list` source networks |
| Upstream unreachable | Ping 203.0.113.2 from core | Check default route, upstream interface |

## Common Misconfigurations

1. **Missing default route on CPE** — customer LAN cannot reach beyond ISP.
2. **Subnet mask mismatch** — /24 LAN with /27 gateway breaks ARP.
3. **ACL blocking ICMP** — ping fails but application traffic works; document intentional blocks.
4. **Duplicate IP** — intermittent connectivity; check `show arp` for conflicts.

## Escalation Checklist

Work top-down (OSI):

1. Link up? (`show ip interface brief`)
2. IP correct? (compare to addressing plan)
3. Local gateway reachable? (`ping` gateway)
4. Remote subnet reachable? (`ping` across VLAN)
5. DNS working? (`nslookup`)
6. Internet working? (`ping 203.0.113.2`, then `8.8.8.8`)

## Python Simulator Debugging

Run the included simulator for a logic-level sanity check:

```powershell
cd D:\08.coding\telecom-portfolio-evan\01-network-fundamentals\01-mini-isp-network-simulation
python simulator/run_simulation.py
```

If Packet Tracer fails but the simulator passes, the issue is likely device config or cabling — not the design.
