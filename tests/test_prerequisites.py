import pytest
from sqlalchemy.orm import Session
from src.models import Student, Course, Schedule, Enrollment, EnrollmentStatus, DayOfWeek
from src.enrollment_service import EnrollmentService, EnrollmentError


class TestPrerequisitesBasic:
    def test_no_prerequisites(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        course = Course(
            course_id="C001",
            name="无先修课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            department="测试"
        )
        course.schedules.append(Schedule(
            day_of_week=DayOfWeek.MONDAY,
            period_start=1,
            period_end=2
        ))
        db_session.add(course)
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        enrollment = service.enroll(student.student_id, course.course_id)
        
        assert enrollment.status == EnrollmentStatus.ENROLLED

    def test_prerequisite_not_completed(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        prereq = Course(
            course_id="PREREQ01",
            name="先修课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            department="测试"
        )
        prereq.schedules.append(Schedule(
            day_of_week=DayOfWeek.MONDAY,
            period_start=1,
            period_end=2
        ))
        
        course = Course(
            course_id="C001",
            name="需要先修的课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            department="测试"
        )
        course.schedules.append(Schedule(
            day_of_week=DayOfWeek.TUESDAY,
            period_start=1,
            period_end=2
        ))
        course.prerequisites.append(prereq)
        
        db_session.add_all([prereq, course])
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(student.student_id, course.course_id)
        
        assert "先修" in excinfo.value.message or "prerequisite" in excinfo.value.message.lower()

    def test_prerequisite_completed_with_passing_grade(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        prereq = Course(
            course_id="PREREQ01",
            name="先修课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            department="测试"
        )
        prereq.schedules.append(Schedule(
            day_of_week=DayOfWeek.MONDAY,
            period_start=1,
            period_end=2
        ))
        
        course = Course(
            course_id="C001",
            name="需要先修的课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            department="测试"
        )
        course.schedules.append(Schedule(
            day_of_week=DayOfWeek.TUESDAY,
            period_start=1,
            period_end=2
        ))
        course.prerequisites.append(prereq)
        
        db_session.add_all([prereq, course])
        
        enrollment = Enrollment(
            student_id=student.student_id,
            course_id=prereq.course_id,
            status=EnrollmentStatus.COMPLETED,
            grade=75.0
        )
        db_session.add(enrollment)
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        result = service.enroll(student.student_id, course.course_id)
        
        assert result.status == EnrollmentStatus.ENROLLED

    def test_prerequisite_completed_but_failed(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        prereq = Course(
            course_id="PREREQ01",
            name="先修课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            department="测试"
        )
        prereq.schedules.append(Schedule(
            day_of_week=DayOfWeek.MONDAY,
            period_start=1,
            period_end=2
        ))
        
        course = Course(
            course_id="C001",
            name="需要先修的课程",
            credits=3,
            capacity=10,
            enrolled_count=0,
            department="测试"
        )
        course.schedules.append(Schedule(
            day_of_week=DayOfWeek.TUESDAY,
            period_start=1,
            period_end=2
        ))
        course.prerequisites.append(prereq)
        
        db_session.add_all([prereq, course])
        
        enrollment = Enrollment(
            student_id=student.student_id,
            course_id=prereq.course_id,
            status=EnrollmentStatus.COMPLETED,
            grade=55.0
        )
        db_session.add(enrollment)
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(student.student_id, course.course_id)
        
        assert "先修" in excinfo.value.message or "prerequisite" in excinfo.value.message.lower()


class TestPrerequisitesChain:
    def test_chain_prerequisites_all_completed(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        a = Course(course_id="A", name="课程A", credits=3, capacity=10, enrolled_count=0, department="测试")
        a.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        
        b = Course(course_id="B", name="课程B", credits=3, capacity=10, enrolled_count=0, department="测试")
        b.schedules.append(Schedule(day_of_week=DayOfWeek.TUESDAY, period_start=1, period_end=2))
        b.prerequisites.append(a)
        
        c = Course(course_id="C", name="课程C", credits=3, capacity=10, enrolled_count=0, department="测试")
        c.schedules.append(Schedule(day_of_week=DayOfWeek.WEDNESDAY, period_start=1, period_end=2))
        c.prerequisites.append(b)
        
        db_session.add_all([a, b, c])
        
        enroll_a = Enrollment(student_id=student.student_id, course_id="A", status=EnrollmentStatus.COMPLETED, grade=80.0)
        enroll_b = Enrollment(student_id=student.student_id, course_id="B", status=EnrollmentStatus.COMPLETED, grade=75.0)
        db_session.add_all([enroll_a, enroll_b])
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        result = service.enroll(student.student_id, "C")
        
        assert result.status == EnrollmentStatus.ENROLLED

    def test_chain_prerequisites_middle_failed(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        a = Course(course_id="A", name="课程A", credits=3, capacity=10, enrolled_count=0, department="测试")
        a.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        
        b = Course(course_id="B", name="课程B", credits=3, capacity=10, enrolled_count=0, department="测试")
        b.schedules.append(Schedule(day_of_week=DayOfWeek.TUESDAY, period_start=1, period_end=2))
        b.prerequisites.append(a)
        
        c = Course(course_id="C", name="课程C", credits=3, capacity=10, enrolled_count=0, department="测试")
        c.schedules.append(Schedule(day_of_week=DayOfWeek.WEDNESDAY, period_start=1, period_end=2))
        c.prerequisites.append(b)
        
        db_session.add_all([a, b, c])
        
        enroll_a = Enrollment(student_id=student.student_id, course_id="A", status=EnrollmentStatus.COMPLETED, grade=80.0)
        enroll_b = Enrollment(student_id=student.student_id, course_id="B", status=EnrollmentStatus.COMPLETED, grade=55.0)
        db_session.add_all([enroll_a, enroll_b])
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(student.student_id, "C")
        
        assert "先修" in excinfo.value.message

    def test_chain_prerequisites_missing_first(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        a = Course(course_id="A", name="课程A", credits=3, capacity=10, enrolled_count=0, department="测试")
        a.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        
        b = Course(course_id="B", name="课程B", credits=3, capacity=10, enrolled_count=0, department="测试")
        b.schedules.append(Schedule(day_of_week=DayOfWeek.TUESDAY, period_start=1, period_end=2))
        b.prerequisites.append(a)
        
        c = Course(course_id="C", name="课程C", credits=3, capacity=10, enrolled_count=0, department="测试")
        c.schedules.append(Schedule(day_of_week=DayOfWeek.WEDNESDAY, period_start=1, period_end=2))
        c.prerequisites.append(b)
        
        db_session.add_all([a, b, c])
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(student.student_id, "C")
        
        assert "先修" in excinfo.value.message


class TestMultiplePrerequisites:
    def test_multiple_prerequisites_all_completed(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        a = Course(course_id="A", name="课程A", credits=3, capacity=10, enrolled_count=0, department="测试")
        a.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        
        b = Course(course_id="B", name="课程B", credits=3, capacity=10, enrolled_count=0, department="测试")
        b.schedules.append(Schedule(day_of_week=DayOfWeek.TUESDAY, period_start=1, period_end=2))
        
        c = Course(course_id="C", name="课程C", credits=3, capacity=10, enrolled_count=0, department="测试")
        c.schedules.append(Schedule(day_of_week=DayOfWeek.WEDNESDAY, period_start=1, period_end=2))
        c.prerequisites.extend([a, b])
        
        db_session.add_all([a, b, c])
        
        enroll_a = Enrollment(student_id=student.student_id, course_id="A", status=EnrollmentStatus.COMPLETED, grade=80.0)
        enroll_b = Enrollment(student_id=student.student_id, course_id="B", status=EnrollmentStatus.COMPLETED, grade=75.0)
        db_session.add_all([enroll_a, enroll_b])
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        result = service.enroll(student.student_id, "C")
        
        assert result.status == EnrollmentStatus.ENROLLED

    def test_multiple_prerequisites_one_missing(self, db_session: Session, test_semester, create_test_student):
        student = create_test_student("S001", "学生1")
        
        a = Course(course_id="A", name="课程A", credits=3, capacity=10, enrolled_count=0, department="测试")
        a.schedules.append(Schedule(day_of_week=DayOfWeek.MONDAY, period_start=1, period_end=2))
        
        b = Course(course_id="B", name="课程B", credits=3, capacity=10, enrolled_count=0, department="测试")
        b.schedules.append(Schedule(day_of_week=DayOfWeek.TUESDAY, period_start=1, period_end=2))
        
        c = Course(course_id="C", name="课程C", credits=3, capacity=10, enrolled_count=0, department="测试")
        c.schedules.append(Schedule(day_of_week=DayOfWeek.WEDNESDAY, period_start=1, period_end=2))
        c.prerequisites.extend([a, b])
        
        db_session.add_all([a, b, c])
        
        enroll_a = Enrollment(student_id=student.student_id, course_id="A", status=EnrollmentStatus.COMPLETED, grade=80.0)
        db_session.add(enroll_a)
        db_session.commit()
        
        service = EnrollmentService(db_session)
        
        with pytest.raises(EnrollmentError) as excinfo:
            service.enroll(student.student_id, "C")
        
        assert "先修" in excinfo.value.message
