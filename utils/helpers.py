from datetime import datetime, date, timedelta
from sqlalchemy import func
from models import db, Task, Subject, StudySchedule, Notification

DEFAULT_SUBJECTS = [
    {"name": "Computer Science", "code": "CS101", "color": "#6C5CE7", "instructor": "Prof. Alan Turing"},
    {"name": "Data Structures & Algorithms", "code": "CS201", "color": "#0984E3", "instructor": "Dr. Donald Knuth"},
    {"name": "Database Systems", "code": "CS302", "color": "#00B894", "instructor": "Prof. Edgar Codd"},
    {"name": "Mathematics & Statistics", "code": "MATH102", "color": "#E17055", "instructor": "Dr. Katherine Johnson"},
    {"name": "Web & Cloud Development", "code": "CS404", "color": "#FD79A8", "instructor": "Prof. Tim Berners-Lee"}
]

def seed_default_subjects(user_id):
    """Seed helpful default subjects for a newly registered student."""
    for sub_data in DEFAULT_SUBJECTS:
        existing = Subject.query.filter_by(user_id=user_id, name=sub_data["name"]).first()
        if not existing:
            subject = Subject(
                user_id=user_id,
                name=sub_data["name"],
                code=sub_data["code"],
                color=sub_data["color"],
                instructor=sub_data["instructor"]
            )
            db.session.add(subject)
    db.session.commit()

def sync_student_notifications(user_id):
    """
    Scans student's tasks and synchronizes notifications:
    - Overdue task alerts (tasks with due_date < today and status != 'Completed')
    - Upcoming deadline reminders (due within 48 hours and status != 'Completed')
    Avoids duplicate notifications on the same day.
    """
    today = date.today()
    in_two_days = today + timedelta(days=2)
    
    # 1. Check for overdue tasks
    overdue_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.status != 'Completed',
        Task.due_date < today
    ).all()

    for task in overdue_tasks:
        days_late = (today - task.due_date).days
        title = f"Overdue Alert: {task.title}"
        existing_alert = Notification.query.filter(
            Notification.user_id == user_id,
            Notification.title == title,
            Notification.notification_type == 'overdue',
            func.date(Notification.created_at) == today
        ).first()

        if not existing_alert:
            notif = Notification(
                user_id=user_id,
                title=title,
                message=f"Task '{task.title}' was due on {task.due_date.strftime('%b %d, %Y')} ({days_late} day{'s' if days_late != 1 else ''} ago). Please complete or reschedule it.",
                notification_type='overdue',
                action_link=f"/tasks?search={task.title}"
            )
            db.session.add(notif)

    # 2. Check for upcoming deadlines (due today or within 2 days)
    upcoming_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.status != 'Completed',
        Task.due_date >= today,
        Task.due_date <= in_two_days
    ).all()

    for task in upcoming_tasks:
        days_left = (task.due_date - today).days
        time_text = "Today" if days_left == 0 else ("Tomorrow" if days_left == 1 else f"in {days_left} days")
        title = f"Upcoming Deadline: {task.title}"
        
        existing_notif = Notification.query.filter(
            Notification.user_id == user_id,
            Notification.title == title,
            Notification.notification_type == 'deadline',
            func.date(Notification.created_at) == today
        ).first()

        if not existing_notif:
            notif = Notification(
                user_id=user_id,
                title=title,
                message=f"Task '{task.title}' is due {time_text} ({task.due_date.strftime('%b %d')}). Priority: {task.priority}.",
                notification_type='deadline',
                action_link=f"/tasks?search={task.title}"
            )
            db.session.add(notif)

    db.session.commit()

def calculate_student_stats(user_id):
    """Calculates all key metrics for the student dashboard."""
    today = date.today()
    all_tasks = Task.query.filter_by(user_id=user_id).all()
    
    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.status == 'Completed')
    in_progress = sum(1 for t in all_tasks if t.status == 'In Progress')
    pending = sum(1 for t in all_tasks if t.status == 'Pending')
    overdue = sum(1 for t in all_tasks if t.is_overdue)
    completion_rate = round((completed / total * 100), 1) if total > 0 else 0

    # Upcoming deadlines within next 7 days
    next_week = today + timedelta(days=7)
    upcoming_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.status != 'Completed',
        Task.due_date >= today,
        Task.due_date <= next_week
    ).order_by(Task.due_date.asc(), Task.priority.desc()).limit(5).all()

    # Recent activities (latest 5 tasks updated or created)
    recent_tasks = Task.query.filter_by(user_id=user_id).order_by(Task.updated_at.desc()).limit(6).all()

    # High priority pending
    high_priority_count = sum(1 for t in all_tasks if t.priority == 'High' and t.status != 'Completed')

    return {
        'total': total,
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending,
        'overdue': overdue,
        'completion_rate': completion_rate,
        'upcoming_tasks': upcoming_tasks,
        'recent_tasks': recent_tasks,
        'high_priority_count': high_priority_count
    }

