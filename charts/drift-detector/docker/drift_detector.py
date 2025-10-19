#!/usr/bin/env python3
import os
import subprocess
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
NTFY_TOPIC = os.getenv('NTFY_TOPIC', 'k8s-drift-detector')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'kubernetes')

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

def check_argocd_sync_status():
    """Verifica status de sync das aplicações ArgoCD"""
    try:
        # Lista todas as aplicações ArgoCD
        result = subprocess.run(
            ['kubectl', 'get', 'applications', '-n', 'argocd', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Erro ao listar aplicações ArgoCD: {result.stderr}")
            return []

        import json
        apps = json.loads(result.stdout)

        out_of_sync = []
        failed = []
        degraded = []

        for app in apps.get('items', []):
            app_name = app['metadata']['name']
            status = app.get('status', {})

            sync_status = status.get('sync', {}).get('status', 'Unknown')
            health_status = status.get('health', {}).get('status', 'Unknown')

            # Detecta apps fora de sync
            if sync_status != 'Synced':
                out_of_sync.append({
                    'name': app_name,
                    'sync_status': sync_status,
                    'health_status': health_status
                })

            # Detecta apps com problemas de health
            if health_status == 'Degraded':
                degraded.append({
                    'name': app_name,
                    'sync_status': sync_status,
                    'health_status': health_status
                })

        return {
            'out_of_sync': out_of_sync,
            'degraded': degraded
        }

    except Exception as e:
        logger.error(f"Erro ao verificar status do ArgoCD: {str(e)}")
        return {'out_of_sync': [], 'degraded': []}

def detect_manual_changes():
    """Detecta mudanças manuais em recursos gerenciados pelo ArgoCD"""
    try:
        # Busca pods/deployments sem a label do ArgoCD
        result = subprocess.run(
            ['kubectl', 'get', 'deployments', '-A', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return []

        import json
        deployments = json.loads(result.stdout)

        # Namespaces que devem ser gerenciados pelo ArgoCD
        managed_namespaces = [
            'pod-restart-tracker', 'health-check', 'scaler-advisor',
            'pvc-monitor', 'node-disk-monitor', 'drift-detector',
            'cluster-monitor'
        ]

        unmanaged = []

        for deployment in deployments.get('items', []):
            namespace = deployment['metadata']['namespace']
            name = deployment['metadata']['name']
            labels = deployment['metadata'].get('labels', {})

            # Verifica se está em namespace gerenciado mas sem label do ArgoCD
            if namespace in managed_namespaces:
                if 'argocd.argoproj.io/instance' not in labels:
                    unmanaged.append({
                        'namespace': namespace,
                        'name': name,
                        'type': 'Deployment'
                    })

        return unmanaged

    except Exception as e:
        logger.error(f"Erro ao detectar mudanças manuais: {str(e)}")
        return []

def check_deployment_drift():
    """Verifica drift entre cluster e git"""
    logger.info("Iniciando verificação de drift...")

    # Verifica status do ArgoCD
    argocd_status = check_argocd_sync_status()

    # Detecta mudanças manuais
    manual_changes = detect_manual_changes()

    # Envia notificações
    if argocd_status['out_of_sync']:
        message = f"⚠️ {len(argocd_status['out_of_sync'])} aplicação(ões) ArgoCD fora de sync no cluster {CLUSTER_NAME}:\n\n"
        for app in argocd_status['out_of_sync']:
            message += f"• {app['name']}: {app['sync_status']}\n"
            message += f"  Health: {app['health_status']}\n"

        send_ntfy_notification(
            f"WARNING: ArgoCD Out of Sync - {CLUSTER_NAME}",
            message,
            priority="high",
            tags=["warning", "git"]
        )

    if argocd_status['degraded']:
        message = f"🔴 {len(argocd_status['degraded'])} aplicação(ões) ArgoCD degradadas no cluster {CLUSTER_NAME}:\n\n"
        for app in argocd_status['degraded']:
            message += f"• {app['name']}: {app['health_status']}\n"
            message += f"  Sync: {app['sync_status']}\n"

        send_ntfy_notification(
            f"CRITICAL: ArgoCD Degraded - {CLUSTER_NAME}",
            message,
            priority="urgent",
            tags=["rotating_light", "warning"]
        )

    if manual_changes:
        message = f"⚠️ Detectadas {len(manual_changes)} mudanças manuais (não gerenciadas pelo ArgoCD) no cluster {CLUSTER_NAME}:\n\n"
        for change in manual_changes[:10]:  # Limita a 10
            message += f"• {change['type']}: {change['namespace']}/{change['name']}\n"

        if len(manual_changes) > 10:
            message += f"\n... e mais {len(manual_changes) - 10} recursos não gerenciados"

        send_ntfy_notification(
            f"WARNING: Manual Changes Detected - {CLUSTER_NAME}",
            message,
            priority="high",
            tags=["warning", "git"]
        )

    if not argocd_status['out_of_sync'] and not argocd_status['degraded'] and not manual_changes:
        logger.info("Nenhum drift detectado - cluster em conformidade com GitOps")

    return {
        'out_of_sync': len(argocd_status['out_of_sync']),
        'degraded': len(argocd_status['degraded']),
        'manual_changes': len(manual_changes)
    }

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy'}, 200

@app.route('/check', methods=['POST'])
def check():
    """Endpoint para verificar drift"""
    try:
        result = check_deployment_drift()
        return result, 200
    except Exception as e:
        logger.error(f"Erro ao verificar drift: {str(e)}")
        return {'error': str(e)}, 500

if __name__ == '__main__':
    logger.info("Iniciando Deployment Drift Detector...")
    app.run(host='0.0.0.0', port=8080, debug=False)
