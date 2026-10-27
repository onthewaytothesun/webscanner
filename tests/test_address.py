"""Addresses from Identity (transliteration back to Russian) and the installer's task texts."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import address  # noqa: E402
import core  # noqa: E402
import health  # noqa: E402
import tasks  # noqa: E402
from core import Device  # noqa: E402
from store import ConfigStore, app_dir  # noqa: E402


def test_router_identities_become_russian_addresses():
    assert address.parse_identity("CP_Natashi_Kovshovoy_29") == ("Наташи Ковшовой 29", "")
    assert address.parse_identity("S_Varshavskoe_sh_128k1") == ("Варшавское ш. 128к1", "")
    assert address.parse_identity("V_Dorozhnaya_1k5s3")[0] == "Дорожная 1к5с3"
    assert address.parse_identity("CPL_Kirovogradskaya_20a")[0] == "Кировоградская 20а"
    assert address.parse_identity("R_Elektrozavodskaya_5")[0] == "Электрозаводская 5"
    assert address.parse_identity("CP_Podolskikh_Kursantov_7")[0] == "Подольских Курсантов 7"


def test_the_number_in_brackets_at_the_end_is_ignored():
    assert address.parse_identity("CP_Natashi_Kovshovoy_29(2)")[0] == "Наташи Ковшовой 29"
    assert address.parse_identity("CP_Natashi_Kovshovoy_29 (12)")[0] == "Наташи Ковшовой 29"
    assert address.parse_identity("AP_Dorozhnaya_1k5s3->Dnepropetrovskaya_1(2)") == (
        "Дорожная 1к5с3", "Днепропетровская 1")


def test_antenna_identities_have_both_addresses_and_no_prefix():
    assert address.parse_identity("AP_Varshavskoe_sh_128k1->Kavkazskiy_b_r_59s2") == (
        "Варшавское ш. 128к1", "Кавказский б-р 59с2")
    assert address.parse_identity("CPE_Dorozhnaya_1k5s3->Dnepropetrovskaya_1") == (
        "Дорожная 1к5с3", "Днепропетровская 1")
    assert address.parse_identity("") == ("", "")


def test_the_operators_own_spellings_win():
    for latin, russian in (("R_Sovetskaya_10", "Советская 10"), ("S_Shkolnaya_1", "Школьная 1"),
                           ("S_Ilyinskaya_1", "Ильинская 1"), ("CP_Oktyabrskaya_9", "Октябрьская 9"),
                           ("S_Tsentralnyy_pr_d_4", "Центральный пр-д 4"), ("S_Solnechnaya_1", "Солнечная 1"),
                           ("S_Vasilyevskaya_2", "Васильевская 2"), ("V_Bratskaya_ul_5", "Братская ул. 5"),
                           ("S_Tsvetochnaya_2", "Цветочная 2"), ("S_Novyy_Arbat_1", "Новый Арбат 1")):
        assert address.parse_identity(latin)[0] == russian, latin
    assert address.parse_identity("CP_Ulyanova_3")[0] == "Ульянова 3"             # built in (the soft sign)
    assert address.parse_identity("CP_Ulyanova_3", {"Ulyanova": "Ульяновой"})[0] == "Ульяновой 3"
    assert address.parse_identity("CP_Zhukova_1", {"zhukova": "Жукова"})[0] == "Жукова 1"


def _router():
    return Device(
        ip="10.20.0.1", identity="AP_Varshavskoe_sh_128k1->Kavkazskiy_b_r_59s2", board_name="SXTsq 5",
        macs=[{"name": "ether1", "type": "ether", "mac": "AA:00:00:00:00:01"},
              {"name": "wlan1", "type": "wlan", "mac": "AA:00:00:00:00:02"}],
        radio_findings=[{"interface": "wlan1", "peer": "CC:00:00:00:00:09", "rx": -80, "tx": -70,
                         "kinds": ["weak"]}])


def test_radio_task_names_the_opposite_antenna():
    dev = _router()
    assert tasks.radio_tasks(dev) == [
        "Варшавское ш. 128к1 Юстировать SXTsq 5 AA:00:00:00:00:02 в сторону Кавказский б-р 59с2"]
    # the device that owns the MAC at the other end is better than the name after «->»
    peer = Device(ip="10.20.0.2", identity="CPE_Dorozhnaya_1k5s3->Varshavskoe_sh_128k1",
                  macs=[{"name": "wlan1", "type": "wlan", "mac": "CC:00:00:00:00:09"}])
    found = tasks.radio_tasks(dev, lambda mac: core.find_by_mac([dev, peer], mac))
    assert found == ["Варшавское ш. 128к1 Юстировать SXTsq 5 AA:00:00:00:00:02 в сторону Дорожная 1к5с3"]
    plain = _router()
    plain.identity = "CP_Natashi_Kovshovoy_29"                     # a router: nothing says who is there
    assert tasks.radio_tasks(plain)[0].endswith("в сторону CC:00:00:00:00:09")
    plain.radio_findings[0]["peer"] = ""
    assert tasks.radio_tasks(plain) == ["Наташи Ковшовой 29 Юстировать SXTsq 5 AA:00:00:00:00:02"]


def test_port_task_names_the_port_the_mac_and_the_problem():
    dev = Device(ip="10.20.0.1", identity="CP_Natashi_Kovshovoy_29(2)",
                 macs=[{"name": "ether1", "type": "ether", "mac": "AA:00:00:00:00:01"}],
                 port_findings=[
                     {"name": "ether3", "mode": "10Mbps full-duplex", "rate": "10Mbps", "half": False,
                      "errors": {}, "flaps": 0},
                     {"name": "ether5", "mode": "", "rate": "1Gbps", "half": False,
                      "errors": {"rx-fcs-error": 40}, "flaps": 12},
                     {"name": "sfp1", "mode": "100Mbps half-duplex", "rate": "100Mbps", "half": True,
                      "errors": {}, "flaps": 0}])
    assert tasks.port_tasks(dev) == [
        "Наташи Ковшовой 29 проверить кабель и 3-й порт роутера AA:00:00:00:00:01, согласование в 10М",
        "Наташи Ковшовой 29 проверить кабель и 5-й порт роутера AA:00:00:00:00:01, ошибки, частые падения",
        "Наташи Ковшовой 29 проверить кабель и порт sfp1 роутера AA:00:00:00:00:01, "
        "согласование в 100М half duplex"]


def test_findings_keep_what_the_task_needs():
    ports = [{"name": "ether2", "running": True, "rate": "10Mbps", "full_duplex": "true",
              "link_downs": 30, "errors": {"rx-fcs-error": 11}}]
    old = [{"name": "ether2", "link_downs": 10}]
    (f,) = health.port_findings(ports, old)
    assert f["name"] == "ether2" and f["rate"] == "10Mbps" and f["errors"] == {"rx-fcs-error": 11}
    assert f["flaps"] == 20 and f["mode"].startswith("10Mbps")
    links = health.radio_findings(
        [{"interface": "wlan1", "mac": "BB", "rx": -80, "tx": -60}],
        [{"interface": "wlan1", "mac": "BB", "rx": -60, "tx": -60}],
        [{"name": "wlan1", "link_downs": 40}], [{"name": "wlan1", "link_downs": 5}])
    assert links[0]["kinds"] == ["weak", "drop"] and links[0]["peer"] == "BB"
    assert links[1]["kinds"] == ["flap"] and links[1]["flaps"] == 35


def test_macs_are_found_by_physical_interfaces_only():
    dev = Device(macs=[{"name": "ether1", "type": "ether", "mac": "AA:00:00:00:00:01"},
                       {"name": "wlan1", "type": "wlan", "mac": "AA:00:00:00:00:02"}])
    assert core.device_macs(dev) == ["AA:00:00:00:00:01", "AA:00:00:00:00:02"]
    assert core.find_by_mac([dev], "aa-00-00-00-00-02") is dev and core.find_by_mac([dev], "ZZ") is None


def test_one_config_file_is_shared_by_two_programs_without_losing_each_others_sections():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "mt_config.json")
        scanner, viewer = ConfigStore(path), ConfigStore(path)
        scanner.set("devices", [{"ip": "10.0.0.1"}])
        viewer.set("viewer_settings", {"user": "stp"})     # the viewer's own copy is older than the file
        scanner.set("ui", {"column_widths": {}})
        fresh = ConfigStore(path)
        assert fresh.get("devices") == [{"ip": "10.0.0.1"}]
        assert fresh.get("viewer_settings") == {"user": "stp"} and fresh.has("ui")
        viewer.remove("viewer_settings")
        assert not ConfigStore(path).has("viewer_settings") and ConfigStore(path).has("devices")


def test_config_is_adopted_from_the_old_place_and_a_compiled_build_uses_the_exe_folder():
    with tempfile.TemporaryDirectory() as new, tempfile.TemporaryDirectory() as old:
        with open(os.path.join(old, "mt_config.json"), "w", encoding="utf-8") as fh:
            fh.write('{"devices": [{"ip": "10.0.0.7"}]}')
        store = ConfigStore(os.path.join(new, "mt_config.json"), fallback=[os.path.join(old, "mt_config.json")])
        assert store.get("devices") == [{"ip": "10.0.0.7"}]
        assert os.path.exists(os.path.join(old, "mt_config.json"))       # the old file stays
    assert app_dir(__file__) == os.path.dirname(os.path.abspath(__file__))
    sys.frozen, real_exe = True, sys.executable
    try:
        sys.executable = os.path.join(os.sep, "apps", "mt", "mikrotik_scanner.exe")
        assert app_dir(__file__) == os.path.join(os.sep, "apps", "mt")
    finally:
        del sys.frozen
        sys.executable = real_exe
