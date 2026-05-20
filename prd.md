# Course Registration — 学生选课系统

## 项目概述

大学选课系统后端服务，支持课程管理、学生选课退课、容量限制、先修课程检查、时间冲突检测。每学期初开放选课，高并发场景下保证数据一致性。

## 功能需求

### 1. 数据模型（models.py）

- **Student**：学号、姓名、年级、学分上限、已修学分
- **Course**：课程号、课程名、学分、容量、已选人数、先修课程列表
- **Schedule**：上课时间（星期几、第几节、教室）
- **Enrollment**：选课记录（学生、课程、状态：已选/已退/已完成、成绩）
- **Semester**：学期信息（开始日期、结束日期、选课开始时间、选课结束时间）

### 2. 课程管理（course_service.py）

- 添加/修改/删除课程
- 设置课程容量和先修课程
- 查询课程列表（按学院、时间、学分筛选）
- 课程详情（含已选人数、剩余名额）

### 3. 选课逻辑（enrollment_service.py）

- 选课前置检查：
  - 学分上限检查（已选学分 + 新课程学分 ≤ 上限）
  - 先修课程检查（必须已完成先修课程且成绩 ≥ 60）
  - 时间冲突检查（新课程与已选课程时间不能重叠）
  - 容量检查（已选人数 < 容量）
  - 重复选课检查
- 选课操作（原子性：更新选课记录 + 课程已选人数 +1）
- 退课操作（原子性：更新选课记录 + 课程已选人数 -1）
- 退课截止时间检查

### 4. 并发控制（concurrency.py）

- 乐观锁：课程表增加 version 字段，选课时检查版本号
- 重试机制：冲突时自动重试（最多 3 次）
- 数据库事务：选课操作必须在事务内完成

### 5. 成绩管理（grade_service.py）

- 录入成绩（0-100）
- 成绩录入后更新学生已修学分
- 成绩录入后状态变为"已完成"
- 成绩修改记录（审计日志）

### 6. 统计查询（stats_service.py）

- 课程选课统计（各课程选课人数、满员率）
- 学生选课统计（已选学分、课程数）
- 热门课程排行
- 退课率统计

### 7. REST API（app.py）

```
# 课程
POST /api/courses
GET  /api/courses?department=&credits=&time=
GET  /api/courses/{course_id}
PUT  /api/courses/{course_id}
DELETE /api/courses/{course_id}

# 选课
POST /api/enrollments          # 选课
DELETE /api/enrollments/{course_id}  # 退课
GET  /api/students/{student_id}/enrollments  # 查看已选课程

# 成绩
PUT  /api/enrollments/{student_id}/{course_id}/grade
GET  /api/students/{student_id}/grades

# 统计
GET  /api/stats/courses
GET  /api/stats/students/{student_id}
GET  /api/stats/popular
```

## 技术要求

- Python 3.9+
- FastAPI
- SQLAlchemy + SQLite
- Pydantic（数据校验）
- APScheduler（定时任务，如选课时间窗口控制）

## 项目结构

```
course-registration/
├── src/
│   ├── __init__.py
│   ├── app.py               # FastAPI 入口
│   ├── models.py            # SQLAlchemy 模型
│   ├── schemas.py           # Pydantic 数据校验
│   ├── database.py          # 数据库配置
│   ├── course_service.py    # 课程管理
│   ├── enrollment_service.py # 选课退课逻辑
│   ├── grade_service.py     # 成绩管理
│   ├── stats_service.py     # 统计查询
│   ├── concurrency.py       # 并发控制工具
│   └── utils.py             # 工具函数
├── data/
│   └── seed.py              # 示例数据生成
├── tests/
│   ├── test_enrollment.py
│   ├── test_prerequisites.py
│   └── test_concurrency.py
├── requirements.txt
└── README.md
```

## 验收标准

1. 能正确创建课程、设置容量和先修课程
2. 选课时正确检查先修课程（未修过或成绩不及格不能选）
3. 选课时正确检查时间冲突
4. 选课时正确检查学分上限
5. 并发选课不超卖（10人抢最后1个名额，只有1人成功）
6. 退课后名额正确释放
7. 成绩录入后正确更新已修学分
8. 统计数据准确
9. API 文档自动生成
10. 错误处理友好（课程不存在、已选满、有先修未完成等）

## 注意事项

- 并发选课是核心难点，必须保证名额不超卖
- 先修课程检查需要递归（A→B→C，选C需要先完成A和B）
- 时间冲突检测需要考虑课程可能有多节课（如周一三五上午）
- 选课时间窗口：选课开始前和结束后不能选课
