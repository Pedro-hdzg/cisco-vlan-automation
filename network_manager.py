import os
from datetime import datetime
from netmiko import ConnectHandler

def configurar_y_validar_switch(device_info, hostname, vlans):
    resultados = {"status": "success", "mensajes": [], "alertas": []}
    
    try:
        conexion = ConnectHandler(**device_info)
        conexion.enable()

        # Configurar Hostname y VLANs
        comandos = [f"hostname {hostname}"]
        for vlan in vlans:
            comandos.append(f"vlan {vlan['id']}")
            comandos.append(f"name {vlan['name']}")
        
        conexion.send_config_set(comandos)
        resultados["mensajes"].append("Configuración de Hostname y VLANs aplicada.")

        # Guardar en NVRAM
        conexion.save_config()
        resultados["mensajes"].append("Configuración guardada en NVRAM (write memory).")

        # Backup local
        running_config = conexion.send_command("show running-config")
        os.makedirs("backups", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backups/{hostname}_{timestamp}.txt"
        
        with open(backup_filename, "w") as f:
            f.write(running_config)
        resultados["mensajes"].append(f"Backup guardado en: {backup_filename}")

        # Validación de Configuración
        alertas = validar_configuracion(conexion, hostname, vlans)
        resultados["alertas"] = alertas

        conexion.disconnect()
        
    except Exception as e:
        resultados["status"] = "error"
        resultados["mensajes"].append(f"Error de conexión o ejecución: {str(e)}")
        
    return resultados

def validar_configuracion(conexion, hostname_esperado, vlans_esperadas):
    alertas = []
    
    run_config = conexion.send_command("show running-config | include hostname")
    if f"hostname {hostname_esperado}" not in run_config:
        alertas.append(f"ALERTA: El hostname actual no coincide con '{hostname_esperado}'.")

    vlan_output = conexion.send_command("show vlan brief")
    for vlan in vlans_esperadas:
        if vlan['id'] not in vlan_output or vlan['name'] not in vlan_output:
            alertas.append(f"ALERTA: Desviación detectada en VLAN {vlan['id']} ({vlan['name']}).")
            
    return alertas
