#!/usr/bin/env python3
"""
MetroLink ISP Network Simulation — CLI runner.

Demonstrates routing, DHCP, and DNS behavior defined in the project docs.
Requires Python 3.9+ (stdlib only).

Usage:
    python run_simulation.py
    python run_simulation.py --trace 192.168.100.10 10.0.0.36
"""

from __future__ import annotations

import argparse
import ipaddress
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from network_model import build_network, run_connectivity_tests, trace_path


def banner() -> None:
    print("=" * 60)
    print("  MetroLink ISP - Mini Network Simulation")
    print("  Router | Switch | DHCP | DNS | Routing validation")
    print("=" * 60)
    print()


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def show_topology(network: dict) -> None:
    section("Network Topology")
    for name, router in network["routers"].items():
        print(f"\n  [{name}]")
        for iface in router.interfaces:
            nat = ""
            if iface.nat_inside:
                nat = " (NAT inside)"
            elif iface.nat_outside:
                nat = " (NAT outside)"
            print(f"    {iface.name}: {iface.ip}{nat}")
        for route in router.routes:
            print(f"    route {route.destination} -> {route.next_hop}")


def show_dhcp(network: dict) -> None:
    section("DHCP Lease Simulation")
    clients = [
        ("AA:BB:CC:00:01:01", "ACME-LAN", "PC-ACME-01"),
        ("AA:BB:CC:00:01:02", "ACME-LAN", "PC-ACME-02"),
        ("AA:BB:CC:00:02:01", "BETA-LAN", "PC-BETA-01"),
    ]
    pools = {p.name: p for p in network["dhcp_pools"]}

    for mac, pool_name, hostname in clients:
        pool = pools[pool_name]
        ip = pool.assign(mac)
        if ip:
            print(f"  {hostname} ({mac})")
            print(f"    IP:      {ip}/{pool.network.prefixlen}")
            print(f"    Gateway: {pool.gateway}")
            print(f"    DNS:     {pool.dns}")
        else:
            print(f"  {hostname}: DHCP NAK — pool exhausted")


def show_dns(network: dict) -> None:
    section("DNS Resolution")
    dns = network["dns"]
    queries = [
        "portal.metrolink.local",
        "dns.metrolink.local",
        "unknown.metrolink.local",
    ]
    for q in queries:
        result = dns.resolve(q)
        status = str(result) if result else "NXDOMAIN"
        print(f"  {q} -> {status}")


def show_routing_tests(network: dict) -> None:
    section("Connectivity Tests")
    results = run_connectivity_tests(network)
    passed = sum(1 for _, _, status in results if status == "PASS")
    for name, _, status in results:
        icon = "OK" if status == "PASS" else "XX"
        print(f"  [{icon}] {name}: {status}")
    print(f"\n  Result: {passed}/{len(results)} tests passed")


def show_trace(network: dict, source: str, dest: str, start_router: str) -> None:
    section(f"Traceroute: {source} → {dest} (from {start_router})")
    try:
        dest_ip = ipaddress.IPv4Address(dest)
    except ipaddress.AddressValueError:
        resolved = network["dns"].resolve(dest)
        if not resolved:
            print(f"  Cannot resolve {dest}")
            return
        print(f"  Resolved {dest} -> {resolved}")
        dest_ip = resolved

    hops = trace_path(
        network["routers"],
        start_router,
        ipaddress.IPv4Address(source) if source != "0.0.0.0" else ipaddress.IPv4Address("192.168.100.10"),
        dest_ip,
    )
    for i, hop in enumerate(hops, 1):
        print(f"  {i}. {hop}")


def main() -> int:
    parser = argparse.ArgumentParser(description="MetroLink ISP network simulation")
    parser.add_argument(
        "--trace",
        nargs=2,
        metavar=("DEST", "ROUTER"),
        help="Trace path to DEST starting from ROUTER (e.g. 10.0.0.36 R-ACME)",
    )
    args = parser.parse_args()

    network = build_network()
    banner()

    if args.trace:
        dest, router = args.trace
        show_trace(network, "0.0.0.0", dest, router)
        return 0

    show_topology(network)
    show_dhcp(network)
    show_dns(network)
    show_routing_tests(network)

    section("Skills Demonstrated")
    skills = [
        "IP subnetting (/30 WAN, /27 services, /24 customer LANs)",
        "VLAN segmentation and inter-VLAN routing",
        "Static routing and default routes",
        "DHCP pool design with excluded addresses",
        "Internal DNS zone management",
        "NAT/PAT at CPE and core (documented in configs/)",
        "Structured troubleshooting (see docs/troubleshooting-guide.md)",
    ]
    for skill in skills:
        print(f"  - {skill}")

    print()
    return 0 if all(s == "PASS" for _, _, s in run_connectivity_tests(network)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
