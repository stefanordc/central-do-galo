import os  
def fix_file(filepath):  
    with open(filepath, 'r', encoding='utf-8') as f:  
        content = f.read()  
    try:  
        fixed_content = content.encode('latin-1').decode('utf-8')  
        if content != fixed_content:  
            with open(filepath, 'w', encoding='utf-8') as f:  
                f.write(fixed_content)  
            print(f'Fixed {filepath}')  
    except Exception as e:  
        pass  
for root, _, files in os.walk('frontend/src'):  
    for file in files:  
        if file.endswith('.tsx') or file.endswith('.ts'):  
            fix_file(os.path.join(root, file)) 
