import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField


# ── Django auth / session（managed=False）────────────────────────────────────

class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


# ── 業務資料表 ────────────────────────────────────────────────────────────────

class Member(models.Model):
    """會員主表。
    emails: text[]  → 電子郵件清單
    roles:  text[]  → 角色清單，例如 ['student', 'teacher', 'staff']
    各角色的詳細資料存在 teachers / students / staff 表，透過 member_id FK 反向關聯。
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.TextField(default='')
    emails = ArrayField(models.TextField(), default=list)
    phone = models.TextField(blank=True, null=True)
    roles = ArrayField(models.TextField(), default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    logged_at = models.DateTimeField(blank=True, null=True)
    deregistered_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'members'


class Teacher(models.Model):
    """老師 profile。member_id → members.id"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    member = models.ForeignKey(Member, models.DO_NOTHING, related_name='teachers')
    nick_name = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'teachers'


class Course(models.Model):
    """Google Classroom 課程。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    owner = models.TextField()
    name = models.TextField()
    status = models.TextField()
    course_group_email = models.TextField()
    alternate_link = models.TextField()
    student_invitation_id = models.TextField(blank=True, null=True)
    advisor_invitation_id = models.TextField(blank=True, null=True)
    orientation_assignment_id = models.TextField(blank=True, null=True)
    folder_id = models.UUIDField(blank=True, null=True)
    classroom_course_id = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'courses'


class TeacherSchedule(models.Model):
    """老師每週循環排班。
    day_of_week: smallint[]，例如 [1, 3, 5] 表示週一三五（1=週一 … 7=週日）
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    teacher = models.ForeignKey(Teacher, models.CASCADE, related_name='schedules')
    day_of_week = ArrayField(models.SmallIntegerField())
    start_time = models.TimeField()
    end_time = models.TimeField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'teacher_schedules'


class TeacherLeave(models.Model):
    """老師請假記錄。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    teacher = models.ForeignKey(Teacher, models.CASCADE, related_name='leaves')
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'teacher_leaves'


class TeacherProject(models.Model):
    """老師負責的專案關聯。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    teacher = models.ForeignKey(Teacher, models.DO_NOTHING, related_name='teacher_projects')
    project = models.ForeignKey('Project', models.DO_NOTHING, related_name='teacher_links')
    status = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'teacher_projects'


class Student(models.Model):
    """學生 profile。member_id → members.id"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    member = models.ForeignKey(Member, models.DO_NOTHING, related_name='students')
    brand = models.TextField()
    course_id = models.UUIDField(blank=True, null=True)
    orientation_id = models.UUIDField(blank=True, null=True)
    drive_id = models.UUIDField(blank=True, null=True)
    hasura_member_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'students'


class Staff(models.Model):
    """職員 profile。member_id → members.id"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    member = models.ForeignKey(Member, models.DO_NOTHING, related_name='staff_profiles')
    auth_permission = models.TextField(blank=True, null=True)
    password_hash = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'staff'


class BookingCalendar(models.Model):
    """Google Calendar 對應表（按品牌區分）。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    google_calendar_id = models.TextField()
    title = models.TextField()
    brand = models.TextField()
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'booking_calendars'


class Booking(models.Model):
    """預約。時間以 date + time 分開儲存。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    member_project = models.ForeignKey('MemberProject', models.DO_NOTHING,
                                       blank=True, null=True, related_name='bookings')
    calendar = models.ForeignKey(BookingCalendar, models.DO_NOTHING, related_name='bookings')
    teacher = models.ForeignKey(Teacher, models.DO_NOTHING, related_name='bookings')
    student = models.ForeignKey(Student, models.DO_NOTHING, related_name='bookings')
    booked_by_email = models.TextField()
    start_date = models.DateField()
    start_time = models.TimeField()
    end_date = models.DateField(blank=True, null=True)
    end_time = models.TimeField()
    google_event_id = models.TextField()
    meet_url = models.TextField()
    event_url = models.TextField()
    status = models.TextField(default='confirmed')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'bookings'


class ProjectCategory(models.Model):
    """專案分類。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.TextField()
    key = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_categories'


class Project(models.Model):
    """專案目錄（類型表）。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    key = models.SmallIntegerField()
    category = models.ForeignKey(ProjectCategory, models.DO_NOTHING, related_name='projects')
    topic = models.TextField(blank=True, null=True)
    level = models.TextField(blank=True, null=True)
    points = models.SmallIntegerField(blank=True, null=True)
    sale = models.BooleanField(default=False)
    take_cases = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'projects'


class MemberProject(models.Model):
    """學生與老師的專案分配記錄（實際執行中的專案）。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    student = models.ForeignKey(Student, models.DO_NOTHING, related_name='member_projects')
    teacher = models.ForeignKey(Teacher, models.DO_NOTHING, related_name='member_projects')
    project = models.ForeignKey(Project, models.DO_NOTHING, related_name='member_projects')
    course = models.ForeignKey(Course, models.DO_NOTHING, related_name='member_projects', db_column='course_id')
    section_id = models.TextField(blank=True, null=True)
    start_at = models.DateField()
    end_at = models.DateField(blank=True, null=True)
    status = models.TextField()
    inherit_submissions = models.BooleanField(default=False)
    modified_from = models.UUIDField(blank=True, null=True)
    booking_calendar = models.ForeignKey(BookingCalendar, models.DO_NOTHING,
                                         blank=True, null=True, related_name='member_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'member_projects'


# ── Django managed（本系統自建）──────────────────────────────────────────────

class CalendarSyncState(models.Model):
    """儲存 Google Calendar Webhook 的 channel 和 sync token。"""
    channel_id = models.TextField(unique=True)
    resource_id = models.TextField(blank=True, null=True)
    sync_token = models.TextField(blank=True, null=True)
    expiration = models.BigIntegerField(blank=True, null=True)  # Unix ms
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'calendar_sync_state'
