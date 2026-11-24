# Plan de Automatización de VPN IPSec Site-to-Site (FortiGate <-> Palo Alto)

## 1. Arquitectura y Definición de Parámetros

Se establece un túnel **IPSec Route-Based (basado en rutas)** entre un firewall **FortiGate (FortiOS)** y un firewall **Palo Alto (PAN-OS)** utilizando IKEv2 para mayor seguridad, resiliencia y menor sobrecarga de negociación.

### Topología y Direccionamiento IP

| Parámetro | Extremo A: FortiGate (Sede Central) | Extremo B: Palo Alto (Sucursal) |
| :--- | :--- | :--- |
| **Interfaz WAN (Pública)** | `port1` (`203.0.113.1/24`) | `ethernet1/1` (`198.51.100.1/24`) |
| **Gateway WAN** | `203.0.113.254` | `198.51.100.254` |
| **Red LAN Local** | `10.10.0.0/16` (`port2`) | `10.20.0.0/16` (`ethernet1/2`) |
| **Red de Túnel (`/30`)** | `169.255.1.1/30` (Interfaz virtual `VPN_TO_PA`) | `169.255.1.2/30` (Interfaz virtual `tunnel.1`) |
| **Identificador IKE (Local ID)** | `203.0.113.1` | `198.51.100.1` |

### Propuestas Criptográficas Compatibles
Para garantizar la interoperabilidad sin fallos de negociación (`NO_PROPOSAL_CHOSEN`), ambos extremos deben compartir parámetros idénticos:

* **Phase 1 (IKE Gateway / Crypto Profile):**
  * **Versión IKE:** IKEv2
  * **Modo de Autenticación:** Pre-Shared Key (PSK) almacenada en variables de entorno/Vault
  * **Cifrado (Encryption):** AES-256-CBC (o AES-256-GCM)
  * **Integridad / Hash (Authentication):** SHA-256
  * **Grupo Diffie-Hellman (DH):** Group 14 (2048-bit) o Group 19 (ECP-256)
  * **Lifetime (SA):** `86400` segundos (24 horas)
  * **Dead Peer Detection (DPD):** Habilitado (`On-Idle` / Intervalo `10s`, Reintentos `3`)
  * **NAT Traversal (NAT-T):** Habilitado (Puerto UDP 4500)

* **Phase 2 (IPSec Tunnel / Crypto Profile):**
  * **Protocolo:** ESP (Encapsulating Security Payload)
  * **Cifrado:** AES-256-CBC
  * **Integridad / Hash:** SHA-256
  * **Perfect Forward Secrecy (PFS):** Habilitado — DH Group 14
  * **Lifetime:** `3600` segundos (1 hora)
  * **Proxy IDs / Selectores de Tráfico:** `0.0.0.0/0` <-> `0.0.0.0/0` (enrutamiento controlado por tablas de rutas estáticas/BGP sobre la red `169.255.1.0/30`).

---

## 2. Identificación de Herramientas y APIs

| Fabricante | Mecanismo Principal Recomendado | Bibliotecas / Herramientas Alternativas | Justificación Técnica |
| :--- | :--- | :--- | :--- |
| **FortiGate (FortiOS)** | **FortiOS REST API** (`/api/v2/cmdb/...` y `/api/v2/monitor/...`) autenticada mediante *API Token* (Bearer). | **Ansible** (`fortinet.fortios`), **Netmiko** (`fortinet` vía SSH), **FortiManager API** (JSON-RPC). | La API REST de FortiOS aplica cambios de forma inmediata y transaccional por endpoint sin requerir un paso separado de `commit`. |
| **Palo Alto (PAN-OS)** | **PAN-OS XML API / REST API** (`/restapi/v10.2/...` o `/api/?type=config`) autenticada mediante *X-PAN-KEY*. | **pan-os-python** (SDK oficial), **Ansible** (`paloaltonetworks.panos`), **Netmiko** (`paloalto_panos`). | PAN-OS opera con configuración candidata (*Candidate Config*); requiere obligatoriamente invocar un `commit` vía API para pasar los cambios a *Running Config*. |
| **Orquestación** | **Python 3** (`requests` + Pydantic/YAML para inventario como *Single Source of Truth*). | **GitLab CI / GitHub Actions** + **HashiCorp Vault** (gestión segura de PSK y API Keys). | Permite definir los parámetros una sola vez en un archivo YAML y traducirlos al esquema específico de cada fabricante. |

---

## 3. Pasos Lógicos del Flujo de Automatización

Un script orquestador en Python debe ejecutar la configuración de forma secuencial y atómica:

1. **Carga y Validación de Variables (Single Source of Truth):**
   * Leer el archivo de intención (`vpn_intent.yaml`) y extraer secretos (`PSK`, `FORTI_TOKEN`, `PA_API_KEY`) desde variables de entorno.
   * Validar sintaxis de subredes IP y asegurar que ambos extremos utilicen exactamente los mismos algoritmos de Fase 1 y Fase 2.
2. **Pre-Checks y Respaldo (Backup):**
   * Verificar alcanzabilidad HTTPS hacia las APIs de gestión de ambos firewalls.
   * Descargar el backup actual (`GET /api/v2/monitor/system/config/backup` en FortiGate y `export configuration` en Palo Alto).
