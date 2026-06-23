import os
import base64
from typing import List, Dict
from openai import OpenAI
from PIL import Image
from io import BytesIO


class OCRProcessor:
    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1')
        )
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')
    
    def extractTextFromImage(self, imagePath: str) -> str:
        try:
            with open(imagePath, 'rb') as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all text from this image. Preserve the structure and formatting. Return only the extracted text without any additional commentary."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096
            )
            
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Failed to extract text from image: {str(e)}")
    
    def extractTextFromPDF(self, pdfPath: str) -> List[str]:
        from pdf2image import convert_from_path
        
        try:
            images = convert_from_path(pdfPath)
            extracted_texts = []
            
            for i, image in enumerate(images):
                img_byte_arr = BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                base64_image = base64.b64encode(img_byte_arr.read()).decode('utf-8')
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Extract all text from page {i+1} of this document. Preserve the structure and formatting. Return only the extracted text without any additional commentary."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4096
                )
                
                extracted_texts.append(response.choices[0].message.content)
            
            return extracted_texts
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
    
    def cleanExtractedText(self, rawText: str) -> str:
        lines = rawText.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        return '\n'.join(cleaned_lines)
