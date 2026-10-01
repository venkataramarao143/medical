"""
MedAnnotate — Production Flask App
Connects to MongoDB. All data stored and retrieved from DB.
"""
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
import os

from config import Config
from extensions import mongo, jwt


def create_app():
    app = Flask(__name__, static_folder='frontend', static_url_path='')
    app.config.from_object(Config)

    # Use lazy connection — app starts even if MongoDB is initializing
    mongo_uri = Config.MONGO_URI
    if 'mongodb+srv' in mongo_uri:
        app.config['MONGO_URI'] = mongo_uri
        if Config.MONGO_CONNECT_KWARGS:
            for k, v in Config.MONGO_CONNECT_KWARGS.items():
                app.config[f'MONGO_{k.upper()}'] = v
    else:
        # Local MongoDB — add connect=false for lazy init
        if '?' in mongo_uri:
            app.config['MONGO_URI'] = mongo_uri + '&connect=false'
        else:
            app.config['MONGO_URI'] = mongo_uri + '?connect=false'

    # Extensions
    CORS(app, resources={r'/api/*': {'origins': '*'}})
    mongo.init_app(app)
    jwt.init_app(app)

    # Blueprints
    from routes.auth        import auth_bp
    from routes.images      import images_bp
    from routes.annotations import annotations_bp
    from routes.admin       import admin_bp

    app.register_blueprint(auth_bp,        url_prefix='/api/auth')
    app.register_blueprint(images_bp,      url_prefix='/api/images')
    app.register_blueprint(annotations_bp, url_prefix='/api/annotations')
    app.register_blueprint(admin_bp,       url_prefix='/api/admin')

    # ── Frontend HTML routes ──────────────────────────────
    @app.route('/')
    def index():      return send_from_directory('frontend', 'index.html')

    @app.route('/login')
    def login_page(): return send_from_directory('frontend', 'login.html')

    @app.route('/register')
    def register_page(): return send_from_directory('frontend', 'register.html')

    @app.route('/doctor/dashboard')
    def doctor_dashboard(): return send_from_directory('frontend/doctor', 'dashboard.html')

    @app.route('/doctor/annotate')
    def doctor_annotate():  return send_from_directory('frontend/doctor', 'annotate.html')

    @app.route('/doctor/earnings')
    def doctor_earnings():  return send_from_directory('frontend/doctor', 'earnings.html')

    @app.route('/company/dashboard')
    def company_dashboard(): return send_from_directory('frontend/company', 'dashboard.html')

    @app.route('/company/upload')
    def company_upload():    return send_from_directory('frontend/company', 'upload.html')

    @app.route('/company/batches')
    def company_batches():   return send_from_directory('frontend/company', 'batches.html')

    @app.route('/company/review')
    def company_review():    return send_from_directory('frontend/company', 'review.html')

    @app.route('/admin/dashboard')
    def admin_dashboard():   return send_from_directory('frontend/admin', 'dashboard.html')

    # ── Static files ──────────────────────────────────────
    @app.route('/css/<path:filename>')
    def css(filename): return send_from_directory('frontend/css', filename)

    @app.route('/js/<path:filename>')
    def js(filename):  return send_from_directory('frontend/js', filename)

    # ── Error handlers ────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e): return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(413)
    def too_large(e): return jsonify({'error': 'File too large (max 500MB)'}), 413

    @app.errorhandler(500)
    def server_error(e): return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    print("\n" + "="*55)
    print("  MedAnnotate -- Production Server")
    print("="*55)
    print("  URL:   http://localhost:5000")
    db_display = Config.MONGO_URI.split('@')[-1] if '@' in Config.MONGO_URI else Config.MONGO_URI
    print("  DB:   ", db_display)
    print()
    print("  First time? Create admin account:")
    print("  Open: http://localhost:5000/api/admin/seed")
    print("="*55 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
