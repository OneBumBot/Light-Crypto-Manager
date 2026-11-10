const fs = require('fs');
const telemetry = db.getSiblingDB('telemetry');
telemetry.createCollection('measurements', {
  validator: {$jsonSchema: {
    bsonType: 'object', additionalProperties: false,
    required: ['_id','device_id','key_epoch','sequence_number','measured_at','received_at',
               'crypto_profile','temperature','humidity','sensors'],
    properties: {
      _id: {bsonType: 'string', maxLength: 120},
      device_id: {bsonType: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$'},
      key_epoch: {bsonType: ['int','long'], minimum: 1, maximum: 2147483647},
      sequence_number: {bsonType: ['int','long'], minimum: 1},
      measured_at: {bsonType: 'date'}, received_at: {bsonType: 'date'},
      crypto_profile: {enum: ['Ascon-AEAD128', 'AES-128-GCM']},
      temperature: {bsonType: ['int','long','double'], minimum: -80, maximum: 150},
      humidity: {bsonType: ['int','long','double'], minimum: 0, maximum: 100},
      sensors: {bsonType: 'object', maxProperties: 0}
    }
  }}, validationLevel: 'strict', validationAction: 'error'
});
telemetry.measurements.createIndex({device_id:1,key_epoch:1,sequence_number:1},{unique:true});
telemetry.measurements.createIndex({device_id:1,measured_at:-1,_id:-1});
telemetry.measurements.createIndex({measured_at:-1,_id:-1});
telemetry.createRole({role:'telemetryRelay', privileges:[{resource:{db:'telemetry',collection:'measurements'},actions:['find','insert']}],roles:[]});
telemetry.createRole({role:'telemetryHistory', privileges:[{resource:{db:'telemetry',collection:'measurements'},actions:['find']}],roles:[]});
for (const [user,role] of [['relay','telemetryRelay'],['history','telemetryHistory']]) {
  telemetry.createUser({user, pwd:fs.readFileSync('/run/mongo/'+user+'.password','utf8').trim(), roles:[role]});
}
