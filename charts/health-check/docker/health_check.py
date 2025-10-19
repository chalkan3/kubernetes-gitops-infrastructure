#!/usr/bin/env python3
"""
Health Check Service - Verifica saúde do cluster Kubernetes
"""

import os
import logging
import requests
import socket
import subprocess
from flask import Flask, jsonify
from datetime import datetime
import time

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
NTFY_URL = os.getenv('NTFY_URL', 'https://ntfy.sh')
NTFY_TOPIC = os.getenv('NTFY_TOPIC', 'k8s-health-check')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'kube.chalkan3.com.br')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))  # 5 minutos

# Serviços críticos para verificar
CRITICAL_SERVICES = os.getenv('CRITICAL_SERVICES', '').split(',')
if not CRITICAL_SERVICES or CRITICAL_SERVICES == ['']:
    CRITICAL_SERVICES = [
        'kubernetes.default.svc.cluster.local:443',
        'kube-dns.kube-system.svc.cluster.local:53'
    ]

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
            logger.info(f"Notificacao enviada: {title_clean}")
            return True
        else:
            logger.error(f"Erro ao enviar notificacao: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Erro ao enviar notificacao: {e}")
        return False

def check_dns_resolution(hostname):
    """Verifica resolução DNS"""
    try:
        start_time = time.time()
        result = socket.gethostbyname(hostname)
        latency = (time.time() - start_time) * 1000
        return {
            "success": True,
            "ip": result,
            "latency_ms": round(latency, 2)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def check_tcp_connectivity(host, port, timeout=5):
    """Verifica conectividade TCP"""
    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        latency = (time.time() - start_time) * 1000
        sock.close()

        return {
            "success": result == 0,
            "latency_ms": round(latency, 2)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def check_http_endpoint(url, timeout=10):
    """Verifica endpoint HTTP"""
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout, verify=False)
        latency = (time.time() - start_time) * 1000

        return {
            "success": response.status_code < 500,
            "status_code": response.status_code,
            "latency_ms": round(latency, 2)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def check_kubernetes_api():
    """Verifica conectividade com API do Kubernetes"""
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'nodes', '--request-timeout=5s'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            nodes = len([line for line in result.stdout.split('\n') if line and 'Ready' in line])
            return {
                "success": True,
                "nodes": nodes,
                "output": result.stdout
            }
        else:
            return {
                "success": False,
                "error": result.stderr
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def check_node_connectivity():
    """Verifica conectividade entre nodes"""
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'nodes', '-o', 'jsonpath={.items[*].status.addresses[?(@.type=="InternalIP")].address}'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            ips = result.stdout.strip().split()
            connectivity_results = []

            for ip in ips[:5]:  # Limitar a 5 nodes para evitar timeout
                ping_result = subprocess.run(
                    ['ping', '-c', '1', '-W', '2', ip],
                    capture_output=True,
                    timeout=5
                )
                connectivity_results.append({
                    "ip": ip,
                    "reachable": ping_result.returncode == 0
                })

            return {
                "success": all(r['reachable'] for r in connectivity_results),
                "results": connectivity_results
            }
        else:
            return {
                "success": False,
                "error": "Could not get node IPs"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def perform_health_check():
    """Realiza verificação completa de saúde"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "cluster": CLUSTER_NAME,
        "checks": {}
    }

    # 1. Verificar API do Kubernetes
    logger.info("Verificando API do Kubernetes...")
    results["checks"]["kubernetes_api"] = check_kubernetes_api()

    # 2. Verificar DNS
    logger.info("Verificando DNS...")
    results["checks"]["dns"] = {}
    test_domains = ['kubernetes.default', 'kube-dns.kube-system']
    for domain in test_domains:
        results["checks"]["dns"][domain] = check_dns_resolution(domain)

    # 3. Verificar serviços críticos
    logger.info("Verificando serviços críticos...")
    results["checks"]["critical_services"] = {}
    for service in CRITICAL_SERVICES:
        if ':' in service:
            host, port = service.rsplit(':', 1)
            port = int(port)
            results["checks"]["critical_services"][service] = check_tcp_connectivity(host, port)

    # 4. Verificar conectividade entre nodes
    logger.info("Verificando conectividade entre nodes...")
    results["checks"]["node_connectivity"] = check_node_connectivity()

    # Analisar resultados e enviar alertas se necessário
    failed_checks = []
    for check_category, check_results in results["checks"].items():
        if isinstance(check_results, dict):
            if not check_results.get("success", True):
                failed_checks.append(check_category)
            # Verificar sub-checks
            for subcheck, subresult in check_results.items():
                if isinstance(subresult, dict) and not subresult.get("success", True):
                    failed_checks.append(f"{check_category}.{subcheck}")

    if failed_checks:
        message = (
            f"=== PROBLEMAS DE SAUDE DETECTADOS ===\n\n"
            f"Cluster: {CLUSTER_NAME}\n"
            f"Timestamp: {results['timestamp']}\n\n"
            f"Verificacoes falhadas:\n"
        )
        for failed in failed_checks:
            message += f"- {failed}\n"

        message += f"\n\nDetalhes completos disponíveis no endpoint /health"

        send_ntfy_notification(
            f"WARNING: Health Check Failed - {CLUSTER_NAME}",
            message,
            priority="high",
            tags=["warning", "health_worker"]
        )
    else:
        logger.info("Todas as verificações de saúde passaram")

    return results

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "cluster": CLUSTER_NAME}), 200

@app.route('/check', methods=['POST'])
def run_check():
    """Executa verificação de saúde sob demanda"""
    results = perform_health_check()
    return jsonify(results), 200

@app.route('/test', methods=['POST'])
def test_notification():
    """Endpoint para testar notificações"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_ntfy_notification(
        f"TEST - Health Check - {CLUSTER_NAME}",
        f"=== TESTE DO HEALTH CHECK ===\n\n"
        f"Cluster: {CLUSTER_NAME}\n"
        f"Status: Health Check funcionando corretamente\n"
        f"Timestamp: {timestamp}\n\n"
        f"Verificacoes habilitadas:\n"
        f"- Kubernetes API\n"
        f"- DNS Resolution\n"
        f"- Critical Services\n"
        f"- Node Connectivity",
        priority="default",
        tags=["bell", "white_check_mark"]
    )
    return jsonify({"status": "ok", "message": "Test notification sent"}), 200

if __name__ == '__main__':
    logger.info(f"Iniciando Health Check Service")
    logger.info(f"Cluster: {CLUSTER_NAME}")
    logger.info(f"ntfy URL: {NTFY_URL}")
    logger.info(f"ntfy Topic: {NTFY_TOPIC}")
    logger.info(f"Check Interval: {CHECK_INTERVAL} segundos")

    # Enviar notificação de inicialização
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_ntfy_notification(
        f"Health Check STARTED - {CLUSTER_NAME}",
        f"=== HEALTH CHECK INICIADO ===\n\n"
        f"Cluster: {CLUSTER_NAME}\n"
        f"Servico: Health Check iniciado\n"
        f"Timestamp: {timestamp}\n\n"
        f"Configuracao:\n"
        f"- Check Interval: {CHECK_INTERVAL}s\n"
        f"- Critical Services: {len(CRITICAL_SERVICES)}",
        priority="low",
        tags=["rocket", "information_source"]
    )

    # Iniciar servidor
    app.run(host='0.0.0.0', port=8080)
