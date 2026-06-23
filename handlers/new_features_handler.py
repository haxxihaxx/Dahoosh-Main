"""
Flask API handler for the four new AI features:
  1. RAG system          → /api/rag/*
  2. Podcast generator   → /api/podcast/*
  3. Persian chatbot     → /api/chatbot/*
  4. Math solver         → /api/math/*
"""

import os
import uuid
from flask import Blueprint, request, jsonify, send_file

from werkzeug.utils import secure_filename

from services.rag_service import RAGService
from services.podcast_service import PodcastService
from services.persian_chatbot_service import PersianChatbotService
from services.math_solver_service import MathSolverService
from services.pdf_extractor import PDFExtractor


# ── Resolve absolute paths relative to THIS file so they work no matter
#    which directory Python is launched from. ──────────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))          # …/handlers/
_PROJECT_ROOT = os.path.dirname(_HERE)                              # …/grading_system/
_PODCAST_DIR  = os.path.join(_PROJECT_ROOT, 'storage', 'podcasts') # absolute
_UPLOADS_DIR  = os.path.join(_PROJECT_ROOT, 'uploads')             # absolute


class NewFeaturesHandler:
    ALLOWED_DOC = {'pdf', 'txt'}
    ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

    def __init__(self, api_key: str = None):
        self.rag     = RAGService(api_key)
        self.podcast = PodcastService(api_key)
        self.chatbot = PersianChatbotService(api_key)
        self.math    = MathSolverService(api_key)
        self.pdf_ext = PDFExtractor()

        # Create directories at startup using absolute paths
        os.makedirs(_PODCAST_DIR, exist_ok=True)
        os.makedirs(_UPLOADS_DIR, exist_ok=True)

        self.blueprint = Blueprint('new_features', __name__, url_prefix='/api')
        self._register_routes()

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _allowed(self, filename: str, types: set) -> bool:
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in types

    def _extract_text(self, filepath: str) -> str:
        if filepath.lower().endswith('.pdf'):
            return self.pdf_ext.extractText(filepath)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def _save_upload(self, file, prefix: str = '') -> str:
        """Save an uploaded file to the absolute uploads directory."""
        raw_name = f"{prefix}_{file.filename}" if prefix else file.filename
        filename = secure_filename(raw_name)
        path = os.path.join(_UPLOADS_DIR, filename)
        file.save(path)
        return path

    # ------------------------------------------------------------------ #
    #  Route registration                                                  #
    # ------------------------------------------------------------------ #

    def _register_routes(self):
        bp = self.blueprint

        # ── RAG ──────────────────────────────────────────────────────────
        @bp.route('/rag/index', methods=['POST', 'OPTIONS'])
        def rag_index():
            if request.method == 'OPTIONS':
                return '', 200
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file provided'}), 400
            f      = request.files['file']
            doc_id = request.form.get('doc_id', str(uuid.uuid4())[:8])
            if not self._allowed(f.filename, self.ALLOWED_DOC):
                return jsonify({'success': False, 'error': 'Only PDF or TXT files are accepted'}), 400
            path = self._save_upload(f, f'rag_{doc_id}')
            try:
                text     = self._extract_text(path)
                n_chunks = self.rag.index_document(doc_id, text)
                return jsonify({'success': True, 'doc_id': doc_id,
                                'chunks_created': n_chunks, 'chars': len(text)})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @bp.route('/rag/query', methods=['POST', 'OPTIONS'])
        def rag_query():
            if request.method == 'OPTIONS':
                return '', 200
            data     = request.get_json(force=True)
            question = data.get('question', '').strip()
            doc_id   = data.get('doc_id')
            top_k    = int(data.get('top_k', 5))
            if not question:
                return jsonify({'success': False, 'error': 'question is required'}), 400
            try:
                result = self.rag.query(question, doc_id, top_k)
                return jsonify({'success': True, **result})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @bp.route('/rag/documents', methods=['GET'])
        def rag_list():
            return jsonify({'success': True, 'documents': self.rag.list_documents()})

        @bp.route('/rag/documents/<doc_id>', methods=['DELETE'])
        def rag_delete(doc_id):
            ok = self.rag.delete_document(doc_id)
            return jsonify({'success': ok, 'doc_id': doc_id})

        # ── Podcast ──────────────────────────────────────────────────────
        @bp.route('/podcast/generate', methods=['POST', 'OPTIONS'])
        def podcast_generate():
            if request.method == 'OPTIONS':
                return '', 200
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file provided'}), 400
            f             = request.files['file']
            language      = request.form.get('language', 'fa')
            num_exchanges = int(request.form.get('num_exchanges', 8))
            if not self._allowed(f.filename, self.ALLOWED_DOC):
                return jsonify({'success': False, 'error': 'Only PDF or TXT files accepted'}), 400
            path = self._save_upload(f, 'podcast')
            try:
                text        = self._extract_text(path)
                podcast_id  = str(uuid.uuid4())[:8]
                # Guarantee the storage directory exists right before we need it
                os.makedirs(_PODCAST_DIR, exist_ok=True)
                # Always use the absolute path so open() works on every OS
                output_path = os.path.join(_PODCAST_DIR, f'{podcast_id}.mp3')
                meta        = self.podcast.generate_podcast_audio(
                                  text, output_path, language, num_exchanges)
                meta['podcast_id'] = podcast_id
                # Return a relative download URL — the frontend prepends API_BASE_URL
                return jsonify({'success': True, **meta,
                                'download_url': f'/api/podcast/download/{podcast_id}'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @bp.route('/podcast/script', methods=['POST', 'OPTIONS'])
        def podcast_script_only():
            if request.method == 'OPTIONS':
                return '', 200
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file provided'}), 400
            f             = request.files['file']
            language      = request.form.get('language', 'fa')
            num_exchanges = int(request.form.get('num_exchanges', 8))
            if not self._allowed(f.filename, self.ALLOWED_DOC):
                return jsonify({'success': False, 'error': 'Only PDF or TXT files accepted'}), 400
            path = self._save_upload(f, 'podcast_script')
            try:
                text   = self._extract_text(path)
                script = self.podcast.generate_script(text, language, num_exchanges)
                return jsonify({'success': True, **script})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @bp.route('/podcast/download/<podcast_id>', methods=['GET'])
        def podcast_download(podcast_id):
            # Sanitise to prevent path traversal
            safe_id = secure_filename(podcast_id)
            path    = os.path.join(_PODCAST_DIR, f'{safe_id}.mp3')
            if not os.path.isfile(path):
                return jsonify({'success': False, 'error': 'Podcast not found'}), 404
            return send_file(
                path,
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=f'podcast_{safe_id}.mp3'
            )

        # ── Persian Chatbot ───────────────────────────────────────────────
        @bp.route('/chatbot/chat', methods=['POST', 'OPTIONS'])
        def chatbot_chat():
            if request.method == 'OPTIONS':
                return '', 200
            data         = request.get_json(force=True)
            message      = data.get('message', '').strip()
            session_id   = data.get('session_id', str(uuid.uuid4())[:8])
            doc_context  = data.get('document_context')
            if not message:
                return jsonify({'success': False, 'error': 'message is required'}), 400
            try:
                result = self.chatbot.chat(session_id, message, doc_context)
                return jsonify({'success': True, **result})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @bp.route('/chatbot/history/<session_id>', methods=['GET'])
        def chatbot_history(session_id):
            return jsonify({'success': True, 'session_id': session_id,
                            'history': self.chatbot.get_history(session_id)})

        @bp.route('/chatbot/sessions', methods=['GET'])
        def chatbot_sessions():
            return jsonify({'success': True, 'sessions': self.chatbot.list_sessions()})

        @bp.route('/chatbot/clear/<session_id>', methods=['DELETE'])
        def chatbot_clear(session_id):
            ok = self.chatbot.clear_session(session_id)
            return jsonify({'success': ok, 'session_id': session_id})

        # ── Math Solver ───────────────────────────────────────────────────
        @bp.route('/math/solve-text', methods=['POST', 'OPTIONS'])
        def math_solve_text():
            if request.method == 'OPTIONS':
                return '', 200
            data    = request.get_json(force=True)
            problem = data.get('problem', '').strip()
            if not problem:
                return jsonify({'success': False, 'error': 'problem text is required'}), 400
            try:
                result = self.math.solve_text(problem)
                return jsonify({'success': True, **result})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @bp.route('/math/solve-image', methods=['POST', 'OPTIONS'])
        def math_solve_image():
            if request.method == 'OPTIONS':
                return '', 200
            hint = request.form.get('hint', '')
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No image file provided'}), 400
            f = request.files['file']
            if not self._allowed(f.filename, self.ALLOWED_IMG):
                return jsonify({'success': False,
                                'error': 'Only image files (PNG, JPG, JPEG, WEBP, GIF) accepted'}), 400
            image_bytes = f.read()
            ext  = f.filename.rsplit('.', 1)[-1].lower()
            mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else f'image/{ext}'
            try:
                result = self.math.solve_from_image_bytes(image_bytes, mime, hint)
                return jsonify({'success': True, **result})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

    # ------------------------------------------------------------------ #

    def get_blueprint(self) -> Blueprint:
        return self.blueprint
