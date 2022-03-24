from email.policy import default
import profile
from click import option

from sqlalchemy import true
from . import login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from flask import current_app
from flask_login import UserMixin, AnonymousUserMixin
from datetime import datetime
from . import db

class Resident(db.Model):
    __tablename__ = 'resident'
    __table_args__ ={
        'extend_existing': true
    }
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(64))
    gender = db.Column(db.String(64))
    dob = db.Column(db.Date)    
    marital_status = db.Column(db.String(64))
    biography = db.Column(db.String(3000))
    ethnicity = db.Column(db.String(64))
    medical_condition = db.Column(db.String(500))
    laundry_info = db.Column(db.String(500))
    abilities = db.Column(db.String(500))
    allergies = db.Column(db.String(500))
    diet = db.Column(db.String(500))
    nok_name = db.Column(db.String(64))
    nok_email = db.Column(db.String(64))
    nok_phone = db.Column(db.String(64))
    profile_photo = db.Column(db.String(64), default='avatar.png')
    care_plan = db.Column(db.String(64),default='careplan.pdf')
    resident_type = db.Column(db.String(64), default='Permanent')
    care_address = db.Column(db.String(256))
    admission_date = db.Column(db.Date)
    medication = db.relationship('Medication', backref='med_resident', foreign_keys='Medication.med_recipient_id')
class Permission:
    READ = 1
    EDIT = 2
    WRITE = 4
    DELETE = 8
    ADMIN = 16

class Role(db.Model):
    __tablename__ = 'roles'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    User = db.relationship('User', backref='role', lazy='dynamic')
    def __init__(self, **kwargs):
        super(Role, self).__init__(**kwargs)
        if self.permissions is None:
            self.permissions = 0

    @staticmethod
    def insert_roles():
        roles = {
            'Care Manager': [Permission.ADMIN],
            'Senior Carer': [],
            'Health Care Assistant': [],
            'Activity Staff': [],
            'Kitchen Staff': [],
            'Maintenance Staff': [],
            'Cleaning Staff': [],
            'Laundry Staff': []
        }
        default_role = 'Activity Staff'
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.reset_permissions()
            for perm in roles[r]:
                role.add_permission(perm)
            role.default = (role.name == default_role)
            db.session.add(role)
        db.session.commit()
    def add_permission(self, perm):
        if not self.has_permission(perm):
            self.permissions += perm

    def remove_permission(self, perm):
        if self.has_permission(perm):
            self.permissions -= perm

    def reset_permissions(self):
        self.permissions = 0

    def has_permission(self, perm):
        return self.permissions & perm == perm
    def __repr__(self):
        return '<Role %r>' % self.name

class User(UserMixin, db.Model):
    __tablename__ = 'User'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    cleaner = db.relationship('Cleaning', backref='cleaner', foreign_keys='Cleaning.cleaned_by')
    repairs_reported = db.relationship('Maintenance', backref='reporter', foreign_keys='Maintenance.reported_by')
    timeline_entry = db.relationship('Timeline', backref='user_entry', foreign_keys='Timeline.user_entry_id')
    med_issue = db.relationship('Medication', backref='med_issuer_staff', foreign_keys='Medication.med_issuer')
    confirmed = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    last_seen = db.Column(db.DateTime, server_default=db.func.now())
    profile_photo = db.Column(db.String(64), default='avatar.png')
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['CHERISH_ADMIN']:
                self.role = Role.query.filter_by(name='Care Manager')
            if self.role is None:
                self.role = Role.query.filter_by(default=True)

    @property
    def password(self):
        raise AttributeError('Password is not readable')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm':self.id}).decode('utf-8')
    
    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps(
            {'change_email': self.id, 'new_email': new_email}).decode('utf-8')

    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        db.session.add(self)
        return True
    def can(self, perm):
        return self.role is not None and self.role.has_permission(perm)
    
    def is_administrator(self):
        return self.can(Permission.ADMIN)

    def __repr__(self):
        return '<User %r>' % self.username


class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Messages(db.Model):
    __tablename__ = 'messages'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100))
    category = db.Column(db.String(20))
    message = db.Column(db.String(500))
    sender_id = db.Column(db.ForeignKey('User.id'))    
    recipient_ids = db.Column(db.String(100))    
    recipients = db.Column(db.String(50000))        
    is_trashed = db.Column(db.Boolean, default=False)
    trashed_by_id = db.Column(db.String(100), default='')    
    deleted_by_id = db.Column(db.String(100), default='')    
    date_time = db.Column(db.DateTime, server_default=db.func.now())

    def __init__(self, **kwargs):
        super(Messages, self).__init__(**kwargs)

class Timeline(db.Model):
    __tablename__ = 'timeline'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.String(64), default='')
    activity_group_id = db.Column(db.String(64), db.ForeignKey('act_group.id'))
    action = db.Column(db.String(2048), default='')
    resident_id = db.Column(db.Integer, db.ForeignKey('resident.id'))
    user_entry_id = db.Column(db.Integer, db.ForeignKey('User.id'))
    date = db.Column(db.Date)

hasAct=db.Table('hasAct',
    db.Column('activity_id', db.Integer, db.ForeignKey('activity.id')),
    db.Column('act_group_id', db.Integer, db.ForeignKey('act_group.id'))
)

class Activity(db.Model):
    __tablename__ = 'activity'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    act_name = db.Column(db.String(64))    
    selection_type = db.Column(db.String(64))
    options = db.Column(db.String(1024), default="")
    act_group = db.relationship('ActivityGroup',
    secondary=hasAct,
    backref=db.backref('activity', lazy='dynamic'),
    lazy='dynamic')
    
class ActivityGroup(db.Model):
    __tablename__ = 'act_group'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(64))
    time = db.Column(db.String(64))

class Kitchen(db.Model):
    __tablename__ = 'kitchen'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100))
    quantity_left = db.Column(db.Float)
    safe_quantity = db.Column(db.Float)
    location = db.Column(db.String(100))    

class Maintenance(db.Model):
    __tablename__ = 'maintenance'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    issue = db.Column(db.String(100))
    location = db.Column(db.String(100))
    reported_by = db.Column(db.ForeignKey('User.id'))    
    status = db.Column(db.String(100))    
    report_date = db.Column(db.DateTime, server_default=db.func.now())

class Cleaning(db.Model):
    __tablename__ = 'cleaning'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100))
    cleaned_by = db.Column(db.ForeignKey('User.id'))    
    date_time = db.Column(db.DateTime, server_default=db.func.now())

class Medication(db.Model):
    __tablename__ = 'medication'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    dosage = db.Column(db.String(100))
    med_issuer = db.Column(db.ForeignKey('User.id'))    
    med_recipient_id = db.Column(db.ForeignKey('resident.id'))    
    complaint = db.Column(db.String(100))    
    date_time = db.Column(db.DateTime, server_default=db.func.now())

class HandoverNotes(db.Model):
    __tablename__ = 'handovernotes'
    __table_args__ = {
        'extend_existing': True
    }
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500))
    date_time = db.Column(db.DateTime, server_default=db.func.now())
