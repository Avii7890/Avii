from datetime import time

from extensions import db
from models import Admin, Task, TaskLog


def _create_admin_and_tasks(app):
    with app.app_context():
        admin = Admin(username="admin")
        admin.set_password("testpass123")
        db.session.add(admin)
        db.session.add_all(
            [
                Task(title="Workout", time_slot=time(6, 0), description="Morning run"),
                Task(title="Read", time_slot=time(21, 30)),
            ]
        )
        db.session.commit()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "testpass123"},
        follow_redirects=True,
    )


def test_login_requires_correct_password(app, client):
    _create_admin_and_tasks(app)
    r = client.post(
        "/login", data={"username": "admin", "password": "wrong"}, follow_redirects=True
    )
    assert b"Invalid username or password" in r.data


def test_login_success_and_dashboard_shows_tasks(app, client):
    _create_admin_and_tasks(app)
    r = _login(client)
    assert r.status_code == 200

    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"Workout" in r.data
    assert b"Read" in r.data


def test_complete_and_fail_task(app, client):
    _create_admin_and_tasks(app)
    _login(client)

    with app.app_context():
        workout_log = TaskLog.query.join(Task).filter(Task.title == "Workout").first()
        read_log = TaskLog.query.join(Task).filter(Task.title == "Read").first()
        workout_id, read_id = workout_log.id, read_log.id

    r = client.post(f"/log/{workout_id}/complete", follow_redirects=True)
    assert r.status_code == 200

    r = client.post(
        f"/log/{read_id}/fail",
        data={"fail_reason": "too tired", "improvement_note": "sleep earlier"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    with app.app_context():
        assert db.session.get(TaskLog, workout_id).status == "completed"
        failed = db.session.get(TaskLog, read_id)
        assert failed.status == "failed"
        assert failed.fail_reason == "too tired"
        assert failed.improvement_note == "sleep earlier"


def test_reports_pages_render(app, client):
    _create_admin_and_tasks(app)
    _login(client)

    for report_type in ("daily", "weekly", "yearly", "hourly"):
        r = client.get(f"/reports?type={report_type}")
        assert r.status_code == 200


def test_task_crud(app, client):
    _create_admin_and_tasks(app)
    _login(client)

    r = client.post(
        "/tasks/add",
        data={"title": "Meditate", "time_slot": "07:00", "description": ""},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"Meditate" in r.data


def test_dashboard_requires_login(client):
    r = client.get("/dashboard", follow_redirects=True)
    assert b"Admin Login" in r.data or b"Please log in" in r.data
