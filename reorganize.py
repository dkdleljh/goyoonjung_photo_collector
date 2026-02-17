import os
import shutil
from pathlib import Path
from PIL import Image
import logging

# 설정
ROOT_DIR = Path("/home/zenith/Desktop/goyoonjung_photo_collector")
SOURCE_DIRS = [ROOT_DIR] # 루트부터 날짜별 폴더 전체 탐색
ORGANIZED_DIR = ROOT_DIR / "Organized"

# 분류 기준 (Downloader와 동일)
def classify_and_copy(path: Path):
    try:
        with Image.open(path) as img:
            width, height = img.size
            size_bytes = path.stat().st_size
            
            filename = path.name
            destinations = []

            # 1. Best Cuts (Ultra HD)
            if width >= 3000 or size_bytes >= 2 * 1024 * 1024:
                destinations.append(ORGANIZED_DIR / "Best_Cuts")

            # 2. Mobile Wallpapers
            if height > width * 1.2 and height >= 1500:
                destinations.append(ORGANIZED_DIR / "Mobile_Wallpapers")

            # 3. Desktop Wallpapers
            if width > height * 1.2 and width >= 1920:
                destinations.append(ORGANIZED_DIR / "Desktop_Wallpapers")

            # 4. Instagram Best
            if 1000 <= width <= 1200:
                destinations.append(ORGANIZED_DIR / "Instagram_Best")
            
            # 복사 실행
            for dest in destinations:
                dest.mkdir(parents=True, exist_ok=True)
                dest_path = dest / filename
                if not dest_path.exists():
                    shutil.copy2(path, dest_path)
                    print(f"[COPY] {filename} -> {dest.name}")
                    
    except Exception as e:
        print(f"[ERROR] Failed to process {path}: {e}")

def main():
    print("--- Starting Re-organization ---")
    
    # jpg, png, webp 등 이미지 파일 탐색
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    
    count = 0
    for root, dirs, files in os.walk(ROOT_DIR):
        # Organized 폴더 내부는 건너뛰기 (이미 분류된 것 중복 방지)
        if "Organized" in root:
            continue
            
        for file in files:
            if Path(file).suffix.lower() in extensions:
                file_path = Path(root) / file
                classify_and_copy(file_path)
                count += 1
                
    print(f"--- Completed. Processed {count} files. ---")

if __name__ == "__main__":
    main()
