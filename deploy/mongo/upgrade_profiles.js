// Explicit additive validator upgrade. Never recreates collection or deletes data.
const fs = require('fs');
if (!db.getSiblingDB('admin').auth('root',fs.readFileSync('/run/mongo/root.password','utf8').trim())) quit(1);
const telemetry = db.getSiblingDB('telemetry');
const info = telemetry.getCollectionInfos({name:'measurements'})[0];
if (!info || !info.options.validator.$jsonSchema) throw new Error('Existing telemetry schema required');
const schema = info.options.validator;
const values = schema.$jsonSchema.properties.crypto_profile.enum;
if (!Array.isArray(values) || values.some(x=>!['Ascon-AEAD128','AES-128-GCM'].includes(x))) throw new Error('Unexpected schema; review required');
schema.$jsonSchema.properties.crypto_profile.enum = ['Ascon-AEAD128','AES-128-GCM'];
const result = telemetry.runCommand({collMod:'measurements',validator:schema,validationLevel:'strict',validationAction:'error'});
if (!result.ok) throw new Error('Validator upgrade failed');
print('AEAD profile validator expanded; data and indexes preserved');
