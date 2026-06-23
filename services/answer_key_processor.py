import json
import re
import base64
import os
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI


SYSTEM_PROMPT = (
    "You are an expert exam answer-key parser fluent in Persian and English. "
    "You receive one or more images of an answer key and return ONLY a JSON object — "
    "no markdown fences, no extra text."
)

USER_PROMPT = """Extract every question and its correct answer from these answer-key images.

Return ONLY this JSON (no markdown, no extra text):
{
  "questions": [
    {
      "question_number": 1,
      "question_text": "...",
      "correct_answer": "...",
      "points": 5
    }
  ],
  "total_points": 20,
  "test_name": "..."
}"""


class AnswerKeyProcessor:
    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1')
        )
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _b64(path: str) -> str:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()

    @staticmethod
    def _page_to_b64(page_image) -> str:
        """Convert a pdf2image PIL page to base64 PNG."""
        from io import BytesIO
        buf = BytesIO()
        page_image.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()

    def _rasterize_pdf_parallel(self, pdf_path: str) -> List[str]:
        """Convert all PDF pages to base64 PNG in parallel."""
        from pdf2image import convert_from_path
        pages = convert_from_path(pdf_path)
        if len(pages) == 1:
            return [self._page_to_b64(pages[0])]
        with ThreadPoolExecutor(max_workers=min(len(pages), 6)) as ex:
            futures = {ex.submit(self._page_to_b64, p): i for i, p in enumerate(pages)}
            results = [None] * len(pages)
            for fut in as_completed(futures):
                results[futures[fut]] = fut.result()
        return results

    # ── main entry ─────────────────────────────────────────────────────────

    def processAnswerKey(self, file_path: str) -> Dict:
        """Single vision API call: image(s) → structured JSON."""
        ext = file_path.rsplit('.', 1)[-1].lower()

        content: List[dict] = [{"type": "text", "text": USER_PROMPT}]

        if ext == 'pdf':
            for b64 in self._rasterize_pdf_parallel(file_path):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}
                })
        else:
            mime = "image/png" if ext == "png" else "image/jpeg"
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{self._b64(file_path)}", "detail": "high"}
            })

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": content}
            ],
            temperature=0.0,
            max_tokens=2048,
        )

        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'```$', '', raw).strip()
        result = json.loads(raw)

        if not self.validateAnswerKeyStructure(result):
            raise ValueError("Invalid answer key structure returned by model")
        return result

    # kept for compatibility
    def parseAnswerFormat(self, text: str) -> Dict:
        raise NotImplementedError("Use processAnswerKey(file_path) instead")

    def validateAnswerKeyStructure(self, key: Dict) -> bool:
        if not isinstance(key, dict) or 'questions' not in key:
            return False
        if not isinstance(key['questions'], list):
            return False
        for q in key['questions']:
            if not isinstance(q, dict):
                return False
            if 'question_number' not in q or 'correct_answer' not in q:
                return False
        return True
