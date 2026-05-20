import pytest
from sqlalchemy.orm import Session
from src.models import EnrollmentStatus, Course, Student, Enrollment
from src.enrollment_service import EnrollmentService, EnrollmentError
from src.grade_service import GradeService


class TestEnrollmentBasic:
    def test_enroll_success(self, db_session: Session, test_student: Student, test_course: Course, test_semester):
        service = EnrollmentService(db_session)
        
        enrollment = service.enroll(test_student.student_id, test_course.course_id)
        
        assert enrollment is not None
        assert enrollment.student_id == test_student.student_id
        assert enrollment.course_id == test_course.course_id
        assert enrollment.status == EnrollmentStatus.ENROLLED
        
        db_session.refresh(test_course)
        assert test_course.enrolled_count == 1

    def test_enroll_duplicate(self, db_session: Session, test_student: Student, test_course: Course, test_semester):
        service = EnrollmentService(db_session)
        
        service.enroll(test_student.student_id, test_course.course_id)
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(test_student.student_id, test_course.course_id)
        
        assert "已选择" in excinfo.value.message or "DUPLICATE" in excinfo.value.error_code

    def test_enroll_course_full(self, db_session: Session, test_semester, create_test_student, create_test_course):
        course = create_test_course("C001", "满员课程", capacity=1)
        student1 = create_test_student("S001", "学生1")
        student2 = create_test_student("S002", "学生2")
        
        service = EnrollmentService(db_session)
        
        service.enroll(student1.student_id, course.course_id)
        
        db_session.refresh(course)
        assert course.enrolled_count == 1
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(student2.student_id, course.course_id)
        
        assert "已满" in excinfo.value.message or "FULL" in excinfo.value.error_code

    def test_drop_success(self, db_session: Session, test_student: Student, test_course: Course, test_semester):
        service = EnrollmentService(db_session)
        
        enrollment = service.enroll(test_student.student_id, test_course.course_id)
        db_session.refresh(test_course)
        assert test_course.enrolled_count == 1
        
        dropped = service.drop(test_student.student_id, test_course.course_id)
        
        assert dropped.status == EnrollmentStatus.DROPPED
        assert dropped.dropped_at is not None
        
        db_session.refresh(test_course)
        assert test_course.enrolled_count == 0

    def test_drop_not_enrolled(self, db_session: Session, test_student: Student, test_course: Course, test_semester):
        service = EnrollmentService(db_session)
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.drop(test_student.student_id, test_course.course_id)
        
        assert "未选择" in excinfo.value.message or "NOT_FOUND" in excinfo.value.error_code


class TestCreditLimit:
    def test_credit_limit_check(self, db_session: Session, test_semester, create_test_student):
        from src.models import DayOfWeek, Schedule
        
        student = create_test_student("S001", "学生1", credit_limit=5)
        
        course1 = Course(course_id="C001", name="课程1", credits=3, capacity=10, enrolled_count=0, department="测试")
        course1.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        db_session.add(course1)
        
        course2 = Course(course_id="C002", name="课程2", credits=3, capacity=10, enrolled_count=0, department="测试")
        course2.schedules.append(Schedule(day_of_week=DayOfWeek.TUESDAY, period_start=1, period_end=2))
        db_session.add(course2)
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        service.enroll(student.student_id, "C001")
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(student.student_id, "C002")
        
        assert "学分上限" in excinfo.value.message or "credit" in excinfo.value.message.lower()


