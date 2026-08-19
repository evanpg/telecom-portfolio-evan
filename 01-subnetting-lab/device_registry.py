"""Device-to-IP assignment and tagged subnet registry backed by SQLite."""

from __future__ import annotations

import ipaddress
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from network_utils import iter_usable_addresses, parse_cidr, subnets_overlap, usable_hosts

DEFAULT_DB = Path(__file__).resolve().parent / "assignments.db"

RESERVED_NETWORK = "(network)"
RESERVED_BROADCAST = "(broadcast)"
RESERVED_DEVICE_NAMES = frozenset({RESERVED_NETWORK, RESERVED_BROADCAST})


@dataclass
class TaggedSubnet:
    tag: str
    subnet_cidr: str
    network_address: str
    broadcast_address: str
    created_at: str


@dataclass
class DeviceAssignment:
    subnet_cidr: str
    device_name: str
    ip_address: str
    created_at: str
    tag: str | None = None
    reserved: bool = False


class DeviceRegistry:
    def __init__(self, db_path: Path | str = DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subnets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    subnet_cidr TEXT NOT NULL UNIQUE,
                    network_address TEXT NOT NULL DEFAULT '',
                    broadcast_address TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS device_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subnet_cidr TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (subnet_cidr, device_name),
                    UNIQUE (subnet_cidr, ip_address)
                )
                """
            )
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(subnets)")}
        if "network_address" not in columns:
            conn.execute(
                "ALTER TABLE subnets ADD COLUMN network_address TEXT NOT NULL DEFAULT ''"
            )
        if "broadcast_address" not in columns:
            conn.execute(
                "ALTER TABLE subnets ADD COLUMN broadcast_address TEXT NOT NULL DEFAULT ''"
            )

        rows = conn.execute(
            """
            SELECT tag, subnet_cidr, network_address, broadcast_address
            FROM subnets
            WHERE network_address = '' OR broadcast_address = ''
            """
        ).fetchall()
        for row in rows:
            network = parse_cidr(row["subnet_cidr"])
            conn.execute(
                """
                UPDATE subnets
                SET network_address = ?, broadcast_address = ?
                WHERE tag = ?
                """,
                (
                    str(network.network_address),
                    str(network.broadcast_address),
                    row["tag"],
                ),
            )
            self._seed_reserved_addresses(conn, row["subnet_cidr"], network)

    def _subnet_row_to_model(self, row: sqlite3.Row) -> TaggedSubnet:
        return TaggedSubnet(
            tag=row["tag"],
            subnet_cidr=row["subnet_cidr"],
            network_address=row["network_address"],
            broadcast_address=row["broadcast_address"],
            created_at=row["created_at"],
        )

    def _reserved_addresses(
        self, subnet: ipaddress.IPv4Network,
    ) -> list[tuple[str, str]]:
        network_addr = str(subnet.network_address)
        broadcast_addr = str(subnet.broadcast_address)
        reserved = [(RESERVED_NETWORK, network_addr)]
        if broadcast_addr != network_addr:
            reserved.append((RESERVED_BROADCAST, broadcast_addr))
        return reserved

    def _seed_reserved_addresses(
        self,
        conn: sqlite3.Connection,
        subnet_cidr: str,
        subnet: ipaddress.IPv4Network,
        created_at: str | None = None,
    ) -> None:
        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        for device_name, ip_address in self._reserved_addresses(subnet):
            existing = conn.execute(
                """
                SELECT 1 FROM device_assignments
                WHERE subnet_cidr = ? AND device_name = ?
                """,
                (subnet_cidr, device_name),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """
                INSERT INTO device_assignments
                (subnet_cidr, device_name, ip_address, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (subnet_cidr, device_name, ip_address, timestamp),
            )

    def _normalize_tag(self, tag: str) -> str:
        name = tag.strip()
        if not name:
            raise ValueError("Subnet tag cannot be empty.")
        return name

    def _ensure_no_overlap(self, candidate: ipaddress.IPv4Network) -> None:
        for existing in self.list_subnets():
            other = parse_cidr(existing.subnet_cidr)
            if subnets_overlap(candidate, other):
                raise ValueError(
                    f"Subnet {candidate.with_prefixlen} overlaps with "
                    f"'{existing.tag}' ({existing.subnet_cidr}). "
                    "Registered subnets must not share address space."
                )

    def get_registered_subnet(self, tag_or_cidr: str) -> TaggedSubnet:
        key = tag_or_cidr.strip()
        if not key:
            raise ValueError("Provide a registered subnet tag or CIDR.")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tag, subnet_cidr, network_address, broadcast_address, created_at
                FROM subnets
                WHERE tag = ? COLLATE NOCASE
                """,
                (key,),
            ).fetchone()

            if row is None and self._looks_like_cidr(key):
                row = conn.execute(
                    """
                    SELECT tag, subnet_cidr, network_address, broadcast_address, created_at
                    FROM subnets
                    WHERE subnet_cidr = ?
                    """,
                    (parse_cidr(key).with_prefixlen,),
                ).fetchone()

        if row is None:
            if self._looks_like_cidr(key):
                cidr = parse_cidr(key).with_prefixlen
                raise ValueError(f"No registered subnet found for {cidr}.")
            raise ValueError(f"No registered subnet found with tag '{key}'.")

        return self._subnet_row_to_model(row)

    def _looks_like_cidr(self, value: str) -> bool:
        return "/" in value

    def create_subnet(self, tag: str, subnet_cidr: str) -> TaggedSubnet:
        """Register a named subnet and reserve network/broadcast addresses."""
        name = self._normalize_tag(tag)
        subnet = parse_cidr(subnet_cidr)
        if subnet.version != 4:
            raise ValueError("Tagged subnets currently support IPv4 only.")

        normalized_cidr = subnet.with_prefixlen
        self._ensure_no_overlap(subnet)

        network_address = str(subnet.network_address)
        broadcast_address = str(subnet.broadcast_address)
        created_at = datetime.now(timezone.utc).isoformat()

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO subnets
                    (tag, subnet_cidr, network_address, broadcast_address, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, normalized_cidr, network_address, broadcast_address, created_at),
                )
                self._seed_reserved_addresses(conn, normalized_cidr, subnet, created_at)
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Tag or CIDR already registered. Each tag and subnet must be unique."
            ) from exc

        return TaggedSubnet(
            name,
            normalized_cidr,
            network_address,
            broadcast_address,
            created_at,
        )

    def remove_subnet(self, tag_or_cidr: str) -> tuple[TaggedSubnet, int]:
        """Remove a registered subnet and all device assignments within its range."""
        registered = self.get_registered_subnet(tag_or_cidr)
        subnet = parse_cidr(registered.subnet_cidr)

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, ip_address FROM device_assignments"
            ).fetchall()
            removed_count = 0
            for row in rows:
                if ipaddress.ip_address(row["ip_address"]) in subnet:
                    conn.execute(
                        "DELETE FROM device_assignments WHERE id = ?",
                        (row["id"],),
                    )
                    removed_count += 1

            conn.execute(
                "DELETE FROM subnets WHERE subnet_cidr = ?",
                (registered.subnet_cidr,),
            )

        return registered, removed_count

    def resolve_subnet(self, tag_or_cidr: str) -> str:
        key = tag_or_cidr.strip()
        if not key:
            raise ValueError("Provide a subnet tag or CIDR.")

        with self._connect() as conn:
            row = conn.execute(
                "SELECT subnet_cidr FROM subnets WHERE tag = ? COLLATE NOCASE",
                (key,),
            ).fetchone()
        if row:
            return row["subnet_cidr"]

        subnet = parse_cidr(key)
        if subnet.version != 4:
            raise ValueError("Device assignment currently supports IPv4 subnets only.")
        return subnet.with_prefixlen

    def get_tag_for_subnet(self, subnet_cidr: str) -> str | None:
        subnet = parse_cidr(subnet_cidr)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tag FROM subnets WHERE subnet_cidr = ?",
                (subnet.with_prefixlen,),
            ).fetchone()
        return row["tag"] if row else None

    def list_subnets(self) -> list[TaggedSubnet]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT tag, subnet_cidr, network_address, broadcast_address, created_at
                FROM subnets
                ORDER BY tag COLLATE NOCASE
                """
            ).fetchall()
        return [self._subnet_row_to_model(r) for r in rows]

    def _is_reserved_name(self, device_name: str) -> bool:
        return device_name in RESERVED_DEVICE_NAMES

    def _user_assignments(self, subnet_key: str) -> list[DeviceAssignment]:
        return [
            assignment
            for assignment in self.list_assignments(subnet_key)
            if not assignment.reserved
        ]

    def add_device(self, subnet_key: str, device_name: str, ip_address: str) -> DeviceAssignment:
        normalized_subnet = self.resolve_subnet(subnet_key)
        subnet = parse_cidr(normalized_subnet)

        name = device_name.strip()
        if not name:
            raise ValueError("Device name cannot be empty.")
        if self._is_reserved_name(name):
            raise ValueError(
                f"Device name '{name}' is reserved for system network/broadcast entries."
            )

        try:
            ip = ipaddress.ip_address(ip_address.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid IP address: {exc}") from exc

        if ip not in subnet:
            raise ValueError(f"{ip} is not inside subnet {subnet.with_prefixlen}.")

        assignable = {str(addr) for addr in iter_usable_addresses(subnet)}
        if str(ip) not in assignable:
            raise ValueError(f"{ip} is not a usable host address in {subnet.with_prefixlen}.")

        created_at = datetime.now(timezone.utc).isoformat()

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO device_assignments (subnet_cidr, device_name, ip_address, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (normalized_subnet, name, str(ip), created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Device name or IP already assigned in this subnet."
            ) from exc

        return DeviceAssignment(
            normalized_subnet,
            name,
            str(ip),
            created_at,
            tag=self.get_tag_for_subnet(normalized_subnet),
        )

    def remove_device(
        self,
        *,
        subnet_key: str | None = None,
        device_name: str | None = None,
        ip_address: str | None = None,
    ) -> DeviceAssignment:
        if not device_name and not ip_address:
            raise ValueError("Provide a device name or IP address to remove.")

        if device_name and self._is_reserved_name(device_name.strip()):
            raise ValueError(
                "Cannot remove reserved network/broadcast entries. "
                "Remove the entire subnet instead."
            )

        conditions: list[str] = []
        params: list[str] = []

        if subnet_key:
            conditions.append("subnet_cidr = ?")
            params.append(self.resolve_subnet(subnet_key))

        if device_name:
            conditions.append("device_name = ?")
            params.append(device_name.strip())

        if ip_address:
            try:
                ip = str(ipaddress.ip_address(ip_address.strip()))
            except ValueError as exc:
                raise ValueError(f"Invalid IP address: {exc}") from exc
            if self._is_reserved_ip_for_subnet(ip, subnet_key):
                raise ValueError(
                    "Cannot remove reserved network/broadcast address. "
                    "Remove the entire subnet instead."
                )
            conditions.append("ip_address = ?")
            params.append(ip)

        where = " AND ".join(conditions)

        with self._connect() as conn:
            row = conn.execute(
                "SELECT subnet_cidr, device_name, ip_address, created_at "
                f"FROM device_assignments WHERE {where}",
                params,
            ).fetchone()
            if row is None:
                raise ValueError("No matching device assignment found.")
            if self._is_reserved_name(row["device_name"]):
                raise ValueError(
                    "Cannot remove reserved network/broadcast entries. "
                    "Remove the entire subnet instead."
                )

            conn.execute(f"DELETE FROM device_assignments WHERE {where}", params)

        cidr = row["subnet_cidr"]
        return DeviceAssignment(
            cidr,
            row["device_name"],
            row["ip_address"],
            row["created_at"],
            tag=self.get_tag_for_subnet(cidr),
        )

    def _is_reserved_ip_for_subnet(self, ip: str, subnet_key: str | None) -> bool:
        if not subnet_key:
            return False
        try:
            registered = self.get_registered_subnet(subnet_key)
        except ValueError:
            return False
        return ip in {registered.network_address, registered.broadcast_address}

    def list_assignments(self, subnet_key: str | None = None) -> list[DeviceAssignment]:
        with self._connect() as conn:
            if subnet_key:
                cidr = self.resolve_subnet(subnet_key)
                rows = conn.execute(
                    """
                    SELECT subnet_cidr, device_name, ip_address, created_at
                    FROM device_assignments
                    WHERE subnet_cidr = ?
                    ORDER BY ip_address
                    """,
                    (cidr,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT subnet_cidr, device_name, ip_address, created_at
                    FROM device_assignments
                    ORDER BY subnet_cidr, ip_address
                    """
                ).fetchall()

        return [
            DeviceAssignment(
                r["subnet_cidr"],
                r["device_name"],
                r["ip_address"],
                r["created_at"],
                tag=self.get_tag_for_subnet(r["subnet_cidr"]),
                reserved=self._is_reserved_name(r["device_name"]),
            )
            for r in rows
        ]

    def remaining_ips(self, subnet_key: str) -> int:
        cidr = self.resolve_subnet(subnet_key)
        subnet = parse_cidr(cidr)
        total_usable = usable_hosts(subnet)
        assigned = len(self._user_assignments(cidr))
        return max(total_usable - assigned, 0)

    def print_subnets(self) -> None:
        subnets = self.list_subnets()

        print("\n  Registered Subnets")
        print("  " + "=" * 58)

        if not subnets:
            print("\n  No tagged subnets yet. Use menu option 5 to create one.")
            print("")
            return

        print(f"\n  {'Tag':<14} {'CIDR':<18} {'Usable':<7} {'Used':<5} {'Free'}")
        print(f"  {'-' * 14} {'-' * 18} {'-' * 7} {'-' * 5} {'-' * 6}")

        for item in subnets:
            network = parse_cidr(item.subnet_cidr)
            usable = usable_hosts(network)
            used = len(self._user_assignments(item.subnet_cidr))
            free = max(usable - used, 0)
            print(f"  {item.tag:<14} {item.subnet_cidr:<18} {usable:<7,} {used:<5} {free:,}")
            print(f"    Network:   {item.network_address}")
            print(f"    Broadcast: {item.broadcast_address}")

        print("")

    def print_assignments(self, subnet_key: str | None = None) -> None:
        registered_subnets = self.list_subnets()
        assignments = self.list_assignments(subnet_key)

        if subnet_key:
            cidr = self.resolve_subnet(subnet_key)
            try:
                registered = self.get_registered_subnet(cidr)
                registered_subnets = [registered]
            except ValueError:
                registered_subnets = []

        if not registered_subnets and not assignments:
            print("\n  No subnets or device assignments in database.")
            return

        subnets_with_devices: dict[str, list[DeviceAssignment]] = {}
        for item in assignments:
            subnets_with_devices.setdefault(item.subnet_cidr, []).append(item)

        registered_map = {s.subnet_cidr: s for s in registered_subnets}
        all_cidrs = set(registered_map) | set(subnets_with_devices)

        print("\n  Subnets and Assignments")
        print(f"  {'Name / Device':<22} {'CIDR / IP':<20} {'Free':>6}")
        print(f"  {'-' * 22} {'-' * 20} {'-' * 6}")

        for cidr in sorted(all_cidrs, key=lambda c: ipaddress.ip_network(c, strict=False)):
            registered = registered_map.get(cidr)
            devices = sorted(
                subnets_with_devices.get(cidr, []),
                key=lambda d: ipaddress.ip_address(d.ip_address),
            )
            label = registered.tag if registered else cidr
            free = self.remaining_ips(cidr)
            print(f"  {label:<22} {cidr:<20} {free:>6,}")

            if not devices:
                print(f"    {'(no assignments)':<20}")
                continue

            for device in devices:
                print(f"    {device.device_name:<20} {device.ip_address}")

        print("")
