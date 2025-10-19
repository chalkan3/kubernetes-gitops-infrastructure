#!/usr/bin/env python3
"""
Pod Restart Tracker - Rastreia e analisa reinicializações frequentes de pods
"""

import os
import logging
import requests
from flask import Flask, request, jsonify
from cloudevents.http import from_http
from datetime import datetime, timedelta
from collections import defaultdict
import json

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
NTFY_URL = os.getenv('NTFY_URL', 'https://ntfy.sh')
NTFY_TOPIC = os.getenv('NTFY_TOPIC', 'k8s-restart-tracker')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'kube.chalkan3.com.br')
RESTART_THRESHOLD = int(os.getenv('RESTART_THRESHOLD', '5'))  # Alertar após N restarts
TIME_WINDOW_MINUTES = int(os.getenv('TIME_WINDOW_MINUTES', '60'))  # Janela de tempo

# Armazenamento em memória de histórico de restarts
restart_history = defaultdict(list)
last_log_collected = {}

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
            logger.error(f"Erro ao enviar notificacao: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Erro ao enviar notificacao: {e}")
        return False

def get_pod_logs(namespace, pod_name, container_name, lines=50):
    """Tenta coletar logs de um pod usando kubectl (se disponível)"""
    try:
        import subprocess
        result = subprocess.run(
            ['kubectl', 'logs', '-n', namespace, pod_name, '-c', container_name, '--tail', str(lines)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Erro ao coletar logs: {result.stderr}"
    except Exception as e:
        logger.error(f"Erro ao coletar logs: {e}")
        return "Logs não disponíveis"

def analyze_restart_pattern(pod_key, restart_count):
    """Analisa padrão de restarts de um pod"""
    now = datetime.now()
    restart_history[pod_key].append({
        'timestamp': now,
        'restart_count': restart_count
    })

    # Limpar histórico antigo (mais de TIME_WINDOW_MINUTES minutos)
    cutoff_time = now - timedelta(minutes=TIME_WINDOW_MINUTES)
    restart_history[pod_key] = [
        r for r in restart_history[pod_key]
        if r['timestamp'] > cutoff_time
    ]

    # Calcular taxa de restart
    if len(restart_history[pod_key]) > 1:
        time_diff = (restart_history[pod_key][-1]['timestamp'] -
                     restart_history[pod_key][0]['timestamp']).total_seconds() / 60
        if time_diff > 0:
            restart_rate = len(restart_history[pod_key]) / time_diff
            return restart_rate

    return 0

def process_pod_event(event_data):
    """Processa eventos de Pods e detecta restarts excessivos"""
    try:
        metadata = event_data.get('metadata', {})
        status = event_data.get('status', {})

        name = metadata.get('name', 'unknown')
        namespace = metadata.get('namespace', 'default')
        phase = status.get('phase', 'Unknown')

        logger.info(f"Pod restart check: {namespace}/{name}")

        # Verificar container statuses para restarts
        container_statuses = status.get('containerStatuses', [])

        for container in container_statuses:
            container_name = container.get('name', 'unknown')
            restart_count = container.get('restartCount', 0)

            pod_key = f"{namespace}/{name}/{container_name}"

            # Se tiver muitos restarts, alertar
            if restart_count >= RESTART_THRESHOLD:
                restart_rate = analyze_restart_pattern(pod_key, restart_count)

                # Determinar severidade
                priority = "default"
                if restart_count > 10:
                    priority = "high"
                if restart_count > 20:
                    priority = "max"

                # Coletar informações do estado atual
                state = container.get('state', {})
                last_state = container.get('lastState', {})

                state_info = ""
                if 'waiting' in state:
                    state_info = f"Status: {state['waiting'].get('reason', 'Waiting')}\n"
                    state_info += f"Mensagem: {state['waiting'].get('message', 'N/A')}\n"

                if 'terminated' in last_state:
                    state_info += f"\nÚltima terminação:\n"
                    state_info += f"Razão: {last_state['terminated'].get('reason', 'Unknown')}\n"
                    state_info += f"Exit Code: {last_state['terminated'].get('exitCode', 'N/A')}\n"
                    state_info += f"Mensagem: {last_state['terminated'].get('message', 'N/A')}\n"

                # Tentar coletar logs se ainda não coletamos recentemente
                log_snippet = ""
                if pod_key not in last_log_collected or \
                   (datetime.now() - last_log_collected[pod_key]).total_seconds() > 300:
                    logs = get_pod_logs(namespace, name, container_name)
                    if logs:
                        log_snippet = f"\n=== ÚLTIMAS LINHAS DO LOG ===\n{logs[-500:]}\n"
                        last_log_collected[pod_key] = datetime.now()

                message = (
                    f"=== POD COM RESTARTS EXCESSIVOS ===\n\n"
                    f"Namespace: {namespace}\n"
                    f"Pod: {name}\n"
                    f"Container: {container_name}\n"
                    f"Total de Restarts: {restart_count}\n"
                    f"Taxa de Restart: {restart_rate:.2f}/min\n\n"
                    f"{state_info}"
                    f"{log_snippet}"
                    f"\nRecomendacao:\n"
                    f"- Verificar logs completos: kubectl logs -n {namespace} {name} -c {container_name}\n"
                    f"- Verificar eventos: kubectl describe pod -n {namespace} {name}\n"
                    f"- Verificar recursos: kubectl top pod -n {namespace} {name}\n"
                )

                send_ntfy_notification(
                    f"ALERT: Pod Restarts - {CLUSTER_NAME}",
                    message,
                    priority=priority,
                    tags=["warning", "rotating_light"]
                )

        return True

    except Exception as e:
        logger.error(f"Erro ao processar evento de Pod: {e}")
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

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "cluster": CLUSTER_NAME,
        "tracked_pods": len(restart_history)
    }), 200

