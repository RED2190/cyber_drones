from __future__ import annotations

from flask import Blueprint, render_template, send_from_directory

from demo.webui.page_context import build_index_context
from demo.webui.runtime import GCS_C4_DIR, GCS_DIAGRAMS_DIR


pages = Blueprint("pages", __name__)


@pages.get("/")
def index():
    return render_template("web/index.html", **build_index_context())


@pages.get("/gcs-diagrams/<path:filename>")
def gcs_diagrams(filename: str):
    return send_from_directory(GCS_DIAGRAMS_DIR, filename)


@pages.get("/gcs-c4/<path:filename>")
def gcs_c4(filename: str):
    return send_from_directory(GCS_C4_DIR, filename)
