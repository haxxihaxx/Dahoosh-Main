import os
import base64
import json
import re
from typing import Dict, Optional
from openai import OpenAI


MATH_SYSTEM_PROMPT = """You are an expert mathematics teacher and problem solver.
Your job is to solve math problems step by step with crystal-clear explanations.

Guidelines:
- Always show EVERY step of the solution clearly.
- Label steps as: گام ۱، گام ۲، ... (or Step 1, Step 2, ... in English).
- Identify the type of problem first (e.g., algebra, geometry, calculus, statistics).
- State the formulas/theorems used.
- Double-check your final answer.
- If the problem is from an image, first describe what you see, then solve it.
- Answer in Persian (فارسی) if the problem is in Persian, otherwise in English.
- Use LaTeX-style notation for formulas when writing text (e.g., x^2 + 3x + 2 = 0).
- At the end, provide a concise "خلاصه پاسخ" (Answer Summary) box.

Return your response as JSON:
{
  "problem_type": "نوع مسئله",
  "identified_problem": "توضیح مسئله",
  "steps": [
    {"step_number": 1, "title": "عنوان گام", "explanation": "توضیح", "math": "فرمول/محاسبات"},
    ...
  ],
  "final_answer": "پاسخ نهایی",
  "answer_summary": "خلاصه یک‌خطی",
  "difficulty": "easy|medium|hard",
  "topics": ["algebra", "geometry", ...]
}
"""


class MathSolverService:
    """
    AI Math Solver that can process both text and image-based math problems
    using OpenAI GPT-4o vision capabilities.
    """

    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1')
        )
        # Use gpt-4o for vision; note: "GPT-5.2" is not a real model name yet,
        # so we fall back to gpt-4o which has full vision support.
        self.model = os.getenv('MATH_SOLVER_MODEL', os.getenv('OPENAI_MODEL', 'gpt-4o'))

    def _encode_image(self, image_path: str) -> tuple[str, str]:
        """Encode image file to base64 and detect media type."""
        ext = image_path.rsplit('.', 1)[-1].lower()
        media_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                     'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
        media_type = media_map.get(ext, 'image/jpeg')
        with open(image_path, 'rb') as f:
            encoded = base64.standard_b64encode(f.read()).decode('utf-8')
        return encoded, media_type

    def _encode_image_bytes(self, image_bytes: bytes, media_type: str = 'image/jpeg') -> str:
        return base64.standard_b64encode(image_bytes).decode('utf-8')

    def _parse_response(self, raw: str) -> Dict:
        """Parse JSON from model response, handling markdown fences."""
        cleaned = re.sub(r'^```[a-z]*\n?', '', raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'```$', '', cleaned.strip(), flags=re.MULTILINE)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Return a structured fallback with the raw text
            return {
                "problem_type": "نامشخص",
                "identified_problem": "",
                "steps": [{"step_number": 1, "title": "پاسخ", "explanation": raw, "math": ""}],
                "final_answer": raw,
                "answer_summary": raw[:200],
                "difficulty": "unknown",
                "topics": []
            }

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def solve_text(self, problem: str) -> Dict:
        """Solve a math problem given as text."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": MATH_SYSTEM_PROMPT},
                {"role": "user", "content": f"لطفاً این مسئله را حل کن:\n\n{problem}"}
            ],
            max_tokens=2048,
            temperature=0.2
        )
        raw = response.choices[0].message.content
        result = self._parse_response(raw)
        result["input_type"] = "text"
        result["original_problem"] = problem
        return result

    def solve_from_image_path(self, image_path: str, hint: str = "") -> Dict:
        """Solve a math problem from an image file on disk."""
        encoded, media_type = self._encode_image(image_path)
        return self._solve_with_image(encoded, media_type, hint)

    def solve_from_image_bytes(self, image_bytes: bytes,
                                media_type: str = 'image/jpeg', hint: str = "") -> Dict:
        """Solve a math problem from raw image bytes."""
        encoded = self._encode_image_bytes(image_bytes, media_type)
        return self._solve_with_image(encoded, media_type, hint)

    def _solve_with_image(self, encoded: str, media_type: str, hint: str = "") -> Dict:
        hint_text = f"\nراهنمایی اضافی: {hint}" if hint else ""
        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{encoded}",
                        "detail": "high"
                    }
                },
                {
                    "type": "text",
                    "text": f"این تصویر یک مسئله ریاضی است. لطفاً مسئله را شناسایی کرده و گام‌به‌گام حل کن.{hint_text}"
                }
            ]
        }

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": MATH_SYSTEM_PROMPT},
                user_message
            ],
            max_tokens=2048,
            temperature=0.2
        )
        raw = response.choices[0].message.content
        result = self._parse_response(raw)
        result["input_type"] = "image"
        return result
