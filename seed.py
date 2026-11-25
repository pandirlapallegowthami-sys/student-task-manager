"""
Seed Script for Student Task Manager.
Creates a demo student account preloaded with realistic courses, tasks,
study schedules, and notifications for immediate demonstration.

Demo credentials:
- Email: alex@university.edu
- Password: password123
"""

from datetime import date, datetime, timedelta
from app import app, db
from models import User, Subject, Task, StudySchedule, Notification

def seed_demo_data():
    with app.app_context():
        db.create_all()

        demo_email = 'alex@university.edu'
        existing_user = User.query.filter_by(email=demo_email).first()
        if existing_user:
            print(f"Demo user '{demo_email}' already exists. Skipping seed.")
            return

        print("Creating demo student account...")
        user = User(
            name="Alex Rivera",
            email=demo_email,
            college="University Institute of Technology",
            major="Computer Science & Engineering",
            semester="Semester 5 (Fall 2026)",
            avatar_color="#6C5CE7"
        )
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        print("Seeding subjects...")
        subjects_data = [
            {"name": "Design & Analysis of Algorithms", "code": "CS301", "color": "#6C5CE7", "instructor": "Prof. Alan Turing"},
            {"name": "Database Management Systems", "code": "CS302", "color": "#0984E3", "instructor": "Dr. Edgar F. Codd"},
            {"name": "Computer Networks & Security", "code": "CS303", "color": "#00B894", "instructor": "Prof. Vint Cerf"},
            {"name": "Web & Cloud Architecture", "code": "CS304", "color": "#FD79A8", "instructor": "Dr. Tim Berners-Lee"},
            {"name": "Linear Algebra & Statistics", "code": "MATH201", "color": "#E17055", "instructor": "Dr. Katherine Johnson"}
        ]

        created_subjects = []
        for s in subjects_data:
            subj = Subject(user_id=user.id, name=s["name"], code=s["code"], color=s["color"], instructor=s["instructor"])
            db.session.add(subj)
            created_subjects.append(subj)
        db.session.commit()

        s_algo = created_subjects[0]
        s_db = created_subjects[1]
        s_net = created_subjects[2]
        s_web = created_subjects[3]
        s_math = created_subjects[4]

        today = date.today()
        print("Seeding realistic academic tasks...")
        tasks = [
            # 1. High priority due soon
            Task(
                user_id=user.id,
                subject_id=s_algo.id,
                title="Dynamic Programming Assignment 3",
                description="Solve 0/1 Knapsack, Longest Common Subsequence, and Matrix Chain Multiplication with formal proofs.",
                category="Assignment",
                priority="High",
                status="In Progress",
                start_date=today - timedelta(days=2),
                due_date=today + timedelta(days=1),
                due_time="23:59",
                estimated_hours=4.0
            ),
            # 2. Medium priority due this week
            Task(
                user_id=user.id,
                subject_id=s_db.id,
                title="SQL Schema Normalization & B+ Tree Lab",
                description="Design 3NF relational schema and benchmark B-Tree indexing on 100k customer records.",
                category="Lab Work",
                priority="Medium",
                status="Pending",
                start_date=today,
                due_date=today + timedelta(days=3),
                due_time="17:00",
                estimated_hours=3.5
            ),
            # 3. High priority exam prep
            Task(
                user_id=user.id,
                subject_id=s_net.id,
                title="Computer Networks Midterm Examination",
                description="Covers OSI 7-Layer model, TCP sliding window flow control, subnetting, and congestion algorithms.",
                category="Exam Prep",
                priority="High",
                status="Pending",
                start_date=today - timedelta(days=5),
                due_date=today + timedelta(days=5),
                due_time="09:30",
                estimated_hours=8.0
            ),
            # 4. Web dev project
            Task(
                user_id=user.id,
                subject_id=s_web.id,
                title="Flask RESTful API Microservice Project",
                description="Implement JWT authentication, rate limiting, and PostgreSQL persistence with Docker containerization.",
                category="Project",
                priority="High",
                status="In Progress",
                start_date=today - timedelta(days=4),
                due_date=today + timedelta(days=7),
                due_time="23:59",
                estimated_hours=6.0
            ),
            # 5. Overdue task for testing alert banner
            Task(
                user_id=user.id,
                subject_id=s_math.id,
                title="Eigenvalues & Vector Spaces Problem Set",
                description="Submit Chapter 5 exercises questions 1-20 via university portal.",
                category="Assignment",
                priority="Medium",
                status="Pending",
                start_date=today - timedelta(days=6),
                due_date=today - timedelta(days=1),
                due_time="23:59",
                estimated_hours=2.5
            ),
            # 6. Completed tasks (for analytics charts)
            Task(
                user_id=user.id,
                subject_id=s_algo.id,
                title="Divide & Conquer Merge Sort Implementation",
                description="Analyze recurrence relations using Master Theorem.",
                category="Assignment",
                priority="Medium",
                status="Completed",
                start_date=today - timedelta(days=10),
                due_date=today - timedelta(days=2),
                completed_at=datetime.utcnow() - timedelta(days=2),
                estimated_hours=3.0
            ),
            Task(
                user_id=user.id,
                subject_id=s_db.id,
                title="ER Diagram Design for Hospital System",
                description="Complete cardinality constraints and schema translation.",
                category="Project",
                priority="Low",
                status="Completed",
                start_date=today - timedelta(days=12),
                due_date=today - timedelta(days=3),
                completed_at=datetime.utcnow() - timedelta(days=3),
                estimated_hours=2.0
            ),
            Task(
                user_id=user.id,
                subject_id=s_net.id,
                title="Wireshark Packet Analysis Quiz",
                description="Capture and inspect TCP 3-way handshake and DNS queries.",
                category="Lab Work",
                priority="Low",
                status="Completed",
                start_date=today - timedelta(days=14),
                due_date=today - timedelta(days=4),
                completed_at=datetime.utcnow() - timedelta(days=4),
                estimated_hours=1.5
            )
        ]
        db.session.add_all(tasks)
        db.session.commit()

        print("Seeding weekly timetable and study schedules...")
        schedules = [
            StudySchedule(
                user_id=user.id,
                subject_id=s_algo.id,
                title="Algorithm Problem Solving Session",
                schedule_type="Weekly Timetable",
                day_of_week="Monday",
                start_time="09:00",
                end_time="11:00",
                location="Main Science Library, Room 204",
                notes="Work on LeetCode dynamic programming list"
            ),
            StudySchedule(
                user_id=user.id,
                subject_id=s_db.id,
                title="Database Query Optimization Practice",
                schedule_type="Weekly Timetable",
                day_of_week="Tuesday",
                start_time="14:00",
                end_time="16:00",
                location="CS Computing Lab 3",
                notes="Explain execution plans and composite indexes"
            ),
            StudySchedule(
                user_id=user.id,
                subject_id=s_net.id,
                title="Networks Midterm Revision Drill",
                schedule_type="Exam Prep",
                day_of_week="Wednesday",
                specific_date=today + timedelta(days=2),
                start_time="10:00",
                end_time="12:30",
                location="Engineering Reading Room",
                notes="Memorize routing protocols (OSPF, BGP, RIP)"
            ),
            StudySchedule(
                user_id=user.id,
                subject_id=s_web.id,
                title="Full-Stack Web Dev Sprint",
                schedule_type="Weekly Timetable",
                day_of_week="Thursday",
                start_time="15:30",
                end_time="18:00",
                location="Study Pod A",
                notes="Complete CRUD controllers and responsive dashboard"
            ),
            StudySchedule(
                user_id=user.id,
                subject_id=s_math.id,
                title="Linear Algebra Group Study",
                schedule_type="Weekly Timetable",
                day_of_week="Friday",
                start_time="11:00",
                end_time="13:00",
                location="Math Department Lounge",
                notes="Review past 5 years of exam papers"
            ),
            # Today's study session
            StudySchedule(
                user_id=user.id,
                subject_id=s_algo.id,
                title="Daily Coding & Algorithm Warmup",
                schedule_type="Daily Study",
                day_of_week=today.strftime('%A'),
                start_time="08:30",
                end_time="09:30",
                location="Home Desk",
                notes="Greedy algorithms and heap operations",
                is_completed=True
            )
        ]
        db.session.add_all(schedules)
        db.session.commit()

        print("Seeding initial notifications...")
        notifications = [
            Notification(
                user_id=user.id,
                title="Overdue Alert: Eigenvalues & Vector Spaces Problem Set",
                message="This assignment was due yesterday. Please complete or reschedule it as soon as possible.",
                notification_type="overdue",
                action_link="/tasks?search=Eigenvalues"
            ),
            Notification(
                user_id=user.id,
                title="Upcoming Deadline: Dynamic Programming Assignment 3",
                message="Due tomorrow at 11:59 PM. Priority: High.",
                notification_type="deadline",
                action_link="/tasks?search=Dynamic"
            ),
            Notification(
                user_id=user.id,
                title="Exam Reminder: Computer Networks Midterm",
                message="Exam is scheduled in 5 days. Ensure all practice packets are finished.",
                notification_type="deadline",
                action_link="/planner"
            )
        ]
        db.session.add_all(notifications)
        db.session.commit()

        print("\nSeed successfully completed!")
        print("Demo Account Credentials:")
        print(f"  Email:    {demo_email}")
        print("  Password: password123")

if __name__ == '__main__':
    seed_demo_data()
