import threading
import time
import pytest
import tempfile
import os
from datetime import datetime, date, timedelta
from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import Base
from src.models import (
    Student, Course, Schedule, Enrollment, Semester,
    DayOfWeek, EnrollmentStatus
)
from src.enrollment_service import EnrollmentService, EnrollmentError


class TestConcurrencyBasic:
    def test_optimistic_lock_version_increment(self, db_session, test_semester):
        from src.models import Course, Schedule, DayOfWeek
        from src.concurrency import increment_version
        
        course = Course(
            course_id="C001",
            name="测试课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            version=0
        )
        db_session.add(course)
        db_session.commit()
        db_session.refresh(course)
        
        assert course.version == 0
        
        increment_version(db_session, course)
        db_session.commit()
        db_session.refresh(course)
        
        assert course.version == 1

    def test_enroll_increments_enrolled_count(self, db_session, test_semester):
        from src.models import Course, Schedule, DayOfWeek, Student
        
        student = Student(student_id="S001", name="学生1", grade=3, credit_limit=25, earned_credits=0)
        course = Course(
            course_id="C001",
            name="测试课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            version=0
        )
        course.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        db_session.add_all([student, course])
        db_session.commit()
        
        service = EnrollmentService(db_session)
        enrollment = service.enroll("S001", "C001")
        
        db_session.refresh(course)
        assert course.enrolled_count == 1
        assert course.version == 1


class TestConcurrentEnrollment:
    def create_temp_db_engine(self):
        temp_dir = tempfile.gettempdir()
        db_path = os.path.join(temp_dir, f"test_concurrency_{int(time.time() * 1000)}.db")
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=10,
        )
        return engine, db_path

    def setup_database(self, engine):
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        
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
        session.add(semester)
        
        course = Course(
            course_id="HOT001",
            name="热门课程-限量版",
            credits=2,
            capacity=1,
            enrolled_count=0,
            department="测试",
            version=0
        )
        course.schedules.append(Schedule(
            day_of_week=DayOfWeek.MONDAY,
            period_start=1,
            period_end=2
        ))
        session.add(course)
        
        for i in range(10):
            student = Student(
                student_id=f"S{i:03d}",
                name=f"学生{i}",
                grade=3,
                credit_limit=25,
                earned_credits=0
            )
            session.add(student)
        
        session.commit()
        session.close()

    def test_concurrent_enrollment_single_slot(self):
        engine, db_path = self.create_temp_db_engine()
        try:
            self.setup_database(engine)
            
            Session = sessionmaker(bind=engine)
            
            results = []
            errors = []
            lock = threading.Lock()
            
            def enroll_student(student_id: str):
                session = Session()
                try:
                    service = EnrollmentService(session)
                    enrollment = service.enroll(student_id, "HOT001")
                    with lock:
                        results.append({"student_id": student_id, "success": True})
                except EnrollmentError as e:
                    with lock:
                        errors.append({"student_id": student_id, "error": str(e), "error_code": e.error_code})
                except Exception as e:
                    with lock:
                        errors.append({"student_id": student_id, "error": str(e), "error_code": "UNKNOWN"})
                finally:
                    session.close()
            
            threads = []
            for i in range(10):
                t = threading.Thread(target=enroll_student, args=(f"S{i:03d}",))
                threads.append(t)
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            verify_session = Session()
            course = verify_session.query(Course).filter(Course.course_id == "HOT001").first()
            enrolled_count = verify_session.query(Enrollment).filter(
                Enrollment.course_id == "HOT001",
                Enrollment.status == EnrollmentStatus.ENROLLED
            ).count()
            
            verify_session.close()
            
            assert len(results) <= 1, f"最多只能有1人成功，但有{len(results)}人成功"
            assert course.enrolled_count <= 1, f"课程已选人数不能超过1，但实际是{course.enrolled_count}"
            assert enrolled_count == course.enrolled_count, "选课记录数应与课程已选人数一致"
            assert course.version >= 1, f"版本号应该递增，但实际是{course.version}"
            
        finally:
            try:
                os.remove(db_path)
            except:
                pass

    def test_concurrent_enrollment_multiple_slots(self):
        engine, db_path = self.create_temp_db_engine()
        try:
            Base.metadata.create_all(bind=engine)
            
            Session = sessionmaker(bind=engine)
            session = Session()
            
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
            session.add(semester)
            
            course = Course(
                course_id="MULTI001",
                name="多名额课程",
                credits=2,
                capacity=3,
                enrolled_count=0,
                department="测试",
                version=0
            )
            course.schedules.append(Schedule(
                day_of_week=DayOfWeek.MONDAY,
                period_start=1,
                period_end=2
            ))
            session.add(course)
            
            for i in range(10):
                student = Student(
                    student_id=f"MS{i:03d}",
                    name=f"学生{i}",
                    grade=3,
                    credit_limit=25,
                    earned_credits=0
                )
                session.add(student)
            
            session.commit()
            session.close()
            
            results = []
            errors = []
            lock = threading.Lock()
            
            def enroll_student(student_id: str):
                session = Session()
                try:
                    service = EnrollmentService(session)
                    enrollment = service.enroll(student_id, "MULTI001")
                    with lock:
                        results.append({"student_id": student_id, "success": True})
                except EnrollmentError:
                    with lock:
                        errors.append(student_id)
                except Exception:
                    with lock:
                        errors.append(student_id)
                finally:
                    session.close()
            
            threads = []
            for i in range(10):
                t = threading.Thread(target=enroll_student, args=(f"MS{i:03d}",))
                threads.append(t)
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            verify_session = Session()
            course = verify_session.query(Course).filter(Course.course_id == "MULTI001").first()
            enrolled_count = verify_session.query(Enrollment).filter(
                Enrollment.course_id == "MULTI001",
                Enrollment.status == EnrollmentStatus.ENROLLED
            ).count()
            
            verify_session.close()
            
            assert len(results) <= 3, f"最多只能有3人成功，但有{len(results)}人成功"
            assert course.enrolled_count <= 3, f"课程已选人数不能超过3，但实际是{course.enrolled_count}"
            assert enrolled_count == course.enrolled_count, "选课记录数应与课程已选人数一致"
            
        finally:
            try:
                os.remove(db_path)
            except:
                pass


