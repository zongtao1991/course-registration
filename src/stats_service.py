from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, case, coalesce
from src.models import Student, Course, Enrollment, EnrollmentStatus
from src.schemas import CourseStats, StudentStats, PopularCourse, DropStats
from src.grade_service import GradeService


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    def _get_enrollment_stats_by_course(self) -> Dict[str, Dict]:
        stats_query = (
            self.db.query(
                Course.course_id.label('course_id'),
                Course.name.label('course_name'),
                Course.capacity.label('capacity'),
                Course.enrolled_count.label('table_enrolled_count'),
                Course.credits.label('credits'),
                coalesce(
                    func.count(
                        case(
                            (Enrollment.status == EnrollmentStatus.ENROLLED, 1),
                            else_=None
                        )
                    ),
                    0
                ).label('active_enrolled_count'),
                coalesce(
                    func.count(
                        case(
                            (Enrollment.status == EnrollmentStatus.COMPLETED, 1),
                            else_=None
                        )
                    ),
                    0
                ).label('completed_count'),
                coalesce(
                    func.count(
                        case(
                            (Enrollment.status == EnrollmentStatus.DROPPED, 1),
                            else_=None
                        )
                    ),
                    0
                ).label('drop_count'),
                coalesce(
                    func.count(Enrollment.id),
                    0
                ).label('total_count')
            )
            .select_from(Course)
            .outerjoin(Enrollment, Course.course_id == Enrollment.course_id)
            .group_by(Course.course_id)
        )
        
        result = {}
        for row in stats_query:
            result[row.course_id] = {
                'course_id': row.course_id,
                'course_name': row.course_name,
                'capacity': row.capacity,
                'table_enrolled_count': row.table_enrolled_count,
                'credits': row.credits,
                'active_enrolled_count': int(row.active_enrolled_count or 0),
                'completed_count': int(row.completed_count or 0),
                'drop_count': int(row.drop_count or 0),
                'total_count': int(row.total_count or 0)
            }
        
        return result

    def _get_all_courses_with_info(self) -> List[Tuple]:
        enrollment_stats = self._get_enrollment_stats_by_course()
        
        courses = (
            self.db.query(Course)
            .options(joinedload(Course.schedules))
            .all()
        )
        
        result = []
        for course in courses:
            stats = enrollment_stats.get(course.course_id, {
                'active_enrolled_count': 0,
                'completed_count': 0,
                'drop_count': 0,
                'total_count': 0
            })
            result.append((course, stats))
        
        return result

    def get_course_stats(self) -> List[CourseStats]:
        enrollment_stats = self._get_enrollment_stats_by_course()
        
        stats_list = []
        for course_id, stats in enrollment_stats.items():
            enrolled_count = stats['table_enrolled_count']
            fill_rate = (enrolled_count / stats['capacity'] * 100) if stats['capacity'] > 0 else 0
            stats_obj = CourseStats(
                course_id=stats['course_id'],
                course_name=stats['course_name'],
                capacity=stats['capacity'],
                enrolled_count=enrolled_count,
                fill_rate=round(fill_rate, 2),
                credits=stats['credits']
            )
            stats_list.append(stats_obj)

        return sorted(stats_list, key=lambda x: x.fill_rate, reverse=True)

    def get_student_stats(self, student_id: str) -> Optional[StudentStats]:
        student = self.db.query(Student).filter(Student.student_id == student_id).first()
        if not student:
            return None

        enrollment_query = (
            self.db.query(
                Enrollment.status,
                Course.credits
            )
            .join(Course, Enrollment.course_id == Course.course_id)
            .filter(Enrollment.student_id == student_id)
        )
        
        enrolled_count = 0
        enrolled_credits = 0
        completed_count = 0
        
        for row in enrollment_query:
            status, credits = row
            
            if status == EnrollmentStatus.ENROLLED:
                enrolled_count += 1
                enrolled_credits += credits or 0
            
            if status == EnrollmentStatus.COMPLETED:
                completed_count += 1

        grade_service = GradeService(self.db)
        gpa = grade_service.calculate_gpa(student_id)

        return StudentStats(
            student_id=student.student_id,
            student_name=student.name,
            enrolled_courses_count=enrolled_count,
            enrolled_credits=enrolled_credits,
            earned_credits=student.earned_credits,
            completed_courses_count=completed_count,
            gpa=gpa
        )

    def get_popular_courses(self, top_n: int = 10) -> List[PopularCourse]:
        enrollment_stats = self._get_enrollment_stats_by_course()
        
        popular_list = []
        for course_id, stats in enrollment_stats.items():
            enrolled_count = stats['table_enrolled_count']
            fill_rate = (enrolled_count / stats['capacity'] * 100) if stats['capacity'] > 0 else 0
            total_enrollments = stats['total_count']
            drop_count = stats['drop_count']
            drop_rate = (drop_count / total_enrollments * 100) if total_enrollments > 0 else 0
            
            popular = PopularCourse(
                course_id=stats['course_id'],
                course_name=stats['course_name'],
                capacity=stats['capacity'],
                enrolled_count=enrolled_count,
                fill_rate=round(fill_rate, 2),
                credits=stats['credits'],
                drop_count=drop_count,
                drop_rate=round(drop_rate, 2)
            )
            popular_list.append(popular)

        return sorted(popular_list, key=lambda x: x.fill_rate, reverse=True)[:top_n]

    def get_drop_stats(self) -> List[DropStats]:
        enrollment_stats = self._get_enrollment_stats_by_course()
        
        stats_list = []
        for course_id, stats in enrollment_stats.items():
            total_enrollments = stats['total_count']
            
            if total_enrollments == 0:
                continue
            
            drop_count = stats['drop_count']
            drop_rate = (drop_count / total_enrollments * 100)
            
            stats_obj = DropStats(
                course_id=stats['course_id'],
                course_name=stats['course_name'],
                total_enrollments=total_enrollments,
                drop_count=drop_count,
                drop_rate=round(drop_rate, 2)
            )
            stats_list.append(stats_obj)

        return sorted(stats_list, key=lambda x: x.drop_rate, reverse=True)

    def get_department_stats(self, department: str) -> dict:
        enrollment_stats = self._get_enrollment_stats_by_course()
        
        dept_courses = (
            self.db.query(Course)
            .filter(Course.department == department)
            .all()
        )
        
        if not dept_courses:
            return {
                "department": department,
                "total_courses": 0,
                "total_capacity": 0,
                "total_enrolled": 0,
                "full_courses_count": 0,
                "partial_courses_count": 0,
                "empty_courses_count": 0,
                "average_fill_rate": 0.0
            }
        
        total_courses = len(dept_courses)
        total_capacity = 0
        total_enrolled = 0
        full_courses = 0
        partial_courses = 0
        empty_courses = 0
        
        for course in dept_courses:
            stats = enrollment_stats.get(course.course_id, {})
            enrolled = stats.get('table_enrolled_count', course.enrolled_count)
            capacity = course.capacity
            
            total_capacity += capacity
            total_enrolled += enrolled
            
            if enrolled >= capacity:
                full_courses += 1
            elif 0 < enrolled < capacity:
                partial_courses += 1
            else:
                empty_courses += 1
        
        avg_fill_rate = (total_enrolled / total_capacity * 100) if total_capacity > 0 else 0
        
        return {
            "department": department,
            "total_courses": total_courses,
            "total_capacity": total_capacity,
            "total_enrolled": total_enrolled,
            "full_courses_count": full_courses,
            "partial_courses_count": partial_courses,
            "empty_courses_count": empty_courses,
            "average_fill_rate": round(avg_fill_rate, 2)
        }
