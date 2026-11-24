import os
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FG_HOST = os.getenv("FG_HOST", "https://203.0.113.1")
FG_TOKEN = os.getenv("FG_API_TOKEN", "TOKEN_DE_EJEMPLO")
VPN_PSK = os.getenv("VPN_PSK", "ClaveSuperSegura2026!")

HEADERS = {
    "Authorization": f"Bearer {FG_TOKEN}",
    "Content-Type": "application/json",
}

def configurar_fortigate_vpn():
    # 1. Crear Phase 1 (IKEv2)
    phase1_payload = {
        "name": "VPN_TO_PA",
        "interface": "port1",
        "ike-version": "2",
        "peertype": "any",
        "proposal": "aes256-sha256",
        "dhgrp": "14",
        "keylife": 86400,
        "remote-gw": "198.51.100.1",
        "psksecret": VPN_PSK,
        "dpd": "on-idle",
    }
    r1 = requests.post(
        f"{FG_HOST}/api/v2/cmdb/vpn.ipsec/phase1-interface",
        json=phase1_payload,
        headers=HEADERS,
        verify=False,
    )
    print(f"[FortiGate] Phase 1 status: {r1.status_code}")

    # 2. Crear Phase 2
    phase2_payload = {
        "name": "VPN_TO_PA_P2",
        "phase1name": "VPN_TO_PA",
        "proposal": "aes256-sha256",
        "pfs": "enable",
        "dhgrp": "14",
        "keylifeseconds": 3600,
    }
    r2 = requests.post(
        f"{FG_HOST}/api/v2/cmdb/vpn.ipsec/phase2-interface",
        json=phase2_payload,
        headers=HEADERS,
        verify=False,
    )
    print(f"[FortiGate] Phase 2 status: {r2.status_code}")

    # 3. Asignar IP de túnel 169.255.1.1/30
    iface_payload = {
        "ip": "169.255.1.1 255.255.255.252",
        "remote-ip": "169.255.1.2 255.255.255.252",
        "allowaccess": "ping",
    }
    r3 = requests.put(
        f"{FG_HOST}/api/v2/cmdb/system/interface/VPN_TO_PA",
        json=iface_payload,
        headers=HEADERS,
        verify=False,
    )
    print(f"[FortiGate] Tunnel Interface IP status: {r3.status_code}")

    # 4. Ruta estática hacia LAN remota (10.20.0.0/16)
    route_payload = {
        "dst": "10.20.0.0 255.255.0.0",
        "device": "VPN_TO_PA",
    }
    r4 = requests.post(
        f"{FG_HOST}/api/v2/cmdb/router/static",
        json=route_payload,
        headers=HEADERS,
        verify=False,
    )
    print(f"[FortiGate] Static Route status: {r4.status_code}")

if __name__ == "__main__":
    configurar_fortigate_vpn()