@app.route('/stats', methods=['GET'])
def stats():
    """Retorna estatísticas de restarts"""
    stats_data = {}
    for pod_key, history in restart_history.items():
        if history:
            stats_data[pod_key] = {
                "total_events": len(history),
                "last_restart_count": history[-1]['restart_count'],
                "last_seen": history[-1]['timestamp'].isoformat()
            }

    return jsonify(stats_data), 200

@app.route('/test', methods=['POST'])
def test_notification():
    """Endpoint para testar notificações"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_ntfy_notification(
        f"TEST - Restart Tracker - {CLUSTER_NAME}",
        f"=== TESTE DO RESTART TRACKER ===\n\n"
        f"Cluster: {CLUSTER_NAME}\n"
        f"Status: Tracker funcionando corretamente\n"
        f"Timestamp: {timestamp}\n"
        f"Threshold: {RESTART_THRESHOLD} restarts\n"
        f"Time Window: {TIME_WINDOW_MINUTES} minutos\n\n"
        f"Pods rastreados: {len(restart_history)}",
        priority="default",
        tags=["bell", "white_check_mark"]
    )
    return jsonify({"status": "ok", "message": "Test notification sent"}), 200

if __name__ == '__main__':
    logger.info(f"Iniciando Pod Restart Tracker")
    logger.info(f"Cluster: {CLUSTER_NAME}")
    logger.info(f"ntfy URL: {NTFY_URL}")
    logger.info(f"ntfy Topic: {NTFY_TOPIC}")
    logger.info(f"Restart Threshold: {RESTART_THRESHOLD}")
    logger.info(f"Time Window: {TIME_WINDOW_MINUTES} minutos")

    # Enviar notificação de inicialização
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_ntfy_notification(
        f"Restart Tracker STARTED - {CLUSTER_NAME}",
        f"=== RESTART TRACKER INICIADO ===\n\n"
        f"Cluster: {CLUSTER_NAME}\n"
        f"Servico: Pod Restart Tracker iniciado\n"
        f"Timestamp: {timestamp}\n\n"
        f"Configuracao:\n"
        f"- Threshold: {RESTART_THRESHOLD} restarts\n"
        f"- Time Window: {TIME_WINDOW_MINUTES} minutos\n"
        f"- Coleta de logs: Habilitada",
        priority="low",
        tags=["rocket", "information_source"]
    )

    # Iniciar servidor
    app.run(host='0.0.0.0', port=8080)
