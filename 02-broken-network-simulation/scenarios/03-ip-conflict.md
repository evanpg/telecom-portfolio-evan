# Scenario 3 — IP Address Conflict

## Problem

PC-USER experiences intermittent connectivity — ping succeeds then fails, ARP entries flip between MAC addresses, and the switch may log duplicate address warnings. Both local and remote access are unreliable.

**Broken configuration:** A second device (PC-CONFLICT or misconfigured laptop) also uses `192.168.1.10` on the Sales VLAN.

## Diagnosis

Symptoms suggest Layer 2/Layer 3 duplicate addressing:

```text
ping 192.168.1.1          → Intermittent success/failure
ping 192.168.1.35         → Intermittent
arp -a
```

Look for the same IP mapped to different MAC addresses over time:

```
192.168.1.10    aa-bb-cc-dd-ee-01   dynamic
192.168.1.10    aa-bb-cc-dd-ee-99   dynamic   ← conflict
```

On the switch:

```text
show mac address-table
show arp
```

Two MAC addresses on the same VLAN claiming traffic for `.10` indicates duplicate IP.

Check all devices on VLAN:

```text
! On each PC
ipconfig
```

**Root cause:** Two hosts configured with identical IP `192.168.1.10/24` — gratuitous ARP causes unstable reachability.

## Fix

1. Identify both devices using `192.168.1.10` (`ipconfig` on each PC)
2. On **PC-CONFLICT**, switch from static to **DHCP** and renew:

```text
! Packet Tracer: Desktop -> IP Configuration -> DHCP
! CLI equivalent on PC-CONFLICT:
ipconfig /release
ipconfig /renew
```

R-GW DHCP pool (`192.168.1.50` – `192.168.1.200`) assigns a new unique address, e.g. `192.168.1.50`.

3. Clear ARP cache on PC-USER if needed:

```text
arp -d *
```

**Simulator:** run `ipconfig pc-conflict` to inspect the duplicate host, then `fix` to apply DHCP lease.

Broken reference: [`configs/broken/pc-conflict-duplicate-ip.txt`](../configs/broken/pc-conflict-duplicate-ip.txt)  
Fixed reference: [`configs/broken/pc-conflict-dhcp-fixed.txt`](../configs/broken/pc-conflict-dhcp-fixed.txt)

## Verification

```text
arp -a                    → Single MAC for 192.168.1.10
ping 192.168.1.1          → Consistent success
ping 192.168.1.35         → Consistent success
ping 192.168.2.10         → Consistent success
tracert 192.168.2.10      → Stable hop list every attempt
```

Run ping 10 times — zero packet loss confirms conflict is resolved.
