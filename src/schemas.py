from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from src.models import EnrollmentStatus, DayOfWeek


class DayOfWeekEnum(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class EnrollmentStatusEnum(str, Enum):
    ENROLLED = "enrolled"
    DROPPED = "dropped"
    COMPLETED = "completed"


class ScheduleBase(BaseModel):
    day_of_week: DayOfWeekEnum
    period_start: int = Field(ge=1, le=12, description="课程节次开始，1-12")
    period_end: int = Field(ge=1, le=12, description="课程节次结束，1-12")
    classroom: Optional[str] = None

    @field_validator('period_end')
    def check_period_order(cls, v, info):
        if 'period_start' in info.data and v < info.data['period_start']:
            raise ValueError('period_end must be greater than period_start')
        return v


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(ScheduleBase):
    pass


class Schedule(ScheduleBase):
    id: int
    course_id: str

    class Config:
        from_attributes = True


class CourseBase(BaseModel):
    course_id: str = Field(description="课程号")
    name: str = Field(min_length=1, description="课程名称")
    credits: int = Field(ge=1, le=10, description="学分")
    capacity: int = Field(ge=1, description="课程容量")
    department: Optional[str] = None
    description: Optional[str] = None
    prerequisite_ids: Optional[List[str]] = Field(default=[], description="先修课程ID列表")
    schedules: Optional[List[ScheduleCreate]] = Field(default=[], description="上课时间列表")


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    credits: Optional[int] = Field(None, ge=1, le=10)
    capacity: Optional[int] = Field(None, ge=1)
    department: Optional[str] = None
    description: Optional[str] = None
    prerequisite_ids: Optional[List[str]] = None
    schedules: Optional[List[ScheduleCreate]] = None


class Course(BaseModel):
    course_id: str
    name: str
    credits: int
    capacity: int
    enrolled_count: int
    department: Optional[str]
    description: Optional[str]
    version: int
    remaining_slots: int
    schedules: List[Schedule] = []
    prerequisites: List['Course'] = []

    @field_validator('remaining_slots', mode='before')
    def calculate_remaining(cls, v, info):
        if isinstance(v, int):
            return v
        return info.data['capacity'] - info.data['enrolled_count']

    class Config:
        from_attributes = True


class StudentBase(BaseModel):
    student_id: str = Field(description="学号")
    name: str = Field(min_length=1, description="姓名")
    grade: int = Field(ge=1, le=5, description="年级，1-5")
    credit_limit: int = Field(default=25, ge=1, description="学分上限")
    earned_credits: int = Field(default=0, ge=0, description="已修学分")


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    grade: Optional[int] = Field(None, ge=1, le=5)
    credit_limit: Optional[int] = Field(None, ge=1)


class Student(StudentBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnrollmentBase(BaseModel):
    student_id: str
    course_id: str


class EnrollmentCreate(BaseModel):
    student_id: str
    course_id: str


class Enrollment(BaseModel):
    id: int
    student_id: str
    course_id: str
    status: EnrollmentStatusEnum
    grade: Optional[float]
    enrolled_at: datetime
    dropped_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class EnrollmentWithCourse(Enrollment):
    course: Optional[Course] = None


class GradeUpdate(BaseModel):
    grade: float = Field(ge=0, le=100, description="成绩，0-100")
    changed_by: Optional[str] = None
    reason: Optional[str] = None


class SemesterBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    enrollment_start: datetime
    enrollment_end: datetime
    drop_deadline: date
    is_active: int = Field(default=0, ge=0, le=1)


class SemesterCreate(SemesterBase):
    pass


class Semester(SemesterBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourseStats(BaseModel):
    course_id: str
    course_name: str
    capacity: int
    enrolled_count: int
    fill_rate: float
    credits: int


class StudentStats(BaseModel):
    student_id: str
    student_name: str
    enrolled_courses_count: int
    enrolled_credits: int
    earned_credits: int
    completed_courses_count: int
    gpa: Optional[float]


class PopularCourse(CourseStats):
    drop_count: int
    drop_rate: float


class DropStats(BaseModel):
    course_id: str
    course_name: str
    total_enrollments: int
    drop_count: int
    drop_rate: float


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[dict] = None


Course.model_rebuild()
