"""Explicit editable fields and input conversion for legacy table operations."""
from datetime import datetime, timezone
import math
from urllib.parse import unquote, urlsplit

from flask import abort
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String

EDITABLE = {
 'algorithms': {'Algorithm_Name','Parameters_ID','Algorithm_Type_ID'},
 'algorithm_types': {'Algorithm_Name'}, 'algorithm_schemes': {'Algorithm_Scheme'},
 'parameters': {'Key_Size','Rounds_Count','Algorithm_Scheme_ID'},
 'device_configuration': {'Algorithm_ID','Tag_ID'},
 'tag_journal': {'Tag_Name','Creation_Date'},
 'log_journal': {'Log_Type_ID','Record_Date','Anomaly_ID'}, 'log_types': {'Log_Type'},
 'anomalies': {'Anomaly_Date','Anomaly_Cause_ID','Device_ID','Configuration_Update_Date'},
 'anomaly_causes': {'Anomaly_Cause'},
 'global_reports': {'Report_Name','Report_Type_ID','Record_ID'}, 'report_types': {'Report_Type'},
 'sensor_data': {'Temperature','Humidity'},
}


def safe_next(value):
    if not isinstance(value,str) or len(value)>2048: return False
    value=unquote(value)
    if any(ord(c)<32 for c in value) or '\\' in value: return False
    try: parsed=urlsplit(value)
    except ValueError: return False
    return value.startswith('/') and not value.startswith('//') and not parsed.scheme and not parsed.netloc


def record_identity(model, value):
    # Scalar API cannot safely address a composite PK. Do not guess a component.
    if len(model.__table__.primary_key.columns)!=1: abort(400)
    try: result=int(value)
    except (ValueError,TypeError): abort(400)
    if not 0<=result<=2**31-1: abort(400)
    return result


def validated_changes(table, model, data):
    if type(data) is not dict or not data or not set(data)<=EDITABLE[table]: abort(400)
    converted={}
    for name,value in data.items():
        column=model.__table__.columns[name]
        if column.primary_key: abort(400)
        if value is None:
            if not column.nullable: abort(400)
        elif isinstance(column.type,Boolean):
            if type(value) is not bool: abort(400)
        elif isinstance(column.type,Integer):
            if type(value) is not int or not 0<=value<=2**31-1: abort(400)
        elif isinstance(column.type,Numeric):
            if type(value) not in (int,float) or not -1e6<=value<=1e6 or not math.isfinite(value): abort(400)
            if name=='Temperature' and not -80<=value<=150: abort(400)
            if name=='Humidity' and not 0<=value<=100: abort(400)
        elif isinstance(column.type,String):
            if type(value) is not str or (column.type.length and len(value)>column.type.length): abort(400)
        elif isinstance(column.type,DateTime):
            if type(value) is not str or len(value)>40: abort(400)
            try: value=datetime.fromisoformat(value)
            except ValueError: abort(400)
            if value.tzinfo: value=value.astimezone(timezone.utc).replace(tzinfo=None)
        else: abort(400)
        converted[name]=value
    return converted
