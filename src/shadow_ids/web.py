"""Read-only research view. Separate SQLite, current PG authorization, no commands."""
import os,sqlite3
from urllib.parse import urlsplit
from flask import Blueprint,abort,jsonify,render_template,request
from flask_login import current_user,login_required
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from src.web.models import db
from .journal import Journal
blueprint=Blueprint('shadow_ids',__name__)
def access():
 if not current_user.has_table_access('sensor_data'):abort(403)
 origin=request.headers.get('Origin')
 if origin and urlsplit(origin).netloc!=request.host:abort(403)
@blueprint.get('/research/shadow-ids')
@login_required
def page():access();return render_template('shadow_ids.html')
@blueprint.get('/api/research/shadow-ids')
@login_required
def snapshot():
 access()
 try:
  limit=int(request.args.get('limit','25'));offset=int(request.args.get('offset','0'))
  if not 1<=limit<=100 or not 0<=offset<=50000:raise ValueError('bounds')
 except ValueError:return jsonify(error='Invalid pagination'),400
 try:
  db.session.execute(text('SELECT 1'));path=os.environ.get('SHADOW_JOURNAL')
  if not path:raise ValueError('Not configured')
  journal=Journal(path,readonly=True)
  try:value=journal.snapshot(limit,offset)
  finally:journal.close()
  return jsonify(value)
 except (SQLAlchemyError,sqlite3.Error,OSError,ValueError):
  db.session.rollback();return jsonify(available=False,results=[],capture={'status':'UNAVAILABLE'},worker={'status':'UNAVAILABLE'},mode='SHADOW_ONLY',trusted_detector=False,error='Research source unavailable'),503
