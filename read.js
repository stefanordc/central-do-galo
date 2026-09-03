const fs = require('fs');  
let c = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');  
let yt = c.indexOf('youtube-home-grid');  
let x = c.indexOf('secaoAtiva === \\" "x\');  
fs.writeFileSync('out.txt', c.substring(yt - 500, yt + 1500) + \\\n\\n---" X SECTION "---\\n\\n\ + c.substring(x - 100, x + 1500));  
