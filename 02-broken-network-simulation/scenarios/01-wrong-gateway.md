# Scenario 1 — Wrong Default Gateway

## Problem

PC-USER cannot reach the DNS server, application server, or any remote subnet. Local subnet communication may appear partially functional, but all off-segment traffic fails immediately.

**Broken configuration:** Default gateway set to `192.168.1.254` (non-existent) instead of `192.168.1.1`.

## Diagnosis

Work top-down from the user device:

```text
ipconfig /all
```

Expected finding:

```
Default Gateway . . . . . . . . . : 192.168.1.254   ← WRONG
```

Confirm the gateway is unreachable for **remote** traffic:

```text
ping 192.168.1.254        → Request timed out
ping 192.168.1.1          → Reply from 192.168.1.1 (correct GW is alive)
ping 192.168.1.35         → Success (same subnet — does not use default gateway)
ping 192.168.2.10         → Fails (requires correct gateway)
```

On the router, verify the correct gateway interface is up:

```text
show ip interface brief
```

R-GW `192.168.1.1` should be `up/up`.

**Root cause:** Layer 3 misconfiguration on the end host — traffic for non-local destinations is forwarded to an invalid next-hop.

## Fix

Update PC-USER network settings:

```
Default Gateway: 192.168.1.1
```

Packet Tracer: Desktop → IP Configuration → set Default Gateway to `192.168.1.1`.

Simulator: `set gateway 192.168.1.1`

Broken config reference: [`configs/broken/pc-user-wrong-gateway.txt`](../configs/broken/pc-user-wrong-gateway.txt)  
Fixed config reference: [`configs/baseline/pc-user.cfg`](../configs/baseline/pc-user.cfg)

## Verification

```text
ping 192.168.1.1          → Success
ping 192.168.1.35         → Success
ping 192.168.2.10         → Success
tracert 192.168.2.10      → Hops: PC → 192.168.1.1 → 10.0.0.2 → 10.0.0.6 → 192.168.2.10
nslookup app.internal     → 192.168.2.10
```

All remote tests should pass once the gateway is corrected.