def get_analytics_data(user_id):
    """Aggregates rich productivity analytics for Chart.js."""
    today = date.today()
    all_tasks = Task.query.filter_by(user_id=user_id).all()

    # 1. Weekly completion trend (Last 7 days)
    last_7_days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    weekly_labels = [d.strftime('%a (%b %d)') for d in last_7_days]
    
    weekly_completed = []
    weekly_created = []

    for d in last_7_days:
        comp_count = sum(1 for t in all_tasks if t.completed_at and t.completed_at.date() == d)
        creat_count = sum(1 for t in all_tasks if t.created_at and t.created_at.date() == d)
        weekly_completed.append(comp_count)
        weekly_created.append(creat_count)

    # 2. Monthly productivity trend (Last 6 months)
    monthly_labels = []
    monthly_completed = []
    for i in range(5, -1, -1):
        # Approximate month subtraction
        month_date = today - timedelta(days=i * 30)
        m_label = month_date.strftime('%b %Y')
        monthly_labels.append(m_label)
        m_count = sum(
            1 for t in all_tasks 
            if t.completed_at and t.completed_at.year == month_date.year and t.completed_at.month == month_date.month
        )
        monthly_completed.append(m_count)

    # 3. Subject-wise distribution
    subjects = Subject.query.filter_by(user_id=user_id).all()
    subject_map = {s.id: {"name": s.name, "color": s.color, "count": 0} for s in subjects}
    general_count = 0

    for t in all_tasks:
        if t.subject_id and t.subject_id in subject_map:
            subject_map[t.subject_id]["count"] += 1
        else:
            general_count += 1

    subject_labels = []
    subject_counts = []
    subject_colors = []

    for sid, info in subject_map.items():
        if info["count"] > 0 or len(subject_map) <= 5:
            subject_labels.append(info["name"])
            subject_counts.append(info["count"])
            subject_colors.append(info["color"])

    if general_count > 0:
        subject_labels.append("General")
        subject_counts.append(general_count)
        subject_colors.append("#6C5CE7")

    # If no subjects yet
    if not subject_labels:
        subject_labels = ["No Tasks Yet"]
        subject_counts = [0]
        subject_colors = ["#E2E8F0"]

    # 4. Priority-wise distribution
    priority_labels = ["High", "Medium", "Low"]
    priority_counts = [
        sum(1 for t in all_tasks if t.priority == 'High'),
        sum(1 for t in all_tasks if t.priority == 'Medium'),
        sum(1 for t in all_tasks if t.priority == 'Low')
    ]
    priority_colors = ["#FF7675", "#FDCB6E", "#74B9FF"]

    # 5. Status distribution
    status_labels = ["Completed", "In Progress", "Pending"]
    status_counts = [
        sum(1 for t in all_tasks if t.status == 'Completed'),
        sum(1 for t in all_tasks if t.status == 'In Progress'),
        sum(1 for t in all_tasks if t.status == 'Pending')
    ]
    status_colors = ["#00B894", "#FDCB6E", "#A29BFE"]

    # Productivity Score (0 to 100)
    total_tasks = len(all_tasks)
    completed_tasks = sum(1 for t in all_tasks if t.status == 'Completed')
    overdue_tasks = sum(1 for t in all_tasks if t.is_overdue)

    if total_tasks > 0:
        base_rate = (completed_tasks / total_tasks) * 70
        on_time_penalty = min(30, overdue_tasks * 5)
        productivity_score = max(0, min(100, round(base_rate + (30 - on_time_penalty))))
    else:
        productivity_score = 0

    return {
        'weekly': {
            'labels': weekly_labels,
            'completed': weekly_completed,
            'created': weekly_created
        },
        'monthly': {
            'labels': monthly_labels,
            'completed': monthly_completed
        },
        'subject': {
            'labels': subject_labels,
            'counts': subject_counts,
            'colors': subject_colors
        },
        'priority': {
            'labels': priority_labels,
            'counts': priority_counts,
            'colors': priority_colors
        },
        'status': {
            'labels': status_labels,
            'counts': status_counts,
            'colors': status_colors
        },
        'metrics': {
            'productivity_score': productivity_score,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'overdue_tasks': overdue_tasks,
            'completion_rate': round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0
        }
    }