class TestConcurrentDrop:
    def test_concurrent_drop_and_enroll(self):
        temp_dir = tempfile.gettempdir()
        db_path = os.path.join(temp_dir, f"test_drop_{int(time.time() * 1000)}.db")
        
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=QueuePool,
            pool_size=10,
        )
        
        try:
            Base.metadata.create_all(bind=engine)
            
            Session = sessionmaker(bind=engine)
            session = Session()
            
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
            session.add(semester)
            
            course = Course(
                course_id="DROP001",
                name="退课测试课程",
                credits=2,
                capacity=1,
                enrolled_count=1,
                department="测试",
                version=0
            )
            course.schedules.append(Schedule(
                day_of_week=DayOfWeek.MONDAY,
                period_start=1,
                period_end=2
            ))
            session.add(course)
            
            student_with = Student(student_id="WITH001", name="已选学生", grade=3, credit_limit=25, earned_credits=0)
            student_wait = Student(student_id="WAIT001", name="等待学生", grade=3, credit_limit=25, earned_credits=0)
            session.add_all([student_with, student_wait])
            
            enrollment = Enrollment(
                student_id="WITH001",
                course_id="DROP001",
                status=EnrollmentStatus.ENROLLED
            )
            session.add(enrollment)
            
            session.commit()
            session.close()
            
            results = {"dropped": False, "enrolled": False}
            lock = threading.Lock()
            
            def drop_course():
                session = Session()
                try:
                    service = EnrollmentService(session)
                    service.drop("WITH001", "DROP001")
                    with lock:
                        results["dropped"] = True
                except Exception:
                    pass
                finally:
                    session.close()
            
            def try_enroll():
                session = Session()
                try:
                    service = EnrollmentService(session)
                    service.enroll("WAIT001", "DROP001")
                    with lock:
                        results["enrolled"] = True
                except Exception:
                    pass
                finally:
                    session.close()
            
            for _ in range(3):
                t1 = threading.Thread(target=drop_course)
                t2 = threading.Thread(target=try_enroll)
                t1.start()
                t2.start()
                t1.join()
                t2.join()
            
            verify_session = Session()
            course = verify_session.query(Course).filter(Course.course_id == "DROP001").first()
            
            dropped_enrollment = verify_session.query(Enrollment).filter(
                Enrollment.student_id == "WITH001",
                Enrollment.course_id == "DROP001"
            ).first()
            
            new_enrollment = verify_session.query(Enrollment).filter(
                Enrollment.student_id == "WAIT001",
                Enrollment.course_id == "DROP001"
            ).first()
            
            verify_session.close()
            
            assert dropped_enrollment.status == EnrollmentStatus.DROPPED
            assert course.enrolled_count in [0, 1]
            
            if new_enrollment:
                assert new_enrollment.status == EnrollmentStatus.ENROLLED
                assert course.enrolled_count == 1
            else:
                assert course.enrolled_count == 0
            
        finally:
            try:
                os.remove(db_path)
            except:
                pass
