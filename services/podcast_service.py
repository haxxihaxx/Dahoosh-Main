import os
import re
import json
from typing import Dict, List
from openai import OpenAI


class PodcastService:
    """
    Generates an AI podcast from document text using OpenAI TTS.
    Produces a natural two-host dialogue and converts it to audio.
    """

    VOICES = {
        "host_a": "alloy",   # first host
        "host_b": "echo",    # second host
    }

    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1')
        )
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        self.tts_model = "tts-1"

    # ------------------------------------------------------------------ #
    #  Script generation                                                   #
    # ------------------------------------------------------------------ #

    def generate_script(self, text: str, language: str = "fa", num_exchanges: int = 8) -> Dict:
        """
        Generate a podcast script from document text.
        Returns {"title": "...", "script": [{"speaker": "Alex"|"Sara", "line": "..."}, ...]}
        """
        excerpt = text[:6000] if len(text) > 6000 else text

        lang_instruction = (
            "Respond entirely in Persian (فارسی). Use natural conversational Persian."
            if language == "fa"
            else "Respond in English using natural conversational language."
        )

        prompt = f"""You are a podcast script writer. Create an engaging two-host podcast script \
based on the following document content.

Hosts:
- Alex: enthusiastic, asks great questions, simplifies complex ideas
- Sara: knowledgeable, provides depth, gives relatable examples

Requirements:
- Exactly {num_exchanges} exchanges (back-and-forth) between the hosts
- Cover the key ideas from the document naturally
- Include an intro and a brief outro
- Keep each line to 2-4 sentences max for good audio pacing
- {lang_instruction}

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
  "title": "podcast title",
  "script": [
    {{"speaker": "Alex", "line": "..."}},
    {{"speaker": "Sara", "line": "..."}}
  ]
}}

Document content:
{excerpt}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.75
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```[a-z]*\n?', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'```$', '', raw, flags=re.MULTILINE)

        data = json.loads(raw.strip())
        return data

    # ------------------------------------------------------------------ #
    #  Audio generation                                                    #
    # ------------------------------------------------------------------ #

    def _text_to_speech(self, text: str, voice: str) -> bytes:
        """Convert a single line to audio bytes using OpenAI TTS."""
        response = self.client.audio.speech.create(
            model=self.tts_model,
            voice=voice,
            input=text
        )
        return response.content

    def generate_podcast_audio(self, text: str, output_path: str,
                                language: str = "fa", num_exchanges: int = 8) -> Dict:
        """
        Full pipeline: generate script → TTS each line → concatenate → save mp3.
        output_path MUST be an absolute path (callers are responsible for this).
        Returns metadata dict.
        """
        script_data = self.generate_script(text, language, num_exchanges)
        script = script_data.get("script", [])
        title  = script_data.get("title", "AI Podcast")

        audio_segments: List[bytes] = []
        for entry in script:
            speaker = entry.get("speaker", "Alex")
            line    = entry.get("line", "").strip()
            if not line:
                continue
            voice   = self.VOICES["host_a"] if speaker == "Alex" else self.VOICES["host_b"]
            segment = self._text_to_speech(line, voice)
            audio_segments.append(segment)

        combined = b"".join(audio_segments)

        # output_path must already exist — the caller (handler) is responsible
        # for creating the directory.  We do NOT call makedirs here to avoid the
        # Windows edge-case where dirname("relative/path") can return "" and
        # makedirs("") raises FileNotFoundError.
        with open(output_path, "wb") as f:
            f.write(combined)

        return {
            "title": title,
            "language": language,
            "num_exchanges": len(script),
            "audio_path": output_path,
            "script": script,
            "file_size_kb": round(len(combined) / 1024, 1)
        }
