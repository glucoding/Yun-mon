"""控制面进程入口。"""

from __future__ import annotations

import uvicorn

from .api import create_app
from .config import get_settings


def main() -> None:
    settings = get_settings()
    app = create_app(settings=settings)
    uvicorn.run(app, host=settings.http_host, port=settings.http_port, log_level="info")


if __name__ == "__main__":
    main()
