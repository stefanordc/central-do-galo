const fs = require('fs');  
let txt = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');  
txt = txt.replace(/Cruzeiro/g, 'Galo');  
fs.writeFileSync('frontend/src/app/page.tsx', txt);  
