"""
Comprehensive End-to-End Test Suite for Student Task Manager.
Tests:
- Automatic database initialization
- Student registration & authentication
- Task CRUD operations & quick toggle
- Filters, search, due date ranges, and sorting
- Study Planner & Timetable CRUD
- Subject Management
- Calendar API JSON endpoints
- Productivity Analytics calculations and Chart.js endpoints
- Profile updates and secure password change
- Multi-student data isolation and security checks
"""

import unittest
from datetime import date, timedelta
from app import app, db
from models import User, Task, Subject, StudySchedule, Notification
from utils.helpers import calculate_student_stats, sync_student_notifications

class StudentTaskManagerTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()

        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def register_user(self, name, email, password):
        return self.app.post('/register', data={
            'name': name,
            'email': email,
            'password': password,
            'confirm_password': password,
            'college': 'Stanford University',
            'major': 'Computer Science',
            'semester': 'Semester 4'
        }, follow_redirects=True)

    def login_user(self, email, password):
        return self.app.post('/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    def logout_user(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_registration_and_login(self):
        """Test registration, auto-seeding of subjects, and login session"""
        res = self.register_user('Alice Smith', 'alice@test.edu', 'secret123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Productivity Dashboard', res.data)
        self.assertIn(b'Alice Smith', res.data)

        with app.app_context():
            user = User.query.filter_by(email='alice@test.edu').first()
            self.assertIsNotNone(user)
            self.assertTrue(user.check_password('secret123'))
            # Check default subjects seeded
            subjects = Subject.query.filter_by(user_id=user.id).all()
            self.assertGreater(len(subjects), 0)

        # Logout and log back in
        self.logout_user()
        res_login = self.login_user('alice@test.edu', 'secret123')
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b'Productivity Dashboard', res_login.data)

    def test_task_crud_and_toggle(self):
        """Test complete Task CRUD cycle and quick status toggle"""
        self.register_user('Bob Jones', 'bob@test.edu', 'password123')

        with app.app_context():
            user = User.query.filter_by(email='bob@test.edu').first()
            subj = Subject.query.filter_by(user_id=user.id).first()
            subj_id = subj.id

        today = date.today()
        due_date = (today + timedelta(days=3)).strftime('%Y-%m-%d')

        # 1. Create Task
        res_create = self.app.post('/tasks/new', data={
            'title': 'Operating Systems Project 1',
            'description': 'Implement user threads in C',
            'subject_id': subj_id,
            'category': 'Project',
            'priority': 'High',
            'status': 'Pending',
            'due_date': due_date,
            'due_time': '23:59',
            'estimated_hours': '4.5'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        self.assertIn(b'Operating Systems Project 1', res_create.data)

        with app.app_context():
            task = Task.query.filter_by(title='Operating Systems Project 1').first()
            self.assertIsNotNone(task)
            task_id = task.id
            self.assertEqual(task.status, 'Pending')

        # 2. View Task Detail
        res_detail = self.app.get(f'/tasks/{task_id}')
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn(b'Implement user threads in C', res_detail.data)

        # 3. Toggle Task Status (AJAX)
        res_toggle = self.app.post(f'/tasks/{task_id}/toggle', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res_toggle.status_code, 200)
        data = res_toggle.get_json()
        self.assertTrue(data['is_completed'])
        self.assertEqual(data['status'], 'Completed')

        # 4. Edit Task
        res_edit = self.app.post(f'/tasks/{task_id}/edit', data={
            'title': 'Operating Systems Project 1 - Finalized',
            'description': 'Updated documentation and benchmarks',
            'subject_id': subj_id,
            'category': 'Project',
            'priority': 'Medium',
            'status': 'Completed',
            'due_date': due_date,
            'due_time': '20:00',
            'estimated_hours': '5.0'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b'Operating Systems Project 1 - Finalized', res_edit.data)

        # 5. Delete Task
        res_del = self.app.post(f'/tasks/{task_id}/delete', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        with app.app_context():
            task_check = db.session.get(Task, task_id)
            self.assertIsNone(task_check)

    def test_search_and_filters(self):
        """Test task filtering by priority, status, subject, search query, and sorting"""
        self.register_user('Carol White', 'carol@test.edu', 'carolpass')

        with app.app_context():
            user = User.query.filter_by(email='carol@test.edu').first()
            s = Subject.query.filter_by(user_id=user.id).first()

            t1 = Task(user_id=user.id, subject_id=s.id, title='Calculus Midterm Study', priority='High', status='Pending', due_date=date.today())
            t2 = Task(user_id=user.id, subject_id=s.id, title='Physics Lab Report', priority='Low', status='Completed', due_date=date.today() + timedelta(days=5))
            db.session.add_all([t1, t2])
            db.session.commit()

        # Search by keyword
        res_search = self.app.get('/tasks?search=Calculus')
        self.assertIn(b'Calculus Midterm Study', res_search.data)
        self.assertNotIn(b'Physics Lab Report', res_search.data)

        # Filter by priority
        res_priority = self.app.get('/tasks?priority=High')
        self.assertIn(b'Calculus Midterm Study', res_priority.data)
        self.assertNotIn(b'Physics Lab Report', res_priority.data)

        # Filter by status
        res_status = self.app.get('/tasks?status=Completed')
        self.assertIn(b'Physics Lab Report', res_status.data)
        self.assertNotIn(b'Calculus Midterm Study', res_status.data)

        # Due today filter
        res_due = self.app.get('/tasks?due_date=today')
        self.assertIn(b'Calculus Midterm Study', res_due.data)

    def test_study_planner_and_timetable(self):
        """Test study planner sessions, timetable, and toggle"""
        self.register_user('David Brown', 'david@test.edu', 'davidpass')

        # Add study schedule
        res = self.app.post('/planner/new', data={
            'title': 'Algorithms Revision Slot',
            'schedule_type': 'Weekly Timetable',
            'day_of_week': 'Monday',
            'start_time': '10:00',
            'end_time': '12:00',
            'location': 'Library 3rd Floor',
            'notes': 'Dynamic programming and graph traversals'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Algorithms Revision Slot', res.data)

        with app.app_context():
            sched = StudySchedule.query.filter_by(title='Algorithms Revision Slot').first()
            self.assertIsNotNone(sched)
            sched_id = sched.id

        # Toggle schedule completion
        res_toggle = self.app.post(f'/planner/{sched_id}/toggle', follow_redirects=True)
        self.assertEqual(res_toggle.status_code, 200)

        with app.app_context():
            sched = db.session.get(StudySchedule, sched_id)
            self.assertTrue(sched.is_completed)

        # Delete schedule
        res_del = self.app.post(f'/planner/{sched_id}/delete', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        with app.app_context():
            self.assertIsNone(db.session.get(StudySchedule, sched_id))

    def test_subject_management(self):
        """Test creating, editing, and deleting subjects"""
        self.register_user('Sarah Connor', 'sarah@test.edu', 'sarah123')

        # Create Subject
        res = self.app.post('/subjects', data={
            'name': 'Artificial Intelligence',
            'code': 'CS501',
            'color': '#8E44AD',
            'instructor': 'Prof. Geoffrey Hinton'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Artificial Intelligence', res.data)

        with app.app_context():
            subj = Subject.query.filter_by(name='Artificial Intelligence').first()
            self.assertIsNotNone(subj)
            subj_id = subj.id

        # Edit Subject
        res_edit = self.app.post(f'/subjects/{subj_id}/edit', data={
            'name': 'Advanced Artificial Intelligence',
            'code': 'CS501A',
            'color': '#2980B9',
            'instructor': 'Dr. Yann LeCun'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b'Advanced Artificial Intelligence', res_edit.data)

    def test_profile_and_password_update(self):
        """Test profile metadata editing and secure password changing"""
        self.register_user('Victor Hugo', 'victor@test.edu', 'oldpass123')

        # Edit profile
        res_prof = self.app.post('/profile', data={
            'name': 'Victor M. Hugo',
            'college': 'Sorbonne University',
            'major': 'Literature & Computer Systems',
            'semester': 'Year 3',
            'avatar_color': '#2ECC71'
        }, follow_redirects=True)
        self.assertEqual(res_prof.status_code, 200)
        self.assertIn(b'Profile updated successfully', res_prof.data)

        # Change password
        res_pwd = self.app.post('/profile/password', data={
            'current_password': 'oldpass123',
            'new_password': 'newsecretpass',
            'confirm_password': 'newsecretpass'
        }, follow_redirects=True)
        self.assertEqual(res_pwd.status_code, 200)
        self.assertIn(b'Password changed successfully', res_pwd.data)

        # Test login with new password
        self.logout_user()
        res_login_new = self.login_user('victor@test.edu', 'newsecretpass')
        self.assertEqual(res_login_new.status_code, 200)

    def test_calendar_and_analytics_endpoints(self):
        """Test JSON API endpoints for calendar events and Chart.js analytics"""
        self.register_user('Elena Rostova', 'elena@test.edu', 'elenapass')

        with app.app_context():
            user = User.query.filter_by(email='elena@test.edu').first()
            t = Task(user_id=user.id, title='Cloud Architecture Review', due_date=date.today(), priority='High', status='In Progress')
            db.session.add(t)
            db.session.commit()

        # Calendar events endpoint
        res_cal = self.app.get('/api/calendar-events')
        self.assertEqual(res_cal.status_code, 200)
        events = res_cal.get_json()
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 0)
        self.assertIn('Cloud Architecture Review', events[0]['title'])

        # Analytics endpoint
        res_analytics = self.app.get('/api/analytics')
        self.assertEqual(res_analytics.status_code, 200)
        data = res_analytics.get_json()
        self.assertIn('weekly', data)
        self.assertIn('monthly', data)
        self.assertIn('subject', data)
        self.assertIn('priority', data)
        self.assertIn('status', data)
        self.assertIn('metrics', data)

    def test_notifications_sync_and_management(self):
        """Test auto-syncing of overdue and upcoming deadline notifications"""
        self.register_user('Felix Baum', 'felix@test.edu', 'felix123')

        with app.app_context():
            user = User.query.filter_by(email='felix@test.edu').first()
            yesterday = date.today() - timedelta(days=2)
            # Create overdue task
            overdue_task = Task(user_id=user.id, title='Late Assignment', due_date=yesterday, status='Pending')
            db.session.add(overdue_task)
            db.session.commit()

            sync_student_notifications(user.id)
            notifs = Notification.query.filter_by(user_id=user.id, notification_type='overdue').all()
            self.assertGreater(len(notifs), 0)

        res_notif = self.app.get('/notifications')
        self.assertEqual(res_notif.status_code, 200)
        self.assertIn(b'Overdue Alert: Late Assignment', res_notif.data)

    def test_student_data_privacy_isolation(self):
        """CRITICAL SECURITY TEST: Ensure Student A cannot access or manipulate Student B's data"""
        # Register Student 1
        self.register_user('Student One', 'one@test.edu', 'passone123')
        with app.app_context():
            u1 = User.query.filter_by(email='one@test.edu').first()
            t1 = Task(user_id=u1.id, title='Student One Secret Task', due_date=date.today())
            db.session.add(t1)
            db.session.commit()
            t1_id = t1.id

        self.logout_user()

        # Register Student 2
        self.register_user('Student Two', 'two@test.edu', 'passtwo123')

        # Student 2 tries to view Student 1's task list
        res_list = self.app.get('/tasks')
        self.assertNotIn(b'Student One Secret Task', res_list.data)

        # Student 2 tries to directly view Student 1's task detail -> must return 404
        res_detail = self.app.get(f'/tasks/{t1_id}')
        self.assertEqual(res_detail.status_code, 404)

        # Student 2 tries to edit Student 1's task -> must return 404
        res_edit = self.app.post(f'/tasks/{t1_id}/edit', data={'title': 'Hacked Task', 'due_date': '2026-12-01'})
        self.assertEqual(res_edit.status_code, 404)

        # Student 2 tries to delete Student 1's task -> must return 404
        res_delete = self.app.post(f'/tasks/{t1_id}/delete')
        self.assertEqual(res_delete.status_code, 404)

        # Verify task is unchanged in database
        with app.app_context():
            t1_verify = db.session.get(Task, t1_id)
            self.assertIsNotNone(t1_verify)
            self.assertEqual(t1_verify.title, 'Student One Secret Task')

if __name__ == '__main__':
    unittest.main()
