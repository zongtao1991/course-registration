from datetime import datetime, date
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Enum, Table, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from src.database import Base


class EnrollmentStatus(str, PyEnum):
    ENROLLED = "enrolled"
    DROPPED = "dropped"
    COMPLETED = "completed"


class DayOfWeek(str, PyEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


course_prerequisite = Table(
    "course_prerequisite",
    Base.metadata,
    Column("course_id", String, ForeignKey("courses.course_id"), primary_key=True),
    Column("prerequisite_id", String, ForeignKey("courses.course_id"), primary_key=True),
)


class Student(Base):
    __tablename__ = "students"

    student_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    grade = Column(Integer, nullable=False)
    credit_limit = Column(Integer, nullable=False, default=25)
    earned_credits = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enrollments = relationship("Enrollment", back_populates="student")


class Course(Base):
    __tablename__ = "courses"

    course_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    credits = Column(Integer, nullable=False)
    capacity = Column(Integer, nullable=False)
    enrolled_count = Column(Integer, nullable=False, default=0)
    department = Column(String, nullable=True)
    description = Column(String, nullable=True)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schedules = relationship("Schedule", back_populates="course", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="course")
    prerequisites = relationship(
        "Course",
        secondary=course_prerequisite,
        primaryjoin=course_prerequisite.c.course_id == course_id,
        secondaryjoin=course_prerequisite.c.prerequisite_id == course_id,
        backref="dependent_courses"
    )

    @validates("enrolled_count")
    def validate_enrolled_count(self, key, value):
        if value < 0:
            raise ValueError("Enrolled count cannot be negative")
        if value > self.capacity:
            raise ValueError("Enrolled count cannot exceed capacity")
        return value


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=False, index=True)
    day_of_week = Column(Enum(DayOfWeek), nullable=False)
    period_start = Column(Integer, nullable=False)
    period_end = Column(Integer, nullable=False)
    classroom = Column(String, nullable=True)

    course = relationship("Course", back_populates="schedules")

    __table_args__ = (
        UniqueConstraint(
            'course_id', 'day_of_week', 'period_start', 'period_end',
            name='uq_schedule_course_time'
        ),
    )

    @validates("period_end")
    def validate_periods(self, key, value):
        if value < self.period_start:
            raise ValueError("Period end must be greater than period start")
        return value


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.student_id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=False, index=True)
    status = Column(Enum(EnrollmentStatus), nullable=False, default=EnrollmentStatus.ENROLLED)
    grade = Column(Float, nullable=True)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    dropped_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint('student_id', 'course_id', name='uq_enrollment_student_course'),
    )


class Semester(Base):
    __tablename__ = "semesters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    enrollment_start = Column(DateTime, nullable=False)
    enrollment_end = Column(DateTime, nullable=False)
    drop_deadline = Column(Date, nullable=False)
    is_active = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GradeAuditLog(Base):
    __tablename__ = "grade_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False, index=True)
    student_id = Column(String, nullable=False, index=True)
    course_id = Column(String, nullable=False, index=True)
    old_grade = Column(Float, nullable=True)
    new_grade = Column(Float, nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    changed_by = Column(String, nullable=True)
    reason = Column(String, nullable=True)
