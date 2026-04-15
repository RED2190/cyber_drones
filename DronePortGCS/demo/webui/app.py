from __future__ import annotations

import atexit
import os
import signal
import traceback

from flask import Flask

from demo.webui.routes import droneport_api, nus_api, pages, system_api
from demo.webui.runtime import DEMO_ROOT, demo
from demo.webui.utils import discover_bind_urls, env_bool


_CLEANUP_DONE = False


def cleanup_demo_stack() -> None:
    global _CLEANUP_DONE
    if _CLEANUP_DONE:
        return

    _CLEANUP_DONE = True
    print("\n[shutdown] Stopping demo stack...")
    try:
        output = demo.down_all()
        if output:
            print(output)
        print("[shutdown] Demo stack stopped.")
    except Exception as exc:
        print(f"[shutdown] Failed to stop demo stack cleanly: {exc}")
        print(f"[shutdown] Traceback: {traceback.format_exc()}")


def _handle_exit_signal(signum, _frame) -> None:
    signal_name = signal.Signals(signum).name
    print(f"\n[shutdown] Received {signal_name}.")
    cleanup_demo_stack()
    raise SystemExit(128 + signum)


def bootstrap_gcs_stack() -> None:
    auto_bootstrap = env_bool("GCS_WEB_AUTO_BOOTSTRAP", True)
    if not auto_bootstrap:
        return

    print("[bootstrap] Starting stack: broker → SITL → GCS → DronePort → AgroDron")
    try:
        print("[bootstrap] Step 1/7: Preparing systems... ")
        demo.prepare_systems_stream(on_output=lambda chunk: print(chunk, end=""))

        print("\n[bootstrap] Step 2/7: Starting broker (shared)... ")
        demo.broker_up_stream(on_output=lambda chunk: print(chunk, end=""))
        demo.wait_for_broker(timeout=90)

        print("\n[bootstrap] Step 3/7: Starting SITL... ")
        demo.sitl_up_stream(on_output=lambda chunk: print(chunk, end=""))

        print("\n[bootstrap] Step 4/7: Starting GCS... ")
        demo.gcs_up_stream(on_output=lambda chunk: print(chunk, end=""))

        print("\n[bootstrap] Step 5/7: Starting DronePort (no broker)... ")
        demo.drone_port_up_stream(on_output=lambda chunk: print(chunk, end=""))

        print("\n[bootstrap] Step 6/7: Starting AgroDron (no broker)... ")
        demo.cyber_drons_up_stream(on_output=lambda chunk: print(chunk, end=""))

        print("\n[bootstrap] Step 7/7: Connecting and waiting for readiness... ")
        demo.connect_bus()
        demo.wait_until_ready(timeout=180)

        print("[bootstrap] ✓ All components ready (shared broker).")
    except Exception as exc:
        print(f"[bootstrap] ✗ Failed: {exc}")
        print(f"[bootstrap] Traceback: {traceback.format_exc()}")
        print("[bootstrap] Web UI exposed, components may be unavailable.")


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(DEMO_ROOT / "templates"),
        static_folder=str(DEMO_ROOT / "static"),
    )
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.register_blueprint(pages)
    app.register_blueprint(system_api)
    app.register_blueprint(nus_api)
    app.register_blueprint(droneport_api)
    return app


def run_server() -> None:
    app = create_app()
    app.jinja_env.auto_reload = True
    atexit.register(cleanup_demo_stack)
    signal.signal(signal.SIGINT, _handle_exit_signal)
    signal.signal(signal.SIGTERM, _handle_exit_signal)
    bootstrap_gcs_stack()

    host = os.environ.get("GCS_WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("GCS_WEB_PORT", "8000"))
    debug = env_bool("GCS_WEB_DEBUG", False)

    print("[web] Interface is available at:")
    for url in discover_bind_urls(host, port):
        print(f"[web]   {url}")

    try:
        app.run(host=host, port=port, debug=debug, threaded=True)
    finally:
        cleanup_demo_stack()
