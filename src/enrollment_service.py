from datetime import datetime
from typing import List, Optional, Set
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from src.models import Student, Course, Schedule, Enrollment, Semester, EnrollmentStatus
from src.concurrency import (
    enroll_with_optimistic_lock,
    drop_with_optimistic_lock,
    CapacityExceededError,
    OptimisticLockError
)


class EnrollmentError(Exception):
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class EnrollmentService:
    def __init__(self, db: Session):
        self.db = db

    def _get_active_semester(self) -> Optional[Semester]:
        return self.db.query(Semester).filter(Semester.is_active == 1).first()

    def _is_enrollment_window_open(self) -> bool:
        semester = self._get_active_semester()
        if not semester:
            return True
        now = datetime.utcnow()
        return semester.enrollment_start <= now <= semester.enrollment_end

    def _is_before_drop_deadline(self) -> bool:
        semester = self._get_active_semester()
        if not semester:
            return True
        today = datetime.utcnow().date()
        return today <= semester.drop_deadline

    def _get_enrolled_credits(self, student_id: str) -> int:
        enrolled_courses = self.db.query(Enrollment).options(
            joinedload(Enrollment.course)
        ).filter(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.ENROLLED
        ).all()
        return sum(e.course.credits for e in enrolled_courses if e.course)

    def _has_completed_course(self, student_id: str, course_id: str) -> bool:
        enrollment = self.db.query(Enrollment).filter(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.COMPLETED,
            Enrollment.grade >= 60
        ).first()
        return enrollment is not None

    def _get_all_prerequisites(self, course: Course) -> Set[str]:
        prerequisites = set()
        visited = set()

        def traverse(c: Course):
            if c.course_id in visited:
                return
            visited.add(c.course_id)
            for prereq in c.prerequisites:
                prerequisites.add(prereq.course_id)
                traverse(prereq)

        traverse(course)
        return prerequisites

    def _check_prerequisites(self, student_id: str, course: Course) -> tuple[bool, List[str]]:
        all_prereqs = self._get_all_prerequisites(course)
        missing_prereqs = []

        for prereq_id in all_prereqs:
            if not self._has_completed_course(student_id, prereq_id):
                missing_prereqs.append(prereq_id)

        return len(missing_prereqs) == 0, missing_prereqs

    def _check_time_conflict(self, student_id: str, course: Course) -> tuple[bool, Optional[str]]:
        if not course.schedules:
            return True, None

        enrolled_enrollments = self.db.query(Enrollment).options(
            joinedload(Enrollment.course).joinedload(Course.schedules)
        ).filter(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.ENROLLED
        ).all()

        for enrollment in enrolled_enrollments:
            if enrollment.course_id == course.course_id:
                continue
            enrolled_course = enrollment.course
            if not enrolled_course or not enrolled_course.schedules:
                continue

            for new_schedule in course.schedules:
                for enrolled_schedule in enrolled_course.schedules:
                    if new_schedule.day_of_week == enrolled_schedule.day_of_week:
                        new_start = new_schedule.period_start
                        new_end = new_schedule.period_end
                        enrolled_start = enrolled_schedule.period_start
                        enrolled_end = enrolled_schedule.period_end

                        if not (new_end < enrolled_start or new_start > enrolled_end):
                            conflict_msg = (
                                f"与课程 {enrolled_course.course_id} ({enrolled_course.name}) 时间冲突："
                                f"{new_schedule.day_of_week.value} 第 {enrolled_start}-{enrolled_end} 节"
                            )
                            return False, conflict_msg

        return True, None

    def _check_duplicate_enrollment(self, student_id: str, course_id: str) -> bool:
        enrollment = self.db.query(Enrollment).filter(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
            Enrollment.status.in_([EnrollmentStatus.ENROLLED, EnrollmentStatus.COMPLETED])
        ).first()
        return enrollment is not None

    def _check_all_prerequisites(
        self,
        student_id: str,
        course: Course,
        student: Student
    ) -> tuple[bool, List[str]]:
        errors = []

        enrolled_credits = self._get_enrolled_credits(student_id)
        if enrolled_credits + course.credits > student.credit_limit:
            errors.append(
                f"学分上限检查失败：已选 {enrolled_credits} 学分，"
                f"添加 {course.credits} 学分后超过上限 {student.credit_limit} 学分"
            )

        prereq_ok, missing_prereqs = self._check_prerequisites(student_id, course)
        if not prereq_ok:
            errors.append(f"先修课程检查失败：未完成先修课程 {', '.join(missing_prereqs)}")

        time_ok, conflict_msg = self._check_time_conflict(student_id, course)
        if not time_ok:
            errors.append(f"时间冲突检查失败：{conflict_msg}")

        if self._check_duplicate_enrollment(student_id, course.course_id):
            errors.append("重复选课检查失败：已选择或已完成该课程")

        return len(errors) == 0, errors

    def enroll(self, student_id: str, course_id: str) -> Enrollment:
        if not self._is_enrollment_window_open():
            raise EnrollmentError("不在选课时间窗口内", "ENROLLMENT_WINDOW_CLOSED")

        student = self.db.query(Student).filter(Student.student_id == student_id).first()
        if not student:
            raise EnrollmentError(f"学生 {student_id} 不存在", "STUDENT_NOT_FOUND")

        course = self.db.query(Course).options(
            joinedload(Course.schedules),
            joinedload(Course.prerequisites)
        ).filter(Course.course_id == course_id).first()
        if not course:
            raise EnrollmentError(f"课程 {course_id} 不存在", "COURSE_NOT_FOUND")

        check_ok, errors = self._check_all_prerequisites(student_id, course, student)
        if not check_ok:
            raise EnrollmentError("；".join(errors), "ENROLLMENT_CHECK_FAILED")

        def _do_enroll(db: Session, s_id: str, c_id: str) -> Enrollment:
            existing = db.query(Enrollment).filter(
                Enrollment.student_id == s_id,
                Enrollment.course_id == c_id
            ).first()

            if existing:
                if existing.status == EnrollmentStatus.DROPPED:
                    existing.status = EnrollmentStatus.ENROLLED
                    existing.dropped_at = None
                    db.add(existing)
                    return existing
                else:
                    raise EnrollmentError("已选择该课程", "DUPLICATE_ENROLLMENT")

            enrollment = Enrollment(
                student_id=s_id,
                course_id=c_id,
                status=EnrollmentStatus.ENROLLED
            )
            db.add(enrollment)
            return enrollment

        try:
            enrollment = enroll_with_optimistic_lock(
                self.db, course_id, student_id, _do_enroll
            )
            self.db.refresh(enrollment)
            return enrollment
        except CapacityExceededError:
            raise EnrollmentError("课程容量已满", "COURSE_FULL")
        except OptimisticLockError as e:
            raise EnrollmentError(f"选课失败，请重试：{str(e)}", "CONCURRENCY_ERROR")

    def drop(self, student_id: str, course_id: str) -> Enrollment:
        if not self._is_before_drop_deadline():
            raise EnrollmentError("已过退课截止时间", "DROP_DEADLINE_PASSED")

        student = self.db.query(Student).filter(Student.student_id == student_id).first()
        if not student:
            raise EnrollmentError(f"学生 {student_id} 不存在", "STUDENT_NOT_FOUND")

        course = self.db.query(Course).filter(Course.course_id == course_id).first()
        if not course:
            raise EnrollmentError(f"课程 {course_id} 不存在", "COURSE_NOT_FOUND")

        def _do_drop(db: Session, s_id: str, c_id: str) -> Enrollment:
            enrollment = db.query(Enrollment).filter(
                Enrollment.student_id == s_id,
                Enrollment.course_id == c_id,
                Enrollment.status == EnrollmentStatus.ENROLLED
            ).first()

            if not enrollment:
                raise EnrollmentError("未选择该课程或已退课", "ENROLLMENT_NOT_FOUND")

            enrollment.status = EnrollmentStatus.DROPPED
            enrollment.dropped_at = datetime.utcnow()
            db.add(enrollment)
            return enrollment

        try:
            enrollment = drop_with_optimistic_lock(
                self.db, course_id, student_id, _do_drop
            )
            self.db.refresh(enrollment)
            return enrollment
        except OptimisticLockError as e:
            raise EnrollmentError(f"退课失败，请重试：{str(e)}", "CONCURRENCY_ERROR")

    def get_student_enrollments(
        self,
        student_id: str,
        status: Optional[str] = None
    ) -> List[Enrollment]:
        query = self.db.query(Enrollment).options(
            joinedload(Enrollment.course).joinedload(Course.schedules)
        ).filter(Enrollment.student_id == student_id)

        if status:
            try:
                status_enum = EnrollmentStatus(status)
                query = query.filter(Enrollment.status == status_enum)
            except ValueError:
                pass

        return query.order_by(Enrollment.enrolled_at.desc()).all()

    def get_course_enrollments(self, course_id: str) -> List[Enrollment]:
        return self.db.query(Enrollment).options(
            joinedload(Enrollment.student)
        ).filter(
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.ENROLLED
        ).order_by(Enrollment.enrolled_at).all()
