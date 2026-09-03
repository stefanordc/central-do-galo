import re  
with open('frontend/src/app/page.tsx', 'r', encoding='utf-8') as f: c = f.read()  
c = c.replace('Cruzeiro', 'Galo')  
with open('frontend/src/app/page.tsx', 'w', encoding='utf-8') as f: f.write(c)  
