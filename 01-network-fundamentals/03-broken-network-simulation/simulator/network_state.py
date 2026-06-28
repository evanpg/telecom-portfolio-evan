"""Summit Office Network — broken-state model for troubleshooting lab."""

from __future__ import annotations

import ipaddress
import random
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Route:
    destination: ipaddress.IPv4Network
    next_hop: ipaddress.IPv4Address


@dataclass
class Router:
    name: str
    interfaces: dict[str, ipaddress.IPv4Interface]
    routes: list[Route] = field(default_factory=list)

    def lookup(self, dest: ipaddress.IPv4Address) -> Optional[ipaddress.IPv4Address]:
        for iface in self.interfaces.values():
            if dest in iface.network:
                return dest
        best: Optional[tuple[int, ipaddress.IPv4Address]] = None
        for route in self.routes:
            if dest in route.destination:
                prefix = route.destination.prefixlen
                if best is None or prefix > best[0]:
                    best = (prefix, route.next_hop)
        return best[1] if best else None


@dataclass
class Scenario:
    id: str
    title: str
    problem: str
    diagnosis_hint: str
    fix_hint: str


SCENARIOS = [
    Scenario(
        id="wrong-gateway",
        title="Wrong Default Gateway",
        problem="PC cannot reach any host outside the local subnet.",
        diagnosis_hint="Run ipconfig, then ping 192.168.1.1 vs 192.168.1.254",
        fix_hint="Set default gateway to 192.168.1.1",
    ),
    Scenario(
        id="dns-misconfig",
        title="DNS Misconfiguration",
        problem="Ping to 192.168.2.10 works but app.internal does not resolve.",
        diagnosis_hint="Compare ping 192.168.2.10 vs nslookup app.internal",
        fix_hint="Set DNS to 192.168.1.35 and fix zone record",
    ),
    Scenario(
        id="ip-conflict",
        title="IP Address Conflict",
        problem="Connectivity is intermittent; duplicate IP on the LAN.",
        diagnosis_hint="Run arp -a and ping repeatedly",
        fix_hint="Set PC-CONFLICT to DHCP; renew to obtain a new lease",
    ),
    Scenario(
        id="missing-route",
        title="Missing Static Route",
        problem="Local hosts OK; Engineering subnet unreachable.",
        diagnosis_hint="Run tracert 192.168.2.10 — stops at R-CORE",
        fix_hint="Run: ip route 192.168.2.0 255.255.255.0 10.0.0.6",
    ),
]


