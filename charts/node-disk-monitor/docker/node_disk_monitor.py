#!/usr/bin/env python3
import os
import subprocess
import json
import logging
import requests
from flask import Flask

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
NTFY_URL = os.getenv('NTFY_URL', 'https://ntfy.sh')
NTFY_TOPIC = os.getenv('NTFY_TOPIC', 'k8s-node-disk-monitor')
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

def get_node_disk_usage():
    """Obtém uso de disco dos nodes do cluster"""
    try:
        # Lista todos os nodes
        result = subprocess.run(
            ['kubectl', 'get', 'nodes', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Erro ao listar nodes: {result.stderr}")
            return []

        nodes = json.loads(result.stdout)
        node_usage = []

        for node in nodes.get('items', []):
            node_name = node['metadata']['name']

            # Verifica se node está Ready
            is_ready = any(
                condition['type'] == 'Ready' and condition['status'] == 'True'
                for condition in node['status'].get('conditions', [])
            )

            if not is_ready:
                logger.warning(f"Node {node_name} not Ready, skipping")
                continue

            # Obtém informações de uso de disco via kubectl debug
            disk_info = get_node_disk_info(node_name)
            if disk_info:
                node_usage.append({
                    'node': node_name,
                    **disk_info
                })

        return node_usage

    except Exception as e:
        logger.error(f"Erro ao obter uso de disco dos nodes: {str(e)}")
        return []

def get_node_disk_info(node_name):
    """Obtém informações de disco de um node específico"""
    try:
        # Usa kubectl top node para obter informações de disco
        # Nota: Esta abordagem usa métricas do node
        result = subprocess.run(
            ['kubectl', 'get', '--raw', f'/api/v1/nodes/{node_name}/proxy/stats/summary'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.error(f"Erro ao obter stats do node {node_name}")
            return None

        stats = json.loads(result.stdout)
        fs_stats = stats.get('node', {}).get('fs', {})

        if not fs_stats:
            return None

        used_bytes = fs_stats.get('usedBytes', 0)
        capacity_bytes = fs_stats.get('capacityBytes', 1)
        available_bytes = fs_stats.get('availableBytes', 0)

        usage_percent = int((used_bytes / capacity_bytes) * 100) if capacity_bytes > 0 else 0

        # Converte bytes para GB
        used_gb = used_bytes / (1024**3)
        capacity_gb = capacity_bytes / (1024**3)
        available_gb = available_bytes / (1024**3)

        return {
            'used_gb': f"{used_gb:.2f}",
            'capacity_gb': f"{capacity_gb:.2f}",
            'available_gb': f"{available_gb:.2f}",
            'usage_percent': usage_percent
        }

    except Exception as e:
        logger.error(f"Erro ao obter informações do node {node_name}: {str(e)}")
        return None

def check_node_disk_space():
    """Verifica espaço em disco dos nodes"""
    logger.info("Iniciando verificação de disco dos nodes...")

    node_usage = get_node_disk_usage()

    warnings = []
    criticals = []

    for node in node_usage:
        usage_percent = node.get('usage_percent', 0)

        if usage_percent >= CRITICAL_THRESHOLD:
            criticals.append(node)
        elif usage_percent >= WARNING_THRESHOLD:
            warnings.append(node)

    # Envia notificações
    if criticals:
        message = f"🔴 CRITICAL: {len(criticals)} node(s) com disco crítico no cluster {CLUSTER_NAME}:\n\n"
        for node in criticals:
            message += f"• {node['node']}: {node['usage_percent']}% usado\n"
            message += f"  Usado: {node['used_gb']}GB / {node['capacity_gb']}GB\n"
            message += f"  Disponível: {node['available_gb']}GB\n"

        send_ntfy_notification(
            f"CRITICAL: Node Disk Alert - {CLUSTER_NAME}",
            message,
            priority="urgent",
            tags=["rotating_light", "warning", "cd"]
        )

    if warnings:
        message = f"⚠️ WARNING: {len(warnings)} node(s) com disco alto no cluster {CLUSTER_NAME}:\n\n"
        for node in warnings:
            message += f"• {node['node']}: {node['usage_percent']}% usado\n"
            message += f"  Usado: {node['used_gb']}GB / {node['capacity_gb']}GB\n"
            message += f"  Disponível: {node['available_gb']}GB\n"

        send_ntfy_notification(
            f"WARNING: Node Disk Alert - {CLUSTER_NAME}",
            message,
            priority="high",
            tags=["warning", "cd"]
        )

    if not criticals and not warnings:
        logger.info(f"Todos os {len(node_usage)} nodes estão com uso normal de disco")

    return {
        'total_nodes': len(node_usage),
        'warnings': len(warnings),
        'criticals': len(criticals)
    }

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy'}, 200

@app.route('/check', methods=['POST'])
def check():
    """Endpoint para verificar nodes"""
    try:
        result = check_node_disk_space()
        return result, 200
    except Exception as e:
        logger.error(f"Erro ao verificar nodes: {str(e)}")
        return {'error': str(e)}, 500

if __name__ == '__main__':
    logger.info("Iniciando Node Disk Space Monitor...")
    app.run(host='0.0.0.0', port=8080, debug=False)
