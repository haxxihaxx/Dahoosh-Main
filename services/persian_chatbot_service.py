import os
from typing import List, Dict
from openai import OpenAI


SYSTEM_PROMPT = """You are a knowledgeable and patient educational assistant specializing in Persian textbook material.
Your role is to help students (دانش‌آموزان) understand their textbook content.

Core behaviors:
- Always answer in Persian (فارسی) unless the student writes in English.
- Use clear, simple language appropriate for the student's apparent grade level.
- Break down complex concepts into digestible steps.
- When relevant, provide examples that resonate with Iranian culture and curriculum.
- If a student seems confused, rephrase and try a different explanation approach.
- For math and science, show step-by-step solutions (حل گام به گام).
- Be encouraging and supportive (دلگرم‌کننده باش).
- When a student asks about a textbook topic, first confirm which subject/grade, then tailor your answer.
- Reference common Iranian textbook series (e.g., کتاب‌های درسی وزارت آموزش و پرورش) when appropriate.
- Do NOT do homework FOR the student — guide them to the answer instead.

If provided with a document context, prioritize answering from that material.
"""


class PersianChatbotService:
    """
    A conversational chatbot optimized for Persian textbook material.
    Maintains per-session conversation history.
    """

    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1')
        )
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        # sessions: { session_id: [{"role": ..., "content": ...}, ...] }
        self.sessions: Dict[str, List[Dict]] = {}

    def _get_history(self, session_id: str) -> List[Dict]:
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        return self.sessions[session_id]

    def chat(self, session_id: str, user_message: str,
             document_context: str = None) -> Dict:
        """
        Send a message and get a response.
        Optionally inject document context for RAG-like grounding.
        """
        history = self._get_history(session_id)

        # Build system message, optionally with doc context
        system_content = SYSTEM_PROMPT
        if document_context:
            excerpt = document_context[:3000]
            system_content += (
                f"\n\n--- متن کتاب درسی برای مرجع ---\n{excerpt}\n"
                "از این متن برای پاسخ به سوالات دانش‌آموز استفاده کن."
            )

        messages = [{"role": "system", "content": system_content}] + history + \
                   [{"role": "user", "content": user_message}]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1024,
            temperature=0.6
        )

        assistant_reply = response.choices[0].message.content

        # Store turn in history (cap at 20 turns to manage context)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_reply})
        if len(history) > 40:
            self.sessions[session_id] = history[-40:]

        return {
            "session_id": session_id,
            "reply": assistant_reply,
            "turn": len(history) // 2,
            "tokens_used": response.usage.total_tokens if response.usage else None
        }

    def get_history(self, session_id: str) -> List[Dict]:
        return self._get_history(session_id)

    def clear_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[str]:
        return list(self.sessions.keys())
