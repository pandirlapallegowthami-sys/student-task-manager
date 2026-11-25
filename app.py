import os
from datetime import datetime, date, time
from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify, abort
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Subject, Task, StudySchedule, Notification
from utils.helpers import (
    seed_default_subjects,
    sync_student_notifications,
    calculate_student_stats,
    get_analytics_data
)

basedir = os.path.abspath(os.path.dirname(__file__))
database_dir = os.path.join(basedir, 'database')
os.makedirs(database_dir, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'student-task-manager-super-secret-key-2026-prod-grade'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(database_dir, 'student_task_manager.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Context processor for global template variables
@app.context_processor
def inject_global_data():
    if current_user.is_authenticated:
        unread_count = Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).count()
        recent_notifs = Notification.query.filter_by(
            user_id=current_user.id
        ).order_by(Notification.created_at.desc()).limit(5).all()
        user_subjects = Subject.query.filter_by(user_id=current_user.id).all()
        return {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifs,
            'user_subjects': user_subjects,
            'today_date': date.today(),
            'current_year': datetime.now().year
        }
    return {
        'unread_notifications_count': 0,
        'recent_notifications': [],
        'user_subjects': [],
        'today_date': date.today(),
        'current_year': datetime.now().year
    }


# ==========================================
# AUTHENTICATION ROUTES
# ==========================================

@app.route('/register', methods=['GET', 'POST'])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        college = request.form.get('college', '').strip()
        major = request.form.get('major', '').strip()
        semester = request.form.get('semester', '').strip()

        # Input validations
        if not name or not email or not password:
            flash('Please fill in all required fields (Name, Email, Password).', 'danger')
            return render_template('auth/register.html', name=name, email=email, college=college, major=major, semester=semester)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/register.html', name=name, email=email, college=college, major=major, semester=semester)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html', name=name, email=email, college=college, major=major, semester=semester)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email address already exists. Please log in.', 'warning')
            return redirect(url_for('auth_login'))

        # Create user
        new_user = User(
            name=name,
            email=email,
            college=college,
            major=major,
            semester=semester,
            avatar_color='#6C5CE7'
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Seed helpful default subjects for student
        seed_default_subjects(new_user.id)

        # Welcome notification
        welcome_notif = Notification(
            user_id=new_user.id,
            title='Welcome to Student Task Manager!',
            message=f'Hi {name}! Your smart student productivity workspace is ready. Start by adding your assignments and exams.',
            notification_type='system',
            action_link='/tasks/new'
        )
        db.session.add(welcome_notif)
        db.session.commit()

        login_user(new_user)
        flash(f'Welcome aboard, {name}! Your account has been created.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('auth/register.html')


@app.route('/login', methods=['GET', 'POST'])
def auth_login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('auth/login.html', email=email)

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password. Please try again.', 'danger')
            return render_template('auth/login.html', email=email)

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(next_page if next_page else url_for('dashboard'))

    return render_template('auth/login.html')


@app.route('/logout')
@login_required
def auth_logout():
    logout_user()
    flash('You have been securely logged out.', 'info')
    return redirect(url_for('auth_login'))


# ==========================================
# DASHBOARD ROUTE
# ==========================================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    # Sync reminders and overdue alerts for current student
    sync_student_notifications(current_user.id)

    stats = calculate_student_stats(current_user.id)
    subjects = Subject.query.filter_by(user_id=current_user.id).all()

    # Today's study schedules
    today_day_name = date.today().strftime('%A')
    today_schedules = StudySchedule.query.filter(
        StudySchedule.user_id == current_user.id,
        db.or_(
            StudySchedule.day_of_week == today_day_name,
            StudySchedule.specific_date == date.today()
        )
    ).order_by(StudySchedule.start_time.asc()).all()

    # High priority alerts
    urgent_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status != 'Completed',
        Task.priority == 'High'
    ).order_by(Task.due_date.asc()).limit(4).all()

    return render_template(
        'dashboard.html',
        stats=stats,
        subjects=subjects,
        today_schedules=today_schedules,
        urgent_tasks=urgent_tasks
    )


# ==========================================
# TASK MANAGEMENT (CRUD + SEARCH & FILTER)
# ==========================================

@app.route('/tasks')
@login_required
def task_list():
    query = Task.query.filter_by(user_id=current_user.id)

    # Search by title or description
    search_query = request.args.get('search', '').strip()
    if search_query:
        query = query.filter(
            db.or_(
                Task.title.ilike(f'%{search_query}%'),
                Task.description.ilike(f'%{search_query}%')
            )
        )

    # Filter by Subject
    subject_id = request.args.get('subject')
    if subject_id and subject_id != 'all':
        query = query.filter_by(subject_id=int(subject_id))

    # Filter by Priority
    priority = request.args.get('priority')
    if priority and priority in ['High', 'Medium', 'Low']:
        query = query.filter_by(priority=priority)

    # Filter by Status
    status = request.args.get('status')
    if status and status in ['Pending', 'In Progress', 'Completed']:
        query = query.filter_by(status=status)

    # Filter by Category
    category = request.args.get('category')
    if category and category != 'all':
        query = query.filter_by(category=category)

    # Filter by Due Date
    due_filter = request.args.get('due_date')
    today = date.today()
    if due_filter == 'today':
        query = query.filter(Task.due_date == today)
    elif due_filter == 'week':
        start_week = today
        end_week = today + timedelta(days=7)
        query = query.filter(Task.due_date >= start_week, Task.due_date <= end_week)
    elif due_filter == 'overdue':
        query = query.filter(Task.due_date < today, Task.status != 'Completed')

    # Sorting
    sort_by = request.args.get('sort', 'due_date_asc')
    if sort_by == 'due_date_asc':
        query = query.order_by(Task.due_date.asc(), Task.due_time.asc())
    elif sort_by == 'due_date_desc':
        query = query.order_by(Task.due_date.desc())
    elif sort_by == 'priority_desc':
        # High, Medium, Low ordering
        priority_case = db.case(
            (Task.priority == 'High', 1),
            (Task.priority == 'Medium', 2),
            (Task.priority == 'Low', 3),
            else_=4
        )
        query = query.order_by(priority_case.asc(), Task.due_date.asc())
    elif sort_by == 'title_asc':
        query = query.order_by(Task.title.asc())
    elif sort_by == 'created_desc':
        query = query.order_by(Task.created_at.desc())
    else:
        query = query.order_by(Task.due_date.asc())

    tasks = query.all()
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    view_mode = request.args.get('view', 'grid')

    return render_template(
        'tasks/index.html',
        tasks=tasks,
        subjects=subjects,
        current_search=search_query,
        current_subject=subject_id,
        current_priority=priority,
        current_status=status,
        current_category=category,
        current_due=due_filter,
        current_sort=sort_by,
        view_mode=view_mode
    )


@app.route('/tasks/new', methods=['GET', 'POST'])
@login_required
def task_create():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        subject_id_raw = request.form.get('subject_id')
        category = request.form.get('category', 'Assignment')
        priority = request.form.get('priority', 'Medium')
        status = request.form.get('status', 'Pending')
        start_date_raw = request.form.get('start_date')
        due_date_raw = request.form.get('due_date')
        due_time = request.form.get('due_time', '23:59')
        estimated_hours_raw = request.form.get('estimated_hours', '1.0')

        if not title:
            flash('Task title is required.', 'danger')
            return render_template('tasks/form.html', subjects=subjects, is_edit=False)

        if not due_date_raw:
            flash('Due date is required.', 'danger')
            return render_template('tasks/form.html', subjects=subjects, is_edit=False)

        try:
            due_date_obj = datetime.strptime(due_date_raw, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid due date format.', 'danger')
            return render_template('tasks/form.html', subjects=subjects, is_edit=False)

        start_date_obj = None
        if start_date_raw:
            try:
                start_date_obj = datetime.strptime(start_date_raw, '%Y-%m-%d').date()
            except ValueError:
                pass

        try:
            estimated_hours = float(estimated_hours_raw) if estimated_hours_raw else 1.0
        except ValueError:
            estimated_hours = 1.0

        subject_id = int(subject_id_raw) if subject_id_raw and subject_id_raw != 'none' else None
        
        # Verify subject ownership if specified
        if subject_id:
            subj_check = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
            if not subj_check:
                subject_id = None

        new_task = Task(
            user_id=current_user.id,
            subject_id=subject_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=status,
            start_date=start_date_obj,
            due_date=due_date_obj,
            due_time=due_time,
            estimated_hours=estimated_hours,
            completed_at=datetime.utcnow() if status == 'Completed' else None
        )

        db.session.add(new_task)
        db.session.commit()

        flash(f'Task "{title}" created successfully!', 'success')
        return redirect(url_for('task_list'))

    return render_template('tasks/form.html', subjects=subjects, is_edit=False, task=None)


@app.route('/tasks/<int:task_id>')
@login_required
def task_detail(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    return render_template('tasks/detail.html', task=task)


@app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def task_edit(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    subjects = Subject.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        subject_id_raw = request.form.get('subject_id')
        category = request.form.get('category', 'Assignment')
        priority = request.form.get('priority', 'Medium')
        status = request.form.get('status', 'Pending')
        start_date_raw = request.form.get('start_date')
        due_date_raw = request.form.get('due_date')
        due_time = request.form.get('due_time', '23:59')
        estimated_hours_raw = request.form.get('estimated_hours', '1.0')

        if not title:
            flash('Task title is required.', 'danger')
            return render_template('tasks/form.html', subjects=subjects, is_edit=True, task=task)

        if not due_date_raw:
            flash('Due date is required.', 'danger')
            return render_template('tasks/form.html', subjects=subjects, is_edit=True, task=task)

        try:
            due_date_obj = datetime.strptime(due_date_raw, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid due date format.', 'danger')
            return render_template('tasks/form.html', subjects=subjects, is_edit=True, task=task)

        start_date_obj = None
        if start_date_raw:
            try:
                start_date_obj = datetime.strptime(start_date_raw, '%Y-%m-%d').date()
            except ValueError:
                pass

        try:
            estimated_hours = float(estimated_hours_raw) if estimated_hours_raw else 1.0
        except ValueError:
            estimated_hours = 1.0

        subject_id = int(subject_id_raw) if subject_id_raw and subject_id_raw != 'none' else None
        if subject_id:
            subj_check = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
            if not subj_check:
                subject_id = None

        # Check if status flipped to Completed
        if status == 'Completed' and task.status != 'Completed':
            task.completed_at = datetime.utcnow()
        elif status != 'Completed':
            task.completed_at = None

        task.title = title
        task.description = description
        task.subject_id = subject_id
        task.category = category
        task.priority = priority
        task.status = status
        task.start_date = start_date_obj
        task.due_date = due_date_obj
        task.due_time = due_time
        task.estimated_hours = estimated_hours

        db.session.commit()
        flash(f'Task "{title}" updated successfully!', 'success')
        return redirect(url_for('task_list'))

    return render_template('tasks/form.html', subjects=subjects, is_edit=True, task=task)


@app.route('/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def task_toggle(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if task.status == 'Completed':
        task.status = 'Pending'
        task.completed_at = None
    else:
        task.status = 'Completed'
        task.completed_at = datetime.utcnow()

    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'task_id': task.id,
            'status': task.status,
            'is_completed': task.status == 'Completed',
            'status_badge_class': task.status_badge_class
        })

    flash(f'Task "{task.title}" updated to {task.status}.', 'success')
    return redirect(request.referrer or url_for('task_list'))


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def task_delete(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    title = task.title
    db.session.delete(task)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': f'Task "{title}" deleted.'})

    flash(f'Task "{title}" was deleted.', 'info')
    return redirect(request.referrer or url_for('task_list'))


# ==========================================
# STUDY PLANNER & TIMETABLE
# ==========================================

@app.route('/planner')
@login_required
def study_planner():
    today = date.today()
    today_day_name = today.strftime('%A')
    
    # Days of week order
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Schedules
    schedules = StudySchedule.query.filter_by(user_id=current_user.id).all()
    subjects = Subject.query.filter_by(user_id=current_user.id).all()

    # Daily study planner (today's scheduled blocks)
    today_sessions = [
        s for s in schedules 
        if (s.day_of_week == today_day_name and not s.specific_date) or (s.specific_date == today)
    ]
    today_sessions.sort(key=lambda x: x.start_time)

    # Weekly timetable grouped by day
    weekly_grid = {day: [] for day in days}
    for s in schedules:
        if s.day_of_week in weekly_grid and not s.specific_date:
            weekly_grid[s.day_of_week].append(s)
    
    for day in days:
        weekly_grid[day].sort(key=lambda x: x.start_time)

    # Exam preparation schedules (items with specific_date >= today and type == 'Exam Prep' or title containing Exam)
    exam_prep_sessions = [
        s for s in schedules 
        if s.schedule_type == 'Exam Prep' or (s.specific_date and s.specific_date >= today)
    ]
    exam_prep_sessions.sort(key=lambda x: (x.specific_date or date.max, x.start_time))

    # Upcoming exams/assignments from Tasks as well for unified prep view!
    exam_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.due_date >= today,
        db.or_(
            Task.category == 'Exam Prep',
            Task.title.ilike('%exam%'),
            Task.title.ilike('%quiz%'),
            Task.title.ilike('%midterm%'),
            Task.title.ilike('%final%')
        )
    ).order_by(Task.due_date.asc()).all()

    return render_template(
        'planner/index.html',
        days=days,
        today_day_name=today_day_name,
        today_sessions=today_sessions,
        weekly_grid=weekly_grid,
        exam_prep_sessions=exam_prep_sessions,
        exam_tasks=exam_tasks,
        subjects=subjects,
        schedules=schedules
    )


@app.route('/planner/new', methods=['POST'])
@login_required
def planner_create():
    title = request.form.get('title', '').strip()
    schedule_type = request.form.get('schedule_type', 'Weekly Timetable')
    day_of_week = request.form.get('day_of_week')
    specific_date_raw = request.form.get('specific_date')
    start_time = request.form.get('start_time', '09:00')
    end_time = request.form.get('end_time', '10:00')
    subject_id_raw = request.form.get('subject_id')
    location = request.form.get('location', '').strip()
    notes = request.form.get('notes', '').strip()

    if not title:
        flash('Schedule title is required.', 'danger')
        return redirect(url_for('study_planner'))

    subject_id = int(subject_id_raw) if subject_id_raw and subject_id_raw != 'none' else None
    if subject_id:
        subj_check = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
        if not subj_check:
            subject_id = None

    specific_date_obj = None
    if specific_date_raw:
        try:
            specific_date_obj = datetime.strptime(specific_date_raw, '%Y-%m-%d').date()
        except ValueError:
            pass

    # If it's a specific date, we can also derive the day of the week if not provided
    if specific_date_obj and not day_of_week:
        day_of_week = specific_date_obj.strftime('%A')

    schedule = StudySchedule(
        user_id=current_user.id,
        subject_id=subject_id,
        title=title,
        schedule_type=schedule_type,
        day_of_week=day_of_week,
        specific_date=specific_date_obj,
        start_time=start_time,
        end_time=end_time,
        location=location,
        notes=notes
    )

    db.session.add(schedule)
    db.session.commit()

    flash(f'Study schedule "{title}" added!', 'success')
    return redirect(url_for('study_planner'))


@app.route('/planner/<int:schedule_id>/toggle', methods=['POST'])
@login_required
def planner_toggle(schedule_id):
    schedule = StudySchedule.query.filter_by(id=schedule_id, user_id=current_user.id).first_or_404()
    schedule.is_completed = not schedule.is_completed
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'is_completed': schedule.is_completed})

    flash(f'Schedule "{schedule.title}" updated.', 'success')
    return redirect(url_for('study_planner'))


@app.route('/planner/<int:schedule_id>/delete', methods=['POST'])
@login_required
def planner_delete(schedule_id):
    schedule = StudySchedule.query.filter_by(id=schedule_id, user_id=current_user.id).first_or_404()
    title = schedule.title
    db.session.delete(schedule)
    db.session.commit()

    flash(f'Schedule item "{title}" removed.', 'info')
    return redirect(url_for('study_planner'))


# ==========================================
# CALENDAR VIEW & FULLCALENDAR API
# ==========================================

@app.route('/calendar')
@login_required
def calendar_view():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    return render_template('calendar/index.html', subjects=subjects)


@app.route('/api/calendar-events')
@login_required
def calendar_events_api():
    """Returns calendar events formatted for FullCalendar.js"""
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    schedules = StudySchedule.query.filter_by(user_id=current_user.id).all()

    events = []

    # Add Tasks to Calendar
    for t in tasks:
        # Determine color based on status or subject
        color = t.subject.color if t.subject else '#6C5CE7'
        if t.status == 'Completed':
            color = '#00B894'
        elif t.is_overdue:
            color = '#FF7675'

        due_date_str = t.due_date.strftime('%Y-%m-%d')
        start_time_str = f"T{t.due_time}:00" if t.due_time else "T23:59:00"

        events.append({
            'id': f"task-{t.id}",
            'title': f"[{t.priority}] {t.title}",
            'start': f"{due_date_str}{start_time_str}",
            'allDay': False,
            'backgroundColor': color,
            'borderColor': color,
            'textColor': '#ffffff',
            'extendedProps': {
                'type': 'task',
                'task_id': t.id,
                'status': t.status,
                'priority': t.priority,
                'category': t.category,
                'subject': t.subject.name if t.subject else 'General',
                'description': t.description or '',
                'is_overdue': t.is_overdue
            }
        })

    # Add specific-date Study Schedules to Calendar
    for s in schedules:
        if s.specific_date:
            date_str = s.specific_date.strftime('%Y-%m-%d')
            color = s.subject.color if s.subject else '#0984E3'
            events.append({
                'id': f"schedule-{s.id}",
                'title': f"[Study] {s.title}",
                'start': f"{date_str}T{s.start_time}:00",
                'end': f"{date_str}T{s.end_time}:00",
                'allDay': False,
                'backgroundColor': color,
                'borderColor': color,
                'textColor': '#ffffff',
                'extendedProps': {
                    'type': 'schedule',
                    'schedule_id': s.id,
                    'schedule_type': s.schedule_type,
                    'location': s.location or '',
                    'notes': s.notes or '',
                    'subject': s.subject.name if s.subject else 'General Study'
                }
            })

    return jsonify(events)


# ==========================================
# PRODUCTIVITY ANALYTICS (CHART.JS API)
# ==========================================

@app.route('/analytics')
@login_required
def analytics_view():
    data = get_analytics_data(current_user.id)
    return render_template('analytics/index.html', data=data)


@app.route('/api/analytics')
@login_required
def analytics_api():
    data = get_analytics_data(current_user.id)
    return jsonify(data)


# ==========================================
# NOTIFICATIONS & REMINDERS
# ==========================================

@app.route('/notifications')
@login_required
def notification_list():
    sync_student_notifications(current_user.id)
    
    filter_type = request.args.get('type', 'all')
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if filter_type != 'all':
        query = query.filter_by(notification_type=filter_type)

    notifications = query.order_by(Notification.created_at.desc()).all()
    return render_template('notifications/index.html', notifications=notifications, current_filter=filter_type)


@app.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def notification_mark_read(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    notif.is_read = True
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})

    return redirect(request.referrer or url_for('notification_list'))


@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def notification_mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(request.referrer or url_for('notification_list'))


@app.route('/notifications/clear', methods=['POST'])
@login_required
def notification_clear():
    Notification.query.filter_by(user_id=current_user.id, is_read=True).delete()
    db.session.commit()
    flash('Read notifications cleared.', 'info')
    return redirect(request.referrer or url_for('notification_list'))


# ==========================================
# SUBJECTS MANAGEMENT
# ==========================================

@app.route('/subjects', methods=['GET', 'POST'])
@login_required
def subject_list():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip().upper()
        color = request.form.get('color', '#6C5CE7')
        instructor = request.form.get('instructor', '').strip()

        if not name:
            flash('Subject name is required.', 'danger')
            return redirect(url_for('subject_list'))

        new_subj = Subject(
            user_id=current_user.id,
            name=name,
            code=code,
            color=color,
            instructor=instructor
        )
        db.session.add(new_subj)
        db.session.commit()
        flash(f'Subject "{name}" added successfully!', 'success')
        return redirect(url_for('subject_list'))

    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    # Compute task counts per subject
    subject_stats = []
    for s in subjects:
        task_count = Task.query.filter_by(user_id=current_user.id, subject_id=s.id).count()
        completed_count = Task.query.filter_by(user_id=current_user.id, subject_id=s.id, status='Completed').count()
        subject_stats.append({
            'subject': s,
            'total_tasks': task_count,
            'completed_tasks': completed_count,
            'rate': round((completed_count / task_count * 100), 1) if task_count > 0 else 0
        })

    return render_template('subjects/index.html', subject_stats=subject_stats)


@app.route('/subjects/<int:subject_id>/edit', methods=['POST'])
@login_required
def subject_edit(subject_id):
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip().upper()
    color = request.form.get('color', '#6C5CE7')
    instructor = request.form.get('instructor', '').strip()

    if not name:
        flash('Subject name is required.', 'danger')
        return redirect(url_for('subject_list'))

    subject.name = name
    subject.code = code
    subject.color = color
    subject.instructor = instructor
    db.session.commit()

    flash(f'Subject "{name}" updated.', 'success')
    return redirect(url_for('subject_list'))


@app.route('/subjects/<int:subject_id>/delete', methods=['POST'])
@login_required
def subject_delete(subject_id):
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    name = subject.name
    # Associated tasks will have subject_id set to NULL due to SET NULL rule
    db.session.delete(subject)
    db.session.commit()
    flash(f'Subject "{name}" deleted. Any associated tasks are now in General.', 'info')
    return redirect(url_for('subject_list'))


# ==========================================
# STUDENT PROFILE & SETTINGS
# ==========================================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_view():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        college = request.form.get('college', '').strip()
        major = request.form.get('major', '').strip()
        semester = request.form.get('semester', '').strip()
        avatar_color = request.form.get('avatar_color', '#6C5CE7')

        if not name:
            flash('Name cannot be empty.', 'danger')
            return redirect(url_for('profile_view'))

        current_user.name = name
        current_user.college = college
        current_user.major = major
        current_user.semester = semester
        current_user.avatar_color = avatar_color
        db.session.commit()

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile_view'))

    # Quick metrics for profile
    stats = calculate_student_stats(current_user.id)
    return render_template('profile/index.html', stats=stats)


@app.route('/profile/password', methods=['POST'])
@login_required
def profile_change_password():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not current_user.check_password(current_password):
        flash('Incorrect current password.', 'danger')
        return redirect(url_for('profile_view'))

    if len(new_password) < 6:
        flash('New password must be at least 6 characters.', 'danger')
        return redirect(url_for('profile_view'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('profile_view'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile_view'))


# Initialize database automatically on startup
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    # Local development server
    app.run(host='127.0.0.1', port=5000, debug=True)
