const fs = require('fs');
const admin = db.getSiblingDB('admin');
if (!admin.auth('root', fs.readFileSync('/run/mongo/root.password','utf8').trim())) quit(1);
if (admin.runCommand({ping:1}).ok !== 1) quit(1);
