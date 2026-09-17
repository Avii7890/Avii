from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db

STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUSES = (STATUS_PENDING, STATUS_COMPLETED, STATUS_FAILED)


class Admin(UserMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Task(db.Model):
    """A recurring daily habit/task with a fixed time slot."""

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    time_slot = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    logs = db.relationship(
        "TaskLog", backref="task", cascade="all, delete-orphan", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Task {self.title} @ {self.time_slot}>"


class TaskLog(db.Model):
    """One day's occurrence of a task: pending / completed / failed."""

    __tablename__ = "task_logs"
    __table_args__ = (
        db.UniqueConstraint("task_id", "log_date", name="uq_task_per_day"),
    )

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    log_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    fail_reason = db.Column(db.Text, nullable=True)
    improvement_note = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DailyReflection(db.Model):
    """End-of-day note: what can be done better tomorrow."""

    __tablename__ = "daily_reflections"

    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.Date, unique=True, nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
