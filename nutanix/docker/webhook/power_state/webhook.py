from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid
import requests
import urllib3
import configparser

# Desactivar advertencias de SSL (solo en entorno controlado)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
captured_events = []

# Leer configuración
config = configparser.ConfigParser()
config.read('config.ini')

PROJECT_FILTER = config['general']['project_filter']
PRISM_CENTRAL = config['general']['prism_central']
PRISM_USER = config['general']['prism_user']
PRISM_PASS = config['general']['prism_pass']

SMTP_SERVER = config['smtp']['server']
SMTP_PORT = int(config['smtp']['port'])
EMAIL_FROM = config['smtp']['from']
EMAIL_TO = config['smtp']['to']

# --- Función para enviar correo ---
def send_email(event_record):
    subject = f"[Nutanix VM] Evento de energía: {event_record['event_type'].upper()}"
    body = f"""
    Se ha registrado un evento de energía en una VM Nutanix.

    🔌 Tipo de evento: {event_record['event_type']}
    🖥 Nombre de la VM: {event_record['vm_name']}
    🌐 IP de la VM: {event_record['vm_ip']}
    🕒 Timestamp: {event_record['timestamp']}
    """

    message = MIMEMultipart()
    message["From"] = EMAIL_FROM
    message["To"] = EMAIL_TO
    message["Subject"] = subject
    message["Message-ID"] = f"<{uuid.uuid4()}@velocitycloud.us>"
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(EMAIL_FROM, EMAIL_TO, message.as_string())
        print("📧 Correo enviado con éxito.")
    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")

# --- Obtener proyecto desde Prism Central ---
def get_project_from_vm(vm_uuid):
    try:
        url = f"https://{PRISM_CENTRAL}:9440/api/nutanix/v3/vms/{vm_uuid}"
        response = requests.get(url, auth=(PRISM_USER, PRISM_PASS), verify=False)
        if response.status_code == 200:
            vm_data = response.json()
            return vm_data.get("metadata", {}).get("project_reference", {}).get("name")
        else:
            print(f"⚠️ Error al consultar Prism Central: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error al obtener datos de la VM: {e}")
        return None

# --- Ruta principal del webhook ---
@app.route('/webhook', methods=['POST'])
def nutanix_webhook():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid or empty payload"}), 400

    print("🔔 Evento recibido")

    event_type = data.get("event_type", "").lower()
    vm_uuid = data.get("entity_reference", {}).get("uuid")
    if not vm_uuid:
        return jsonify({"error": "No VM UUID found"}), 400

    # Verificar proyecto asociado a la VM
    project = get_project_from_vm(vm_uuid)
    if project != PROJECT_FILTER:
        print(f"🔕 Evento ignorado: VM no pertenece al proyecto '{PROJECT_FILTER}'")
        return jsonify({"status": "event ignored - wrong project"}), 200

    # Obtener nombre e IP de la VM
    vm_name = data.get("data", {}).get("metadata", {}).get("status", {}).get("name", "unknown")
    nic_list = data.get("data", {}).get("metadata", {}).get("status", {}).get("resources", {}).get("nic_list", [])
    vm_ip = "unknown"
    if nic_list:
        ip_list = nic_list[0].get("ip_endpoint_list", [])
        if ip_list and isinstance(ip_list, list) and "ip" in ip_list[0]:
            vm_ip = ip_list[0]["ip"]

    # Timestamp
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

    if event_type:
        event_record = {
            "event_type": event_type,
            "vm_name": vm_name,
            "vm_ip": vm_ip,
            "timestamp": timestamp
        }
        captured_events.append(event_record)
        print("✅ Evento registrado:", event_record)
        send_email(event_record)
        return jsonify({"status": "event captured", "event": event_record}), 200

    return jsonify({"status": "event ignored"}), 200

# --- Ver historial de eventos ---
@app.route('/events', methods=['GET'])
def get_events():
    return jsonify(captured_events), 200

@app.route('/web', methods=['GET'])
def view_events():
    html_template = """
    <!doctype html>
    <html>
    <head>
        <title>Eventos Nutanix</title>
        <meta http-equiv="refresh" content="10"> <!-- refresca cada 10 segundos -->
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h2>Eventos VMs Nutanix</h2>
        <table>
            <tr>
                <th>Timestamp</th>
                <th>Evento</th>
                <th>VM Name</th>
                <th>IP</th>
            </tr>
            {% for event in events %}
            <tr>
                <td>{{ event.timestamp }}</td>
                <td>{{ event.event_type }}</td>
                <td>{{ event.vm_name }}</td>
                <td>{{ event.vm_ip }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """
    return render_template_string(html_template, events=captured_events)

# --- Iniciar la app ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
