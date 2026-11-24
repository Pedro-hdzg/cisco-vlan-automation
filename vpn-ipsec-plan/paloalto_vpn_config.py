import os
import time
import xml.etree.ElementTree as ET
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PA_HOST = os.getenv("PA_HOST", "https://198.51.100.1")
PA_API_KEY = os.getenv("PA_API_KEY", "API_KEY_DE_EJEMPLO")
VPN_PSK = os.getenv("VPN_PSK", "ClaveSuperSegura2026!")

def panos_api_call(params):
    params["key"] = PA_API_KEY
    resp = requests.get(f"{PA_HOST}/api/", params=params, verify=False)
    resp.raise_for_status()
    return ET.fromstring(resp.text)

def configurar_paloalto_vpn():
    # 1. Configurar IKE Crypto Profile (Phase 1)
    ike_crypto_xpath = "/config/devices/entry[@name='localhost.localdomain']/network/ike/crypto-profiles/ike-crypto-profiles/entry[@name='IKE-P1-AES256']"
    ike_crypto_xml = "<hash><member>sha256</member></hash><dh-group><member>group14</member></dh-group><encryption><member>aes-256-cbc</member></encryption><lifetime><seconds>86400</seconds></lifetime>"
    panos_api_call({"type": "config", "action": "set", "xpath": ike_crypto_xpath, "element": ike_crypto_xml})
    print("[Palo Alto] IKE Crypto Profile configurado.")

    # 2. Configurar IPSec Crypto Profile (Phase 2)
    ipsec_crypto_xpath = "/config/devices/entry[@name='localhost.localdomain']/network/ike/crypto-profiles/ipsec-crypto-profiles/entry[@name='IPSEC-P2-AES256']"
    ipsec_crypto_xml = "<esp><authentication><member>sha256</member></authentication><encryption><member>aes-256-cbc</member></encryption></esp><dh-group>group14</dh-group><lifetime><seconds>3600</seconds></lifetime>"
    panos_api_call({"type": "config", "action": "set", "xpath": ipsec_crypto_xpath, "element": ipsec_crypto_xml})
    print("[Palo Alto] IPSec Crypto Profile configurado.")

    # 3. Configurar Interfaz tunnel.1 (169.255.1.2/30)
    tunnel_if_xpath = "/config/devices/entry[@name='localhost.localdomain']/network/interface/tunnel/units/entry[@name='tunnel.1']"
    tunnel_if_xml = "<ip><entry name='169.255.1.2/30'/></ip><comment>VPN hacia FortiGate</comment>"
    panos_api_call({"type": "config", "action": "set", "xpath": tunnel_if_xpath, "element": tunnel_if_xml})
    print("[Palo Alto] Interfaz tunnel.1 (169.255.1.2/30) configurada.")

    # 4. Configurar IKE Gateway
    ike_gw_xpath = "/config/devices/entry[@name='localhost.localdomain']/network/ike/gateway/entry[@name='GW-TO-FORTIGATE']"
    ike_gw_xml = f"<authentication><pre-shared-key><key>{VPN_PSK}</key></pre-shared-key></authentication><protocol><ikev2><ike-crypto-profile>IKE-P1-AES256</ike-crypto-profile></ikev2><version>ikev2</version></protocol><local-address><interface>ethernet1/1</interface><ip>198.51.100.1/24</ip></local-address><peer-address><ip>203.0.113.1</ip></peer-address>"
    panos_api_call({"type": "config", "action": "set", "xpath": ike_gw_xpath, "element": ike_gw_xml})
    print("[Palo Alto] IKE Gateway configurado.")

    # 5. Ejecutar Commit en PAN-OS
    commit_res = panos_api_call({"type": "commit", "cmd": "<commit></commit>"})
    job_id = commit_res.findtext(".//job")
    print(f"[Palo Alto] Commit iniciado (Job ID: {job_id}). Esperando finalización...")

    while True:
        job_status = panos_api_call({"type": "op", "cmd": f"<show><jobs><id>{job_id}</id></jobs></show>"})
        status = job_status.findtext(".//status")
        if status == "FIN":
            result = job_status.findtext(".//result")
            print(f"[Palo Alto] Commit finalizado con resultado: {result}")
            break
        time.sleep(5)

if __name__ == "__main__":
    configurar_paloalto_vpn()
