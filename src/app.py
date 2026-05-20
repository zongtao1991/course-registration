from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from src.database import get_db, init_db
from src.models import Student, Course, EnrollmentStatus
from src.schemas import (
    Course as CourseSchema,
    CourseCreate,
    CourseUpdate,
    Student as StudentSchema,
    StudentCreate,
    StudentUpdate,
    Enrollment as EnrollmentSchema,
    EnrollmentCreate,
    GradeUpdate,
    CourseStats,
    StudentStats,
    PopularCourse,
    DropStats,
    ErrorResponse
)
from src.course_service import CourseService
from src.enrollment_service import EnrollmentService, EnrollmentError
from src.grade_service import GradeService, GradeError
from src.stats_service import StatsService


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="学生选课系统",
    description="大学选课系统后端服务，支持课程管理、学生选课退课、容量限制、先修课程检查、时间冲突检测",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "学生选课系统 API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/api/students", response_model=StudentSchema, status_code=status.HTTP_201_CREATED)
def create_student(student_data: StudentCreate, db: Session = Depends(get_db)):
    existing = db.query(Student).filter(Student.student_id == student_data.student_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"学生 {student_data.student_id} 已存在"
        )
    
    student = Student(
        student_id=student_data.student_id,
        name=student_data.name,
        grade=student_data.grade,
        credit_limit=student_data.credit_limit,
        earned_credits=student_data.earned_credits
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@app.get("/api/students/{student_id}", response_model=StudentSchema)
def get_student(student_id: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"学生 {student_id} 不存在"
        )
    return student


@app.put("/api/students/{student_id}", response_model=StudentSchema)
def update_student(student_id: str, update_data: StudentUpdate, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"学生 {student_id} 不存在"
        )
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if value is not None:
            setattr(student, key, value)
    
    db.commit()
    db.refresh(student)
    return student


@app.post("/api/courses", response_model=CourseSchema, status_code=status.HTTP_201_CREATED)
def create_course(course_data: CourseCreate, db: Session = Depends(get_db)):
    course_service = CourseService(db)
    if course_service.check_course_exists(course_data.course_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"课程 {course_data.course_id} 已存在"
        )
    
    try:
        course = course_service.create_course(course_data)
        course.remaining_slots = course.capacity - course.enrolled_count
        return course
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get("/api/courses", response_model=List[CourseSchema])
def list_courses(
    department: Optional[str] = Query(None, description="按学院筛选"),
    credits: Optional[int] = Query(None, description="按学分筛选"),
    day_of_week: Optional[str] = Query(None, description="按星期几筛选"),
    period: Optional[int] = Query(None, description="按节次筛选"),
    db: Session = Depends(get_db)
):
    course_service = CourseService(db)
    courses = course_service.get_all_courses(department, credits, day_of_week, period)
    for course in courses:
        course.remaining_slots = course.capacity - course.enrolled_count
    return courses


@app.get("/api/courses/{course_id}", response_model=CourseSchema)
def get_course(course_id: str, db: Session = Depends(get_db)):
    course_service = CourseService(db)
    course = course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"课程 {course_id} 不存在"
        )
    course.remaining_slots = course.capacity - course.enrolled_count
    return course


@app.put("/api/courses/{course_id}", response_model=CourseSchema)
def update_course(course_id: str, update_data: CourseUpdate, db: Session = Depends(get_db)):
    course_service = CourseService(db)
    
    if not course_service.check_course_exists(course_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"课程 {course_id} 不存在"
        )
    
    try:
        course = course_service.update_course(course_id, update_data)
        if course:
            course.remaining_slots = course.capacity - course.enrolled_count
        return course
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.delete("/api/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: str, db: Session = Depends(get_db)):
    course_service = CourseService(db)
    
    if not course_service.check_course_exists(course_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"课程 {course_id} 不存在"
        )
    
    try:
        success = course_service.delete_course(course_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除失败"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.post("/api/enrollments", response_model=EnrollmentSchema, status_code=status.HTTP_201_CREATED)
def enroll_course(enrollment_data: EnrollmentCreate, db: Session = Depends(get_db)):
    enrollment_service = EnrollmentService(db)
    
    try:
        enrollment = enrollment_service.enroll(
            enrollment_data.student_id,
            enrollment_data.course_id
        )
        return enrollment
    except EnrollmentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "error_code": e.error_code}
        )


@app.delete("/api/enrollments/{course_id}", response_model=EnrollmentSchema)
def drop_course(course_id: str, student_id: str = Query(..., description="学生ID"), db: Session = Depends(get_db)):
    enrollment_service = EnrollmentService(db)
    
    try:
        enrollment = enrollment_service.drop(student_id, course_id)
        return enrollment
    except EnrollmentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "error_code": e.error_code}
        )


@app.get("/api/students/{student_id}/enrollments", response_model=List[EnrollmentSchema])
def get_student_enrollments(
    student_id: str,
    status: Optional[str] = Query(None, description="按状态筛选: enrolled/dropped/completed"),
    db: Session = Depends(get_db)
):
    enrollment_service = EnrollmentService(db)
    
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"学生 {student_id} 不存在"
        )
    
    return enrollment_service.get_student_enrollments(student_id, status)


@app.put("/api/enrollments/{student_id}/{course_id}/grade", response_model=EnrollmentSchema)
def update_grade(
    student_id: str,
    course_id: str,
    grade_data: GradeUpdate,
    db: Session = Depends(get_db)
):
    grade_service = GradeService(db)
    
    try:
        enrollment = grade_service.update_grade(
            student_id,
            course_id,
            grade_data.grade,
            grade_data.changed_by,
            grade_data.reason
        )
        return enrollment
    except GradeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "error_code": e.error_code}
        )


@app.get("/api/students/{student_id}/grades")
def get_student_grades(
    student_id: str,
    include_dropped: bool = Query(False, description="是否包含已退课的课程"),
    db: Session = Depends(get_db)
):
    grade_service = GradeService(db)
    
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"学生 {student_id} 不存在"
        )
    
    grades = grade_service.get_student_grades(student_id, include_dropped)
    gpa = grade_service.calculate_gpa(student_id)
    
    return {
        "student_id": student_id,
        "student_name": student.name,
        "gpa": gpa,
        "grades": [
            {
                "course_id": g.course_id,
                "course_name": g.course.name if g.course else None,
                "credits": g.course.credits if g.course else None,
                "grade": g.grade,
                "status": g.status.value,
                "enrolled_at": g.enrolled_at
            }
            for g in grades
        ]
    }


@app.get("/api/stats/courses", response_model=List[CourseStats])
def get_course_stats(db: Session = Depends(get_db)):
    stats_service = StatsService(db)
    return stats_service.get_course_stats()


@app.get("/api/stats/students/{student_id}", response_model=StudentStats)
def get_student_stats(student_id: str, db: Session = Depends(get_db)):
    stats_service = StatsService(db)
    stats = stats_service.get_student_stats(student_id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"学生 {student_id} 不存在"
        )
    return stats


@app.get("/api/stats/popular", response_model=List[PopularCourse])
def get_popular_courses(top_n: int = Query(10, ge=1, le=50, description="返回前N个热门课程"), db: Session = Depends(get_db)):
    stats_service = StatsService(db)
    return stats_service.get_popular_courses(top_n)


@app.get("/api/stats/drop-rates", response_model=List[DropStats])
def get_drop_stats(db: Session = Depends(get_db)):
    stats_service = StatsService(db)
    return stats_service.get_drop_stats()
