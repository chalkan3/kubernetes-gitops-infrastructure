#!/usr/bin/env python3
"""
Cluster Monitor - Monitora eventos do Kubernetes e envia notificações via ntfy
"""

import os
import logging
import requests
import json
from flask import Flask, request, jsonify
from cloudevents.http import from_http
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
NTFY_URL = os.getenv('NTFY_URL', 'https://ntfy.sh')
NTFY_TOPIC = os.getenv('NTFY_TOPIC', 'k8s-cluster-monitor')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'kube.chalkan3.com.br')

def send_ntfy_notification(title, message, priority="default", tags=None):
    """
    Envia notificação via ntfy

    Priorities: max, high, default, low, min
    Tags: warning, skull, rotating_light, bell, etc
    """
    try:
        # Remover emojis do título para evitar problemas de encoding
        title_clean = title.encode('ascii', 'ignore').decode('ascii')

        # Limpar a mensagem também para evitar problemas de encoding
        message_clean = message.encode('utf-8')

        # Usar formato simples com headers em vez de JSON para compatibilidade
        headers = {
            "Title": title_clean,
            "Priority": priority,
            "Content-Type": "text/plain; charset=utf-8"
        }

        if tags:
            # Garantir que as tags sejam strings ASCII sem emojis
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
            logger.error(f"Erro ao enviar notificacao: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Erro ao enviar notificacao: {e}")
        return False

def process_pod_event(event_data):
    """
    Processa eventos de Pods
    """
    try:
        metadata = event_data.get('metadata', {})
        status = event_data.get('status', {})

        name = metadata.get('name', 'unknown')
        namespace = metadata.get('namespace', 'default')
        phase = status.get('phase', 'Unknown')

        logger.info(f"Pod event: {namespace}/{name} - Phase: {phase}")

        # Notificar sobre pods com problemas
        container_statuses = status.get('containerStatuses', [])

        for container in container_statuses:
            container_name = container.get('name', 'unknown')
            state = container.get('state', {})

            # Pod em CrashLoopBackOff
            if 'waiting' in state:
                reason = state['waiting'].get('reason', '')
                message_detail = state['waiting'].get('message', 'No details available')
                if 'CrashLoopBackOff' in reason or 'ImagePullBackOff' in reason:
                    send_ntfy_notification(
                        f"ALERT: POD PROBLEM - {CLUSTER_NAME}",
                        f"=== POD COM PROBLEMA ===\n\n"
                        f"Namespace: {namespace}\n"
                        f"Pod: {name}\n"
                        f"Container: {container_name}\n"
                        f"Status: {reason}\n\n"
                        f"Detalhes:\n{message_detail[:200]}",
                        priority="high",
                        tags=["warning", "rotating_light"]
                    )

            # Pod terminado com erro
            if 'terminated' in state:
                exit_code = state['terminated'].get('exitCode', 0)
                reason = state['terminated'].get('reason', '')
                if exit_code != 0:
                    send_ntfy_notification(
                        f"ALERT: POD FAILED - {CLUSTER_NAME}",
                        f"=== POD TERMINOU COM ERRO ===\n\n"
                        f"Namespace: {namespace}\n"
                        f"Pod: {name}\n"
                        f"Container: {container_name}\n"
                        f"Reason: {reason}\n"
                        f"Exit Code: {exit_code}",
                        priority="high",
                        tags=["skull", "warning"]
                    )

        # Pod iniciado com sucesso em produção
        if phase == "Running" and namespace in ['production', 'prod']:
            if metadata.get('creationTimestamp'):
                send_ntfy_notification(
                    f"Pod Running - {CLUSTER_NAME}",
                    f"Pod: {namespace}/{name}\nStatus: {phase}",
                    priority="low",
                    tags=["white_check_mark"]
                )

        return True

    except Exception as e:
        logger.error(f"Erro ao processar evento de Pod: {e}")
        return False

def process_node_event(event_data):
    """
    Processa eventos de Nodes
    """
    try:
        metadata = event_data.get('metadata', {})
        status = event_data.get('status', {})

        name = metadata.get('name', 'unknown')
        conditions = status.get('conditions', [])

        logger.info(f"Node event: {name}")

        # Verificar condições do node
        for condition in conditions:
            condition_type = condition.get('type', '')
            condition_status = condition.get('status', 'Unknown')
            reason = condition.get('reason', '')
            message = condition.get('message', '')

            # Node não está pronto
            if condition_type == 'Ready' and condition_status != 'True':
                send_ntfy_notification(
                    f"CRITICAL: Node Not Ready - {CLUSTER_NAME}",
                    f"Node: {name}\nReason: {reason}\nMessage: {message}",
                    priority="max",
                    tags=["rotating_light", "warning"]
                )

            # Problemas de memória/disco
            if condition_type in ['MemoryPressure', 'DiskPressure'] and condition_status == 'True':
                send_ntfy_notification(
                    f"WARNING: Node Pressure - {CLUSTER_NAME}",
                    f"Node: {name}\nType: {condition_type}\nMessage: {message}",
                    priority="high",
                    tags=["warning"]
                )

        return True

    except Exception as e:
        logger.error(f"Erro ao processar evento de Node: {e}")
        return False

