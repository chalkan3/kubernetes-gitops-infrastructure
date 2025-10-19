#!/usr/bin/env python3
import os
import subprocess
import json
import logging
import requests
from flask import Flask, request

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
NTFY_URL = os.getenv('NTFY_URL', 'https://ntfy.sh')
NTFY_TOPIC = os.getenv('NTFY_TOPIC', 'k8s-pvc-monitor')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'kubernetes')
WARNING_THRESHOLD = int(os.getenv('WARNING_THRESHOLD', '80'))
CRITICAL_THRESHOLD = int(os.getenv('CRITICAL_THRESHOLD', '90'))

def send_ntfy_notification(title, message, priority="default", tags=None):
    """Envia notificação via ntfy"""
    try:
        title_clean = title.encode('ascii', 'ignore').decode('ascii')
        message_clean = message.encode('utf-8')

        headers = {
            "Title": title_clean,
            "Priority": priority,
            "Content-Type": "text/plain; charset=utf-8"
        }

        if tags:
            tags_clean = [str(tag).encode('ascii', 'ignore').decode('ascii') for tag in (tags if isinstance(tags, list) else [tags])]
            headers["Tags"] = ",".join(tags_clean)

        response = requests.post(
            f"{NTFY_URL}/{NTFY_TOPIC}",
            data=message_clean,
            headers=headers
        )

        if response.status_code == 200:
            logger.info(f"Notificacao enviada: {title}")
            return True
        else:
            logger.error(f"Erro ao enviar notificacao: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Erro ao enviar notificacao: {str(e)}")
        return False

def get_pvc_usage():
    """Obtém uso de PVCs no cluster"""
    try:
        # Lista todos os PVCs
        result = subprocess.run(
            ['kubectl', 'get', 'pvc', '-A', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Erro ao listar PVCs: {result.stderr}")
            return []

        pvcs = json.loads(result.stdout)
        pvc_usage = []

        for pvc in pvcs.get('items', []):
            namespace = pvc['metadata']['namespace']
            name = pvc['metadata']['name']

            # Verifica se PVC está bound
            if pvc['status'].get('phase') != 'Bound':
                continue

            # Tenta obter informações de uso do PVC
            usage_info = get_pvc_disk_usage(namespace, name)
            if usage_info:
                pvc_usage.append({
                    'namespace': namespace,
                    'name': name,
                    'capacity': pvc['spec']['resources']['requests'].get('storage', 'unknown'),
                    **usage_info
                })

        return pvc_usage

    except Exception as e:
        logger.error(f"Erro ao obter uso de PVCs: {str(e)}")
        return []

def get_pvc_disk_usage(namespace, pvc_name):
    """Obtém uso de disco de um PVC específico"""
    try:
        # Encontra pods que usam este PVC
        result = subprocess.run(
            ['kubectl', 'get', 'pods', '-n', namespace, '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return None

        pods = json.loads(result.stdout)

        for pod in pods.get('items', []):
            # Verifica se pod usa o PVC
            volumes = pod['spec'].get('volumes', [])
            uses_pvc = any(
                v.get('persistentVolumeClaim', {}).get('claimName') == pvc_name
                for v in volumes
            )

            if not uses_pvc or pod['status'].get('phase') != 'Running':
                continue

            # Encontra o mount path do PVC
            mount_path = None
            for container in pod['spec'].get('containers', []):
                for mount in container.get('volumeMounts', []):
                    # Encontra o volume correspondente
                    for vol in volumes:
                        if vol.get('name') == mount.get('name'):
                            if vol.get('persistentVolumeClaim', {}).get('claimName') == pvc_name:
                                mount_path = mount.get('mountPath')
                                break
                    if mount_path:
                        break
                if mount_path:
                    break

            if not mount_path:
                continue

            # Executa df no pod para obter uso
            pod_name = pod['metadata']['name']
            container_name = pod['spec']['containers'][0]['name']

            df_result = subprocess.run(
                ['kubectl', 'exec', '-n', namespace, pod_name,
                 '-c', container_name, '--', 'df', '-h', mount_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            if df_result.returncode != 0:
                continue

            # Parse output do df
            lines = df_result.stdout.strip().split('\n')
            if len(lines) >= 2:
                fields = lines[1].split()
                if len(fields) >= 5:
                    return {
                        'used': fields[2],
                        'available': fields[3],
                        'usage_percent': int(fields[4].rstrip('%')),
                        'pod': f"{namespace}/{pod_name}"
                    }

        return None

    except Exception as e:
        logger.error(f"Erro ao obter uso do PVC {namespace}/{pvc_name}: {str(e)}")
        return None

def check_pvc_storage():
    """Verifica uso de storage dos PVCs"""
    logger.info("Iniciando verificação de PVCs...")

    pvc_usage = get_pvc_usage()

    warnings = []
    criticals = []

    for pvc in pvc_usage:
        usage_percent = pvc.get('usage_percent', 0)

        if usage_percent >= CRITICAL_THRESHOLD:
            criticals.append(pvc)
        elif usage_percent >= WARNING_THRESHOLD:
            warnings.append(pvc)

    # Envia notificações
    if criticals:
        message = f"🔴 CRITICAL: {len(criticals)} PVC(s) com uso crítico de disco no cluster {CLUSTER_NAME}:\n\n"
        for pvc in criticals:
            message += f"• {pvc['namespace']}/{pvc['name']}: {pvc['usage_percent']}% usado ({pvc['used']}/{pvc['capacity']})\n"
            message += f"  Pod: {pvc['pod']}\n"

        send_ntfy_notification(
            f"CRITICAL: PVC Storage Alert - {CLUSTER_NAME}",
            message,
            priority="urgent",
            tags=["rotating_light", "warning"]
        )

    if warnings:
        message = f"⚠️ WARNING: {len(warnings)} PVC(s) com uso alto de disco no cluster {CLUSTER_NAME}:\n\n"
        for pvc in warnings:
            message += f"• {pvc['namespace']}/{pvc['name']}: {pvc['usage_percent']}% usado ({pvc['used']}/{pvc['capacity']})\n"
            message += f"  Pod: {pvc['pod']}\n"

        send_ntfy_notification(
            f"WARNING: PVC Storage Alert - {CLUSTER_NAME}",
            message,
            priority="high",
            tags=["warning"]
        )

    if not criticals and not warnings:
        logger.info(f"Todos os {len(pvc_usage)} PVCs estão com uso normal de disco")

    return {
        'total_pvcs': len(pvc_usage),
        'warnings': len(warnings),
        'criticals': len(criticals)
    }

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy'}, 200

@app.route('/check', methods=['POST'])
def check():
    """Endpoint para verificar PVCs"""
    try:
        result = check_pvc_storage()
        return result, 200
    except Exception as e:
        logger.error(f"Erro ao verificar PVCs: {str(e)}")
        return {'error': str(e)}, 500

if __name__ == '__main__':
    logger.info("Iniciando PVC Storage Monitor...")
    app.run(host='0.0.0.0', port=8080, debug=False)
