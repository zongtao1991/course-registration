import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session
from sqlalchemy import func, case
from src.database import engine, SessionLocal, Base, init_db
from src.models import (
    Student, Course, Schedule, Enrollment, Semester,
    DayOfWeek, EnrollmentStatus
)


def create_semester(db: Session):
    now = datetime.utcnow()
    today = now.date()
    semester = Semester(
        name="2024-2025学年第二学期",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=120),
        enrollment_start=now - timedelta(days=7),
        enrollment_end=now + timedelta(days=30),
        drop_deadline=today + timedelta(days=60),
        is_active=1
    )
    db.add(semester)
    db.commit()
    print(f"已创建学期: {semester.name}")
    return semester


def create_students(db: Session) -> Dict[str, Student]:
    students_base_data = [
        {"student_id": "2021001", "name": "张三", "grade": 3, "credit_limit": 25},
        {"student_id": "2021002", "name": "李四", "grade": 3, "credit_limit": 25},
        {"student_id": "2021003", "name": "王五", "grade": 3, "credit_limit": 25},
        {"student_id": "2021004", "name": "赵六", "grade": 3, "credit_limit": 25},
        {"student_id": "2021005", "name": "钱七", "grade": 3, "credit_limit": 25},
        {"student_id": "2021006", "name": "孙八", "grade": 3, "credit_limit": 25},
        {"student_id": "2021007", "name": "周九", "grade": 3, "credit_limit": 25},
        {"student_id": "2021008", "name": "吴十", "grade": 3, "credit_limit": 25},
        {"student_id": "2021009", "name": "郑十一", "grade": 3, "credit_limit": 25},
        {"student_id": "2021010", "name": "王十二", "grade": 3, "credit_limit": 25},
        {"student_id": "2022001", "name": "陈一", "grade": 2, "credit_limit": 25},
        {"student_id": "2022002", "name": "褚二", "grade": 2, "credit_limit": 25},
        {"student_id": "2023001", "name": "卫三", "grade": 1, "credit_limit": 25},
        {"student_id": "2023002", "name": "蒋四", "grade": 1, "credit_limit": 25},
    ]

    created_students = {}
    for data in students_base_data:
        existing = db.query(Student).filter(Student.student_id == data["student_id"]).first()
        if not existing:
            student = Student(
                **data,
                earned_credits=0
            )
            db.add(student)
            print(f"已创建学生: {student.student_id} - {student.name}")
            created_students[student.student_id] = student
        else:
            created_students[existing.student_id] = existing

    db.commit()
    return created_students


