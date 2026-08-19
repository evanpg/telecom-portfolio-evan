# Scenario 4 — Missing Static Route

## Problem

PC-USER reaches the local gateway (`192.168.1.1`) and DNS server (`192.168.1.35`) on the same subnet, but cannot reach the Engineering subnet (`192.168.2.10`). Traceroute stops at an intermediate router.

**Broken configuration:** R-CORE is missing the static route to `192.168.2.0/24` via R-ENG (`10.0.0.6`).

## Diagnosis

Establish where traffic dies:

```text
ping 192.168.1.1          → Success (local GW)
ping 192.168.1.35         → Success (same subnet)
ping 192.168.2.10         → Request timed out
tracert 192.168.2.10
```

Expected broken traceroute:

```
  1    1 ms    192.168.1.1      (R-GW)
  2    2 ms    10.0.0.2         (R-CORE)
  3   *        *                Request timed out   ← route missing beyond here
```

On R-CORE:

```text
show ip route
show ip route 192.168.2.10
```

Broken state — no route to `192.168.2.0/24`:

```
Gateway of last resort is 10.0.0.1 to network 0.0.0.0

C    10.0.0.0/30 is directly connected, GigabitEthernet0/0
C    10.0.0.4/30 is directly connected, GigabitEthernet0/1
S    192.168.1.0/24 [1/0] via 10.0.0.1
! Missing: 192.168.2.0/24 via 10.0.0.6
```

On R-GW (should have route to core):

```text
show ip route 192.168.2.0
```

**Root cause:** R-CORE drops packets destined for Engineering — no matching route in the routing table.

## Fix

On R-CORE, add the missing static route:

```text
configure terminal
ip route 192.168.2.0 255.255.255.0 10.0.0.6
end
write memory
```

**Simulator:**

```text
show ip route
ip route 192.168.2.0 255.255.255.0 10.0.0.6
show ip route
```

Broken config: [`configs/broken/r-core-missing-route.cfg`](../configs/broken/r-core-missing-route.cfg)  
Fixed config: [`configs/baseline/r-core.cfg`](../configs/baseline/r-core.cfg)

## Verification

```text
show ip route 192.168.2.0
! S    192.168.2.0/24 [1/0] via 10.0.0.6

ping 192.168.2.10         → Success (from R-CORE)
ping 192.168.2.10         → Success (from PC-USER)
tracert 192.168.2.10
! 1  192.168.1.1 → 2  10.0.0.2 → 3  10.0.0.6 → 4  192.168.2.10
nslookup app.internal
ping app.internal         → Success
```

End-to-end connectivity restored.
