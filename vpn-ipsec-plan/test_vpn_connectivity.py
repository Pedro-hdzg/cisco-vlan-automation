import os
import subprocess
import platform
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FG_HOST = os.getenv("FG_HOST", "https://203.0.113.1")
FG_TOKEN = os.getenv("FG_API_TOKEN", "TOKEN_DE_EJEMPLO")
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

def enviar_alerta(mensaje):
    print(f"🚨 [ALERTA CRÍTICA]: {mensaje}")
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"text": f"🚨 Alerta VPN IPSec: {mensaje}"})

def verificar_ping(destino_ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    comando = ["ping", param, "3", destino_ip]
    resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return resultado.returncode == 0

def auditar_estado_vpn():
    errores = []

    # 1. Verificar estado de Phase 2 en FortiGate vía API Monitor
    try:
        headers = {"Authorization": f"Bearer {FG_TOKEN}"}
        resp = requests.get(f"{FG_HOST}/api/v2/monitor/vpn/ipsec", headers=headers, verify=False, timeout=5)
        data = resp.json()
        tuneles = data.get("results", [])
        tunel_activo = any(t.get("name") == "VPN_TO_PA" and t.get("proxyid", [{}])[0].get("status") == "up" for t in tuneles)
        if not tunel_activo:
            errores.append("El túnel IPSec 'VPN_TO_PA' figura como DOWN en FortiGate.")
    except Exception as e:
        errores.append(f"No se pudo consultar la API de monitoreo de FortiGate: {e}")

    # 2. Verificar conectividad de extremo a extremo (Plano de Datos)
    for ip_objetivo, descripcion in [("169.255.1.2", "IP Túnel Palo Alto"), ("10.20.0.1", "Gateway LAN Sucursal Palo Alto")]:
        if verificar_ping(ip_objetivo):
            print(f"✅ [OK] Conectividad exitosa hacia {descripcion} ({ip_objetivo}).")
        else:
            errores.append(f"Pérdida de conectividad ICMP hacia {descripcion} ({ip_objetivo}).")

    # 3. Disparar alertas si existen desviaciones o fallas
    if errores:
        for err in errores:
            enviar_alerta(err)
    else:
        print("✅ Auditoría completada: Túnel IPSec operativo y sin desviaciones.")

if __name__ == "__main__":
    auditar_estado_vpn()