def create_courses(db: Session) -> Dict[str, Course]:
    courses_data = [
        {
            "course_id": "CS101",
            "name": "计算机科学导论",
            "credits": 2,
            "capacity": 100,
            "department": "计算机科学与技术学院",
            "description": "计算机科学基础入门课程",
            "schedules": [
                {"day_of_week": DayOfWeek.MONDAY, "period_start": 1, "period_end": 2, "classroom": "A101"},
                {"day_of_week": DayOfWeek.WEDNESDAY, "period_start": 1, "period_end": 2, "classroom": "A101"},
            ]
        },
        {
            "course_id": "CS102",
            "name": "高等数学A",
            "credits": 5,
            "capacity": 120,
            "department": "理学院",
            "description": "微积分、线性代数等数学基础",
            "schedules": [
                {"day_of_week": DayOfWeek.MONDAY, "period_start": 3, "period_end": 4, "classroom": "B201"},
                {"day_of_week": DayOfWeek.TUESDAY, "period_start": 5, "period_end": 6, "classroom": "B201"},
                {"day_of_week": DayOfWeek.THURSDAY, "period_start": 3, "period_end": 4, "classroom": "B201"},
            ]
        },
        {
            "course_id": "CS201",
            "name": "数据结构与算法",
            "credits": 4,
            "capacity": 60,
            "department": "计算机科学与技术学院",
            "description": "数组、链表、树、图等数据结构及经典算法",
            "schedules": [
                {"day_of_week": DayOfWeek.TUESDAY, "period_start": 1, "period_end": 2, "classroom": "A301"},
                {"day_of_week": DayOfWeek.THURSDAY, "period_start": 1, "period_end": 2, "classroom": "A301"},
            ]
        },
        {
            "course_id": "CS202",
            "name": "面向对象程序设计",
            "credits": 3,
            "capacity": 80,
            "department": "计算机科学与技术学院",
            "description": "Java/C++ 面向对象编程",
            "schedules": [
                {"day_of_week": DayOfWeek.WEDNESDAY, "period_start": 5, "period_end": 6, "classroom": "A302"},
                {"day_of_week": DayOfWeek.FRIDAY, "period_start": 3, "period_end": 4, "classroom": "A302"},
            ]
        },
        {
            "course_id": "CS301",
            "name": "操作系统",
            "credits": 4,
            "capacity": 50,
            "department": "计算机科学与技术学院",
            "description": "进程管理、内存管理、文件系统等",
            "schedules": [
                {"day_of_week": DayOfWeek.MONDAY, "period_start": 5, "period_end": 6, "classroom": "A401"},
                {"day_of_week": DayOfWeek.WEDNESDAY, "period_start": 3, "period_end": 4, "classroom": "A401"},
            ]
        },
        {
            "course_id": "CS302",
            "name": "计算机网络",
            "credits": 3,
            "capacity": 50,
            "department": "计算机科学与技术学院",
            "description": "TCP/IP 协议栈、网络编程等",
            "schedules": [
                {"day_of_week": DayOfWeek.TUESDAY, "period_start": 7, "period_end": 8, "classroom": "A402"},
                {"day_of_week": DayOfWeek.THURSDAY, "period_start": 5, "period_end": 6, "classroom": "A402"},
            ]
        },
        {
            "course_id": "CS401",
            "name": "人工智能导论",
            "credits": 3,
            "capacity": 40,
            "department": "计算机科学与技术学院",
            "description": "机器学习、深度学习基础",
            "schedules": [
                {"day_of_week": DayOfWeek.FRIDAY, "period_start": 1, "period_end": 2, "classroom": "A501"},
            ]
        },
        {
            "course_id": "HOT001",
            "name": "热门课程-限量版",
            "credits": 2,
            "capacity": 1,
            "department": "热门学院",
            "description": "用于并发测试，只有1个名额",
            "schedules": [
                {"day_of_week": DayOfWeek.FRIDAY, "period_start": 7, "period_end": 8, "classroom": "H101"},
            ]
        },
    ]

    created_courses = {}
    for data in courses_data:
        existing = db.query(Course).filter(Course.course_id == data["course_id"]).first()
        if not existing:
            schedules_data = data.pop("schedules", [])
            course = Course(
                **data,
                enrolled_count=0,
                version=0
            )
            for s_data in schedules_data:
                schedule = Schedule(**s_data)
                course.schedules.append(schedule)
            db.add(course)
            print(f"已创建课程: {course.course_id} - {course.name}")
            created_courses[course.course_id] = course
        else:
            created_courses[existing.course_id] = existing

    db.commit()

    if "CS201" in created_courses and "CS101" in created_courses:
        cs201 = created_courses["CS201"]
        cs101 = created_courses["CS101"]
        if cs101 not in cs201.prerequisites:
            cs201.prerequisites.append(cs101)
            print(f"已设置先修课程: CS201 -> CS101")

    if "CS301" in created_courses and "CS201" in created_courses:
        cs301 = created_courses["CS301"]
        cs201 = created_courses["CS201"]
        if cs201 not in cs301.prerequisites:
            cs301.prerequisites.append(cs201)
            print(f"已设置先修课程: CS301 -> CS201")

    if "CS401" in created_courses and "CS201" in created_courses:
        cs401 = created_courses["CS401"]
        cs201 = created_courses["CS201"]
        if cs201 not in cs401.prerequisites:
            cs401.prerequisites.append(cs201)
            print(f"已设置先修课程: CS401 -> CS201")

    db.commit()
    return created_courses


