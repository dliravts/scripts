#!/usr/bin/env python3
import os
import time
import datetime
import threading
import requests
import boto3
from flask import Flask, Response
from botocore.exceptions import ClientError

app = Flask(__name__)
metrics_output = ""  # Se actualiza cada hora desde el thread

def get_bucket_tags(s3_client, bucket_name):
    try:
        tag_set = s3_client.get_bucket_tagging(Bucket=bucket_name)
        tags = {tag['Key']: tag['Value'] for tag in tag_set['TagSet']}
        return tags
    except ClientError as e:
        return {}  # bucket sin tags o acceso denegado

def fetch_metrics():
    global metrics_output
    while True:


        access_key = os.getenv("WASABI_ACCESS_KEY")
        secret_key = os.getenv("WASABI_SECRET_KEY")

        if not access_key or not secret_key:
            metrics_output = "# ERROR: Missing WASABI_ACCESS_KEY or WASABI_SECRET_KEY\n"
            time.sleep(3600)
            continue

        # Cliente boto3 para Wasabi
        session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='us-east-1'
        )
        s3_client = session.client('s3', endpoint_url='https://s3.wasabisys.com')

        try:
            response = requests.get(
                "https://billing.wasabisys.com/utilization/bucket/?withname=true",
                headers={"Authorization": f'{access_key}:{secret_key}'}
            )
            json_data = response.json()
        except Exception as e:
            metrics_output = f"# ERROR: Failed to fetch Wasabi data: {str(e)}\n"
            time.sleep(3600)
            continue

        try:
            initial_time = datetime.datetime.strptime(json_data[0]['StartTime'], '%Y-%m-%dT%H:%M:%SZ')
        except Exception as e:
            metrics_output = f"# ERROR: Invalid JSON structure or StartTime missing: {str(e)}\n"
            time.sleep(3600)
            continue

        buckets = list(set(bucket['Bucket'] for bucket in json_data))

        lines = []
        lines.append('# HELP wasabi_active_storage_bytes Active storage in bytes per bucket')
        lines.append('# TYPE wasabi_active_storage_bytes gauge')
        lines.append('# HELP wasabi_deleted_storage_bytes Deleted storage in bytes per bucket')
        lines.append('# TYPE wasabi_deleted_storage_bytes gauge')
        lines.append('# HELP wasabi_billable_objects Number of billable objects per bucket')
        lines.append('# TYPE wasabi_billable_objects gauge')
        lines.append('# HELP wasabi_deleted_billable_objects Number of deleted billable objects per bucket')
        lines.append('# TYPE wasabi_deleted_billable_objects gauge')

        try:
            contract_response = requests.get("https://velocityshare.s3.wasabisys.com/internal/wasabi_contract.txt")
            if contract_response.status_code == 200:
                contracted_bytes_str = contract_response.text.strip()
                contracted_bytes = int(contracted_bytes_str)
                lines.append('# HELP wasabi_total_contracted_bytes Total Wasabi storage contracted in bytes')
                lines.append('# TYPE wasabi_total_contracted_bytes gauge')
                lines.append(f'wasabi_total_contracted_bytes {contracted_bytes}')
            else:
                lines.append(f'# ERROR: Failed to fetch contracted value, status {contract_response.status_code}')
        except Exception as e:
            lines.append(f'# ERROR: Exception while fetching contracted value: {str(e)}')

        try:
            csv_response = requests.get("https://velocityshare.s3.wasabisys.com/internal/wasabi_contract_customers.csv")
            if csv_response.status_code == 200:
                lines.append('# HELP wasabi_customer_contracted_bytes Contracted Wasabi storage per customer in bytes')
                lines.append('# TYPE wasabi_customer_contracted_bytes gauge')
                lines.append('# HELP wasabi_contract_term_months Contract term length in months')
                lines.append('# TYPE wasabi_contract_term_months gauge')
                lines.append('# HELP wasabi_service_start_timestamp Service start date as Unix timestamp')
                lines.append('# TYPE wasabi_service_start_timestamp gauge')
                lines.append('# HELP wasabi_service_end_timestamp Service end date as Unix timestamp')
                lines.append('# TYPE wasabi_service_end_timestamp gauge')
                lines.append('# HELP wasabi_days_until_contract_expires Days remaining until contract expiration (can be negative)')
                lines.append('# TYPE wasabi_days_until_contract_expires gauge')

                csv_lines = csv_response.text.strip().splitlines()
                for row in csv_lines[1:]:  # Saltar encabezado
                    parts = row.strip().split(",")
                    if len(parts) < 3:
                        continue

                    customer = parts[0].strip()
                    site = parts[1].strip()
                    contract_tib = parts[2].strip()

                    labels = f'customer="{customer}",site="{site}"'

                    # Métrica de espacio contratado
                    try:
                        contract_bytes = int(contract_tib) * 1024**4
                        lines.append(f'wasabi_customer_contracted_bytes{{{labels}}} {contract_bytes}')
                    except ValueError:
                        lines.append(f'# ERROR: Invalid contract value in row: {row}')
                        continue

                    # Verificar si hay campos adicionales para fechas y término
                    term = 0
                    start_ts = None
                    end_ts = None

                    if len(parts) >= 5:
                        term_str = parts[3].strip()
                        start_str = parts[4].strip()
                        end_str = parts[5].strip() if len(parts) > 5 else ""

                        try:
                            term = int(term_str)
                            lines.append(f'wasabi_contract_term_months{{{labels}}} {term}')
                        except ValueError:
                            pass  # ignorar término inválido

                        try:
                            start_dt = datetime.datetime.strptime(start_str, "%m/%d/%y")
                            lines.append(f'wasabi_service_start_timestamp{{{labels}}} {int(start_dt.timestamp())}')
                        except Exception:
                            start_dt = None  # No se pudo parsear

                        try:
                            end_dt = datetime.datetime.strptime(end_str, "%m/%d/%y")
                            lines.append(f'wasabi_service_end_timestamp{{{labels}}} {int(end_dt.timestamp())}')
                        except Exception:
                            end_dt = None

                        if end_dt:
                            now = datetime.datetime.utcnow()
                            days_left = (end_dt - now).days
                            lines.append(f'wasabi_days_until_contract_expires{{{labels}}} {days_left}')

            else:
                lines.append(f'# ERROR: Failed to fetch contract CSV, status {csv_response.status_code}')
        except Exception as e:
            lines.append(f'# ERROR: Exception while fetching contract CSV: {str(e)}')

        for b in buckets:
            result = {
                'PaddedStorageSizeBytes': 0,
                'DeletedStorageSizeBytes': 0,
                'NumBillableObjects': 0,
                'NumBillableDeletedObjects': 0
            }

            for bucket in json_data:
                if bucket['Bucket'] == b:
                    time_bucket = datetime.datetime.strptime(bucket['StartTime'], '%Y-%m-%dT%H:%M:%SZ')
                    if time_bucket.date() == initial_time.date():
                        result['PaddedStorageSizeBytes'] += bucket['PaddedStorageSizeBytes']
                        result['DeletedStorageSizeBytes'] += bucket['DeletedStorageSizeBytes']
                        result['NumBillableObjects'] += bucket['NumBillableObjects']
                        result['NumBillableDeletedObjects'] += bucket['NumBillableDeletedObjects']

            # Tags como etiquetas adicionales en Prometheus
            tags = get_bucket_tags(s3_client, b)
            if not tags:
                tags = {"untagged": "true"}  # Etiqueta por defecto si no tiene tags

            tag_str = ",".join([f'{k}="{v}"' for k, v in tags.items()])
            labels = f'bucket="{b}",{tag_str}'

            lines.append(f'wasabi_active_storage_bytes{{{labels}}} {result["PaddedStorageSizeBytes"]}')
            lines.append(f'wasabi_deleted_storage_bytes{{{labels}}} {result["DeletedStorageSizeBytes"]}')
            lines.append(f'wasabi_billable_objects{{{labels}}} {result["NumBillableObjects"]}')
            lines.append(f'wasabi_deleted_billable_objects{{{labels}}} {result["NumBillableDeletedObjects"]}')

        metrics_output = "\n".join(lines) + "\n"
        print(f"[{datetime.datetime.now()}] Metrics updated.")
        time.sleep(600)

@app.route('/metrics')
def metrics():
    return Response(metrics_output, mimetype='text/plain')

def start_background_thread():
    thread = threading.Thread(target=fetch_metrics)
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    start_background_thread()
    app.run(host='0.0.0.0', port=9150)
