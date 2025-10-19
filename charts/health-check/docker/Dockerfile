FROM python:3.11-slim

WORKDIR /app

# Instalar kubectl e ferramentas de rede
RUN apt-get update && \
    apt-get install -y curl iputils-ping dnsutils && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/ && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY health_check.py .

EXPOSE 8080

CMD ["python", "-u", "health_check.py"]
