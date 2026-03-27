# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
import json as _json
from django.db import models
from django.db.models.expressions import RawSQL


class SafeJSONField(models.JSONField):
    """psycopg2 在 Supabase 連線下會預先將 json 欄位解析成 Python 物件，
    Django JSONField 再次呼叫 json.loads() 時會報錯。
    此 field 在值已是 Python 物件時直接回傳，避免重複解析。"""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            return _json.loads(value)
        return value


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


class Booking(models.Model):
    id = models.UUIDField(primary_key=True)
    meeting_id = models.TextField(blank=True, null=True)
    title = models.TextField()
    booked_by = models.ForeignKey('Role', models.DO_NOTHING, db_column='booked_by', blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    teacher = models.ForeignKey('Teacher', models.DO_NOTHING, to_field='role_id')
    student = models.ForeignKey('Student', models.DO_NOTHING)
    purpose = models.TextField(blank=True, null=True)
    booking_type = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'booking'
        db_table_comment = 'booking'


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


class Role(models.Model):
    role_id = models.UUIDField(primary_key=True)
    role_type = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'role'


class Member(models.Model):
    member_id = models.UUIDField(primary_key=True)
    id = models.BigIntegerField(db_default=RawSQL("nextval('member_id_seq'::regclass)", []))
    name = models.TextField()
    status = models.CharField(max_length=50, blank=True, null=True)
    email = SafeJSONField(blank=True, null=True)
    role_id = SafeJSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    logged_at = models.DateTimeField(blank=True, null=True)
    deregistered_at = models.DateTimeField(blank=True, null=True)
    phone = models.CharField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'member'
        db_table_comment = 'member'


class Project(models.Model):
    project_id = models.UUIDField(primary_key=True)
    project_topic_id = models.UUIDField(blank=True, null=True)
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    teacher = models.ForeignKey('Teacher', models.DO_NOTHING, to_field='role_id', blank=True, null=True)
    student = models.ForeignKey('Student', models.DO_NOTHING, blank=True, null=True)
    statement = models.ForeignKey('ProjectStatement', models.DO_NOTHING, blank=True, null=True)
    classroom = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project'
        db_table_comment = 'project'


class ProjectStatement(models.Model):
    id = models.UUIDField(primary_key=True)
    statement = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'projects_statement'
        db_table_comment = 'projects_statement'


class Staff(models.Model):
    role = models.OneToOneField('Role', models.DO_NOTHING, primary_key=True)
    id = models.BigIntegerField(db_default=RawSQL("nextval('staff_id_seq'::regclass)", []))
    auth_permission = models.TextField(blank=True, null=True)
    password_hash = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'staff'
        db_table_comment = 'staff'


class Status(models.Model):
    id = models.UUIDField(primary_key=True)
    position = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'status'
        db_table_comment = 'status'


class Student(models.Model):
    role = models.OneToOneField('Role', models.DO_NOTHING, primary_key=True)
    id = models.IntegerField(db_default=RawSQL("nextval('student_id_seq'::regclass)", []))
    brand = SafeJSONField(blank=True, null=True)
    classroom = models.TextField(blank=True, null=True)
    advisor_email = models.TextField(blank=True, null=True)
    deal_at = models.DateTimeField(blank=True, null=True)
    contract_start_time = models.DateTimeField(blank=True, null=True)
    service_duration_months = models.IntegerField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    is_course_start_email_sent = models.BooleanField(blank=True, null=True)
    vacation_id = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'student'
        db_table_comment = 'student'


class Teacher(models.Model):
    pk = models.CompositePrimaryKey('id', 'role_id')
    id = models.BigIntegerField(db_default=RawSQL("nextval('teacher_id_seq'::regclass)", []))
    role = models.OneToOneField('Role', models.DO_NOTHING)
    nick_name = models.TextField(blank=True, null=True)
    cooperation_project = SafeJSONField(blank=True, null=True)
    cycle_time = SafeJSONField(blank=True, null=True)
    open_time = SafeJSONField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'teacher'
        db_table_comment = 'teacher'


class ProjectList(models.Model):
    id = models.UUIDField(primary_key=True)
    points = models.IntegerField(blank=True, null=True)
    can_take_case = models.CharField(max_length=1, blank=True, null=True)
    project_level = models.CharField(max_length=1, blank=True, null=True)
    serial_number = models.CharField(max_length=50, blank=True, null=True)
    topic = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_list'
