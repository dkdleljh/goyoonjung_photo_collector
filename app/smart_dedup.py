import os
import pickle
from pathlib import Path
from PIL import Image

# import imagehash # 제거: 아래 try-except 안에서 import 시도

# dhash 직접 구현 (라이브러리 의존성 제거용)
def dhash(image, hash_size=8):
    # Grayscale and resize
    image = image.convert('L').resize(
        (hash_size + 1, hash_size),
        Image.Resampling.LANCZOS,
    )
    pixels = list(image.getdata())
    # Compare adjacent pixels
    difference = []
    for row in range(hash_size):
        for col in range(hash_size):
            pixel_left = image.getpixel((col, row))
            pixel_right = image.getpixel((col + 1, row))
            difference.append(pixel_left > pixel_right)
    # Convert binary array to hex string
    decimal_value = 0
    hex_string = []
    for index, value in enumerate(difference):
        if value:
            decimal_value += 2**(index % 8)
        if (index % 8) == 7:
            hex_string.append(hex(decimal_value)[2:].rjust(2, '0'))
            decimal_value = 0
    return ''.join(hex_string)

class SmartDedupStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.hashes = {} # {phash: {"path": str, "area": int}}
        self.load()

    def load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "rb") as f:
                    self.hashes = pickle.load(f)
            except Exception:
                self.hashes = {}

    def save(self):
        try:
            with open(self.db_path, "wb") as f:
                pickle.dump(self.hashes, f)
        except Exception:
            pass

    def check_and_update(self, img: Image.Image, new_path: str) -> str:
        """
        return:
          "NEW": 완전히 새로운 사진
          "UPGRADE": 기존보다 고화질이라 교체함
          "DUPLICATE": 기존보다 구려서 버림
        """
        # 1. pHash 계산 (이미지 지문)
        try:
            # imagehash 라이브러리가 있으면 쓰고, 없으면 내장 dhash 사용
            import imagehash
            ph = str(imagehash.phash(img))
        except ImportError:
            ph = dhash(img)
        except Exception:
            ph = dhash(img)

        width, height = img.size
        new_area = width * height

        # 2. 중복 검사
        if ph in self.hashes:
            old_info = self.hashes[ph]
            old_area = old_info.get("area", 0)
            old_path = old_info.get("path", "")

            # 3. 화질 비교 (면적 기준 10% 이상 크면 업그레이드)
            if new_area > old_area * 1.1:
                # 기존 파일 삭제 시도 (선택 사항: 백업하거나 지움)
                # 여기서는 '교체'니까 기존 정보 덮어쓰기만 하고,
                # 실제 파일 삭제는 Downloader에서 처리하도록 신호만 줌
                
                # DB 업데이트
                self.hashes[ph] = {"path": new_path, "area": new_area}
                self.save()
                return "UPGRADE", old_path # 구파일 경로 리턴
            else:
                return "DUPLICATE", old_path
        
        # 4. 신규 등록
        self.hashes[ph] = {"path": new_path, "area": new_area}
        self.save()
        return "NEW", None
