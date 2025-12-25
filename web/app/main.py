"""Flask web application for Guitar Tone Shootout."""

import logging
from pathlib import Path

from flask import Flask, render_template, request, jsonify

logger = logging.getLogger(__name__)


def create_app():
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


def register_routes(app: Flask):
    """Register all routes."""

    @app.route("/")
    def index():
        """Home page."""
        return render_template("index.html")

    @app.route("/compare")
    def compare():
        """New comparison builder page."""
        return render_template("compare.html")

    @app.route("/browse")
    def browse():
        """Browse existing comparisons."""
        comparisons = []
        return render_template("browse.html", comparisons=comparisons)

    @app.route("/about")
    def about():
        """About page."""
        return render_template("about.html")

    # API Routes for HTMX

    @app.route("/api/models", methods=["GET"])
    def list_models():
        """List available NAM models."""
        models = []
        models_dir = Path("../inputs/nam_models")
        if models_dir.exists():
            models = [str(p.relative_to(models_dir)) for p in models_dir.rglob("*.nam")]
        return jsonify(models)

    @app.route("/api/irs", methods=["GET"])
    def list_irs():
        """List available cabinet IRs."""
        irs = []
        irs_dir = Path("../inputs/irs")
        if irs_dir.exists():
            irs = [str(p.relative_to(irs_dir)) for p in irs_dir.rglob("*.wav")]
        return jsonify(irs)

    @app.route("/api/di-tracks", methods=["GET"])
    def list_di_tracks():
        """List available DI tracks."""
        tracks = []
        tracks_dir = Path("../inputs/di_tracks")
        if tracks_dir.exists():
            tracks = [
                str(p.relative_to(tracks_dir))
                for p in tracks_dir.glob("*")
                if p.suffix.lower() in [".wav", ".flac"]
            ]
        return jsonify(tracks)

    @app.route("/api/comparison", methods=["POST"])
    def create_comparison():
        """Create a new comparison from form data."""
        data = request.json
        
        # TODO: Validate data
        # TODO: Generate INI file
        # TODO: Queue processing job
        
        return jsonify({
            "status": "created",
            "id": "placeholder-id",
            "message": "Comparison queued for processing",
        })

    @app.route("/api/comparison/<comparison_id>/status", methods=["GET"])
    def comparison_status(comparison_id: str):
        """Get processing status of a comparison."""
        return jsonify({
            "id": comparison_id,
            "status": "pending",
            "progress": 0,
        })

    # HTMX Partials

    @app.route("/partials/model-select", methods=["GET"])
    def model_select_partial():
        """Render model selection dropdown options."""
        models = []
        models_dir = Path("../inputs/nam_models")
        if models_dir.exists():
            models = [str(p.relative_to(models_dir)) for p in models_dir.rglob("*.nam")]
        return render_template("partials/model_options.html", models=models)

    @app.route("/partials/ir-select", methods=["GET"])
    def ir_select_partial():
        """Render IR selection dropdown options."""
        irs = []
        irs_dir = Path("../inputs/irs")
        if irs_dir.exists():
            irs = [str(p.relative_to(irs_dir)) for p in irs_dir.rglob("*.wav")]
        return render_template("partials/ir_options.html", irs=irs)


# For direct execution
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
