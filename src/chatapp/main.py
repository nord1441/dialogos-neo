from __future__ import annotations

import argparse
import logging
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import Settings, load_keys
from .routes import api as api_routes
from .routes import messages as message_routes
from .routes import pages as page_routes


log = logging.getLogger("chatapp")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.profiles_root.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="chatapp", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.keys = load_keys(settings)
    app.state.templates = Jinja2Templates(directory=str(settings.templates_dir))

    if settings.static_dir.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(settings.static_dir)),
            name="static",
        )

    app.include_router(page_routes.router)
    app.include_router(message_routes.router)
    app.include_router(api_routes.router)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "profiles_root": str(settings.profiles_root)}

    return app


# Default ASGI app for `uvicorn chatapp.main:app`.
app = create_app()


def cli() -> None:
    parser = argparse.ArgumentParser(prog="chatapp")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="run the HTTP server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    if args.cmd == "serve":
        import uvicorn

        settings = Settings.from_env()
        host_port = settings.listen_addr.split(":")
        host = args.host or host_port[0]
        port = args.port or int(host_port[1] if len(host_port) > 1 else "8080")

        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

        uvicorn.run(
            "chatapp.main:app",
            host=host,
            port=port,
            log_level=settings.log_level,
        )
    else:
        parser.print_help()
        sys.exit(1)
