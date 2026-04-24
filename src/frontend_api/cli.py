"""Command line entrypoint for running the read-only API server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from frontend_api.adapters.assembly_adapter import AssemblyAdapter
from frontend_api.settings import FrontendApiSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project-ult-frontend-api")
    subcommands = parser.add_subparsers(dest="command")

    serve = subcommands.add_parser("serve", help="run the FastAPI server")
    serve.add_argument("--project-root", default=None)
    serve.add_argument("--profile", default=None)
    serve.add_argument("--mode", default=None)
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    health = subcommands.add_parser("health", help="print read-only health JSON")
    health.add_argument("--project-root", default=None)
    health.add_argument("--profile", default=None)
    health.add_argument("--mode", default=None)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2

    settings = _settings_from_args(args)

    if args.command == "health":
        adapter = AssemblyAdapter(
            project_root=settings.project_root,
            active_profile=settings.profile,
            mode=settings.mode,
        )
        print(json.dumps(adapter.health().model_dump(mode="json"), indent=2))
        return 0

    if args.command == "serve":
        import uvicorn

        from frontend_api.app import create_app

        uvicorn.run(
            create_app(settings),
            host=settings.host,
            port=settings.port,
            reload=False,
        )
        return 0

    return 2


def _settings_from_args(args: argparse.Namespace) -> FrontendApiSettings:
    settings = FrontendApiSettings.from_env()
    updates: dict[str, object] = {}
    if getattr(args, "project_root", None):
        updates["project_root"] = Path(args.project_root)
    if getattr(args, "profile", None):
        updates["profile"] = args.profile
    if getattr(args, "mode", None):
        updates["mode"] = args.mode
    if getattr(args, "host", None):
        updates["host"] = args.host
    if getattr(args, "port", None):
        updates["port"] = args.port
    return settings.model_copy(update=updates)


if __name__ == "__main__":
    raise SystemExit(main())
