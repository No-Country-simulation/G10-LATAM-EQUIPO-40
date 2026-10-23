FROM python:3.14-alpine3.23@sha256:7c68a82e9ba8544ff4552abaa5b03907d1d9f9f6925eb2b229c0dff842078838 AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY . /app

FROM python:3.14-alpine3.23@sha256:7c68a82e9ba8544ff4552abaa5b03907d1d9f9f6925eb2b229c0dff842078838 AS runtime

WORKDIR /app

COPY --from=build /app/.venv /app/.venv

COPY --from=build /app/app /app/app

COPY --from=build /app/main.py /app/streamlit_app.py /app/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]