# 1. Imagen base oficial ligera de Python
FROM python:3.11-slim

# 2. Variables de entorno de ejecución
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# 3. Directorio de trabajo en el contenedor
WORKDIR /app

# 4. Instalar dependencias mínimas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 5. Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copiar el código de la aplicación
COPY . /app

# 7. Exponer el puerto de Streamlit
EXPOSE 8501

# 8. Comando de arranque de la interfaz MediFlow
ENTRYPOINT ["streamlit", "run", "app.py"]