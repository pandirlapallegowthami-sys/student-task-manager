from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    college = db.Column(db.String(150), nullable=True)
    major = db.Column(db.String(150), nullable=True)
    semester = db.Column(db.String(50), nullable=True)
    avatar_color = db.Column(db.String(20), default='#6C5CE7')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships with strict cascade deletion
    tasks = db.relationship('Task', backref='student', cascade='all, delete-orphan', lazy=True)
    subjects = db.relationship('Subject', backref='student', cascade='all, delete-orphan', lazy=True)
    schedules = db.relationship('StudySchedule', backref='student', cascade='all, delete-orphan', lazy=True)
    notifications = db.relationship('Notification', backref='student', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def initials(self):
        parts = self.name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        elif len(parts) == 1 and len(parts[0]) > 0:
            return parts[0][:2].upper()
        return "ST"

    def __repr__(self):
        return f'<User {self.email}>'


class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(30), nullable=True)
    color = db.Column(db.String(20), default='#6C5CE7')
    instructor = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tasks = db.relationship('Task', backref='subject', lazy=True)
    schedules = db.relationship('StudySchedule', backref='subject', lazy=True)

    def __repr__(self):
        return f'<Subject {self.name}>'


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default='Assignment')  # Assignment, Project, Exam Prep, Reading, Lab, Other
    priority = db.Column(db.String(20), default='Medium')      # High, Medium, Low
    status = db.Column(db.String(20), default='Pending')        # Pending, In Progress, Completed
    start_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=False, index=True)
    due_time = db.Column(db.String(10), nullable=True, default='23:59')
    estimated_hours = db.Column(db.Float, default=1.0)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_overdue(self):
        if self.status == 'Completed':
            return False
        today = date.today()
        return self.due_date < today

    @property
    def days_remaining(self):
        today = date.today()
        delta = (self.due_date - today).days
        return delta

    @property
    def due_status_display(self):
        if self.status == 'Completed':
            return 'Completed'
        days = self.days_remaining
        if days < 0:
            return f'Overdue by {abs(days)} day{"s" if abs(days) != 1 else ""}'
        elif days == 0:
            return 'Due Today'
        elif days == 1:
            return 'Due Tomorrow'
        else:
            return f'Due in {days} days'

    @property
    def priority_badge_class(self):
        mapping = {
            'High': 'badge-priority-high',
            'Medium': 'badge-priority-medium',
            'Low': 'badge-priority-low'
        }
        return mapping.get(self.priority, 'badge-priority-medium')

    @property
    def status_badge_class(self):
        mapping = {
            'Completed': 'badge-status-completed',
            'In Progress': 'badge-status-progress',
            'Pending': 'badge-status-pending'
        }
        return mapping.get(self.status, 'badge-status-pending')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description or '',
            'category': self.category,
            'priority': self.priority,
            'status': self.status,
            'start_date': self.start_date.strftime('%Y-%m-%d') if self.start_date else None,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            'due_time': self.due_time or '23:59',
            'estimated_hours': self.estimated_hours,
            'is_overdue': self.is_overdue,
            'days_remaining': self.days_remaining,
            'due_status_display': self.due_status_display,
            'subject_name': self.subject.name if self.subject else 'General',
            'subject_color': self.subject.color if self.subject else '#6C5CE7',
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

    def __repr__(self):
        return f'<Task {self.title}>'


class StudySchedule(db.Model):
    __tablename__ = 'study_schedules'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    schedule_type = db.Column(db.String(50), default='Daily Study')  # Daily Study, Weekly Timetable, Exam Prep, Assignment Working Session
    day_of_week = db.Column(db.String(20), nullable=True)            # Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
    specific_date = db.Column(db.Date, nullable=True)                # For exam prep or single day schedules
    start_time = db.Column(db.String(10), nullable=False)            # e.g., "09:00"
    end_time = db.Column(db.String(10), nullable=False)              # e.g., "11:00"
    location = db.Column(db.String(150), nullable=True)              # e.g., "Library 2nd Floor", "Home Desk"
    notes = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'schedule_type': self.schedule_type,
            'day_of_week': self.day_of_week,
            'specific_date': self.specific_date.strftime('%Y-%m-%d') if self.specific_date else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'location': self.location or '',
            'notes': self.notes or '',
            'is_completed': self.is_completed,
            'subject_name': self.subject.name if self.subject else 'General Study',
            'subject_color': self.subject.color if self.subject else '#6C5CE7'
        }

    def __repr__(self):
        return f'<StudySchedule {self.title}>'


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(30), default='reminder')  # overdue, deadline, reminder, system
    is_read = db.Column(db.Boolean, default=False)
    action_link = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.notification_type,
            'is_read': self.is_read,
            'action_link': self.action_link or '',
            'created_at': self.created_at.strftime('%b %d, %Y %I:%M %p')
        }

    def __repr__(self):
        return f'<Notification {self.title}>'
