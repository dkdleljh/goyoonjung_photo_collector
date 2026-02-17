import os
from pathlib import Path
from datetime import datetime

def generate_report(root_dir):
    today = datetime.now().strftime('%Y-%m-%d')
    report_path = Path(root_dir) / "reports" / f"Photo_Report_{today}.md"
    report_path.parent.mkdir(exist_ok=True)
    
    # 오늘 날짜 폴더 탐색
    today_folder = Path(root_dir) / today
    count = 0
    if today_folder.exists():
        count = sum(1 for _ in today_folder.rglob('*') if _.is_file())
        
    organized_dir = Path(root_dir) / "Organized"
    best_cuts = sum(1 for _ in (organized_dir / "Best_Cuts").glob('*') if _.is_file())
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# 📸 Photo Collection Report ({today})\n\n")
        f.write(f"## 📥 Collection Stats\n")
        f.write(f"- **Total Collected Today:** {count} images\n")
        f.write(f"- **Total Best Cuts (All time):** {best_cuts}\n")
        
    return str(report_path)
