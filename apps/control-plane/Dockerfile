FROM python:3.12-alpine

WORKDIR /app

COPY server.py /app/server.py
COPY static /app/static

EXPOSE 8090

CMD ["python", "/app/server.py"]
