# 1. Imagen base oficial de Python 3.14
FROM python:3.14-slim

# 2. Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 3. Directorio de trabajo
WORKDIR /app

# 4. Instalar dependencias mínimas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 5. Instalar uv
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/

# 6. Copiar archivos de configuración
COPY pyproject.toml uv.lock ./

# 7. Instalar dependencias del proyecto
RUN uv sync --frozen --no-dev

# 8. Copiar el código de la aplicación
COPY . /app

# 9. Activar el entorno virtual
ENV PATH="/app/.venv/bin:$PATH"

# 10. Exponer el puerto de Streamlit
EXPOSE 8501

# 11. Arrancar la aplicación
ENTRYPOINT ["streamlit", "run", "streamlit_app.py"]