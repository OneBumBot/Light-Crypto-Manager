from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from enum import Enum


db = SQLAlchemy()

# Enum для ролей
class UserRole(Enum):
    ADMIN = 'admin'
    OPERATOR = 'operator'
    VIEWER = 'viewer'

# Определение прав доступа к таблицам
ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        'tables': ['algorithms', 'algorithm_types', 'algorithm_schemes', 'parameters',
                   'device_configuration', 'tag_journal', 'log_journal', 'log_types',
                   'anomalies', 'anomaly_causes', 'global_reports', 'report_types', 'sensor_data'],
        'can_create': True,
        'can_update': True,
        'can_delete': True
    },
    UserRole.OPERATOR: {
        'tables': ['device_configuration', 'tag_journal', 'log_journal', 'sensor_data'],
        'can_create': True,
        'can_update': True,
        'can_delete': False
    },
    UserRole.VIEWER: {
        'tables': ['log_journal', 'sensor_data'],
        'can_create': False,
        'can_update': False,
        'can_delete': False
    }
}

class User(UserMixin, db.Model):
    __tablename__ = 'Users'
    
    id = db.Column('User_ID', db.Integer, primary_key=True)
    username = db.Column('Username', db.String(50), unique=True, nullable=False)
    email = db.Column('Email', db.String(100), unique=True, nullable=False)
    password_hash = db.Column('Password_Hash', db.String(255), nullable=False)
    role = db.Column('Role', db.String(20), nullable=False, default='viewer')
    is_active = db.Column('Is_Active', db.Boolean, default=True)
    created_at = db.Column('Created_At', db.DateTime, default=datetime.now)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_role_enum(self):
        """Получить enum роли"""
        try:
            return UserRole(self.role)
        except ValueError:
            return UserRole.VIEWER
    
    def has_table_access(self, table_name):
        """Проверяет доступ к таблице"""
        role_enum = self.get_role_enum()
        permissions = ROLE_PERMISSIONS.get(role_enum, {})
        return table_name in permissions.get('tables', [])
    
    def can_create(self, table_name=None):
        """Проверяет право на создание"""
        role_enum = self.get_role_enum()
        permissions = ROLE_PERMISSIONS.get(role_enum, {})
        if table_name and not self.has_table_access(table_name):
            return False
        return permissions.get('can_create', False)
    
    def can_update(self, table_name=None):
        """Проверяет право на изменение"""
        role_enum = self.get_role_enum()
        permissions = ROLE_PERMISSIONS.get(role_enum, {})
        if table_name and not self.has_table_access(table_name):
            return False
        return permissions.get('can_update', False)
    
    def can_delete(self, table_name=None):
        """Проверяет право на удаление"""
        role_enum = self.get_role_enum()
        permissions = ROLE_PERMISSIONS.get(role_enum, {})
        if table_name and not self.has_table_access(table_name):
            return False
        return permissions.get('can_delete', False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }




class Algorithm(db.Model):
    __tablename__ = 'Algorithms'
    
    Algorithm_ID = db.Column('Algorithm_ID', db.Integer, primary_key=True)
    Parameters_ID = db.Column('Parameters_ID', db.Integer)
    Algorithm_Name = db.Column('Algorithm_Name', db.String(40))
    Algorithm_Type_ID = db.Column('Algorithm_Type_ID', db.Integer)
    
    def to_dict(self):
        return {
            'Algorithm_ID': self.Algorithm_ID,
            'Parameters_ID': self.Parameters_ID,
            'Algorithm_Name': self.Algorithm_Name,
            'Algorithm_Type_ID': self.Algorithm_Type_ID
        }

class AlgorithmType(db.Model):
    __tablename__ = 'Algorithm_Type'
    
    Algorithm_Type_ID = db.Column('Algorithm_Type_ID', db.Integer, primary_key=True)
    Algorithm_Name = db.Column('Algorithm_Name', db.String(30))
    
    def to_dict(self):
        return {
            'Algorithm_Type_ID': self.Algorithm_Type_ID,
            'Algorithm_Name': self.Algorithm_Name
        }

class AlgorithmScheme(db.Model):
    __tablename__ = 'Algorithm_Scheme'
    
    Algorithm_Scheme_ID = db.Column('Algorithm_Scheme_ID', db.Integer, primary_key=True)
    Algorithm_Scheme = db.Column('Algorithm_Scheme', db.String(20))
    
    def to_dict(self):
        return {
            'Algorithm_Scheme_ID': self.Algorithm_Scheme_ID,
            'Algorithm_Scheme': self.Algorithm_Scheme
        }

class Parameters(db.Model):
    __tablename__ = 'Parameters'
    
    Parameters_ID = db.Column('Parameters_ID', db.Integer, primary_key=True)
    Key_Size = db.Column('Key_Size', db.Integer)
    Rounds_Count = db.Column('Rounds_Count', db.Integer)
    Algorithm_Type_ID = db.Column('Algorithm_Type_ID', db.Integer, primary_key=True)
    Algorithm_Scheme_ID = db.Column('Algorithm_Scheme_ID', db.Integer)
    
    def to_dict(self):
        return {
            'Parameters_ID': self.Parameters_ID,
            'Key_Size': self.Key_Size,
            'Rounds_Count': self.Rounds_Count,
            'Algorithm_Type_ID': self.Algorithm_Type_ID,
            'Algorithm_Scheme_ID': self.Algorithm_Scheme_ID
        }

