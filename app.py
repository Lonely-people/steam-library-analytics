"""Flask entry point for the Steam library and play-cost analysis system."""

from flask import Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__)

    from routes.games import bp as games_bp
    from routes.games import register_error_handlers
    from routes.pages import page_bp
    from routes.purchases import bp as purchases_bp
    from routes.purchases import register_error_handlers as register_purchase_handlers
    from routes.statistics import bp as stats_bp

    app.register_blueprint(games_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(page_bp)
    register_error_handlers(app)
    register_purchase_handlers(app)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "phase": "S7"})

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
