#!/usr/bin/env python3
"""
Custom Metrics Exporter for Kubernetes
Collects custom cluster metrics and exposes them in Prometheus format
"""

import os
import subprocess
import json
import time
from datetime import datetime
from flask import Flask, Response
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# Prometheus Registry
registry = CollectorRegistry()

# Define custom metrics
cluster_nodes_total = Gauge('k8s_cluster_nodes_total', 'Total number of nodes', registry=registry)
cluster_nodes_ready = Gauge('k8s_cluster_nodes_ready', 'Number of ready nodes', registry=registry)
cluster_namespaces_total = Gauge('k8s_cluster_namespaces_total', 'Total number of namespaces', registry=registry)
cluster_deployments_total = Gauge('k8s_cluster_deployments_total', 'Total number of deployments', ['namespace'], registry=registry)
cluster_pods_total = Gauge('k8s_cluster_pods_total', 'Total number of pods', ['namespace', 'phase'], registry=registry)
cluster_services_total = Gauge('k8s_cluster_services_total', 'Total number of services', ['namespace', 'type'], registry=registry)
cluster_pvcs_total = Gauge('k8s_cluster_pvcs_total', 'Total number of PVCs', ['namespace', 'status'], registry=registry)
cluster_configmaps_total = Gauge('k8s_cluster_configmaps_total', 'Total number of ConfigMaps', ['namespace'], registry=registry)
cluster_secrets_total = Gauge('k8s_cluster_secrets_total', 'Total number of Secrets', ['namespace'], registry=registry)
cluster_ingresses_total = Gauge('k8s_cluster_ingresses_total', 'Total number of Ingresses', ['namespace'], registry=registry)
cluster_cronjobs_total = Gauge('k8s_cluster_cronjobs_total', 'Total number of CronJobs', ['namespace'], registry=registry)
cluster_jobs_total = Gauge('k8s_cluster_jobs_total', 'Total number of Jobs', ['namespace', 'status'], registry=registry)
cluster_cpu_capacity = Gauge('k8s_cluster_cpu_capacity_cores', 'Total CPU capacity in cores', registry=registry)
cluster_memory_capacity = Gauge('k8s_cluster_memory_capacity_bytes', 'Total memory capacity in bytes', registry=registry)
cluster_cpu_allocatable = Gauge('k8s_cluster_cpu_allocatable_cores', 'Total allocatable CPU in cores', registry=registry)
cluster_memory_allocatable = Gauge('k8s_cluster_memory_allocatable_bytes', 'Total allocatable memory in bytes', registry=registry)

CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'kubernetes')