class DeviceConfiguration(db.Model):
    __tablename__ = 'Device_Configuration'
    
    Device_ID = db.Column('Device_ID', db.Integer, primary_key=True)
    Algorithm_ID = db.Column('Algorithm_ID', db.Integer)
    Tag_ID = db.Column('Tag_ID', db.Integer)
    Configuration_Update_Date = db.Column('Configuration_Update_Date', 
                                          db.DateTime, primary_key=True)
    
    def to_dict(self):
        return {
            'Device_ID': self.Device_ID,
            'Algorithm_ID': self.Algorithm_ID,
            'Tag_ID': self.Tag_ID,
            'Configuration_Update_Date': self.Configuration_Update_Date.isoformat()
        }

class TagJournal(db.Model):
    __tablename__ = 'Tag_Journal'
    
    Tag_ID = db.Column('Tag_ID', db.Integer, primary_key=True)
    Tag_Name = db.Column('Tag_Name', db.String(30))
    Creation_Date = db.Column('Creation_Date', db.DateTime)
    
    def to_dict(self):
        return {
            'Tag_ID': self.Tag_ID,
            'Tag_Name': self.Tag_Name,
            'Creation_Date': self.Creation_Date.isoformat() if self.Creation_Date else None
        }

class LogJournal(db.Model):
    __tablename__ = 'Log_Journal'
    
    Record_ID = db.Column('Record_ID', db.Integer, primary_key=True)
    Log_Type_ID = db.Column('Log_Type_ID', db.Integer)
    Record_Date = db.Column('Record_Date', db.DateTime)
    Anomaly_ID = db.Column('Anomaly_ID', db.Integer)
    
    def to_dict(self):
        return {
            'Record_ID': self.Record_ID,
            'Log_Type_ID': self.Log_Type_ID,
            'Record_Date': self.Record_Date.isoformat() if self.Record_Date else None,
            'Anomaly_ID': self.Anomaly_ID
        }

class LogType(db.Model):
    __tablename__ = 'Log_Type'
    
    Log_Type_ID = db.Column('Log_Type_ID', db.Integer, primary_key=True)
    Log_Type = db.Column('Log_Type', db.String(50))
    
    def to_dict(self):
        return {
            'Log_Type_ID': self.Log_Type_ID,
            'Log_Type': self.Log_Type
        }

class Anomaly(db.Model):
    __tablename__ = 'Anomalies'
    
    Anomaly_ID = db.Column('Anomaly_ID', db.Integer, primary_key=True)
    Anomaly_Date = db.Column('Anomaly_Date', db.DateTime)
    Anomaly_Cause_ID = db.Column('Anomaly_Cause_ID', db.Integer)
    Device_ID = db.Column('Device_ID', db.Integer)
    Configuration_Update_Date = db.Column('Configuration_Update_Date', db.DateTime)
    
    def to_dict(self):
        return {
            'Anomaly_ID': self.Anomaly_ID,
            'Anomaly_Date': self.Anomaly_Date.isoformat() if self.Anomaly_Date else None,
            'Anomaly_Cause_ID': self.Anomaly_Cause_ID,
            'Device_ID': self.Device_ID,
            'Configuration_Update_Date': self.Configuration_Update_Date.isoformat() if self.Configuration_Update_Date else None
        }

class AnomalyCause(db.Model):
    __tablename__ = 'Anomaly_Causes'
    
    Anomaly_Cause_ID = db.Column('Anomaly_Cause_ID', db.Integer, primary_key=True)
    Anomaly_Cause = db.Column('Anomaly_Cause', db.String(20))
    
    def to_dict(self):
        return {
            'Anomaly_Cause_ID': self.Anomaly_Cause_ID,
            'Anomaly_Cause': self.Anomaly_Cause
        }

class GlobalReport(db.Model):
    __tablename__ = 'Global_Reports'
    
    Creation_Date = db.Column('Creation_Date', db.DateTime, primary_key=True)
    Report_ID = db.Column('Report_ID', db.Integer, primary_key=True)
    Report_Name = db.Column('Report_Name', db.String(100))
    Report_Type_ID = db.Column('Report_Type_ID', db.Integer)
    Record_ID = db.Column('Record_ID', db.Integer)
    
    def to_dict(self):
        return {
            'Creation_Date': self.Creation_Date.isoformat(),
            'Report_ID': self.Report_ID,
            'Report_Name': self.Report_Name,
            'Report_Type_ID': self.Report_Type_ID,
            'Record_ID': self.Record_ID
        }

class ReportType(db.Model):
    __tablename__ = 'Report_Types'
    
    Report_Type_ID = db.Column('Report_Type_ID', db.Integer, primary_key=True)
    Report_Type = db.Column('Report_Type', db.String(30))
    
    def to_dict(self):
        return {
            'Report_Type_ID': self.Report_Type_ID,
            'Report_Type': self.Report_Type
        }

# Дополнительная таблица для сенсорных данных
class SensorData(db.Model):
    __tablename__ = 'Sensor_Data'
    
    Record_ID = db.Column('Record_ID', db.Integer, primary_key=True)
    Temperature = db.Column('Temperature', db.Numeric(5, 2))
    Humidity = db.Column('Humidity', db.Numeric(5, 2))
    
    def to_dict(self):
        return {
            'Record_ID': self.Record_ID,
            'Temperature': float(self.Temperature) if self.Temperature else None,
            'Humidity': float(self.Humidity) if self.Humidity else None,
        }

