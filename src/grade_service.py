from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from src.models import Student, Course, Enrollment, EnrollmentStatus, GradeAuditLog


class GradeError(Exception):
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class GradeService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def calculate_gpa_points(grade: float) -> float:
        if grade >= 90:
            return 4.0
        elif grade >= 85:
            return 3.7
        elif grade >= 80:
            return 3.3
        elif grade >= 75:
            return 3.0
        elif grade >= 70:
            return 2.7
        elif grade >= 65:
            return 2.3
        elif grade >= 60:
            return 2.0
        else:
            return 0.0

    def _update_student_earned_credits(
        self,
        student_id: str,
        course_credits: int,
        old_grade: Optional[float],
        new_grade: float
    ) -> None:
        student = self.db.query(Student).filter(Student.student_id == student_id).first()
        if not student:
            return

        old_passed = old_grade is not None and old_grade >= 60
        new_passed = new_grade >= 60

        if not old_passed and new_passed:
            student.earned_credits += course_credits
        elif old_passed and not new_passed:
            student.earned_credits = max(0, student.earned_credits - course_credits)

        self.db.add(student)

    def _create_audit_log(
        self,
        enrollment: Enrollment,
        old_grade: Optional[float],
        new_grade: float,
        changed_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> GradeAuditLog:
        audit_log = GradeAuditLog(
            enrollment_id=enrollment.id,
            student_id=enrollment.student_id,
            course_id=enrollment.course_id,
            old_grade=old_grade,
            new_grade=new_grade,
            changed_at=datetime.utcnow(),
            changed_by=changed_by,
            reason=reason
        )
        self.db.add(audit_log)
        return audit_log

    def update_grade(
        self,
        student_id: str,
        course_id: str,
        grade: float,
        changed_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Enrollment:
        if grade < 0 or grade > 100:
            raise GradeError("成绩必须在 0-100 之间", "INVALID_GRADE")

        enrollment = self.db.query(Enrollment).options(
            joinedload(Enrollment.course),
            joinedload(Enrollment.student)
        ).filter(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id
        ).first()

        if not enrollment:
            raise GradeError("选课记录不存在", "ENROLLMENT_NOT_FOUND")

        if enrollment.status == EnrollmentStatus.DROPPED:
            raise GradeError("该课程已退课，无法录入成绩", "ENROLLMENT_DROPPED")

        old_grade = enrollment.grade
        enrollment.grade = grade

        if grade >= 60 and enrollment.status != EnrollmentStatus.COMPLETED:
            enrollment.status = EnrollmentStatus.COMPLETED
            enrollment.completed_at = datetime.utcnow()

        self._update_student_earned_credits(
            student_id,
            enrollment.course.credits if enrollment.course else 0,
            old_grade,
            grade
        )

        self._create_audit_log(enrollment, old_grade, grade, changed_by, reason)

        self.db.commit()
        self.db.refresh(enrollment)
        return enrollment

    def get_student_grades(
        self,
        student_id: str,
        include_dropped: bool = False
    ) -> List[Enrollment]:
        query = self.db.query(Enrollment).options(
            joinedload(Enrollment.course)
        ).filter(Enrollment.student_id == student_id)

        if not include_dropped:
            query = query.filter(Enrollment.status != EnrollmentStatus.DROPPED)

        return query.order_by(Enrollment.enrolled_at.desc()).all()

    def calculate_gpa(self, student_id: str) -> Optional[float]:
        enrollments = self.db.query(Enrollment).options(
            joinedload(Enrollment.course)
        ).filter(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.COMPLETED,
            Enrollment.grade.isnot(None)
        ).all()

        if not enrollments:
            return None

        total_credits = 0
        total_points = 0

        for enrollment in enrollments:
            if enrollment.course and enrollment.grade is not None:
                credits = enrollment.course.credits
                points = GradeService.calculate_gpa_points(enrollment.grade)
                total_credits += credits
                total_points += points * credits

        if total_credits == 0:
            return 0.0

        return round(total_points / total_credits, 2)

    def get_grade_history(
        self,
        student_id: str,
        course_id: Optional[str] = None
    ) -> List[GradeAuditLog]:
        query = self.db.query(GradeAuditLog).filter(
            GradeAuditLog.student_id == student_id
        )

        if course_id:
            query = query.filter(GradeAuditLog.course_id == course_id)

        return query.order_by(GradeAuditLog.changed_at.desc()).all()
