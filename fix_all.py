import os
import ftfy

for root, _, files in os.walk('.'):
    if 'node_modules' in root or '.next' in root:
        continue
    for f in files:
        if f.endswith(('.ts', '.tsx', '.js', '.json', '.md')):
            filepath = os.path.join(root, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    content = file.read()
                fixed = ftfy.fix_text(content)
                if fixed != content:
                    with open(filepath, 'w', encoding='utf-8') as file:
                        file.write(fixed)
                    print(f'Fixed {filepath}')
            except Exception:
                pass
