# IP Addressing Plan

## Sales VLAN — 192.168.1.0/24

| Host | IP | Notes |
|------|-----|-------|
| R-GW (LAN) | 192.168.1.1 | Default gateway |
| PC-USER | 192.168.1.10 | Static or DHCP |
| SRV-DNS | 192.168.1.35 | DNS resolver |
| PC-CONFLICT (scenario 3) | 192.168.1.10 | Duplicate — intentional break |

**Usable range:** 192.168.1.1 – 192.168.1.254  
**Mask:** 255.255.255.0 (/24)

## Engineering VLAN — 192.168.2.0/24

| Host | IP | Notes |
|------|-----|-------|
| R-ENG (LAN) | 192.168.2.1 | Engineering gateway |
| SRV-APP | 192.168.2.10 | `app.internal` target |

## Router Interconnects

| Interface | IP | Device |
|-----------|-----|--------|
| R-GW Gi0/1 | 10.0.0.1/30 | Toward core |
| R-CORE Gi0/0 | 10.0.0.2/30 | Toward R-GW |
| R-CORE Gi0/1 | 10.0.0.5/30 | Toward R-ENG |
| R-ENG Gi0/0 | 10.0.0.6/30 | Toward core |

## DNS Zone (internal)

| Record | Type | Value |
|--------|------|-------|
| app.internal | A | 192.168.2.10 |
| dns.internal | A | 192.168.1.35 |

## PC-USER Correct Settings

```
IP Address:     192.168.1.10
Subnet Mask:    255.255.255.0
Default Gateway: 192.168.1.1
DNS Server:     192.168.1.35
```

## Required Routes (R-CORE)

```
192.168.1.0/24 → 10.0.0.1  (R-GW)
192.168.2.0/24 → 10.0.0.6  (R-ENG)
```

## Required Routes (R-GW)

```
192.168.2.0/24 → 10.0.0.2  (R-CORE)
0.0.0.0/0      → 10.0.0.2  (default via core)
```

## Required Routes (R-ENG)

```
192.168.1.0/24 → 10.0.0.5  (R-CORE)
```
