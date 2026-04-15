import json
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote


DOCKER_SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
API_VERSION = os.environ.get("DOCKER_API_VERSION", "v1.51")
HOST = os.environ.get("EXPORTER_HOST", "0.0.0.0")
PORT = int(os.environ.get("EXPORTER_PORT", "9115"))
TARGET_COMPOSE_PROJECT = os.environ.get("TARGET_COMPOSE_PROJECT", "yun-mon")
MAX_WORKERS = int(os.environ.get("EXPORTER_MAX_WORKERS", "8"))


def prom_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def metric_line(name: str, value, labels: dict | None = None) -> str:
    if labels:
        parts = [f'{key}="{prom_escape(str(val))}"' for key, val in sorted(labels.items())]
        return f"{name}{{{','.join(parts)}}} {value}"
    return f"{name} {value}"


class DockerSocketClient:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    def get_json(self, path: str):
        status, _, body = self._request("GET", path)
        if status >= 400:
            raise RuntimeError(f"Docker API GET {path} failed with status {status}")
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    def _request(self, method: str, path: str):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(self.socket_path)
        request = (
            f"{method} {path} HTTP/1.1\r\n"
            f"Host: docker\r\n"
            f"User-Agent: yun-mon-docker-stats-exporter\r\n"
            f"Connection: close\r\n\r\n"
        )
        sock.sendall(request.encode("utf-8"))
        stream = sock.makefile("rb")

        status_line = stream.readline().decode("iso-8859-1").strip()
        header_lines = [status_line]
        headers = {}
        while True:
            raw_line = stream.readline()
            if raw_line in (b"", b"\r\n"):
                break
            line = raw_line.decode("iso-8859-1").strip()
            header_lines.append(line)
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip().lower()

        status = int(header_lines[0].split(" ")[1])
        if headers.get("transfer-encoding") == "chunked":
            body = self._read_chunked(stream)
        elif "content-length" in headers:
            body = stream.read(int(headers["content-length"]))
        else:
            body = stream.read()

        stream.close()
        sock.close()

        return status, headers, body

    @staticmethod
    def _read_chunked(stream) -> bytes:
        decoded = b""
        while True:
            size_line = stream.readline()
            if not size_line:
                break
            size = int(size_line.split(b";", 1)[0], 16)
            if size == 0:
                stream.readline()
                break
            decoded += stream.read(size)
            stream.read(2)
        return decoded


def collect_metrics():
    client = DockerSocketClient(DOCKER_SOCKET)
    containers = client.get_json(f"/{API_VERSION}/containers/json") or []
    if TARGET_COMPOSE_PROJECT:
        containers = [
            container
            for container in containers
            if (container.get("Labels") or {}).get("com.docker.compose.project") == TARGET_COMPOSE_PROJECT
        ]
    lines = [
        "# HELP docker_stats_exporter_up Whether the docker stats exporter could talk to the Docker API.",
        "# TYPE docker_stats_exporter_up gauge",
        "docker_stats_exporter_up 1",
        "# HELP docker_container_info Static information for a Docker container.",
        "# TYPE docker_container_info gauge",
        "# HELP docker_container_cpu_usage_ratio Current CPU usage ratio collected from Docker stats.",
        "# TYPE docker_container_cpu_usage_ratio gauge",
        "# HELP docker_container_memory_usage_bytes Current memory usage bytes collected from Docker stats.",
        "# TYPE docker_container_memory_usage_bytes gauge",
        "# HELP docker_container_memory_working_set_bytes Current working set bytes collected from Docker stats.",
        "# TYPE docker_container_memory_working_set_bytes gauge",
        "# HELP docker_container_network_receive_bytes_total Total network receive bytes collected from Docker stats.",
        "# TYPE docker_container_network_receive_bytes_total counter",
        "# HELP docker_container_network_transmit_bytes_total Total network transmit bytes collected from Docker stats.",
        "# TYPE docker_container_network_transmit_bytes_total counter",
        "# HELP docker_container_blkio_read_bytes_total Total block read bytes collected from Docker stats.",
        "# TYPE docker_container_blkio_read_bytes_total counter",
        "# HELP docker_container_blkio_write_bytes_total Total block write bytes collected from Docker stats.",
        "# TYPE docker_container_blkio_write_bytes_total counter",
        "# HELP docker_container_last_seen Unix timestamp when the exporter last observed the container.",
        "# TYPE docker_container_last_seen gauge",
    ]

    now = int(time.time())
    with ThreadPoolExecutor(max_workers=max(1, MAX_WORKERS)) as executor:
        for container_lines in executor.map(lambda c: collect_container_lines(client, c, now), containers):
            lines.extend(container_lines)

    return "\n".join(lines) + "\n"


