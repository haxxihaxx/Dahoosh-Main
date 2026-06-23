import sys
import io

# Force UTF-8 output on Windows (avoids UnicodeEncodeError with Persian/Arabic text
# when the console codepage is cp1252 or another narrow encoding).
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import os
from services.grading_service import GradingService
from services.storage_manager import StorageManager
from services.file_manager import FileManager
from handlers.flask_api_handler import FlaskAPIHandler
from handlers.new_features_handler import NewFeaturesHandler
from pathlib import Path

load_dotenv()


class WebPageServer:
    pass


def create_app():
    app = Flask(__name__)

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin', '')
        allowed_origins = [
            'http://localhost:3000',
            'http://localhost:3001',
            'http://127.0.0.1:3000',
            'http://192.168.56.1:3000',
        ]
        if origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return response
    @app.route('/download/<filename>')

    @app.errorhandler(500)
    def handle_500(e):
        from flask import jsonify
        return jsonify({'success': False, 'error': f'Internal server error: {str(e)}'}), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        from flask import jsonify
        import traceback
        print(traceback.format_exc())  # Print full traceback to Flask console
        return jsonify({'success': False, 'error': str(e)}), 500

    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
                "http://192.168.56.1:3000",  # Local network host (VirtualBox/LAN)
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Disposition"],
            "supports_credentials": False,
            "automatic_options": True  # Auto-handle OPTIONS preflight requests
        }
    })
    
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    openai_api_key = os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not openai_api_key or openai_api_key in ('your_openai_api_key_here', 'your_gapgpt_api_key_here'):
        print("WARNING: API key not set in .env file")
        print("Please set GAPGPT_API_KEY in your .env file")
    
    grading_service = GradingService(api_key=openai_api_key)
    file_manager = FileManager()
    storage_manager = StorageManager()
    web_page_server = WebPageServer()
    
    api_handler = FlaskAPIHandler(
        grading_service=grading_service,
        file_manager=file_manager,
        storage_manager=storage_manager,
        web_page_server=web_page_server
    )
    
    new_features_handler = NewFeaturesHandler(api_key=openai_api_key)
    
    app.register_blueprint(api_handler.get_blueprint())
    app.register_blueprint(new_features_handler.get_blueprint())
    
    @app.route('/')
    def index():
        return {
            'message': 'Grading System API with OpenAI - داهوش',
            'version': '3.0',
            'ai_provider': 'OpenAI',
            'endpoints': {
                # --- Original ---
                'upload_answer_key': 'POST /api/upload-answer-key/<test_id>',
                'upload_student_answers': 'POST /api/upload-student-answers/<test_id>',
                'grade_test': 'POST /api/grade-test/<test_id>',
                'download_report': 'GET /api/download-report/<test_id>/<student_id>',
                # --- RAG ---
                'rag_index': 'POST /api/rag/index',
                'rag_query': 'POST /api/rag/query',
                'rag_documents': 'GET /api/rag/documents',
                'rag_delete': 'DELETE /api/rag/documents/<doc_id>',
                # --- Podcast ---
                'podcast_generate': 'POST /api/podcast/generate',
                'podcast_script': 'POST /api/podcast/script',
                'podcast_download': 'GET /api/podcast/download/<podcast_id>',
                # --- Chatbot ---
                'chatbot_chat': 'POST /api/chatbot/chat',
                'chatbot_history': 'GET /api/chatbot/history/<session_id>',
                'chatbot_clear': 'DELETE /api/chatbot/clear/<session_id>',
                # --- Math Solver ---
                'math_solve_text': 'POST /api/math/solve-text',
                'math_solve_image': 'POST /api/math/solve-image',
            },
            'supported_formats': ['pdf', 'png', 'jpg', 'jpeg', 'txt'],
            'languages': ['English', 'Persian (فارسی)', 'Mixed']
        }
    
    @app.route('/health')
    def health():
        api_key_set = bool(openai_api_key and openai_api_key != 'your_openai_api_key_here')
        return {
            'status': 'healthy',
            'openai_api_key_configured': api_key_set,
            'ai_provider': 'OpenAI',
            'model': os.getenv('OPENAI_MODEL', 'gpt-4o'),
            'cors_enabled': True
        }
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True') == 'True'
    
    print("\n" + "=" * 70)
    print("Grading System with OpenAI - داهوش")
    print("=" * 70)
    print(f"Server starting on http://0.0.0.0:{port}")
    print(f"OpenAI Model: {os.getenv('OPENAI_MODEL', 'gpt-4o')}")
    print(f"CORS Enabled for: http://localhost:3000")
    print("=" * 70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
