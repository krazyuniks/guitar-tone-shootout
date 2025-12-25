"""Flask web application for Guitar Tone Shootout."""

import logging
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Application factory."""
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    # Configuration
    app.config.update(
        SECRET_KEY="change-this-in-production",
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB max upload
    )

    # Register routes
    register_routes(app)

    return app


def register_routes(app: Flask) -> None:
    """Register all routes."""

    @app.route("/")
    def index() -> str:
        """Home page."""
        return render_template("index.html")

    @app.route("/compare")
    def compare() -> str:
        """New comparison builder page."""
        return render_template("compare.html")

    @app.route("/browse")
    def browse() -> str:
        """Browse existing comparisons."""
        comparisons: list[dict[str, Any]] = []
        return render_template("browse.html", comparisons=comparisons)

    @app.route("/about")
    def about() -> str:
        """About page."""
        return render_template("about.html")

    # API Routes for HTMX

    @app.route("/api/models", methods=["GET"])
    def list_models() -> Response:
        """List available NAM models."""
        models: list[str] = []
        models_dir = Path("../inputs/nam_models")
        if models_dir.exists():
            models = [str(p.relative_to(models_dir)) for p in models_dir.rglob("*.nam")]
        return jsonify(models)

    @app.route("/api/irs", methods=["GET"])
    def list_irs() -> Response:
        """List available cabinet IRs."""
        irs: list[str] = []
        irs_dir = Path("../inputs/irs")
        if irs_dir.exists():
            irs = [str(p.relative_to(irs_dir)) for p in irs_dir.rglob("*.wav")]
        return jsonify(irs)

    @app.route("/api/di-tracks", methods=["GET"])
    def list_di_tracks() -> Response:
        """List available DI tracks."""
        tracks: list[str] = []
        tracks_dir = Path("../inputs/di_tracks")
        if tracks_dir.exists():
            tracks = [
                str(p.relative_to(tracks_dir))
                for p in tracks_dir.glob("*")
                if p.suffix.lower() in [".wav", ".flac"]
            ]
        return jsonify(tracks)

    @app.route("/api/comparison", methods=["POST"])
    def create_comparison() -> Response:
        """Create a new comparison from form data."""
        _data = request.json  # noqa: F841 - will be used when TODO is implemented

        # TODO: Validate data
        # TODO: Generate INI file
        # TODO: Queue processing job

        return jsonify(
            {
                "status": "created",
                "id": "placeholder-id",
                "message": "Comparison queued for processing",
            }
        )

    @app.route("/api/comparison/<comparison_id>/status", methods=["GET"])
    def comparison_status(comparison_id: str) -> Response:
        """Get processing status of a comparison."""
        return jsonify(
            {
                "id": comparison_id,
                "status": "pending",
                "progress": 0,
            }
        )

    # HTMX Partials

    @app.route("/partials/model-select", methods=["GET"])
    def model_select_partial() -> str:
        """Render model selection dropdown options."""
        models: list[str] = []
        models_dir = Path("../inputs/nam_models")
        if models_dir.exists():
            models = [str(p.relative_to(models_dir)) for p in models_dir.rglob("*.nam")]
        return render_template("partials/model_options.html", models=models)

    @app.route("/partials/ir-select", methods=["GET"])
    def ir_select_partial() -> str:
        """Render IR selection dropdown options."""
        irs: list[str] = []
        irs_dir = Path("../inputs/irs")
        if irs_dir.exists():
            irs = [str(p.relative_to(irs_dir)) for p in irs_dir.rglob("*.wav")]
        return render_template("partials/ir_options.html", irs=irs)


# For direct execution
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
