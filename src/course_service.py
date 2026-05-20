from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from src.models import Course, Schedule, DayOfWeek
from src.schemas import CourseCreate, CourseUpdate


class CourseService:
    def __init__(self, db: Session):
        self.db = db

    def create_course(self, course_data: CourseCreate) -> Course:
        course = Course(
            course_id=course_data.course_id,
            name=course_data.name,
            credits=course_data.credits,
            capacity=course_data.capacity,
            enrolled_count=0,
            department=course_data.department,
            description=course_data.description,
            version=0
        )

        if course_data.prerequisite_ids:
            prerequisites = self.db.query(Course).filter(
                Course.course_id.in_(course_data.prerequisite_ids)
            ).all()
            course.prerequisites = prerequisites

        if course_data.schedules:
            for schedule_data in course_data.schedules:
                schedule = Schedule(
                    day_of_week=DayOfWeek(schedule_data.day_of_week.value),
                    period_start=schedule_data.period_start,
                    period_end=schedule_data.period_end,
                    classroom=schedule_data.classroom
                )
                course.schedules.append(schedule)

        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return self.get_course_by_id(course.course_id)

    def get_course_by_id(self, course_id: str) -> Optional[Course]:
        course = self.db.query(Course).options(
            joinedload(Course.schedules),
            joinedload(Course.prerequisites)
        ).filter(Course.course_id == course_id).first()
        return course

    def get_all_courses(
        self,
        department: Optional[str] = None,
        credits: Optional[int] = None,
        day_of_week: Optional[str] = None,
        period: Optional[int] = None
    ) -> List[Course]:
        query = self.db.query(Course).options(
            joinedload(Course.schedules),
            joinedload(Course.prerequisites)
        )

        if department:
            query = query.filter(Course.department == department)
        if credits:
            query = query.filter(Course.credits == credits)

        courses = query.all()

        if day_of_week or period:
            filtered_courses = []
            for course in courses:
                match = True
                if day_of_week and not any(
                    s.day_of_week.value == day_of_week for s in course.schedules
                ):
                    match = False
                if period and not any(
                    s.period_start <= period <= s.period_end for s in course.schedules
                ):
                    match = False
                if match:
                    filtered_courses.append(course)
            return filtered_courses

        return courses

    def update_course(self, course_id: str, update_data: CourseUpdate) -> Optional[Course]:
        course = self.get_course_by_id(course_id)
        if not course:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)

        if 'prerequisite_ids' in update_dict:
            if update_dict['prerequisite_ids'] is not None:
                if course_id in update_dict['prerequisite_ids']:
                    raise ValueError("课程不能以自身为先修课程")
                prerequisites = self.db.query(Course).filter(
                    Course.course_id.in_(update_dict['prerequisite_ids'])
                ).all()
                course.prerequisites = prerequisites
            del update_dict['prerequisite_ids']

        if 'schedules' in update_dict:
            if update_dict['schedules'] is not None:
                for schedule in course.schedules:
                    self.db.delete(schedule)
                course.schedules = []
                for schedule_data in update_dict['schedules']:
                    schedule = Schedule(
                        day_of_week=DayOfWeek(schedule_data.day_of_week.value),
                        period_start=schedule_data.period_start,
                        period_end=schedule_data.period_end,
                        classroom=schedule_data.classroom
                    )
                    course.schedules.append(schedule)
            del update_dict['schedules']

        if update_dict:
            for key, value in update_dict.items():
                if hasattr(course, key) and value is not None:
                    setattr(course, key, value)

        self.db.commit()
        self.db.refresh(course)
        return self.get_course_by_id(course_id)

    def delete_course(self, course_id: str) -> bool:
        course = self.get_course_by_id(course_id)
        if not course:
            return False

        if course.enrolled_count > 0:
            raise ValueError("课程已有学生选修，无法删除")

        dependent_courses = self.db.query(Course).filter(
            Course.prerequisites.any(course_id=course_id)
        ).all()
        for dep_course in dependent_courses:
            dep_course.prerequisites.remove(course)

        for schedule in course.schedules:
            self.db.delete(schedule)

        self.db.delete(course)
        self.db.commit()
        return True

    def get_remaining_slots(self, course_id: str) -> Optional[int]:
        course = self.get_course_by_id(course_id)
        if not course:
            return None
        return course.capacity - course.enrolled_count

    def check_course_exists(self, course_id: str) -> bool:
        return self.db.query(Course).filter(Course.course_id == course_id).first() is not None