def create_completed_enrollments(
    db: Session,
    courses: Dict[str, Course]
) -> List[Enrollment]:
    completed_data = [
        {"student_id": "2021001", "course_id": "CS101", "grade": 85.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021002", "course_id": "CS101", "grade": 78.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021003", "course_id": "CS101", "grade": 92.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021004", "course_id": "CS101", "grade": 55.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021005", "course_id": "CS101", "grade": 88.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021006", "course_id": "CS101", "grade": 72.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021007", "course_id": "CS101", "grade": 81.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021008", "course_id": "CS101", "grade": 65.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021009", "course_id": "CS101", "grade": 90.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021010", "course_id": "CS101", "grade": 95.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2022001", "course_id": "CS101", "grade": 82.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2022002", "course_id": "CS101", "grade": 75.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021001", "course_id": "CS102", "grade": 70.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021003", "course_id": "CS102", "grade": 85.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021001", "course_id": "CS201", "grade": 88.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021003", "course_id": "CS201", "grade": 91.0, "status": EnrollmentStatus.COMPLETED},
        {"student_id": "2021005", "course_id": "CS201", "grade": 76.0, "status": EnrollmentStatus.COMPLETED},
    ]

    created_enrollments = []
    for data in completed_data:
        existing = db.query(Enrollment).filter(
            Enrollment.student_id == data["student_id"],
            Enrollment.course_id == data["course_id"]
        ).first()
        if not existing:
            enrollment = Enrollment(
                student_id=data["student_id"],
                course_id=data["course_id"],
                grade=data["grade"],
                status=data["status"],
                completed_at=datetime.utcnow()
            )
            db.add(enrollment)
            created_enrollments.append(enrollment)
            print(f"已创建完成记录: {data['student_id']} -> {data['course_id']}, 成绩: {data['grade']}")

    db.commit()
    return created_enrollments


def update_earned_credits_consistently(db: Session):
    print("\n[一致性维护] 更新学生已修学分...")
    
    credit_calc = (
        db.query(
            Enrollment.student_id,
            func.sum(
                case(
                    (Enrollment.grade >= 60, Course.credits),
                    else_=0
                )
            ).label('earned_credits')
        )
        .join(Course, Enrollment.course_id == Course.course_id)
        .filter(Enrollment.status == EnrollmentStatus.COMPLETED)
        .group_by(Enrollment.student_id)
    )
    
    for row in credit_calc:
        student = db.query(Student).filter(Student.student_id == row.student_id).first()
        if student:
            old_credits = student.earned_credits
            new_credits = int(row.earned_credits or 0)
            if old_credits != new_credits:
                student.earned_credits = new_credits
                print(f"  更新学生 {student.student_id}: {old_credits} -> {new_credits} 学分")
    
    db.commit()


def update_enrolled_count_consistently(db: Session):
    print("\n[一致性维护] 更新课程已选人数...")
    
    enrolled_count_calc = (
        db.query(
            Enrollment.course_id,
            func.count(Enrollment.id).label('enrolled_count')
        )
        .filter(Enrollment.status == EnrollmentStatus.ENROLLED)
        .group_by(Enrollment.course_id)
    )
    
    enrolled_map = {row.course_id: row.enrolled_count for row in enrolled_count_calc}
    
    all_courses = db.query(Course).all()
    for course in all_courses:
        expected_count = enrolled_map.get(course.course_id, 0)
        if course.enrolled_count != expected_count:
            old_count = course.enrolled_count
            course.enrolled_count = expected_count
            print(f"  更新课程 {course.course_id}: enrolled_count {old_count} -> {expected_count}")
    
    db.commit()


def verify_data_consistency(db: Session) -> bool:
    print("\n[一致性检查] 验证数据一致性...")
    all_ok = True
    
    print("\n1. 检查学生 earned_credits:")
    credit_check = (
        db.query(
            Enrollment.student_id,
            func.sum(
                case(
                    (Enrollment.grade >= 60, Course.credits),
                    else_=0
                )
            ).label('calculated_credits')
        )
        .join(Course, Enrollment.course_id == Course.course_id)
        .filter(Enrollment.status == EnrollmentStatus.COMPLETED)
        .group_by(Enrollment.student_id)
    )
    
    for row in credit_check:
        student = db.query(Student).filter(Student.student_id == row.student_id).first()
        if student:
            calculated = int(row.calculated_credits or 0)
            if student.earned_credits != calculated:
                print(f"  ❌ 不一致: 学生 {student.student_id} - earned_credits={student.earned_credits}, 实际={calculated}")
                all_ok = False
            else:
                print(f"  ✅ 一致: 学生 {student.student_id} - {student.earned_credits} 学分")
    
    print("\n2. 检查课程 enrolled_count:")
    enrolled_check = (
        db.query(
            Enrollment.course_id,
            func.count(Enrollment.id).label('actual_enrolled')
        )
        .filter(Enrollment.status == EnrollmentStatus.ENROLLED)
        .group_by(Enrollment.course_id)
    )
    
    enrolled_map = {row.course_id: row.actual_enrolled for row in enrolled_check}
    
    all_courses = db.query(Course).all()
    for course in all_courses:
        expected = enrolled_map.get(course.course_id, 0)
        if course.enrolled_count != expected:
            print(f"  ❌ 不一致: 课程 {course.course_id} - enrolled_count={course.enrolled_count}, 实际={expected}")
            all_ok = False
        else:
            print(f"  ✅ 一致: 课程 {course.course_id} - enrolled_count={course.enrolled_count}")
    
    if all_ok:
        print("\n✅ 所有数据一致性检查通过！")
    else:
        print("\n❌ 存在数据不一致问题！")
    
    return all_ok


def main():
    print("=" * 70)
    print("开始初始化学生选课系统示例数据（含一致性维护）")
    print("=" * 70)

    print("\n[1/8] 初始化数据库...")
    init_db()

    db = SessionLocal()
    try:
        print("\n[2/8] 创建学期信息...")
        create_semester(db)

        print("\n[3/8] 创建学生数据...")
        students = create_students(db)

        print("\n[4/8] 创建课程数据（含先修课程和上课时间）...")
        courses = create_courses(db)

        print("\n[5/8] 创建已完成的选课记录...")
        enrollments = create_completed_enrollments(db, courses)

        print("\n[6/8] 一致性维护 - 同步更新学生已修学分...")
        update_earned_credits_consistently(db)

        print("\n[7/8] 一致性维护 - 同步更新课程已选人数...")
        update_enrolled_count_consistently(db)

        print("\n[8/8] 验证数据一致性...")
        verify_data_consistency(db)

        print("\n" + "=" * 70)
        print("示例数据初始化完成！")
        print("=" * 70)
        print("\n可用学生账号示例:")
        print("  - 2021001 张三 (三年级，已修学分通过选课记录动态计算)")
        print("  - 2021003 王五 (三年级，完成CS101、CS102、CS201)")
        print("  - 2022001 陈一 (二年级)")
        print("  - 2023001 卫三 (一年级，新生)")
        print("\n课程示例:")
        print("  - CS101 计算机科学导论 (先修: 无)")
        print("  - CS201 数据结构与算法 (先修: CS101)")
        print("  - CS301 操作系统 (先修: CS201)")
        print("  - HOT001 热门课程-限量版 (容量: 1，用于并发测试)")
        print("\nAPI 文档地址: http://localhost:8000/docs")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    main()
