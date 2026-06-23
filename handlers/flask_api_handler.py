from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import json
from typing import Dict, Optional
from datetime import datetime


class FlaskAPIHandler:
    def __init__(self, grading_service, file_manager, storage_manager, web_page_server):
        self.grading_service = grading_service
        self.file_manager = file_manager
        self.storage_manager = storage_manager
        self.web_page_server = web_page_server
        
        self.api_blueprint = Blueprint('api', __name__, url_prefix='/api')
        self._register_routes()
        
        self.UPLOAD_FOLDER = 'uploads'
        self.ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
        os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
    
    def _register_routes(self):
        # Handle CORS preflight OPTIONS requests for all /api/* routes
        @self.api_blueprint.before_request
        def handle_options():
            if request.method == 'OPTIONS':
                from flask import current_app
                response = current_app.make_default_options_response()
                return response

        self.api_blueprint.add_url_rule(
            '/upload-answer-key/<test_id>',
            'upload_answer_key',
            self.POST_uploadAnswerKey,
            methods=['POST', 'OPTIONS']
        )
        
        self.api_blueprint.add_url_rule(
            '/upload-student-answers/<test_id>',
            'upload_student_answers',
            self.POST_uploadStudentAnswers,
            methods=['POST', 'OPTIONS']
        )
        
        self.api_blueprint.add_url_rule(
            '/grade-test/<test_id>',
            'grade_test',
            self.POST_gradeTest,
            methods=['POST', 'OPTIONS']
        )
        
        self.api_blueprint.add_url_rule(
            '/download-report/<test_id>/<student_id>',
            'download_report',
            self.GET_downloadReport,
            methods=['GET', 'OPTIONS']
        )
    
    def _allowed_file(self, filename: str) -> bool:
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS
    
    def POST_uploadAnswerKey(self, test_id: str):
        try:
            if 'file' not in request.files:
                return jsonify({
                    'success': False,
                    'error': 'فایلی ارسال نشده است'
                }), 400
            
            file = request.files['file']
            exam_type = request.form.get('exam_type', 'descriptive')
            
            if file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'فایلی انتخاب نشده است'
                }), 400
            
            if not self._allowed_file(file.filename):
                return jsonify({
                    'success': False,
                    'error': 'فرمت فایل نامعتبر است. فرمت‌های مجاز: PDF, PNG, JPG, JPEG'
                }), 400
            
            filename = secure_filename(f"{test_id}_answer_key_{file.filename}")
            filepath = os.path.join(self.UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            if self.file_manager.validateFileFormat(filepath):
                try:
                    answer_key_data = self.grading_service.processAnswerKeyFile(filepath)
                    answer_key_data['exam_type'] = exam_type
                    
                    self.storage_manager.saveAnswerKey(test_id, answer_key_data)
                    
                    return jsonify({
                        'success': True,
                        'message': 'کلید پاسخ با موفقیت بارگذاری و پردازش شد',
                        'test_id': test_id,
                        'filename': filename,
                        'exam_type': exam_type,
                        'questions_count': len(answer_key_data.get('questions', []))
                    }), 200
                except Exception as e:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    error_msg = str(e)
                    # Provide a clear message if the OpenAI API key is missing/invalid
                    if 'api_key' in error_msg.lower() or 'authentication' in error_msg.lower() or 'invalid' in error_msg.lower():
                        error_msg = 'OpenAI API key is missing or invalid. Please set OPENAI_API_KEY in your .env file.'
                    return jsonify({
                        'success': False,
                        'error': f'خطا در پردازش کلید پاسخ: {error_msg}'
                    }), 500
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({
                    'success': False,
                    'error': 'فرمت فایل نامعتبر است'
                }), 400
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'خطا در بارگذاری فایل: {str(e)}'
            }), 500
    
    def POST_uploadStudentAnswers(self, test_id: str):
        try:
            if 'file' not in request.files:
                return jsonify({
                    'success': False,
                    'error': 'فایلی ارسال نشده است'
                }), 400
            
            file = request.files['file']
            student_id = request.form.get('student_id', 'unknown')
            
            if file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'فایلی انتخاب نشده است'
                }), 400
            
            if not self._allowed_file(file.filename):
                return jsonify({
                    'success': False,
                    'error': 'فرمت فایل نامعتبر است. فرمت‌های مجاز: PDF, PNG, JPG, JPEG'
                }), 400
            
            filename = secure_filename(f"{test_id}_{student_id}_{file.filename}")
            filepath = os.path.join(self.UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            if self.file_manager.validateFileFormat(filepath):
                return jsonify({
                    'success': True,
                    'message': 'پاسخ‌نامه دانش‌آموز با موفقیت بارگذاری شد',
                    'test_id': test_id,
                    'student_id': student_id,
                    'filename': filename,
                    'filepath': filepath
                }), 200
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({
                    'success': False,
                    'error': 'فرمت فایل نامعتبر است'
                }), 400
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'خطا در بارگذاری فایل: {str(e)}'
            }), 500
    
    def POST_gradeTest(self, test_id: str):
        try:
            data = request.get_json()
            student_id = data.get('student_id')
            student_answer_file = data.get('student_answer_file')
            
            if not student_id or not student_answer_file:
                return jsonify({
                    'success': False,
                    'error': 'پارامترهای لازم ارسال نشده است'
                }), 400
            
            answer_key = self.storage_manager.retrieveAnswerKey(test_id)
            if not answer_key:
                return jsonify({
                    'success': False,
                    'error': 'کلید پاسخ یافت نشد. لطفاً ابتدا کلید پاسخ را بارگذاری کنید'
                }), 404
            
            if not os.path.exists(student_answer_file):
                return jsonify({
                    'success': False,
                    'error': 'فایل پاسخ‌نامه دانش‌آموز یافت نشد'
                }), 404
            
            exam_type = answer_key.get('exam_type', 'descriptive')
            
            grading_result = self.grading_service.gradeTest(
                test_id,
                answer_key,
                student_answer_file,
                exam_type
            )
            
            grading_result['student_id'] = student_id
            grading_result['timestamp'] = datetime.now().isoformat()
            
            self.storage_manager.saveGradingResult(test_id, student_id, grading_result)
            
            score = grading_result.get('percentage', 0)
            grade_letter = grading_result.get('grade_letter', 'N/A')
            
            frontend_result = {
                'grade': grade_letter,
                'score': score,
                'full_result': grading_result
            }
            
            return jsonify({
                'success': True,
                'message': 'تصحیح با موفقیت انجام شد',
                'test_id': test_id,
                'student_id': student_id,
                'exam_type': exam_type,
                'grading_result': frontend_result,
                'timestamp': datetime.now().isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'خطا در تصحیح آزمون: {str(e)}'
            }), 500
    
    def GET_downloadReport(self, test_id: str, student_id: str):
        try:
            grading_result = self.storage_manager.retrieveGradingResult(test_id, student_id)
            
            if not grading_result:
                return jsonify({
                    'success': False,
                    'error': 'نتیجه تصحیح یافت نشد'
                }), 404
            
            report_bytes = self.grading_service.generateGradeReport(grading_result)
            
            from io import BytesIO
            report_buffer = BytesIO(report_bytes)
            report_buffer.seek(0)
            
            return send_file(
                report_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'dahoosh_{test_id}_{student_id}.pdf'
            )
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'خطا در دانلود گزارش: {str(e)}'
            }), 500
    
    def get_blueprint(self):
        return self.api_blueprint
