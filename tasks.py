"""
Texts of the tasks for the installer, made from what is known about a device.

Weak radio (one line per bad link):
    <Адрес> Юстировать <модель> <mac wlan> в сторону <ответная антенна>
Port problem (one line per bad port):
    <Адрес> проверить кабель и <3-й порт> роутера <mac ether1>, <ошибки / согласование в 10М / частые падения>

The address comes from the Identity (see address.py). The opposite antenna is, in this
order: the device that owns the MAC at the other end of the link (when it is in the
table), the address after «->» in the Identity, the MAC itself. A part that is unknown
is left out. No Tk here.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

import address
from core import Device, device_macs

Words = Optional[Dict[str, str]]
FindByMac = Callable[[str], Optional[Device]]


def device_address(dev: Device, words: Words = None) -> str:
    own, _remote = address.parse_identity(dev.identity, words)
    return own or dev.identity or dev.ip


def interface_mac(dev: Device, name: str) -> str:
    for m in dev.macs:
        if m.get("name") == name:
            return m.get("mac", "")
    return ""


def main_mac(dev: Device) -> str:
    """The MAC of ether1, else of the first physical interface (what the installer can read on the case)."""
    return interface_mac(dev, "ether1") or next(iter(device_macs(dev)), "")


def port_title(name: str) -> str:
    """ether3 -> «3-й порт»; anything else (sfp1, sfp-sfpplus1) -> «порт sfp1»."""
    m = re.fullmatch(r"ether(\d+)", name)
    return f"{m.group(1)}-й порт" if m else f"порт {name}"


def _speed(rate: str) -> str:
    """10Mbps -> 10М, 100Mbps -> 100М, 1Gbps -> 1Г, 2.5Gbps -> 2.5Г."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*([MG])", rate or "", re.I)
    if not m:
        return rate or "?"
    return m.group(1) + ("Г" if m.group(2).upper() == "G" else "М")


def port_summary(finding: Dict) -> str:
    parts = []
    if finding.get("errors"):
        parts.append("ошибки")
    if finding.get("mode"):
        parts.append(f"согласование в {_speed(finding.get('rate', ''))}"
                     + (" half duplex" if finding.get("half") else ""))
    if finding.get("flaps"):
        parts.append("частые падения")
    return ", ".join(parts)


def port_tasks(dev: Device, words: Words = None) -> List[str]:
    addr, mac = device_address(dev, words), main_mac(dev)
    lines = []
    for f in dev.port_findings:
        text = f"{addr} проверить кабель и {port_title(f['name'])} роутера {mac}, {port_summary(f)}"
        lines.append(_tidy(text))
    return lines


def remote_antenna(dev: Device, peer_mac: str, find_by_mac: Optional[FindByMac] = None,
                   words: Words = None) -> str:
    """Who is at the other end of the link."""
    if peer_mac and find_by_mac is not None:
        peer = find_by_mac(peer_mac)
        if peer is not None and peer is not dev:
            return device_address(peer, words)
    _own, remote = address.parse_identity(dev.identity, words)
    return remote or peer_mac


def radio_tasks(dev: Device, find_by_mac: Optional[FindByMac] = None, words: Words = None) -> List[str]:
    addr = device_address(dev, words)
    lines, seen = [], set()
    for f in dev.radio_findings:
        key = (f["interface"], f.get("peer", ""))
        if key in seen:
            continue
        seen.add(key)
        mac = interface_mac(dev, f["interface"])
        remote = remote_antenna(dev, f.get("peer", ""), find_by_mac, words)
        text = f"{addr} Юстировать {dev.board_name} {mac}" + (f" в сторону {remote}" if remote else "")
        lines.append(_tidy(text))
    return lines


def _tidy(text: str) -> str:
    return " ".join(text.split())
