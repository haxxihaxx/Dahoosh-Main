import os
from typing import Dict


class FileManager:
    def __init__(self):
        self.allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg'}
    
    def uploadFile(self, file) -> bool:
        try:
            return True
        except Exception as e:
            print(f"Failed to upload file: {e}")
            return False
    
    def validateFileFormat(self, filepath: str) -> bool:
        if not os.path.exists(filepath):
            return False
        
        ext = filepath.rsplit('.', 1)[-1].lower()
        return ext in self.allowed_extensions
    
    def deleteFile(self, filepath: str) -> None:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Failed to delete file: {e}")