def run_kubectl(command):
    """Execute kubectl command and return parsed JSON output"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        return None
    except Exception as e:
        print(f"Error running kubectl: {e}")
        return None

def collect_node_metrics():
    """Collect node-related metrics"""
    try:
        nodes = run_kubectl('kubectl get nodes -o json')
        if not nodes or 'items' not in nodes:
            return

        total_nodes = len(nodes['items'])
        ready_nodes = 0
        total_cpu = 0
        total_memory = 0
        total_cpu_alloc = 0
        total_memory_alloc = 0

        for node in nodes['items']:
            # Count ready nodes
            conditions = node.get('status', {}).get('conditions', [])
            for condition in conditions:
                if condition.get('type') == 'Ready' and condition.get('status') == 'True':
                    ready_nodes += 1
                    break

            # Sum capacity and allocatable
            capacity = node.get('status', {}).get('capacity', {})
            allocatable = node.get('status', {}).get('allocatable', {})

            # CPU (convert from millicores to cores)
            cpu_cap = capacity.get('cpu', '0')
            cpu_alloc = allocatable.get('cpu', '0')
            total_cpu += float(cpu_cap.replace('m', '')) if 'm' in cpu_cap else float(cpu_cap) * 1000
            total_cpu_alloc += float(cpu_alloc.replace('m', '')) if 'm' in cpu_alloc else float(cpu_alloc) * 1000

            # Memory (convert to bytes)
            mem_cap = capacity.get('memory', '0Ki')
            mem_alloc = allocatable.get('memory', '0Ki')
            total_memory += parse_memory(mem_cap)
            total_memory_alloc += parse_memory(mem_alloc)

        cluster_nodes_total.set(total_nodes)
        cluster_nodes_ready.set(ready_nodes)
        cluster_cpu_capacity.set(total_cpu / 1000)  # Convert to cores
        cluster_memory_capacity.set(total_memory)
        cluster_cpu_allocatable.set(total_cpu_alloc / 1000)  # Convert to cores
        cluster_memory_allocatable.set(total_memory_alloc)

        print(f"✓ Collected node metrics: {total_nodes} total, {ready_nodes} ready")
    except Exception as e:
        print(f"Error collecting node metrics: {e}")

def parse_memory(mem_str):
    """Parse memory string to bytes"""
    units = {'Ki': 1024, 'Mi': 1024**2, 'Gi': 1024**3, 'Ti': 1024**4}
    for unit, multiplier in units.items():
        if unit in mem_str:
            return int(mem_str.replace(unit, '')) * multiplier
    return int(mem_str) if mem_str.isdigit() else 0

def collect_namespace_metrics():
    """Collect namespace count"""
    try:
        namespaces = run_kubectl('kubectl get namespaces -o json')
        if namespaces and 'items' in namespaces:
            count = len(namespaces['items'])
            cluster_namespaces_total.set(count)
            print(f"✓ Collected namespace metrics: {count} namespaces")
    except Exception as e:
        print(f"Error collecting namespace metrics: {e}")

def collect_workload_metrics():
    """Collect workload metrics (deployments, pods, etc)"""
    try:
        # Deployments by namespace
        deployments = run_kubectl('kubectl get deployments --all-namespaces -o json')
        if deployments and 'items' in deployments:
            deploy_by_ns = {}
            for deploy in deployments['items']:
                ns = deploy.get('metadata', {}).get('namespace', 'unknown')
                deploy_by_ns[ns] = deploy_by_ns.get(ns, 0) + 1

            for ns, count in deploy_by_ns.items():
                cluster_deployments_total.labels(namespace=ns).set(count)
            print(f"✓ Collected deployment metrics: {len(deployments['items'])} total")

        # Pods by namespace and phase
        pods = run_kubectl('kubectl get pods --all-namespaces -o json')
        if pods and 'items' in pods:
            pod_by_ns_phase = {}
            for pod in pods['items']:
                ns = pod.get('metadata', {}).get('namespace', 'unknown')
                phase = pod.get('status', {}).get('phase', 'Unknown')
                key = (ns, phase)
                pod_by_ns_phase[key] = pod_by_ns_phase.get(key, 0) + 1

            for (ns, phase), count in pod_by_ns_phase.items():
                cluster_pods_total.labels(namespace=ns, phase=phase).set(count)
            print(f"✓ Collected pod metrics: {len(pods['items'])} total")

        # Services by namespace and type
        services = run_kubectl('kubectl get services --all-namespaces -o json')
        if services and 'items' in services:
            svc_by_ns_type = {}
            for svc in services['items']:
                ns = svc.get('metadata', {}).get('namespace', 'unknown')
                svc_type = svc.get('spec', {}).get('type', 'ClusterIP')
                key = (ns, svc_type)
                svc_by_ns_type[key] = svc_by_ns_type.get(key, 0) + 1

            for (ns, svc_type), count in svc_by_ns_type.items():
                cluster_services_total.labels(namespace=ns, type=svc_type).set(count)
            print(f"✓ Collected service metrics: {len(services['items'])} total")

        # PVCs by namespace and status
        pvcs = run_kubectl('kubectl get pvc --all-namespaces -o json')
        if pvcs and 'items' in pvcs:
            pvc_by_ns_status = {}
            for pvc in pvcs['items']:
                ns = pvc.get('metadata', {}).get('namespace', 'unknown')
                status = pvc.get('status', {}).get('phase', 'Unknown')
                key = (ns, status)
                pvc_by_ns_status[key] = pvc_by_ns_status.get(key, 0) + 1

            for (ns, status), count in pvc_by_ns_status.items():
                cluster_pvcs_total.labels(namespace=ns, status=status).set(count)
            print(f"✓ Collected PVC metrics: {len(pvcs['items'])} total")

        # ConfigMaps by namespace
        cms = run_kubectl('kubectl get configmaps --all-namespaces -o json')
        if cms and 'items' in cms:
            cm_by_ns = {}
            for cm in cms['items']:
                ns = cm.get('metadata', {}).get('namespace', 'unknown')
                cm_by_ns[ns] = cm_by_ns.get(ns, 0) + 1

            for ns, count in cm_by_ns.items():
                cluster_configmaps_total.labels(namespace=ns).set(count)
            print(f"✓ Collected ConfigMap metrics: {len(cms['items'])} total")

        # Secrets by namespace
        secrets = run_kubectl('kubectl get secrets --all-namespaces -o json')
        if secrets and 'items' in secrets:
            secret_by_ns = {}
            for secret in secrets['items']:
                ns = secret.get('metadata', {}).get('namespace', 'unknown')
                secret_by_ns[ns] = secret_by_ns.get(ns, 0) + 1

            for ns, count in secret_by_ns.items():
                cluster_secrets_total.labels(namespace=ns).set(count)
            print(f"✓ Collected Secret metrics: {len(secrets['items'])} total")

        # Ingresses by namespace
        ingresses = run_kubectl('kubectl get ingresses --all-namespaces -o json')
        if ingresses and 'items' in ingresses:
            ing_by_ns = {}
            for ing in ingresses['items']:
                ns = ing.get('metadata', {}).get('namespace', 'unknown')
                ing_by_ns[ns] = ing_by_ns.get(ns, 0) + 1

            for ns, count in ing_by_ns.items():
                cluster_ingresses_total.labels(namespace=ns).set(count)
            print(f"✓ Collected Ingress metrics: {len(ingresses['items'])} total")

        # CronJobs by namespace
        cronjobs = run_kubectl('kubectl get cronjobs --all-namespaces -o json')
        if cronjobs and 'items' in cronjobs:
            cj_by_ns = {}
            for cj in cronjobs['items']:
                ns = cj.get('metadata', {}).get('namespace', 'unknown')
                cj_by_ns[ns] = cj_by_ns.get(ns, 0) + 1

            for ns, count in cj_by_ns.items():
                cluster_cronjobs_total.labels(namespace=ns).set(count)
            print(f"✓ Collected CronJob metrics: {len(cronjobs['items'])} total")

        # Jobs by namespace and status
        jobs = run_kubectl('kubectl get jobs --all-namespaces -o json')
        if jobs and 'items' in jobs:
            job_by_ns_status = {}
            for job in jobs['items']:
                ns = job.get('metadata', {}).get('namespace', 'unknown')
                status = job.get('status', {})
                if status.get('succeeded', 0) > 0:
                    job_status = 'succeeded'
                elif status.get('failed', 0) > 0:
                    job_status = 'failed'
                elif status.get('active', 0) > 0:
                    job_status = 'active'
                else:
                    job_status = 'unknown'
                key = (ns, job_status)
                job_by_ns_status[key] = job_by_ns_status.get(key, 0) + 1

            for (ns, status), count in job_by_ns_status.items():
                cluster_jobs_total.labels(namespace=ns, status=status).set(count)
            print(f"✓ Collected Job metrics: {len(jobs['items'])} total")

    except Exception as e:
        print(f"Error collecting workload metrics: {e}")

def collect_all_metrics():
    """Collect all custom metrics"""
    print(f"\n{'='*60}")
    print(f"📊 Collecting Custom Metrics - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    collect_node_metrics()
    collect_namespace_metrics()
    collect_workload_metrics()

    print(f"{'='*60}\n")

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    try:
        collect_all_metrics()
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)
    except Exception as e:
        print(f"Error generating metrics: {e}")
        return Response(f"Error: {str(e)}", status=500)

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy', 'cluster': CLUSTER_NAME}, 200

@app.route('/')
def index():
    """Index page with links"""
    return f"""
    <html>
        <head><title>Custom Metrics Exporter</title></head>
        <body>
            <h1>Kubernetes Custom Metrics Exporter</h1>
            <p>Cluster: <strong>{CLUSTER_NAME}</strong></p>
            <ul>
                <li><a href="/metrics">Prometheus Metrics</a></li>
                <li><a href="/health">Health Check</a></li>
            </ul>
            <h2>Available Metrics:</h2>
            <ul>
                <li>k8s_cluster_nodes_total</li>
                <li>k8s_cluster_nodes_ready</li>
                <li>k8s_cluster_namespaces_total</li>
                <li>k8s_cluster_deployments_total</li>
                <li>k8s_cluster_pods_total</li>
                <li>k8s_cluster_services_total</li>
                <li>k8s_cluster_pvcs_total</li>
                <li>k8s_cluster_configmaps_total</li>
                <li>k8s_cluster_secrets_total</li>
                <li>k8s_cluster_ingresses_total</li>
                <li>k8s_cluster_cronjobs_total</li>
                <li>k8s_cluster_jobs_total</li>
                <li>k8s_cluster_cpu_capacity_cores</li>
                <li>k8s_cluster_memory_capacity_bytes</li>
                <li>k8s_cluster_cpu_allocatable_cores</li>
                <li>k8s_cluster_memory_allocatable_bytes</li>
            </ul>
        </body>
    </html>
    """

if __name__ == '__main__':
    print(f"🚀 Starting Custom Metrics Exporter for cluster: {CLUSTER_NAME}")
    print(f"📊 Metrics available at http://0.0.0.0:8080/metrics")
    app.run(host='0.0.0.0', port=8080)
