from pdf2image import convert_from_path
import PyPDF2
from typing import List
import numpy as np


class PDFExtractor:
    def extractPages(self, pdfPath: str) -> List:
        try:
            images = convert_from_path(pdfPath)
            return images
        except Exception as e:
            raise Exception(f"Failed to extract pages from PDF: {str(e)}")
    
    def convertPageToImage(self, page) -> np.ndarray:
        try:
            return np.array(page)
        except Exception as e:
            raise Exception(f"Failed to convert page to image: {str(e)}")
    
    def getPageCount(self, pdfPath: str) -> int:
        try:
            with open(pdfPath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                return len(pdf_reader.pages)
        except Exception as e:
            raise Exception(f"Failed to get page count: {str(e)}")