def process_deployment_event(event_data):
    """
    Processa eventos de Deployments
    """
    try:
        metadata = event_data.get('metadata', {})
        status = event_data.get('status', {})
        spec = event_data.get('spec', {})

        name = metadata.get('name', 'unknown')
        namespace = metadata.get('namespace', 'default')

        replicas = spec.get('replicas', 0)
        available_replicas = status.get('availableReplicas', 0)
        ready_replicas = status.get('readyReplicas', 0)

        logger.info(f"Deployment event: {namespace}/{name} - {available_replicas}/{replicas} available")

        # Deployment com réplicas insuficientes
        if available_replicas < replicas:
            send_ntfy_notification(
                f"WARNING: Deployment Degraded - {CLUSTER_NAME}",
                f"Deployment: {namespace}/{name}\nAvailable: {available_replicas}/{replicas}",
                priority="high",
                tags=["warning"]
            )

        # Deployment totalmente disponível (recovery)
        if available_replicas == replicas and replicas > 0:
            send_ntfy_notification(
                f"OK: Deployment Healthy - {CLUSTER_NAME}",
                f"Deployment: {namespace}/{name}\nAll replicas available: {replicas}/{replicas}",
                priority="low",
                tags=["white_check_mark"]
            )

        return True

    except Exception as e:
        logger.error(f"Erro ao processar evento de Deployment: {e}")
        return False

def process_pvc_event(event_data):
    """
    Processa eventos de PersistentVolumeClaims
    """
    try:
        metadata = event_data.get('metadata', {})
        status = event_data.get('status', {})

        name = metadata.get('name', 'unknown')
        namespace = metadata.get('namespace', 'default')
        phase = status.get('phase', 'Unknown')

        logger.info(f"PVC event: {namespace}/{name} - Phase: {phase}")

        # PVC pendente
        if phase == 'Pending':
            send_ntfy_notification(
                f"INFO: PVC Pending - {CLUSTER_NAME}",
                f"PVC: {namespace}/{name}\nStatus: Pending - aguardando bind",
                priority="default",
                tags=["hourglass"]
            )

        # PVC bound
        if phase == 'Bound':
            send_ntfy_notification(
                f"OK: PVC Bound - {CLUSTER_NAME}",
                f"PVC: {namespace}/{name}\nStatus: Successfully bound",
                priority="low",
                tags=["white_check_mark"]
            )

        return True

    except Exception as e:
        logger.error(f"Erro ao processar evento de PVC: {e}")
        return False

@app.route('/pods', methods=['POST'])
def handle_pod_event():
    """Handler para eventos de Pods"""
    try:
        event = from_http(request.headers, request.get_data())
        logger.info(f"Recebido evento de Pod: {event['type']}")

        success = process_pod_event(event.data)

        if success:
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "error"}), 500

    except Exception as e:
        logger.error(f"Erro ao processar requisição: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/nodes', methods=['POST'])
def handle_node_event():
    """Handler para eventos de Nodes"""
    try:
        event = from_http(request.headers, request.get_data())
        logger.info(f"Recebido evento de Node: {event['type']}")

        success = process_node_event(event.data)

        if success:
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "error"}), 500

    except Exception as e:
        logger.error(f"Erro ao processar requisição: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/deployments', methods=['POST'])
def handle_deployment_event():
    """Handler para eventos de Deployments"""
    try:
        event = from_http(request.headers, request.get_data())
        logger.info(f"Recebido evento de Deployment: {event['type']}")

        success = process_deployment_event(event.data)

        if success:
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "error"}), 500

    except Exception as e:
        logger.error(f"Erro ao processar requisição: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/pvcs', methods=['POST'])
def handle_pvc_event():
    """Handler para eventos de PVCs"""
    try:
        event = from_http(request.headers, request.get_data())
        logger.info(f"Recebido evento de PVC: {event['type']}")

        success = process_pvc_event(event.data)

        if success:
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "error"}), 500

    except Exception as e:
        logger.error(f"Erro ao processar requisição: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "cluster": CLUSTER_NAME}), 200

@app.route('/test', methods=['POST'])
def test_notification():
    """Endpoint para testar notificações"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_ntfy_notification(
        f"TEST - {CLUSTER_NAME}",
        f"=== TESTE DE NOTIFICACAO ===\n\n"
        f"Cluster: {CLUSTER_NAME}\n"
        f"Status: Monitor funcionando corretamente\n"
        f"Timestamp: {timestamp}\n\n"
        f"Se voce recebeu esta notificacao, o sistema esta operacional!",
        priority="default",
        tags=["bell", "white_check_mark"]
    )
    return jsonify({"status": "ok", "message": "Test notification sent"}), 200

if __name__ == '__main__':
    logger.info(f"Iniciando Cluster Monitor Service")
    logger.info(f"Cluster: {CLUSTER_NAME}")
    logger.info(f"ntfy URL: {NTFY_URL}")
    logger.info(f"ntfy Topic: {NTFY_TOPIC}")

    # Enviar notificação de inicialização
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_ntfy_notification(
        f"MONITOR STARTED - {CLUSTER_NAME}",
        f"=== CLUSTER MONITOR INICIADO ===\n\n"
        f"Cluster: {CLUSTER_NAME}\n"
        f"Servico: Monitoramento iniciado com sucesso\n"
        f"Timestamp: {timestamp}\n\n"
        f"Recursos monitorados:\n"
        f"- Pods (CrashLoop, Failures)\n"
        f"- Nodes (Health, Pressure)\n"
        f"- Deployments (Replicas)\n"
        f"- PVCs (Bind Status)",
        priority="low",
        tags=["rocket", "information_source"]
    )

    # Iniciar servidor
    app.run(host='0.0.0.0', port=8080)
