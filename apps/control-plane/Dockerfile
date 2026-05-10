FROM python:3.12-slim AS build

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip build \
    && python -m build --wheel --outdir /dist

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CONTROL_PLANE_HTTP_PORT=8090

WORKDIR /app

COPY --from=build /dist /tmp/dist
RUN pip install --no-cache-dir /tmp/dist/*.whl \
    && rm -rf /tmp/dist

COPY web/dist /app/web/dist

EXPOSE 8090

CMD ["python", "-m", "yunmon_control_plane.main"]
