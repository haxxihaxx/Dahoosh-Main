#!/usr/bin/env python3

import os
import urllib.request

def download_persian_font():
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    os.makedirs(fonts_dir, exist_ok=True)
    
    font_path = os.path.join(fonts_dir, 'NotoSansArabic-Regular.ttf')
    
    if os.path.exists(font_path):
        print(f"Persian font already exists at: {font_path}")
        return
    
    print("Downloading Persian font (Noto Sans Arabic)...")
    
    font_url = "https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic-Regular.ttf"
    
    try:
        urllib.request.urlretrieve(font_url, font_path)
        print(f"Persian font downloaded successfully to: {font_path}")
    except Exception as e:
        print(f"Failed to download font: {e}")
        print("\nManual installation instructions:")
        print("1. Download font from: https://fonts.google.com/noto/specimen/Noto+Sans+Arabic")
        print(f"2. Save as: {font_path}")

if __name__ == '__main__':
    download_persian_font()
