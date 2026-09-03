const fs = require('fs');  
let c = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');  
console.log(c.substring(0, 100));  
