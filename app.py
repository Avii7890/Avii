from collections import OrderedDict
from datetime import date, datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import extract, func

from config import Config
from extensions import db, login_manager
from models import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    Admin,
    DailyReflection,
    Task,
    TaskLog,
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    register_routes(app)
    return app


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


def parse_date(value, default=None):
    if not value:
        return default or date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return default or date.today()


def ensure_logs_for_date(log_date):
    """Create a pending TaskLog for every active task that doesn't have one yet for log_date."""
    active_task_ids = [t.id for t in Task.query.filter_by(is_active=True).all()]
    if not active_task_ids:
        return

    existing_task_ids = {
        row.task_id
        for row in TaskLog.query.filter(
            TaskLog.log_date == log_date, TaskLog.task_id.in_(active_task_ids)
        ).all()
    }

    missing = [tid for tid in active_task_ids if tid not in existing_task_ids]
    for tid in missing:
        db.session.add(TaskLog(task_id=tid, log_date=log_date, status=STATUS_PENDING))

    if missing:
        db.session.commit()


def register_routes(app):
    @app.route("/")
    def index():
        return redirect(url_for("dashboard"))

    # ---------------- Auth ----------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            admin = Admin.query.filter_by(username=username).first()

            if admin and admin.check_password(password):
                login_user(admin)
                flash("Welcome back!", "success")
                next_url = request.args.get("next")
                return redirect(next_url or url_for("dashboard"))

            flash("Invalid username or password.", "danger")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Logged out.", "info")
        return redirect(url_for("login"))

    # ---------------- Dashboard ----------------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        selected_date = parse_date(request.args.get("date"))
        ensure_logs_for_date(selected_date)

        logs = (
            TaskLog.query.join(Task)
            .filter(TaskLog.log_date == selected_date)
            .order_by(Task.time_slot.asc())
            .all()
        )

        counts = {
            STATUS_PENDING: sum(1 for l in logs if l.status == STATUS_PENDING),
            STATUS_COMPLETED: sum(1 for l in logs if l.status == STATUS_COMPLETED),
            STATUS_FAILED: sum(1 for l in logs if l.status == STATUS_FAILED),
        }

        reflection = DailyReflection.query.filter_by(log_date=selected_date).first()

        return render_template(
            "dashboard.html",
            logs=logs,
            selected_date=selected_date,
            prev_date=selected_date - timedelta(days=1),
            next_date=selected_date + timedelta(days=1),
            today=date.today(),
            counts=counts,
            reflection=reflection,
        )

    @app.route("/log/<int:log_id>/complete", methods=["POST"])
    @login_required
    def complete_log(log_id):
        log = TaskLog.query.get_or_404(log_id)
        log.status = STATUS_COMPLETED
        log.completed_at = datetime.utcnow()
        log.fail_reason = None
        db.session.commit()
        flash(f'Marked "{log.task.title}" as completed.', "success")
        return redirect(url_for("dashboard", date=log.log_date.isoformat()))

    @app.route("/log/<int:log_id>/fail", methods=["POST"])
    @login_required
    def fail_log(log_id):
        log = TaskLog.query.get_or_404(log_id)
        reason = request.form.get("fail_reason", "").strip()
        improvement = request.form.get("improvement_note", "").strip()

        log.status = STATUS_FAILED
        log.fail_reason = reason or "No reason given"
        log.improvement_note = improvement or None
        log.completed_at = None
        db.session.commit()
        flash(f'Marked "{log.task.title}" as failed.', "warning")
        return redirect(url_for("dashboard", date=log.log_date.isoformat()))

    @app.route("/log/<int:log_id>/reset", methods=["POST"])
    @login_required
    def reset_log(log_id):
        log = TaskLog.query.get_or_404(log_id)
        log.status = STATUS_PENDING
        log.fail_reason = None
        log.completed_at = None
        db.session.commit()
        flash(f'Reset "{log.task.title}" back to pending.', "info")
        return redirect(url_for("dashboard", date=log.log_date.isoformat()))

    @app.route("/reflections/save", methods=["POST"])
    @login_required
    def save_reflection():
        log_date = parse_date(request.form.get("log_date"))
        note = request.form.get("note", "").strip()

        reflection = DailyReflection.query.filter_by(log_date=log_date).first()
        if reflection:
            reflection.note = note
        else:
            reflection = DailyReflection(log_date=log_date, note=note)
            db.session.add(reflection)

        db.session.commit()
        flash("Saved your notes for tomorrow.", "success")
        return redirect(url_for("dashboard", date=log_date.isoformat()))

    # ---------------- Task management ----------------

    @app.route("/tasks")
    @login_required
    def tasks():
        all_tasks = Task.query.order_by(Task.time_slot.asc()).all()
        return render_template("tasks.html", tasks=all_tasks)

    @app.route("/tasks/add", methods=["GET", "POST"])
    @login_required
    def add_task():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            time_slot = request.form.get("time_slot", "")

            if not title or not time_slot:
                flash("Title and time slot are required.", "danger")
                return render_template("task_form.html", task=None)

            task = Task(
                title=title,
                description=description or None,
                time_slot=datetime.strptime(time_slot, "%H:%M").time(),
            )
            db.session.add(task)
            db.session.commit()
            flash(f'Task "{title}" created.', "success")
            return redirect(url_for("tasks"))

        return render_template("task_form.html", task=None)

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_task(task_id):
        task = Task.query.get_or_404(task_id)

        if request.method == "POST":
            task.title = request.form.get("title", "").strip() or task.title
            task.description = request.form.get("description", "").strip() or None
            time_slot = request.form.get("time_slot", "")
            if time_slot:
                task.time_slot = datetime.strptime(time_slot, "%H:%M").time()
            task.is_active = bool(request.form.get("is_active"))

            db.session.commit()
            flash(f'Task "{task.title}" updated.', "success")
            return redirect(url_for("tasks"))

        return render_template("task_form.html", task=task)

    @app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
    @login_required
    def toggle_task(task_id):
        task = Task.query.get_or_404(task_id)
        task.is_active = not task.is_active
        db.session.commit()
        state = "activated" if task.is_active else "deactivated"
        flash(f'Task "{task.title}" {state}.', "info")
        return redirect(url_for("tasks"))

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    @login_required
    def delete_task(task_id):
        task = Task.query.get_or_404(task_id)
        title = task.title
        db.session.delete(task)
        db.session.commit()
        flash(f'Task "{title}" and its history were deleted.', "warning")
        return redirect(url_for("tasks"))

    # ---------------- Reports ----------------

    @app.route("/reports")
    @login_required
    def reports():
        report_type = request.args.get("type", "daily")

        if report_type == "hourly":
            return hourly_report()
        if report_type == "weekly":
            return weekly_report()
        if report_type == "yearly":
            return yearly_report()
        return daily_report()

    def daily_report():
        selected_date = parse_date(request.args.get("date"))
        logs = (
            TaskLog.query.join(Task)
            .filter(TaskLog.log_date == selected_date)
            .order_by(Task.time_slot.asc())
            .all()
        )
        counts = status_counts(logs)
        return render_template(
            "reports.html",
            report_type="daily",
            selected_date=selected_date,
            logs=logs,
            counts=counts,
        )

    def hourly_report():
        selected_date = parse_date(request.args.get("date"))
        logs = (
            TaskLog.query.join(Task)
            .filter(TaskLog.log_date == selected_date)
            .order_by(Task.time_slot.asc())
            .all()
        )

        hours = OrderedDict((h, []) for h in range(24))
        for log in logs:
            hours[log.task.time_slot.hour].append(log)

        counts = status_counts(logs)
        return render_template(
            "reports.html",
            report_type="hourly",
            selected_date=selected_date,
            hours=hours,
            counts=counts,
        )

    def weekly_report():
        selected_date = parse_date(request.args.get("date"))
        week_start = selected_date - timedelta(days=selected_date.weekday())
        week_days = [week_start + timedelta(days=i) for i in range(7)]

        rows = []
        for day in week_days:
            day_logs = TaskLog.query.filter(TaskLog.log_date == day).all()
            c = status_counts(day_logs)
            total = sum(c.values())
            rate = round((c[STATUS_COMPLETED] / total) * 100, 1) if total else 0.0
            rows.append({"date": day, "counts": c, "total": total, "rate": rate})

        chart_labels = [row["date"].strftime("%a %d") for row in rows]
        chart_rates = [row["rate"] for row in rows]

        return render_template(
            "reports.html",
            report_type="weekly",
            week_start=week_start,
            week_end=week_days[-1],
            rows=rows,
            chart_labels=chart_labels,
            chart_rates=chart_rates,
        )

    def yearly_report():
        year = int(request.args.get("year", date.today().year))

        monthly_counts = (
            db.session.query(
                extract("month", TaskLog.log_date).label("month"),
                TaskLog.status,
                func.count(TaskLog.id),
            )
            .filter(extract("year", TaskLog.log_date) == year)
            .group_by("month", TaskLog.status)
            .all()
        )

        rows = []
        for month in range(1, 13):
            c = {STATUS_PENDING: 0, STATUS_COMPLETED: 0, STATUS_FAILED: 0}
            for m, status, count in monthly_counts:
                if int(m) == month and status in c:
                    c[status] = count
            total = sum(c.values())
            rate = round((c[STATUS_COMPLETED] / total) * 100, 1) if total else 0.0
            rows.append({"month": month, "counts": c, "total": total, "rate": rate})

        month_names = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        chart_labels = [month_names[row["month"] - 1] for row in rows]
        chart_rates = [row["rate"] for row in rows]

        return render_template(
            "reports.html",
            report_type="yearly",
            year=year,
            rows=rows,
            month_names=month_names,
            chart_labels=chart_labels,
            chart_rates=chart_rates,
        )


def status_counts(logs):
    return {
        STATUS_PENDING: sum(1 for l in logs if l.status == STATUS_PENDING),
        STATUS_COMPLETED: sum(1 for l in logs if l.status == STATUS_COMPLETED),
        STATUS_FAILED: sum(1 for l in logs if l.status == STATUS_FAILED),
    }


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
