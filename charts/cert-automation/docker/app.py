#!/usr/bin/env python3
"""
Cert Automation Service
Monitora eventos de Ingress e distribui certificados mkcert automaticamente
"""

import os
import logging
from flask import Flask, request, jsonify
from cloudevents.http import from_http
import paramiko
import time

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
NODE_IPS = os.getenv('NODE_IPS', '').split(',')
BASE_DOMAIN = os.getenv('BASE_DOMAIN', 'kube.chalkan3.com.br')
SSH_KEY_PATH = '/secrets/ssh/id_rsa'
MKCERT_CA_PATH = '/certs/rootCA.pem'

def distribute_ca_to_node(node_ip, ca_content):
    """
    Distribui o CA do mkcert para um node específico
    """
    try:
        logger.info(f"Conectando ao node {node_ip}...")

        # Criar cliente SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Carregar chave privada
        private_key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)

        # Conectar
        ssh.connect(
            hostname=node_ip,
            username='root',
            pkey=private_key,
            timeout=30
        )

        logger.info(f"Conectado ao node {node_ip}")

        # Criar SFTP client para upload
        sftp = ssh.open_sftp()

        # Escrever CA no arquivo temporário
        with sftp.open('/tmp/mkcert-ca.crt', 'w') as f:
            f.write(ca_content)

        logger.info(f"CA enviado para {node_ip}")

        # Executar comandos para instalar CA
        commands = [
            'cp /tmp/mkcert-ca.crt /usr/local/share/ca-certificates/',
            'update-ca-certificates',
            'systemctl restart containerd'
        ]

        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()

            if exit_code != 0:
                error = stderr.read().decode()
                logger.error(f"Erro ao executar '{cmd}' em {node_ip}: {error}")
            else:
                logger.info(f"Comando '{cmd}' executado com sucesso em {node_ip}")

        sftp.close()
        ssh.close()

        logger.info(f"✅ CA instalado com sucesso no node {node_ip}")
        return True

    except Exception as e:
        logger.error(f"❌ Erro ao processar node {node_ip}: {e}")
        return False

def process_ingress_event(event_data):
    """
    Processa evento de Ingress
    """
    try:
        # Log para debug
        logger.info(f"Event data type: {type(event_data)}")
        logger.info(f"Event data keys: {event_data.keys() if hasattr(event_data, 'keys') else 'N/A'}")

        # Extrair informações do Ingress
        ingress_obj = event_data.get('object', event_data)
        metadata = ingress_obj.get('metadata', {})
        spec = ingress_obj.get('spec', {})

        name = metadata.get('name', 'unknown')
        namespace = metadata.get('namespace', 'default')

        # Extrair hostnames
        rules = spec.get('rules', [])
        hostnames = [rule.get('host') for rule in rules if rule.get('host')]

        logger.info(f"Processando Ingress: {namespace}/{name}")
        logger.info(f"Hostnames: {hostnames}")

        # Verificar se algum hostname está no domínio base
        should_process = any(BASE_DOMAIN in host for host in hostnames)

        if not should_process:
            logger.info(f"Ingress não está no domínio {BASE_DOMAIN}, ignorando")
            return True

        logger.info(f"Ingress está no domínio {BASE_DOMAIN}, distribuindo CA...")

        # Ler conteúdo do CA
        with open(MKCERT_CA_PATH, 'r') as f:
            ca_content = f.read()

        # Distribuir para todos os nodes
        results = []
        for node_ip in NODE_IPS:
            if node_ip.strip():
                result = distribute_ca_to_node(node_ip.strip(), ca_content)
                results.append(result)
                time.sleep(2)  # Pequeno delay entre nodes

        success_count = sum(results)
        total_count = len(results)

        logger.info(f"Distribuição completa: {success_count}/{total_count} nodes")

        return success_count > 0

    except Exception as e:
        logger.error(f"Erro ao processar evento de Ingress: {e}")
        return False

@app.route('/', methods=['POST'])
def handle_event():
    """
    Handler HTTP para receber eventos do Knative
    """
    try:
        # Parse CloudEvent
        event = from_http(request.headers, request.get_data())

        logger.info(f"Recebido evento: {event['type']}")
        logger.info(f"Subject: {event.get('subject', 'N/A')}")

        # Processar evento
        event_data = event.data
        success = process_ingress_event(event_data)

        if success:
            return jsonify({"status": "ok", "message": "Evento processado com sucesso"}), 200
        else:
            return jsonify({"status": "error", "message": "Erro ao processar evento"}), 500

    except Exception as e:
        logger.error(f"Erro ao processar requisição: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    logger.info("🚀 Iniciando Cert Automation Service")
    logger.info(f"Nodes configurados: {NODE_IPS}")
    logger.info(f"Domínio base: {BASE_DOMAIN}")

    # Verificar arquivos necessários
    if not os.path.exists(SSH_KEY_PATH):
        logger.error(f"❌ Chave SSH não encontrada em {SSH_KEY_PATH}")
    else:
        logger.info(f"✅ Chave SSH encontrada")

    if not os.path.exists(MKCERT_CA_PATH):
        logger.error(f"❌ CA mkcert não encontrado em {MKCERT_CA_PATH}")
    else:
        logger.info(f"✅ CA mkcert encontrado")

    # Iniciar servidor
    app.run(host='0.0.0.0', port=8080)
