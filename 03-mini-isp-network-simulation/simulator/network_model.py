"""
MetroLink ISP — logical network model.

Models routing, DHCP lease assignment, and DNS resolution for the
mini ISP topology documented in docs/topology.md.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Interface:
    name: str
    ip: ipaddress.IPv4Interface
    nat_inside: bool = False
    nat_outside: bool = False


@dataclass
class Route:
    destination: ipaddress.IPv4Network
    next_hop: ipaddress.IPv4Address


@dataclass
class Router:
    hostname: str
    interfaces: list[Interface] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)

    def connected_networks(self) -> list[ipaddress.IPv4Network]:
        return [iface.ip.network for iface in self.interfaces]

    def lookup(self, dest: ipaddress.IPv4Address) -> Optional[tuple[str, ipaddress.IPv4Address]]:
        """Longest-prefix match; returns (egress_interface_name, next_hop)."""
        best: Optional[tuple[int, str, ipaddress.IPv4Address]] = None

        for iface in self.interfaces:
            if dest in iface.ip.network:
                return iface.name, dest

        for route in sorted(self.routes, key=lambda r: r.destination.prefixlen, reverse=True):
            if dest in route.destination:
                prefix_len = route.destination.prefixlen
                if best is None or prefix_len > best[0]:
                    best = (prefix_len, "routed", route.next_hop)

        if best:
            return best[1], best[2]
        return None


@dataclass
class DhcpPool:
    name: str
    network: ipaddress.IPv4Network
    gateway: ipaddress.IPv4Address
    dns: ipaddress.IPv4Address
    range_start: ipaddress.IPv4Address
    range_end: ipaddress.IPv4Address
    leases: dict[str, ipaddress.IPv4Address] = field(default_factory=dict)

    def assign(self, mac: str) -> Optional[ipaddress.IPv4Address]:
        if mac in self.leases:
            return self.leases[mac]
        used = set(self.leases.values())
        host = int(self.range_start)
        end = int(self.range_end)
        while host <= end:
            candidate = ipaddress.IPv4Address(host)
            if candidate not in used:
                self.leases[mac] = candidate
                return candidate
            host += 1
        return None


@dataclass
class DnsZone:
    domain: str
    records: dict[str, ipaddress.IPv4Address] = field(default_factory=dict)

    def resolve(self, name: str) -> Optional[ipaddress.IPv4Address]:
        fqdn = name.lower().rstrip(".")
        if fqdn.endswith(f".{self.domain}"):
            host = fqdn[: -(len(self.domain) + 1)]
        elif fqdn == self.domain:
            host = "@"
        else:
            host = fqdn.split(".")[0] if "." not in fqdn else fqdn.replace(f".{self.domain}", "")
        return self.records.get(host) or self.records.get(fqdn)


def build_network() -> dict:
    """Construct the MetroLink ISP topology."""
    routers = {
        "R-ISP-CORE": Router(
            hostname="R-ISP-CORE",
            interfaces=[
                Interface("Gi0/0", ipaddress.IPv4Interface("203.0.113.1/30"), nat_outside=True),
                Interface("Gi0/1", ipaddress.IPv4Interface("10.0.0.1/24"), nat_inside=True),
            ],
            routes=[
                Route(ipaddress.IPv4Network("192.168.100.0/24"), ipaddress.IPv4Address("10.0.0.2")),
                Route(ipaddress.IPv4Network("192.168.101.0/24"), ipaddress.IPv4Address("10.0.0.2")),
                Route(ipaddress.IPv4Network("0.0.0.0/0"), ipaddress.IPv4Address("203.0.113.2")),
            ],
        ),
        "SW-DIST": Router(
            hostname="SW-DIST",
            interfaces=[
                Interface("Vlan10", ipaddress.IPv4Interface("10.0.0.2/28")),
                Interface("Vlan20", ipaddress.IPv4Interface("10.0.0.33/27")),
                Interface("Vlan100", ipaddress.IPv4Interface("192.168.100.254/24")),
                Interface("Vlan101", ipaddress.IPv4Interface("192.168.101.254/24")),
            ],
            routes=[
                Route(ipaddress.IPv4Network("0.0.0.0/0"), ipaddress.IPv4Address("10.0.0.1")),
            ],
        ),
        "R-ACME": Router(
            hostname="R-ACME",
            interfaces=[
                Interface("Gi0/0", ipaddress.IPv4Interface("192.168.100.1/24"), nat_inside=True),
                Interface("Gi0/1", ipaddress.IPv4Interface("192.168.100.253/24"), nat_outside=True),
            ],
            routes=[
                Route(ipaddress.IPv4Network("0.0.0.0/0"), ipaddress.IPv4Address("192.168.100.254")),
            ],
        ),
        "R-BETA": Router(
            hostname="R-BETA",
            interfaces=[
                Interface("Gi0/0", ipaddress.IPv4Interface("192.168.101.1/24"), nat_inside=True),
                Interface("Gi0/1", ipaddress.IPv4Interface("192.168.101.253/24"), nat_outside=True),
            ],
            routes=[
                Route(ipaddress.IPv4Network("0.0.0.0/0"), ipaddress.IPv4Address("192.168.101.254")),
            ],
        ),
    }

    dhcp_pools = [
        DhcpPool(
            name="ACME-LAN",
            network=ipaddress.IPv4Network("192.168.100.0/24"),
            gateway=ipaddress.IPv4Address("192.168.100.1"),
            dns=ipaddress.IPv4Address("10.0.0.35"),
            range_start=ipaddress.IPv4Address("192.168.100.50"),
            range_end=ipaddress.IPv4Address("192.168.100.200"),
        ),
        DhcpPool(
            name="BETA-LAN",
            network=ipaddress.IPv4Network("192.168.101.0/24"),
            gateway=ipaddress.IPv4Address("192.168.101.1"),
            dns=ipaddress.IPv4Address("10.0.0.35"),
            range_start=ipaddress.IPv4Address("192.168.101.50"),
            range_end=ipaddress.IPv4Address("192.168.101.200"),
        ),
    ]

    dns = DnsZone(
        domain="metrolink.local",
        records={
            "portal": ipaddress.IPv4Address("10.0.0.36"),
            "dns": ipaddress.IPv4Address("10.0.0.35"),
            "dhcp": ipaddress.IPv4Address("10.0.0.34"),
            "acme-gw": ipaddress.IPv4Address("192.168.100.1"),
            "beta-gw": ipaddress.IPv4Address("192.168.101.1"),
        },
    )

    return {"routers": routers, "dhcp_pools": dhcp_pools, "dns": dns}


def trace_path(
    routers: dict[str, Router],
    start_router: str,
    source: ipaddress.IPv4Address,
    dest: ipaddress.IPv4Address,
    max_hops: int = 10,
) -> list[str]:
    """Simulate hop-by-hop forwarding across routers."""
    path = [f"{start_router} ({source})"]
    current_router = start_router
    hops = 0

    while hops < max_hops:
        router = routers[current_router]
        result = router.lookup(dest)
        if result is None:
            path.append("DROP — no route")
            break

        egress, next_hop = result
        if next_hop == dest:
            path.append(f"{current_router} -> {dest} (delivered via {egress})")
            break

        path.append(f"{current_router} [{egress}] -> next-hop {next_hop}")

        next_router = None
        for name, r in routers.items():
            for iface in r.interfaces:
                if next_hop in iface.ip.network:
                    next_router = name
                    break
            if next_router:
                break

        if next_router is None:
            if dest in ipaddress.IPv4Network("203.0.113.0/30"):
                path.append(f"upstream peer -> {dest} (internet)")
            else:
                path.append(f"unknown next segment toward {dest}")
            break

        current_router = next_router
        hops += 1

    return path


def ping(routers: dict[str, Router], src_router: str, dest: ipaddress.IPv4Address) -> bool:
    path = trace_path(routers, src_router, ipaddress.IPv4Address("0.0.0.0"), dest)
    return not any("DROP" in hop or "unknown" in hop for hop in path)


def run_connectivity_tests(network: dict) -> list[tuple[str, bool, str]]:
    routers = network["routers"]
    tests = [
        ("R-ACME -> ISP DNS", ping(routers, "R-ACME", ipaddress.IPv4Address("10.0.0.35"))),
        ("R-ACME -> Portal", ping(routers, "R-ACME", ipaddress.IPv4Address("10.0.0.36"))),
        ("R-ACME -> Internet peer", ping(routers, "R-ACME", ipaddress.IPv4Address("203.0.113.2"))),
        ("R-BETA -> ISP DNS", ping(routers, "R-BETA", ipaddress.IPv4Address("10.0.0.35"))),
        ("R-BETA -> Internet peer", ping(routers, "R-BETA", ipaddress.IPv4Address("203.0.113.2"))),
        ("Core -> Customer A GW", ping(routers, "R-ISP-CORE", ipaddress.IPv4Address("192.168.100.1"))),
        ("Core -> Customer B GW", ping(routers, "R-ISP-CORE", ipaddress.IPv4Address("192.168.101.1"))),
    ]
    return [(name, ok, "PASS" if ok else "FAIL") for name, ok in tests]
