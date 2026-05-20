import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import Base
from src.models import (
    Student, Course, Schedule, Enrollment, Semester,
    DayOfWeek, EnrollmentStatus
)


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_student(db_session):
    student = Student(
        student_id="S001",
        name="测试学生",
        grade=3,
        credit_limit=25,
        earned_credits=0
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


@pytest.fixture(scope="function")
def test_course(db_session):
    course = Course(
        course_id="C001",
        name="测试课程",
        credits=3,
        capacity=10,
        enrolled_count=0,
        department="测试学院"
    )
    schedule = Schedule(
        day_of_week=DayOfWeek.MONDAY,
        period_start=1,
        period_end=2,
        classroom="A101"
    )
    course.schedules.append(schedule)
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


@pytest.fixture(scope="function")
def test_semester(db_session):
    now = datetime.utcnow()
    today = now.date()
    semester = Semester(
        name="测试学期",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=120),
        enrollment_start=now - timedelta(days=7),
        enrollment_end=now + timedelta(days=30),
        drop_deadline=today + timedelta(days=60),
        is_active=1
    )
    db_session.add(semester)
    db_session.commit()
    db_session.refresh(semester)
    return semester


@pytest.fixture(scope="function")
def create_test_course(db_session):
    def _create(course_id: str, name: str, credits: int = 3, capacity: int = 10, 
                day: DayOfWeek = DayOfWeek.MONDAY, period_start: int = 1, period_end: int = 2):
        course = Course(
            course_id=course_id,
            name=name,
            credits=credits,
            capacity=capacity,
            enrolled_count=0,
            department="测试学院"
        )
        schedule = Schedule(
            day_of_week=day,
            period_start=period_start,
            period_end=period_end,
            classroom=f"Room_{course_id}"
        )
        course.schedules.append(schedule)
        db_session.add(course)
        db_session.commit()
        db_session.refresh(course)
        return course
    return _create


@pytest.fixture(scope="function")
def create_test_student(db_session):
    def _create(student_id: str, name: str, grade: int = 3, credit_limit: int = 25, earned_credits: int = 0):
        student = Student(
            student_id=student_id,
            name=name,
            grade=grade,
            credit_limit=credit_limit,
            earned_credits=earned_credits
        )
        db_session.add(student)
        db_session.commit()
        db_session.refresh(student)
        return student
    return _create


@pytest.fixture(scope="function")
def create_completed_enrollment(db_session):
    def _create(student_id: str, course_id: str, grade: float):
        enrollment = Enrollment(
            student_id=student_id,
            course_id=course_id,
            status=EnrollmentStatus.COMPLETED,
            grade=grade,
            completed_at=datetime.utcnow()
        )
        db_session.add(enrollment)
        db_session.commit()
        return enrollment
    return _create
