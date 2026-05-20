import functools
import time
from typing import Callable, TypeVar, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import update, select
from src.models import Course


T = TypeVar('T')


class ConcurrencyError(Exception):
    pass


class OptimisticLockError(ConcurrencyError):
    def __init__(self, message: str = "乐观锁冲突，请重试"):
        self.message = message
        super().__init__(self.message)


class CapacityExceededError(ConcurrencyError):
    def __init__(self, message: str = "课程容量已满"):
        self.message = message
        super().__init__(self.message)


class EnrollmentWindowError(ConcurrencyError):
    def __init__(self, message: str = "不在选课时间窗口内"):
        self.message = message
        super().__init__(self.message)


class RetryConfig:
    def __init__(
        self,
        max_retries: int = 5,
        initial_delay: float = 0.05,
        max_delay: float = 0.5,
        backoff_factor: float = 1.5,
        retry_exceptions: tuple = (OptimisticLockError, OperationalError, IntegrityError)
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retry_exceptions = retry_exceptions


def with_retry(
    config: RetryConfig = None,
    on_retry: Callable[[int, Exception], None] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = config.initial_delay
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retry_exceptions as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        if on_retry:
                            on_retry(attempt + 1, e)
                        time.sleep(delay)
                        delay = min(delay * config.backoff_factor, config.max_delay)
                    else:
                        raise last_exception
            raise last_exception

        return wrapper
    return decorator


def check_optimistic_lock(db: Session, course: Course, expected_version: int) -> bool:
    if course.version != expected_version:
        return False
    return True


def increment_version(db: Session, course: Course) -> None:
    course.version += 1


def try_enroll_with_version(
    db: Session,
    course_id: str,
    expected_version: int,
) -> tuple[bool, int]:
    enroll_stmt = (
        update(Course)
        .where(
            Course.course_id == course_id,
            Course.version == expected_version,
            Course.enrolled_count < Course.capacity
        )
        .values(
            enrolled_count=Course.enrolled_count + 1,
            version=Course.version + 1
        )
    )
    
    result = db.execute(enroll_stmt)
    db.flush()
    
    return result.rowcount > 0, result.rowcount


def try_drop_with_version(
    db: Session,
    course_id: str,
    expected_version: int,
) -> tuple[bool, int]:
    drop_stmt = (
        update(Course)
        .where(
            Course.course_id == course_id,
            Course.version == expected_version,
            Course.enrolled_count > 0
        )
        .values(
            enrolled_count=Course.enrolled_count - 1,
            version=Course.version + 1
        )
    )
    
    result = db.execute(drop_stmt)
    db.flush()
    
    return result.rowcount > 0, result.rowcount


def enroll_with_optimistic_lock(
    db: Session,
    course_id: str,
    student_id: str,
    enroll_func: Callable[[Session, str, str], Any],
) -> Any:
    @with_retry()
    def _enroll():
        try:
            course = db.query(Course).filter(
                Course.course_id == course_id
            ).first()

            if not course:
                raise ValueError("课程不存在")

            if course.enrolled_count >= course.capacity:
                raise CapacityExceededError("课程容量已满")

            current_version = course.version

            result = enroll_func(db, student_id, course_id)

            success, rowcount = try_enroll_with_version(
                db, course_id, current_version
            )

            if not success:
                db.rollback()
                
                course_after = db.query(Course).filter(
                    Course.course_id == course_id
                ).first()
                
                if course_after:
                    if course_after.enrolled_count >= course_after.capacity:
                        raise CapacityExceededError("课程容量已满")
                    elif course_after.version != current_version:
                        raise OptimisticLockError(f"选课失败，版本号冲突 (expected: {current_version}, actual: {course_after.version})")
                
                raise OptimisticLockError("选课失败，乐观锁冲突")

            db.commit()
            return result

        except CapacityExceededError:
            db.rollback()
            raise
        except ValueError:
            db.rollback()
            raise
        except OptimisticLockError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise OptimisticLockError(f"选课失败: {str(e)}")

    return _enroll()


def drop_with_optimistic_lock(
    db: Session,
    course_id: str,
    student_id: str,
    drop_func: Callable[[Session, str, str], Any],
) -> Any:
    @with_retry()
    def _drop():
        try:
            course = db.query(Course).filter(
                Course.course_id == course_id
            ).first()

            if not course:
                raise ValueError("课程不存在")

            current_version = course.version

            result = drop_func(db, student_id, course_id)

            if course.enrolled_count > 0:
                success, rowcount = try_drop_with_version(
                    db, course_id, current_version
                )

                if not success:
                    db.rollback()
                    raise OptimisticLockError(f"退课失败，版本号冲突 (expected: {current_version})")

            db.commit()
            return result

        except ValueError:
            db.rollback()
            raise
        except OptimisticLockError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise OptimisticLockError(f"退课失败: {str(e)}")

    return _drop()
