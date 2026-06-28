# Scenario 2 — DNS Misconfiguration

## Problem

PC-USER can ping `192.168.2.10` by IP address, but `app.internal` does not resolve. Browser and application access by hostname fail even though routing is correct.

**Broken configuration:** DNS server IP on PC points to `8.8.8.8` (external, no internal zone), or SRV-DNS has wrong/missing A record for `app.internal`.

## Diagnosis

Confirm routing works — isolate DNS as the failure point:

```text
ping 192.168.2.10         → Success (routing OK)
ping app.internal         → Could not find host / Ping request could not find host
nslookup app.internal     → Fails or returns wrong address
```

Check client DNS settings:

```text
ipconfig /all
```

Expected broken finding:

```
DNS Servers . . . . . . . . . . . : 8.8.8.8
```

Test the internal DNS server directly:

```text
nslookup app.internal 192.168.1.35
```

If this returns `192.168.2.10`, the server is fine and the **client DNS setting** is wrong.  
If this fails, inspect the **DNS zone** on SRV-DNS.

On SRV-DNS (Packet Tracer): Services → DNS — verify A record:

```
app.internal → 192.168.2.10
```

**Root cause:** Name resolution path is broken — either wrong resolver configured on client, or incorrect zone data on the DNS server.

## Fix

**Option A — Wrong client DNS server:**

```
set dns 192.168.1.35
```

Or Packet Tracer: Desktop → IP Configuration → DNS Server → `192.168.1.35`

**Option B — Wrong zone record on SRV-DNS:**

```
set dns-record app.internal 192.168.2.10
```

Or add/correct A record on SRV-DNS: `app.internal` → `192.168.2.10`

Both fixes may be required depending on which misconfiguration is loaded.

Broken references:

- [`configs/broken/pc-user-wrong-dns.txt`](../configs/broken/pc-user-wrong-dns.txt)
- [`configs/broken/srv-dns-wrong-record.txt`](../configs/broken/srv-dns-wrong-record.txt)

Fixed reference: [`configs/baseline/`](../configs/baseline/)

## Verification

```text
ipconfig /all             → DNS: 192.168.1.35
nslookup app.internal     → Address: 192.168.2.10
ping app.internal         → Reply from 192.168.2.10
tracert app.internal      → Full path to 192.168.2.10
```

Application access by hostname should succeed.
