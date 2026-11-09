// Explicit administrator operation. Zero disables an existing TTL index.
const fs = require('fs');
const seconds = Number(process.env.TELEMETRY_RETENTION_SECONDS);
if (!Number.isSafeInteger(seconds) || seconds < 0) throw new Error('Explicit retention seconds required');
const admin = db.getSiblingDB('admin');
if (!admin.auth('root',fs.readFileSync('/run/mongo/root.password','utf8').trim())) quit(1);
const col = db.getSiblingDB('telemetry').measurements;
const exists = col.getIndexes().some(i=>i.name==='telemetry_retention');
if (seconds === 0) { if (exists) col.dropIndex('telemetry_retention'); }
else if (exists) db.getSiblingDB('telemetry').runCommand({collMod:'measurements', index:{name:'telemetry_retention',expireAfterSeconds:seconds}});
else col.createIndex({received_at:1},{name:'telemetry_retention',expireAfterSeconds:seconds});
print('Explicit telemetry retention policy applied');
