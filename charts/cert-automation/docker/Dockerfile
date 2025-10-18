FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar script da aplicação
COPY app.py .

# Expor porta 8080 (padrão Knative)
EXPOSE 8080

# Rodar aplicação
CMD ["python", "-u", "app.py"]