def collect_container_lines(client: DockerSocketClient, container: dict, now: int):
    lines = []
    try:
        container_id = container.get("Id", "")
        short_id = container_id[:12]
        names = container.get("Names", [])
        container_name = names[0].lstrip("/") if names else short_id
        labels = container.get("Labels") or {}
        compose_project = labels.get("com.docker.compose.project", "")
        compose_service = labels.get("com.docker.compose.service", "")
        service_name = labels.get("service_name", compose_service or container_name)
        image = container.get("Image", "")
        state = container.get("State", "")
        status = container.get("Status", "")

        base_labels = {
            "container_id": short_id,
            "container_name": container_name,
            "compose_project": compose_project,
            "compose_service": compose_service,
            "service_name": service_name,
            "image": image,
            "state": state,
            "status": status,
        }

        lines.append(metric_line("docker_container_info", 1, base_labels))

        try:
            stats = client.get_json(f"/{API_VERSION}/containers/{quote(container_id)}/stats?stream=false")
        except Exception:
            return lines
        if not stats:
            return lines

        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})
        total_usage = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        prev_total_usage = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        system_usage = cpu_stats.get("system_cpu_usage", 0)
        prev_system_usage = precpu_stats.get("system_cpu_usage", 0)
        online_cpus = cpu_stats.get("online_cpus") or len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", []) or [1])
        cpu_delta = max(total_usage - prev_total_usage, 0)
        system_delta = max(system_usage - prev_system_usage, 0)
        cpu_ratio = 0.0
        if system_delta > 0 and online_cpus > 0:
            cpu_ratio = (cpu_delta / system_delta) * online_cpus
        lines.append(metric_line("docker_container_cpu_usage_ratio", cpu_ratio, base_labels))

        memory_stats = stats.get("memory_stats", {})
        memory_usage = memory_stats.get("usage", 0)
        memory_cache = memory_stats.get("stats", {}).get("cache", 0)
        working_set = max(memory_usage - memory_cache, 0)
        lines.append(metric_line("docker_container_memory_usage_bytes", memory_usage, base_labels))
        lines.append(metric_line("docker_container_memory_working_set_bytes", working_set, base_labels))

        rx_total = 0
        tx_total = 0
        for interface_stats in (stats.get("networks") or {}).values():
            rx_total += interface_stats.get("rx_bytes", 0)
            tx_total += interface_stats.get("tx_bytes", 0)
        lines.append(metric_line("docker_container_network_receive_bytes_total", rx_total, base_labels))
        lines.append(metric_line("docker_container_network_transmit_bytes_total", tx_total, base_labels))

        blkio_entries = stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []
        read_bytes = 0
        write_bytes = 0
        for entry in blkio_entries:
            op = str(entry.get("op", "")).lower()
            value = entry.get("value", 0)
            if op == "read":
                read_bytes += value
            elif op == "write":
                write_bytes += value
        lines.append(metric_line("docker_container_blkio_read_bytes_total", read_bytes, base_labels))
        lines.append(metric_line("docker_container_blkio_write_bytes_total", write_bytes, base_labels))

        lines.append(metric_line("docker_container_last_seen", now, base_labels))
    except Exception:
        return lines

    return lines


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/metrics", "/"):
            self.send_response(404)
            self.end_headers()
            return

        try:
            payload = collect_metrics().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            payload = (
                "# HELP docker_stats_exporter_up Whether the docker stats exporter could talk to the Docker API.\n"
                "# TYPE docker_stats_exporter_up gauge\n"
                "docker_stats_exporter_up 0\n"
                f"# Export error: {exc}\n"
            ).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), MetricsHandler)
    server.serve_forever()
