import json
import os
from typing import Dict, Optional


class StorageManager:
    def __init__(self, storage_dir: str = 'storage'):
        self.storage_dir = storage_dir
        self.answer_keys_dir = os.path.join(storage_dir, 'answer_keys')
        self.results_dir = os.path.join(storage_dir, 'results')
        
        os.makedirs(self.answer_keys_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
    
    def saveAnswerKey(self, testId: str, answerKeyData: Dict) -> bool:
        try:
            filepath = os.path.join(self.answer_keys_dir, f'{testId}.json')
            with open(filepath, 'w') as f:
                json.dump(answerKeyData, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save answer key: {e}")
            return False
    
    def retrieveAnswerKey(self, testId: str) -> Optional[Dict]:
        try:
            filepath = os.path.join(self.answer_keys_dir, f'{testId}.json')
            if not os.path.exists(filepath):
                return None
            
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to retrieve answer key: {e}")
            return None
    
    def saveGradingResult(self, testId: str, studentId: str, gradingData: Dict) -> bool:
        try:
            filepath = os.path.join(self.results_dir, f'{testId}_{studentId}.json')
            with open(filepath, 'w') as f:
                json.dump(gradingData, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save grading result: {e}")
            return False
    
    def retrieveGradingResult(self, testId: str, studentId: str) -> Optional[Dict]:
        try:
            filepath = os.path.join(self.results_dir, f'{testId}_{studentId}.json')
            if not os.path.exists(filepath):
                return None
            
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to retrieve grading result: {e}")
            return None
