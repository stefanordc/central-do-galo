import os
import json
import time

history_dir = os.path.expandvars(r"%APPDATA%\Code\User\History")
home_target = "frontend/src/app/page.tsx"
videos_target = "frontend/src/app/videos/page.tsx"

home_content = None
videos_content = None

for root, dirs, files in os.walk(history_dir):
    if "entries.json" in files:
        try:
            with open(os.path.join(root, "entries.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
            
            resource = data.get("resource", "").replace("\\", "/")
            if resource.endswith(home_target) or resource.endswith(videos_target):
                entries = data.get("entries", [])
                entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
                
                for entry in entries:
                    entry_path = os.path.join(root, entry.get("id"))
                    if os.path.exists(entry_path):
                        with open(entry_path, "r", encoding="utf-8") as ef:
                            content = ef.read()
                            
                        # Ignorar mocks que eu criei
                        if "REVERTIDO" in content or "placeholder-section" in content or "Carregando Radar" in content:
                            continue
                            
                        if resource.endswith(home_target):
                            if "fetch" in content or "XTimelineItem" in content:
                                home_content = content
                                break
                        elif resource.endswith(videos_target):
                            if "fetch" in content or "youtube" in content.lower():
                                videos_content = content
                                break
        except Exception as e:
            pass

if home_content:
    os.makedirs(os.path.dirname(home_target), exist_ok=True)
    with open(home_target, "w", encoding="utf-8") as f:
        f.write(home_content)
    print("page.tsx restaurado.")

if videos_content:
    os.makedirs(os.path.dirname(videos_target), exist_ok=True)
    with open(videos_target, "w", encoding="utf-8") as f:
        f.write(videos_content)
    print("videos/page.tsx restaurado.")
