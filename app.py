"""Flask entry point for the Steam library and play-cost analysis system."""

from flask import Flask, jsonify, render_template


def create_app() -> Flask:
    app = Flask(__name__)

    from routes.games import bp as games_bp
    from routes.games import register_error_handlers

    app.register_blueprint(games_bp)
    register_error_handlers(app)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "phase": "S5"})

    return app


app = create_app()

if __name__ == "__main__":
    from config import Config

    # Bind to loopback only; this app is for local use.
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
    )