class NetworkLab:
    DHCP_POOL_START = ipaddress.IPv4Address("192.168.1.50")
    DHCP_POOL_END = ipaddress.IPv4Address("192.168.1.200")
    DHCP_EXCLUDED = frozenset(
        {
            ipaddress.IPv4Address("192.168.1.1"),   # gateway
            ipaddress.IPv4Address("192.168.1.10"),  # PC-USER
            ipaddress.IPv4Address("192.168.1.35"),  # DNS
        }
    )

    def __init__(self) -> None:
        self.scenario_id: str | None = None
        self.pc_ip = ipaddress.IPv4Address("192.168.1.10")
        self.pc_mask = ipaddress.IPv4Address("255.255.255.0")
        self.pc_gateway = ipaddress.IPv4Address("192.168.1.1")
        self.pc_dns = ipaddress.IPv4Address("192.168.1.35")
        self.dns_records: dict[str, str] = {"app.internal": "192.168.2.10"}
        self.ip_conflict = False
        self.conflict_pc_name = "PC-CONFLICT"
        self.conflict_pc_ip: ipaddress.IPv4Address | None = None
        self.conflict_pc_uses_dhcp = False
        self.dhcp_leases: dict[str, ipaddress.IPv4Address] = {}
        self.conflict_mac = "AA-BB-CC-DD-EE-99"
        self.pc_mac = "AA-BB-CC-DD-EE-01"
        self._routers: dict[str, Router] = {}
        self._ping_counter = 0
        self._build_routers()

    def _build_routers(self) -> None:
        self._routers = {
            "R-GW": Router(
                "R-GW",
                {
                    "lan": ipaddress.IPv4Interface("192.168.1.1/24"),
                    "wan": ipaddress.IPv4Interface("10.0.0.1/30"),
                },
                [
                    Route(ipaddress.IPv4Network("192.168.2.0/24"), ipaddress.IPv4Address("10.0.0.2")),
                    Route(ipaddress.IPv4Network("0.0.0.0/0"), ipaddress.IPv4Address("10.0.0.2")),
                ],
            ),
            "R-CORE": Router(
                "R-CORE",
                {
                    "gw": ipaddress.IPv4Interface("10.0.0.2/30"),
                    "eng": ipaddress.IPv4Interface("10.0.0.5/30"),
                },
                [
                    Route(ipaddress.IPv4Network("192.168.1.0/24"), ipaddress.IPv4Address("10.0.0.1")),
                    Route(ipaddress.IPv4Network("192.168.2.0/24"), ipaddress.IPv4Address("10.0.0.6")),
                ],
            ),
            "R-ENG": Router(
                "R-ENG",
                {
                    "wan": ipaddress.IPv4Interface("10.0.0.6/30"),
                    "lan": ipaddress.IPv4Interface("192.168.2.1/24"),
                },
                [
                    Route(ipaddress.IPv4Network("192.168.1.0/24"), ipaddress.IPv4Address("10.0.0.5")),
                ],
            ),
        }

    def load_scenario(self, scenario_id: str) -> Scenario:
        scenario = next((s for s in SCENARIOS if s.id == scenario_id), None)
        if not scenario:
            raise ValueError(f"Unknown scenario: {scenario_id}")

        self.reset_baseline()
        self.scenario_id = scenario_id

        if scenario_id == "wrong-gateway":
            self.pc_gateway = ipaddress.IPv4Address("192.168.1.254")
        elif scenario_id == "dns-misconfig":
            self.pc_dns = ipaddress.IPv4Address("8.8.8.8")
            self.dns_records["app.internal"] = "192.168.2.99"
        elif scenario_id == "ip-conflict":
            self.ip_conflict = True
            self.conflict_pc_ip = ipaddress.IPv4Address("192.168.1.10")
            self.conflict_pc_uses_dhcp = False
        elif scenario_id == "missing-route":
            core = self._routers["R-CORE"]
            core.routes = [
                r for r in core.routes if r.destination != ipaddress.IPv4Network("192.168.2.0/24")
            ]

        return scenario

    def reset_baseline(self) -> None:
        self.scenario_id = None
        self.pc_gateway = ipaddress.IPv4Address("192.168.1.1")
        self.pc_dns = ipaddress.IPv4Address("192.168.1.35")
        self.dns_records = {"app.internal": "192.168.2.10"}
        self.ip_conflict = False
        self.conflict_pc_ip = None
        self.conflict_pc_uses_dhcp = False
        self.dhcp_leases = {}
        self._ping_counter = 0
        self._build_routers()

    def apply_fix(self) -> str:
        if not self.scenario_id:
            return "No scenario loaded."

        fixes = {
            "wrong-gateway": self._fix_gateway,
            "dns-misconfig": self._fix_dns,
            "ip-conflict": self._fix_conflict,
            "missing-route": self._fix_route,
        }
        return fixes[self.scenario_id]()

    def set_gateway(self, gateway: str) -> str:
        try:
            ip = ipaddress.ip_address(gateway.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid gateway address: {exc}") from exc
        if ip.version != 4:
            raise ValueError("Only IPv4 gateways are supported.")
        self.pc_gateway = ip
        return f"Default gateway set to {ip}"

    def set_dns(self, dns_server: str) -> str:
        try:
            ip = ipaddress.ip_address(dns_server.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid DNS server address: {exc}") from exc
        if ip.version != 4:
            raise ValueError("Only IPv4 DNS servers are supported.")
        self.pc_dns = ip
        return f"DNS server set to {ip}"

    def set_dns_record(self, name: str, address: str) -> str:
        host = name.lower().strip()
        if not host:
            raise ValueError("Record name cannot be empty.")
        try:
            ip = ipaddress.ip_address(address.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid record address: {exc}") from exc
        self.dns_records[host] = str(ip)
        return f"DNS record updated: {host} -> {ip}"

    def _fix_gateway(self) -> str:
        return self.set_gateway("192.168.1.1")

    def _fix_dns(self) -> str:
        client = self.set_dns("192.168.1.35")
        server = self.set_dns_record("app.internal", "192.168.2.10")
        return f"{client}; {server}"

    def _leased_addresses(self) -> set[ipaddress.IPv4Address]:
        return set(self.dhcp_leases.values())

    def _assign_dhcp_lease(self, host_name: str) -> ipaddress.IPv4Address:
        if host_name in self.dhcp_leases:
            return self.dhcp_leases[host_name]

        used = self._leased_addresses() | self.DHCP_EXCLUDED
        host = int(self.DHCP_POOL_START)
        end = int(self.DHCP_POOL_END)
        while host <= end:
            candidate = ipaddress.IPv4Address(host)
            if candidate not in used:
                self.dhcp_leases[host_name] = candidate
                return candidate
            host += 1
        raise ValueError("DHCP pool exhausted on 192.168.1.0/24")

    def _fix_conflict(self) -> str:
        self.ip_conflict = False
        new_ip = self._assign_dhcp_lease(self.conflict_pc_name)
        self.conflict_pc_ip = new_ip
        self.conflict_pc_uses_dhcp = True
        return (
            f"{self.conflict_pc_name} switched from static 192.168.1.10 to DHCP\n"
            f"  ipconfig /release && ipconfig /renew\n"
            f"  DHCP lease assigned: {new_ip} (pool 192.168.1.50-200)"
        )

    def add_ip_route(
        self,
        network: str,
        mask: str,
        next_hop: str,
        router_name: str = "R-CORE",
    ) -> str:
        """Add a static route on a router (Cisco-style: network mask next-hop)."""
        router_key = router_name.upper()
        if router_key not in self._routers:
            raise ValueError(f"Unknown router '{router_name}'. Available: R-GW, R-CORE, R-ENG")

        try:
            dest = ipaddress.ip_network(f"{network.strip()}/{mask.strip()}", strict=False)
            nh = ipaddress.ip_address(next_hop.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid route: {exc}") from exc

        if dest.version != 4 or nh.version != 4:
            raise ValueError("Only IPv4 static routes are supported.")

        router = self._routers[router_key]
        router.routes = [r for r in router.routes if r.destination != dest]
        router.routes.append(Route(dest, nh))
        return f"Static route added on {router_key}: {dest.with_prefixlen} via {nh}"

    def show_ip_route(self, router_name: str = "R-CORE") -> str:
        router_key = router_name.upper()
        if router_key not in self._routers:
            raise ValueError(f"Unknown router '{router_name}'.")

        router = self._routers[router_key]
        lines = [f"Routing table for {router_key}", ""]
        for iface in router.interfaces.values():
            lines.append(f"C    {iface.network.with_prefixlen} is directly connected")
        for route in router.routes:
            lines.append(f"S    {route.destination.with_prefixlen} via {route.next_hop}")
        return "\n".join(lines)

    def _fix_route(self) -> str:
        return self.add_ip_route("192.168.2.0", "255.255.255.0", "10.0.0.6")

    def ipconfig(self, host: str = "pc-user") -> str:
        if host.lower() in {"conflict", "pc-conflict"}:
            return self._ipconfig_conflict_pc()
        return self._ipconfig_pc_user()

    def _ipconfig_pc_user(self) -> str:
        lines = [
            "Windows IP Configuration",
            "",
            "Ethernet adapter Local Area Connection:",
            "",
            f"   Connection-specific DNS Suffix  . :",
            f"   IPv4 Address. . . . . . . . . . . : {self.pc_ip}",
            f"   Subnet Mask . . . . . . . . . . . : {self.pc_mask}",
            f"   Default Gateway . . . . . . . . . : {self.pc_gateway}",
            f"   DNS Servers . . . . . . . . . . . : {self.pc_dns}",
        ]
        return "\n".join(lines)

    def _ipconfig_conflict_pc(self) -> str:
        if self.conflict_pc_ip is None:
            return f"{self.conflict_pc_name} is not part of the current scenario."

        if self.conflict_pc_uses_dhcp:
            lines = [
                f"Windows IP Configuration — {self.conflict_pc_name}",
                "",
                "Ethernet adapter Local Area Connection:",
                "",
                "   DHCP Enabled. . . . . . . . . . . : Yes",
                f"   IPv4 Address. . . . . . . . . . . : {self.conflict_pc_ip}",
                f"   Subnet Mask . . . . . . . . . . . : {self.pc_mask}",
                f"   Default Gateway . . . . . . . . . : {self.pc_gateway}",
                f"   DNS Servers . . . . . . . . . . . : {self.pc_dns}",
                f"   DHCP Server . . . . . . . . . . . : {self.pc_gateway}",
            ]
        else:
            lines = [
                f"Windows IP Configuration — {self.conflict_pc_name}",
                "",
                "Ethernet adapter Local Area Connection:",
                "",
                "   DHCP Enabled. . . . . . . . . . . : No",
                f"   IPv4 Address. . . . . . . . . . . : {self.conflict_pc_ip}",
                f"   Subnet Mask . . . . . . . . . . . : {self.pc_mask}",
                f"   Default Gateway . . . . . . . . . : {self.pc_gateway}",
                f"   DNS Servers . . . . . . . . . . . : {self.pc_dns}",
            ]
        return "\n".join(lines)

    def ping(self, target: str) -> str:
        self._ping_counter += 1
        try:
            if target.lower() in self.dns_records:
                dest = ipaddress.ip_address(self.dns_records[target.lower()])
            else:
                dest = ipaddress.ip_address(target)
        except ValueError:
            return f"Ping request could not find host {target}."

        if self.ip_conflict and dest != ipaddress.IPv4Address("127.0.0.1"):
            if self._ping_counter % 2 == 0:
                return (
                    f"Pinging {dest} with 32 bytes of data:\n"
                    f"Request timed out.\n\n"
                    f"Approximate round trip times: 0% success\n"
                    f"(Duplicate IP detected — ARP instability)"
                )

        if dest == ipaddress.IPv4Address("127.0.0.1"):
            return (
                f"Pinging {dest} with 32 bytes of data:\n"
                f"Reply from {dest}: bytes=32 time<1ms TTL=128\n\n"
                f"Approximate round trip times: 0% loss"
            )

        ok, detail = self._can_reach(dest)
        if ok:
            return (
                f"Pinging {dest} with 32 bytes of data:\n"
                f"Reply from {dest}: bytes=32 time={random.randint(1, 8)}ms TTL=127\n\n"
                f"Approximate round trip times: 0% loss"
            )
        return (
            f"Pinging {dest} with 32 bytes of data:\n"
            f"Request timed out.\n\n"
            f"Approximate round trip times: 100% loss\n"
            f"({detail})"
        )

    def _can_reach(self, dest: ipaddress.IPv4Address) -> tuple[bool, str]:
        local_net = ipaddress.IPv4Network(f"{self.pc_ip}/24", strict=False)
        if dest in local_net:
            if dest == ipaddress.IPv4Address("192.168.1.254"):
                return False, "Destination host unreachable"
            return True, ""

        gw = self.pc_gateway
        if gw == ipaddress.IPv4Address("192.168.1.254"):
            return False, "Gateway 192.168.1.254 unreachable — check default gateway"

        if not self._route_from_pc(dest):
            return False, "Destination net unreachable"

        return True, ""

    def _route_from_pc(self, dest: ipaddress.IPv4Address) -> bool:
        current = "R-GW"
        hops = 0
        while hops < 8:
            router = self._routers[current]
            nh = router.lookup(dest)
            if nh is None:
                return False
            if nh == dest:
                return True
            nxt = self._router_for_ip(nh)
            if nxt is None:
                return dest in ipaddress.IPv4Network("192.168.2.0/24") and dest == ipaddress.IPv4Address("192.168.2.10")
            current = nxt
            hops += 1
        return False

    def _router_for_ip(self, ip: ipaddress.IPv4Address) -> str | None:
        for name, router in self._routers.items():
            for iface in router.interfaces.values():
                if ip == iface.ip:
                    return name
        for name, router in self._routers.items():
            for iface in router.interfaces.values():
                if ip in iface.network and ip != iface.network.network_address:
                    return name
        return None

    def traceroute(self, target: str) -> str:
        try:
            if target.lower() in self.dns_records:
                dest = ipaddress.ip_address(self.dns_records[target.lower()])
            else:
                dest = ipaddress.ip_address(target)
        except ValueError:
            return f"Unable to resolve target host {target}."

        lines = [f"Tracing route to {dest} over a maximum of 30 hops:\n"]
        path = self._trace_path(dest)
        if not path:
            lines.append("  1  *  Request timed out.")
            return "\n".join(lines)

        for i, hop in enumerate(path, 1):
            if hop is None:
                lines.append(f"  {i:2d}  *  Request timed out.")
            else:
                lines.append(f"  {i:2d}  {random.randint(1, 5)} ms  {hop}")
        return "\n".join(lines)

    def _trace_path(self, dest: ipaddress.IPv4Address) -> list[Optional[str]]:
        local_net = ipaddress.IPv4Network(f"{self.pc_ip}/24", strict=False)
        if dest not in local_net:
            if self.pc_gateway == ipaddress.IPv4Address("192.168.1.254"):
                return [str(self.pc_gateway), None]

        path: list[Optional[str]] = []
        if dest not in local_net:
            path.append(str(self.pc_gateway))

        current = "R-GW"
        visited = set()
        while current and current not in visited:
            visited.add(current)
            router = self._routers[current]
            nh = router.lookup(dest)
            if nh is None:
                path.append(None)
                break
            hop_label = f"{nh} [{current}]"
            if hop_label not in path and str(nh) not in path:
                path.append(str(nh))
            if nh == dest:
                break
            nxt = self._router_for_ip(nh)
            if nxt is None:
                if dest == ipaddress.IPv4Address("192.168.2.10"):
                    path.append(str(dest))
                break
            current = nxt
        return path

    def nslookup(self, name: str, server: str | None = None) -> str:
        host = name.lower().rstrip(".")
        resolver = server or str(self.pc_dns)
        try:
            resolver_ip = ipaddress.ip_address(resolver)
        except ValueError:
            return f"*** Can't find server name for address {resolver}: Non-existent host."

        if resolver_ip == ipaddress.IPv4Address("8.8.8.8"):
            return (
                f"Server:  dns.google\n"
                f"Address:  8.8.8.8\n\n"
                f"*** dns.google can't find {host}: Non-existent domain"
            )

        if resolver_ip != ipaddress.IPv4Address("192.168.1.35"):
            return f"*** Request to {resolver} timed-out"

        record = self.dns_records.get(host)
        if not record:
            return (
                f"Server:  dns.internal\n"
                f"Address:  192.168.1.35\n\n"
                f"*** dns.internal can't find {host}: Non-existent domain"
            )
        return (
            f"Server:  dns.internal\n"
            f"Address:  192.168.1.35\n\n"
            f"Name:    {host}\n"
            f"Address:  {record}"
        )

    def arp(self) -> str:
        lines = [
            "Interface: 192.168.1.10 --- 0x2",
            "  Internet Address      Physical Address      Type",
            f"  192.168.1.1           aa-bb-cc-00-00-01     dynamic",
        ]
        if self.ip_conflict:
            lines.append(f"  192.168.1.10          {self.pc_mac.lower()}     dynamic")
            lines.append(
                f"  192.168.1.10          {self.conflict_mac.lower()}     dynamic  <-- DUPLICATE"
            )
        else:
            lines.append(f"  192.168.1.10          {self.pc_mac.lower()}     dynamic")
            if self.conflict_pc_ip and self.conflict_pc_ip != ipaddress.IPv4Address("192.168.1.10"):
                lines.append(
                    f"  {self.conflict_pc_ip}          {self.conflict_mac.lower()}     dynamic"
                )
        lines.append(f"  192.168.1.35          aa-bb-cc-00-00-35     dynamic")
        return "\n".join(lines)

    def verify(self) -> list[tuple[str, bool, str]]:
        tests = [
            ("ping gateway 192.168.1.1", self._ping_ok("192.168.1.1")),
            ("ping DNS 192.168.1.35", self._ping_ok("192.168.1.35")),
            ("ping app 192.168.2.10", self._ping_ok("192.168.2.10")),
            ("nslookup app.internal", self._dns_ok("app.internal")),
        ]
        return [(name, ok, "PASS" if ok else "FAIL") for name, ok in tests]

    def _ping_ok(self, target: str) -> bool:
        saved = self._ping_counter
        result = self.ping(target)
        self._ping_counter = saved
        return "Reply from" in result

    def _dns_ok(self, name: str) -> bool:
        result = self.nslookup(name)
        return "Address:" in result and "192.168.2.10" in result and "can't find" not in result

    def show_scenario(self) -> str:
        if not self.scenario_id:
            return "Baseline network loaded (no active fault)."
        scenario = next(s for s in SCENARIOS if s.id == self.scenario_id)
        return (
            f"Scenario: {scenario.title}\n"
            f"Problem:  {scenario.problem}\n"
            f"Hint:     {scenario.diagnosis_hint}"
        )
