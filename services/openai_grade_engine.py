import os
import json
from typing import Dict
from openai import OpenAI


class OpenAIGradeEngine:
    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1')
        )
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')
    
    def generateGradingPrompt(self, answerKey: Dict, studentAnswers: Dict, exam_type: str = "descriptive") -> str:
        if exam_type == "multiple_choice":
            grading_instructions = """
For multiple choice questions:
- Award full points if the answer exactly matches
- Award zero points for incorrect answers
- Be strict with letter/option matching
"""
        else:
            grading_instructions = """
For descriptive/essay questions:
- Evaluate the content, accuracy, and completeness of the answer
- Award partial credit based on:
  * Correctness of key concepts (40%)
  * Completeness of the answer (30%)
  * Clarity and organization (15%)
  * Supporting details and examples (15%)
- Provide specific feedback on what was done well and what was missing
- Be fair and considerate of different expression styles
- For Persian answers, consider linguistic variations and synonyms
"""
        
        prompt = f"""You are an expert test grading assistant fluent in both English and Persian (فارسی). 
You can grade exams written in English, Persian, or a mix of both languages.

Grade the following student answers against the provided answer key.

ANSWER KEY:
{json.dumps(answerKey, indent=2, ensure_ascii=False)}

STUDENT ANSWERS:
{json.dumps(studentAnswers, indent=2, ensure_ascii=False)}

GRADING INSTRUCTIONS:
{grading_instructions}

IMPORTANT NOTES FOR PERSIAN CONTENT:
- Persian text may appear right-to-left
- Accept equivalent Persian synonyms and expressions
- Consider correct Persian grammar and spelling
- Be culturally aware of Persian academic writing conventions
- Accept both formal and semi-formal Persian academic language

RESPONSE FORMAT:
Provide your grading as a valid JSON object with this exact structure:
{{
    "questions": [
        {{
            "question_number": 1,
            "question_text": "متن سوال",
            "correct_answer": "پاسخ صحيح",
            "student_answer": "پاسخ دانش‌آموز",
            "points_awarded": 4.5,
            "max_points": 5.0,
            "is_correct": true,
            "feedback": "بازخورد دقيق به زبان فارسي",
            "feedback_persian": "بازخورد فارسي",
            "strengths": ["نقاط قوت پاسخ"],
            "improvements": ["نقاط قابل بهبود"]
        }}
    ],
    "total_score": 17.5,
    "max_score": 20.0,
    "score_20": 17.5,
    "percentage": 87.5,
    "grade_letter": "A",
    "overall_feedback": "جمع‌بندي كلي عملكرد دانش‌آموز به فارسي",
    "overall_feedback_persian": "بازخورد كلي فارسي",
    "language_detected": "persian"
}}

CRITICAL: Use the Iranian grading system (نمره از ۲۰). 
- max_score MUST be 20.0
- total_score and score_20 MUST be out of 20 (e.g. 17.5 out of 20)
- Scale each question's max_points proportionally so they sum to 20
- percentage = (total_score / 20) * 100
- All feedback MUST be written in Persian (فارسي)

Respond ONLY with the JSON object, no additional text before or after.
"""
        return prompt
    
    def callOpenAIAPI(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert multilingual test grading assistant. 
You are fluent in English and Persian (فارسی) and can grade exams in both languages.
You provide fair, detailed, and constructive feedback.
You understand academic writing conventions in both languages.
You always respond with valid, well-structured JSON.
For descriptive answers, you evaluate content quality, not just correctness.
You are empathetic but maintain academic standards."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=3000
            )
            
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Failed to call OpenAI API: {str(e)}")
    
    def calculateScore(self, gradingResult: str) -> float:
        try:
            result_json = json.loads(gradingResult)
            return result_json.get('total_score', 0.0)
        except json.JSONDecodeError:
            import re
            lines = gradingResult.split('\n')
            for line in lines:
                if 'total_score' in line.lower() or 'score:' in line.lower():
                    numbers = re.findall(r'\d+\.?\d*', line)
                    if numbers:
                        return float(numbers[0])
            return 0.0
    
    def gradeWithOpenAI(self, answerKey: Dict, studentAnswers: Dict, exam_type: str = "descriptive") -> Dict:
        prompt = self.generateGradingPrompt(answerKey, studentAnswers, exam_type)
        response = self.callOpenAIAPI(prompt)
        
        try:
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.startswith('```'):
                response_clean = response_clean[3:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            grading_result = json.loads(response_clean)

            # Normalize to Iranian 20-point scale regardless of what the AI returned
            max_score = grading_result.get('max_score', 100.0)
            total_score = grading_result.get('total_score', 0.0)
            if max_score != 20.0 and max_score > 0:
                # Re-scale to /20
                total_score_20 = round((total_score / max_score) * 20, 2)
                grading_result['score_20'] = total_score_20
                grading_result['total_score'] = total_score_20
                grading_result['max_score'] = 20.0
            else:
                grading_result['score_20'] = grading_result.get('score_20', total_score)
            grading_result['percentage'] = round((grading_result['score_20'] / 20.0) * 100, 1)
        except json.JSONDecodeError as e:
            score = self.calculateScore(response)
            grading_result = {
                "raw_response": response,
                "total_score": score,
                "parsed": False,
                "error": str(e)
            }
        
        return grading_result
