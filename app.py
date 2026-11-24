from flask import Flask, render_template, request
from network_manager import configurar_y_validar_switch

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    resultado = None
    if request.method == "POST":
        device_info = {
            "device_type": "cisco_ios",
            "host": request.form.get("ip_switch"),
            "username": request.form.get("username"),
            "password": request.form.get("password"),
            "secret": request.form.get("secret"),
            "disabled_algorithms": {"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]},
        }
        
        hostname = request.form.get("hostname")
        
        vlans = [
            {"id": request.form.get("vlan1_id"), "name": request.form.get("vlan1_name")},
            {"id": request.form.get("vlan2_id"), "name": request.form.get("vlan2_name")},
            {"id": request.form.get("vlan3_id"), "name": request.form.get("vlan3_name")},
        ]
        vlans = [v for v in vlans if v["id"] and v["name"]]

        resultado = configurar_y_validar_switch(device_info, hostname, vlans)

    return render_template("index.html", resultado=resultado)

@app.route("/validar", methods=["POST"])
def solo_validar():
    from netmiko import ConnectHandler
    from network_manager import validar_configuracion
    device_info = {
        "device_type": "cisco_ios",
        "host": request.form.get("ip_switch"),
        "username": request.form.get("username"),
        "password": request.form.get("password"),
        "secret": request.form.get("secret"),
        "disabled_algorithms": {"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]},
    }
    conexion = ConnectHandler(**device_info)
    conexion.enable()
    vlans = [
        {"id": "10", "name": "VLAN_DATOS"},
        {"id": "20", "name": "VLAN_VOZ"},
        {"id": "50", "name": "VLAN_SEGURIDAD"},
    ]
    alertas = validar_configuracion(conexion, "SWITCH_AUTOMATIZADO", vlans)
    conexion.disconnect()
    resultado = {
        "status": "warning",
        "mensajes": ["Auditoría de configuración ejecutada."],
        "alertas": alertas,
    }
    return render_template("index.html", resultado=resultado)


if __name__ == "__main__":

    app.run(debug=True)