3. **Aprovisionamiento en FortiGate (API REST):**
   * **Paso 3.1:** Crear el túnel Phase 1 (`POST /api/v2/cmdb/vpn.ipsec/phase1-interface`) vinculándolo a `port1` y generando automáticamente la interfaz virtual `VPN_TO_PA`.
   * **Paso 3.2:** Crear el selector Phase 2 (`POST /api/v2/cmdb/vpn.ipsec/phase2-interface`) asociado a `VPN_TO_PA`.
   * **Paso 3.3:** Asignar la IP de túnel `169.255.1.1/30` (con `remote-ip 169.255.1.2`) en la interfaz `VPN_TO_PA` (`PUT /api/v2/cmdb/system/interface/VPN_TO_PA`).
   * **Paso 3.4:** Crear objetos de dirección (`LAN_LOCAL`, `LAN_REMOTA`) y reglas de firewall bidireccionales (`port2` <-> `VPN_TO_PA`).
   * **Paso 3.5:** Crear la ruta estática hacia `10.20.0.0/16` apuntando a `VPN_TO_PA` (`POST /api/v2/cmdb/router/static`).
4. **Aprovisionamiento en Palo Alto (PAN-OS API):**
   * **Paso 4.1:** Crear interfaz lógica `tunnel.1` con IP `169.255.1.2/30` y asignarla a la zona de seguridad `VPN-ZONE` y al `Virtual Router` predeterminado.
   * **Paso 4.2:** Crear el `IKE Crypto Profile` (Phase 1) y el `IPSec Crypto Profile` (Phase 2).
   * **Paso 4.3:** Crear el `IKE Gateway` apuntando al peer `203.0.113.1` con la PSK compartida.
   * **Paso 4.4:** Crear el `IPSec Tunnel` vinculando `tunnel.1`, el `IKE Gateway` y el `IPSec Crypto Profile`.
   * **Paso 4.5:** Configurar la ruta estática hacia `10.10.0.0/16` con *Next Hop* `169.255.1.1` en el `Virtual Router`, y crear las reglas de seguridad (`Security Policies`) permitiendo tráfico entre `TRUST-ZONE` y `VPN-ZONE`.
   * **Paso 4.6 (Commit):** Ejecutar `type=commit` y monitorear el `job-id` hasta que el estado sea `FIN` con resultado `OK`.
5. **Inicialización y Post-Validación:**
   * Generar tráfico interesante (ping desde `169.255.1.1` hacia `169.255.1.2`) para levantar las SAs y validar el estado operativo.

---

## 4. Consideraciones Específicas en Entornos Multi-Fabricante

* **Modelo de Configuración (Inmediato vs. Candidato):** FortiGate aplica cada llamada API directamente sobre la configuración activa, mientras que Palo Alto acumula cambios en una configuración candidata y exige un `commit` explícito (que puede tardar entre 15 y 45 segundos y bloquear cambios concurrentes). El script debe implementar *polling* sobre el ID de trabajo del `commit` de PAN-OS antes de iniciar las pruebas.
* **Diferencias en Nomenclatura y Valores por Defecto:**
  * Palo Alto requiere definir explícitamente los **Proxy IDs** cuando el extremo remoto no negocia `0.0.0.0/0` (en FortiGate por defecto es `0.0.0.0/0` en modo interfaz, por lo que ambos deben alinearse).
  * El cálculo de **MSS / MTU** difiere debido a la cabecera ESP/NAT-T; es necesario ajustar `tcp-mss` a `1350` bytes en las políticas/interfaces de túnel de ambos equipos para evitar fragmentación silenciosa de paquetes grandes.
* **Manejo de Zonas vs. Interfaces:** FortiGate aplica las políticas directamente sobre interfaces (`port2` -> `VPN_TO_PA`), mientras que Palo Alto exige asociar `tunnel.1` a una **Zona de Seguridad** (`VPN-ZONE`) y habilitar *Intra-zone* o políticas explícitas *Inter-zone*.
* **Idempotencia:** Antes de ejecutar un `POST` (crear), el script debe consultar con `GET` si el objeto ya existe para usar `PUT` (actualizar), evitando errores HTTP `409 Conflict` o `500` al re-ejecutar el script.

---

## 5. Estrategia de Validación y Sistema de Alertas

### Métodos de Verificación Automatizada
1. **Validación de Configuración (Config Audit):**
   * Consultar vía API los perfiles de Phase 1 y Phase 2 en ambos dispositivos y comparar sus hashes/parámetros contra el archivo `vpn_intent.yaml` (*Drift Detection*).
2. **Validación de Estado Operativo (Control Plane):**
   * **FortiGate:** Consultar `GET /api/v2/monitor/vpn/ipsec` y verificar que el estado del túnel `VPN_TO_PA` sea `up` y que existan contadores `incoming_bytes > 0` y `outgoing_bytes > 0`.
   * **Palo Alto:** Ejecutar el comando operacional vía XML API `<show><vpn><flow><name>IPSEC_TO_FG</name></flow></vpn></show>` y confirmar que `state` sea `active` y `encap/decap` incrementen.
3. **Validación de Plano de Datos (Data Plane):**
   * Ejecutar pruebas ICMP/TCP desde la red `10.10.0.0/16` hacia `10.20.0.0/16` y entre las IPs de túnel (`169.255.1.1` <-> `169.255.1.2`).

### Generación de Alertas
Si alguna validación falla o se detecta una desviación:
* **Severidad Crítica (Túnel Caído / Error de Commit):** Envío inmediato de notificación estructurada (JSON) mediante **Webhook a Slack / Microsoft Teams** y creación de incidente automático vía API en **Jira / ServiceNow**, adjuntando el log de error de IKE (`diagnose debug application ike` / `less mp-log ikemgr.log`).
* **Severidad Advertencia (Desviación de Configuración):** Si un administrador modifica manualmente un parámetro en alguno de los firewalls, el script de auditoría programado (Cron/CI) dispara una alerta por correo SMTP/Webhook y puede ejecutar auto-remediación (*self-healing*) reaplicando el estado deseado.
