# Subnetting Lab

Interactive CIDR calculator with tagged subnet registry and device-to-IP assignment stored in SQLite.

## What It Does

- **Calculate subnet** from CIDR notation (hosts, masks, subdivisions)
- **Create tagged subnet** — register a CIDR block with a name; network and broadcast addresses are reserved automatically
- **Remove tagged subnet** — delete a subnet and all device assignments within its range
- **Add device** — assign a device to an IP using a tag or CIDR
- **Remove device** — unassign by device name or IP address
- **Print subnets and assignments** — list all subnet names, capacity, and devices

## Run

```powershell
cd D:\08.coding\telecom-portfolio-evan\01-network-fundamentals\02-subnetting-lab
python subnet_calculator.py
```

## Menu

```
  1. Calculate subnet from CIDR
  2. Add device to IP
  3. Remove device from IP
  4. Print subnets and assignments
  5. Create tagged subnet
  6. Remove tagged subnet
  q. Quit
```

## Example — Print Subnets and Assignments

```
Select option: 4

  Subnets and Assignments
  Name / Device          CIDR / IP            Free
  ---------------------- -------------------- ------
  corporate              192.168.10.0/24         253
    (network)            192.168.10.0
    pc-01                192.168.10.50
    (broadcast)          192.168.10.255
  HR                     192.168.20.0/24         254
    (network)            192.168.20.0
    (broadcast)          192.168.20.255
```

## Example — Device Assignment by Tag

```
Select option: 2

  Subnet tag or CIDR (e.g. corporate or 192.168.1.0/24): corporate
  Device name: router-core
  IP address: 192.168.10.1
  Added router-core -> 192.168.10.1 on 192.168.10.0/24 [corporate]
  Remaining IPs on subnet: 253
```

## Database

Data persists in `assignments.db` (SQLite):

**`subnets` table**

| Field | Description |
|-------|-------------|
| `tag` | Friendly name (e.g. `corporate`, `HR`) — unique |
| `subnet_cidr` | IPv4 network (e.g. `192.168.10.0/24`) — unique, must not overlap other registered subnets |
| `network_address` | First address in the block (auto-assigned) |
| `broadcast_address` | Last address in the block (auto-assigned) |
| `created_at` | UTC timestamp |

Reserved `(network)` and `(broadcast)` entries are also stored in `device_assignments` and cannot be removed individually.

**`device_assignments` table**

| Field | Description |
|-------|-------------|
| `subnet_cidr` | Parent network |
| `device_name` | Device identifier |
| `ip_address` | Assigned IPv4 address |
| `created_at` | UTC timestamp |

## Project Files

```
02-subnetting-lab/
├── subnet_calculator.py   # Main menu (CLI)
├── device_registry.py     # Subnets, devices, SQLite persistence
├── network_utils.py       # CIDR parsing and host math
├── assignments.db         # Created on first save
└── README.md
```

## Requirements

- Python 3.9+ (stdlib only)

## Skills Demonstrated

- CIDR notation and usable host calculation
- IP validation within a subnet range
- Tagged subnet inventory management
- SQLite persistence for network planning
- Subnet capacity tracking (assigned vs remaining)
