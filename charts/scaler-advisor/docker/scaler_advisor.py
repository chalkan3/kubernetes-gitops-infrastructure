#!/usr/bin/env python3
"""
Auto-Scaler Advisor - Analisa uso de recursos e sugere configurações de HPA
"""

import os
import logging
import requests
from flask import Flask, jsonify
from datetime import datetime
import subprocess
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

NTFY_URL = os.getenv('NTFY_URL', 'https://ntfy.sh')
NTFY_TOPIC = os.getenv('NTFY_TOPIC', 'k8s-scaler-advisor')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'kube.chalkan3.com.br')

def send_ntfy(title, message, priority="default", tags=None):
    try:
        headers = {
            "Title": title.encode('ascii', 'ignore').decode('ascii'),
            "Priority": priority,
            "Content-Type": "text/plain; charset=utf-8"
        }
        if tags:
            headers["Tags"] = ",".join([str(t).encode('ascii', 'ignore').decode('ascii') for t in (tags if isinstance(tags, list) else [tags])])

        requests.post(f"{NTFY_URL}/{NTFY_TOPIC}", data=message.encode('utf-8'), headers=headers)
        logger.info(f"Notification sent: {title}")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

def get_deployments():
    try:
        result = subprocess.run(['kubectl', 'get', 'deployments', '-A', '-o', 'json'],
                                capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout).get('items', [])
    except:
        return []

def get_pod_metrics(namespace, deployment):
    try:
        result = subprocess.run(
            ['kubectl', 'top', 'pods', '-n', namespace, '-l', f'app={deployment}', '--no-headers'],
            capture_output=True, text=True, timeout=10
        )
        metrics = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 3:
                    metrics.append({'cpu': parts[1], 'memory': parts[2]})
        return metrics
    except:
        return []

def analyze_scaling():
    results = {"timestamp": datetime.now().isoformat(), "recommendations": []}
    deployments = get_deployments()

    for deploy in deployments[:10]:  # Limitar a 10 para performance
        metadata = deploy.get('metadata', {})
        spec = deploy.get('spec', {})
        status = deploy.get('status', {})

        name = metadata.get('name')
        namespace = metadata.get('namespace')
        replicas = spec.get('replicas', 1)
        available = status.get('availableReplicas', 0)

        # Pegar métricas de uso
        metrics = get_pod_metrics(namespace, name)

        if len(metrics) > 0:
            avg_cpu = sum([int(m['cpu'].rstrip('m')) for m in metrics]) / len(metrics)

            recommendation = None
            if avg_cpu > 800:  # >80% CPU
                recommendation = {
                    "deployment": f"{namespace}/{name}",
                    "current_replicas": replicas,
                    "suggested_action": "SCALE UP",
                    "reason": f"High CPU usage: {avg_cpu}m average",
                    "suggested_hpa": {
                        "minReplicas": replicas,
                        "maxReplicas": replicas * 3,
                        "targetCPUUtilization": 70
                    }
                }
            elif avg_cpu < 200 and replicas > 1:  # <20% CPU
                recommendation = {
                    "deployment": f"{namespace}/{name}",
                    "current_replicas": replicas,
                    "suggested_action": "SCALE DOWN or OPTIMIZE",
                    "reason": f"Low CPU usage: {avg_cpu}m average",
                    "suggestion": "Consider reducing replicas or resources"
                }

            if recommendation:
                results["recommendations"].append(recommendation)

    # Enviar relatório se houver recomendações
    if results["recommendations"]:
        message = f"=== RECOMENDACOES DE SCALING ===\n\nCluster: {CLUSTER_NAME}\n\n"
        for rec in results["recommendations"]:
            message += f"Deployment: {rec['deployment']}\n"
            message += f"Acao: {rec['suggested_action']}\n"
            message += f"Razao: {rec['reason']}\n\n"

        send_ntfy(f"Scaler Advisor Report - {CLUSTER_NAME}", message, "default", ["chart_increasing"])

    return results

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "cluster": CLUSTER_NAME}), 200

@app.route('/analyze', methods=['POST'])
def analyze():
    results = analyze_scaling()
    return jsonify(results), 200

@app.route('/test', methods=['POST'])
def test():
    send_ntfy(f"TEST - Scaler Advisor - {CLUSTER_NAME}",
              f"Scaler Advisor funcionando!\nTimestamp: {datetime.now()}",
              "default", ["bell"])
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    logger.info(f"Starting Scaler Advisor for {CLUSTER_NAME}")
    send_ntfy(f"Scaler Advisor STARTED - {CLUSTER_NAME}",
              f"Scaler Advisor iniciado\nTimestamp: {datetime.now()}",
              "low", ["rocket"])
    app.run(host='0.0.0.0', port=8080)
