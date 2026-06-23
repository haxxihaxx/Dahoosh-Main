import os
from typing import Dict
from services.answer_key_processor import AnswerKeyProcessor
from services.student_answer_processor import StudentAnswerProcessor
from services.openai_grade_engine import OpenAIGradeEngine
from services.file_manager import FileManager
from services.pdf_report_generator import PDFReportGenerator


class GradingService:
    def __init__(self, api_key: str = None):
        # OCRProcessor is no longer needed — vision+parse merged into one call
        self.answer_key_processor = AnswerKeyProcessor(api_key=api_key)
        self.student_processor    = StudentAnswerProcessor(api_key=api_key)
        self.grade_engine         = OpenAIGradeEngine(api_key=api_key)
        self.file_manager         = FileManager()
        self.pdf_generator        = PDFReportGenerator()

    def processAnswerKeyFile(self, answerKeyFile: str) -> Dict:
        """One vision API call: file → structured answer key JSON."""
        try:
            return self.answer_key_processor.processAnswerKey(answerKeyFile)
        except Exception as e:
            raise Exception(f"Failed to process answer key file: {str(e)}")

    def processStudentAnswerFile(self, studentAnswerFile: str) -> Dict:
        """One vision API call: file → structured student answers JSON."""
        try:
            return self.student_processor.processStudentAnswers(studentAnswerFile)
        except Exception as e:
            raise Exception(f"Failed to process student answer file: {str(e)}")

    def gradeTest(self, testId: str, answerKey: Dict, studentAnswerFile: str,
                  exam_type: str = "descriptive") -> Dict:
        try:
            student_answers  = self.processStudentAnswerFile(studentAnswerFile)
            grading_result   = self.grade_engine.gradeWithOpenAI(answerKey, student_answers, exam_type)
            grading_result['test_id']   = testId
            grading_result['exam_type'] = exam_type
            return grading_result
        except Exception as e:
            raise Exception(f"Failed to grade test: {str(e)}")

    def generateGradeReport(self, gradingResult: Dict) -> bytes:
        try:
            return self.pdf_generator.generatePDF(gradingResult)
        except Exception as e:
            raise Exception(f"Failed to generate PDF report: {str(e)}")