class TestTimeConflict:
    def test_time_conflict_same_time(self, db_session: Session, test_semester, create_test_student, create_test_course):
        from src.models import DayOfWeek, Schedule
        
        student = create_test_student("S001", "学生1")
        
        course1 = Course(course_id="C001", name="课程1", credits=2, capacity=10, enrolled_count=0, department="测试")
        course1.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        db_session.add(course1)
        
        course2 = Course(course_id="C002", name="课程2", credits=2, capacity=10, enrolled_count=0, department="测试")
        course2.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=2, period_end=3))
        db_session.add(course2)
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        service.enroll(student.student_id, "C001")
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(student.student_id, "C002")
        
        assert "冲突" in excinfo.value.message or "conflict" in excinfo.value.message.lower()

    def test_time_no_conflict(self, db_session: Session, test_semester, create_test_student, create_test_course):
        from src.models import DayOfWeek, Schedule
        
        student = create_test_student("S001", "学生1")
        
        course1 = Course(course_id="C001", name="课程1", credits=2, capacity=10, enrolled_count=0, department="测试")
        course1.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        db_session.add(course1)
        
        course2 = Course(course_id="C002", name="课程2", credits=2, capacity=10, enrolled_count=0, department="测试")
        course2.schedules.append(Schedule(day_of_week=DayOfWeek.WEDNESDAY, period_start=1, period_end=2))
        db_session.add(course2)
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        enrollment1 = service.enroll(student.student_id, "C001")
        enrollment2 = service.enroll(student.student_id, "C002")
        
        assert enrollment1.status == EnrollmentStatus.ENROLLED
        assert enrollment2.status == EnrollmentStatus.ENROLLED


class TestGradeManagement:
    def test_grade_update_success(self, db_session: Session, test_student: Student, test_course: Course, test_semester):
        enrollment_service = EnrollmentService(db_session)
        grade_service = GradeService(db_session)
        
        enrollment = enrollment_service.enroll(test_student.student_id, test_course.course_id)
        
        updated = grade_service.update_grade(
            test_student.student_id,
            test_course.course_id,
            85.0
        )
        
        assert updated.grade == 85.0
        assert updated.status == EnrollmentStatus.COMPLETED
        assert updated.completed_at is not None

    def test_grade_update_earned_credits(self, db_session: Session, test_semester, create_test_student, create_test_course):
        from src.models import DayOfWeek, Schedule
        
        student = create_test_student("S001", "学生1", earned_credits=0)
        
        course = Course(course_id="C001", name="课程1", credits=3, capacity=10, enrolled_count=0, department="测试")
        course.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        db_session.add(course)
        db_session.commit()
        
        enrollment_service = EnrollmentService(db_session)
        grade_service = GradeService(db_session)
        
        enrollment_service.enroll(student.student_id, "C001")
        
        db_session.refresh(student)
        assert student.earned_credits == 0
        
        grade_service.update_grade(student.student_id, "C001", 75.0)
        
        db_session.refresh(student)
        assert student.earned_credits == 3

    def test_grade_fail_no_credits(self, db_session: Session, test_semester, create_test_student, create_test_course):
        from src.models import DayOfWeek, Schedule
        
        student = create_test_student("S001", "学生1", earned_credits=0)
        
        course = Course(course_id="C001", name="课程1", credits=3, capacity=10, enrolled_count=0, department="测试")
        course.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        db_session.add(course)
        db_session.commit()
        
        enrollment_service = EnrollmentService(db_session)
        grade_service = GradeService(db_session)
        
        enrollment_service.enroll(student.student_id, "C001")
        grade_service.update_grade(student.student_id, "C001", 55.0)
        
        db_session.refresh(student)
        assert student.earned_credits == 0

    def test_gpa_calculation(self, db_session: Session, test_semester, create_test_student):
        from src.models import DayOfWeek, Schedule, Enrollment
        
        student = create_test_student("S001", "学生1")
        
        course1 = Course(course_id="C001", name="课程1", credits=3, capacity=10, enrolled_count=0, department="测试")
        course2 = Course(course_id="C002", name="课程2", credits=2, capacity=10, enrolled_count=0, department="测试")
        db_session.add_all([course1, course2])
        
        enrollment1 = Enrollment(student_id="S001", course_id="C001", status=EnrollmentStatus.COMPLETED, grade=85.0)
        enrollment2 = Enrollment(student_id="S001", course_id="C002", status=EnrollmentStatus.COMPLETED, grade=92.0)
        db_session.add_all([enrollment1, enrollment2])
        db_session.commit()
        
        grade_service = GradeService(db_session)
        gpa = grade_service.calculate_gpa("S001")
        
        assert gpa is not None
        expected = (3.7 * 3 + 4.0 * 2) / 5
        assert abs(gpa - expected) < 0.01
