from rest_framework import serializers
from .models import (
    Member, Staff, Teacher, TeacherSchedule, TeacherLeave,
    Student, Booking, BookingCalendar, Project, ProjectCategory,
    MemberProject, TeacherProject, Course
)
import uuid
from django.contrib.auth.hashers import make_password


# ── Member ───────────────────────────────────────────────────────────────────

class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = [
            'id', 'name', 'emails', 'phone', 'roles',
            'created_at', 'updated_at', 'logged_at', 'deregistered_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


VALID_ROLES = {'staff', 'student', 'teacher'}


class MemberCreateSerializer(serializers.Serializer):
    """建立 Member（同時建立對應 profile table 記錄）"""
    name = serializers.CharField()
    emails = serializers.ListField(child=serializers.EmailField(), min_length=1)
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=list(VALID_ROLES)),
        min_length=1,
    )
    # ── 各角色必填欄位 ──
    password_hash = serializers.CharField(required=False, allow_blank=True)
    nick_name = serializers.CharField(required=False, allow_blank=True)
    brand = serializers.CharField(required=False, allow_blank=True)
    hasura_member_id = serializers.UUIDField(required=False)

    def validate_emails(self, value):
        normalized = [e.lower() for e in value]
        if len(normalized) != len(set(normalized)):
            raise serializers.ValidationError('Email 列表中有重複的項目')
        for e in value:
            if Member.objects.filter(emails__contains=[e]).exists():
                raise serializers.ValidationError(f'{e} 已被使用')
        return value

    def validate(self, data):
        roles = data.get('roles', [])
        errors = {}
        if 'staff' in roles and not data.get('password_hash'):
            errors['password_hash'] = '請輸入密碼'
        if 'student' in roles:
            if not data.get('brand'):
                errors['brand'] = 'student 角色為必填'
            if not data.get('hasura_member_id'):
                errors['hasura_member_id'] = 'student 角色為必填'
        if errors:
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        from django.db import transaction

        roles = validated_data['roles']

        with transaction.atomic():
            member = Member.objects.create(
                id=uuid.uuid4(),
                name=validated_data['name'],
                emails=validated_data['emails'],
                roles=roles,
            )

            for role_type in roles:
                if role_type == 'staff':
                    Staff.objects.create(
                        id=uuid.uuid4(),
                        member=member,
                        password_hash=make_password(validated_data['password_hash']),
                    )
                elif role_type == 'teacher':
                    Teacher.objects.create(
                        id=uuid.uuid4(),
                        member=member,
                        nick_name=validated_data.get('nick_name', ''),
                    )
                elif role_type == 'student':
                    Student.objects.create(
                        id=uuid.uuid4(),
                        member=member,
                        brand=validated_data.get('brand', ''),
                        hasura_member_id=validated_data.get('hasura_member_id', uuid.uuid4()),
                    )

        return member

    def to_representation(self, instance):
        return MemberSerializer(instance).data


# ── Staff ─────────────────────────────────────────────────────────────────────

class StaffSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.name', read_only=True)
    member_emails = serializers.ListField(source='member.emails', read_only=True)

    class Meta:
        model = Staff
        fields = [
            'id', 'member', 'member_name', 'member_emails',
            'auth_permission', 'password_hash',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'password_hash': {'write_only': True}}


# ── Teacher ───────────────────────────────────────────────────────────────────

class TeacherSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.name', read_only=True)
    member_emails = serializers.ListField(source='member.emails', read_only=True)

    class Meta:
        model = Teacher
        fields = [
            'id', 'member', 'member_name', 'member_emails',
            'nick_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── TeacherSchedule ───────────────────────────────────────────────────────────

class TeacherScheduleSerializer(serializers.ModelSerializer):
    """老師每週循環排班（teacher_schedules 表）。
    day_of_week: smallint[]，例如 [1, 3, 5]（1=週一 … 7=週日）
    """

    class Meta:
        model = TeacherSchedule
        fields = [
            'id', 'teacher', 'day_of_week',
            'start_time', 'end_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_day_of_week(self, value):
        if not value:
            raise serializers.ValidationError('day_of_week 不可為空')
        for d in value:
            if d < 1 or d > 7:
                raise serializers.ValidationError('day_of_week 每個值需介於 1（週一）至 7（週日）')
        return value

    def validate(self, data):
        start = data.get('start_time') or (self.instance.start_time if self.instance else None)
        end = data.get('end_time') or (self.instance.end_time if self.instance else None)
        if start and end and end <= start:
            raise serializers.ValidationError('end_time 必須晚於 start_time')
        return data


# ── TeacherLeave ──────────────────────────────────────────────────────────────

class TeacherLeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherLeave
        fields = [
            'id', 'teacher', 'start_date', 'start_time',
            'end_date', 'end_time', 'reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── Student ───────────────────────────────────────────────────────────────────

class StudentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.name', read_only=True)
    member_emails = serializers.ListField(source='member.emails', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'member', 'member_name', 'member_emails',
            'brand', 'course_id', 'orientation_id', 'drive_id',
            'hasura_member_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── BookingCalendar ───────────────────────────────────────────────────────────

class BookingCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingCalendar
        fields = ['id', 'google_calendar_id', 'title', 'brand', 'description',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── Booking ───────────────────────────────────────────────────────────────────

class BookingSerializer(serializers.ModelSerializer):
    teacher_nick_name = serializers.CharField(source='teacher.nick_name', read_only=True)
    student_member_name = serializers.CharField(source='student.member.name', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'member_project', 'calendar',
            'teacher', 'teacher_nick_name',
            'student', 'student_member_name',
            'booked_by_email',
            'start_date', 'start_time', 'end_date', 'end_time',
            'google_event_id', 'meet_url', 'event_url',
            'status', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCategory
        fields = ['id', 'name', 'key', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProjectSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'key', 'category', 'category_name',
            'topic', 'level', 'points', 'sale', 'take_cases',
            'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── MemberProject ─────────────────────────────────────────────────────────────

class MemberProjectSerializer(serializers.ModelSerializer):
    teacher_nick_name = serializers.CharField(source='teacher.nick_name', read_only=True)
    student_member_name = serializers.CharField(source='student.member.name', read_only=True)
    project_topic = serializers.CharField(source='project.topic', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    booking_calendar = serializers.PrimaryKeyRelatedField(
        queryset=BookingCalendar.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = MemberProject
        fields = [
            'id',
            'student', 'student_member_name',
            'teacher', 'teacher_nick_name',
            'project', 'project_topic',
            'course', 'course_name',
            'section_id',
            'start_at', 'end_at', 'status',
            'inherit_submissions', 'modified_from',
            'booking_calendar',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_student(self, value):
        if not Student.objects.filter(id=value.id).exists():
            raise serializers.ValidationError('student_id 不存在')
        return value

    def validate_teacher(self, value):
        if not Teacher.objects.filter(id=value.id).exists():
            raise serializers.ValidationError('teacher_id 不存在')
        return value

    def validate_project(self, value):
        if not Project.objects.filter(id=value.id).exists():
            raise serializers.ValidationError('project_id 不存在')
        return value

    def validate_course(self, value):
        if not Course.objects.filter(id=value.id).exists():
            raise serializers.ValidationError('course_id 不存在')
        return value


# ── TeacherProject ────────────────────────────────────────────────────────────

class TeacherProjectSerializer(serializers.ModelSerializer):
    teacher_nick_name = serializers.CharField(source='teacher.nick_name', read_only=True)
    project_topic = serializers.CharField(source='project.topic', read_only=True)
    status = serializers.CharField(default='active')

    class Meta:
        model = TeacherProject
        fields = [
            'id', 'teacher', 'teacher_nick_name',
            'project', 'project_topic',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── Availability Serializers ──────────────────────────────────────────────────

class CycleScheduleSlotSerializer(serializers.Serializer):
    """單筆週循環排班輸入。"""
    day_of_week = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=7),
        min_length=1,
    )
    start_time = serializers.TimeField()
    end_time = serializers.TimeField(required=False, allow_null=True)

    def validate(self, data):
        if data.get('end_time') and data['end_time'] <= data['start_time']:
            raise serializers.ValidationError('end_time 必須晚於 start_time')
        return data


class SetScheduleSerializer(serializers.Serializer):
    """PUT /api/teachers/{id}/set_schedule/ — 完整取代老師排班"""
    schedules = CycleScheduleSlotSerializer(many=True)


# ── Dashboard Serializer ──────────────────────────────────────────────────────

class TeacherDashboardSerializer(serializers.Serializer):
    teacher_info = TeacherSerializer()
    current_member_projects = MemberProjectSerializer(many=True)
    upcoming_bookings = BookingSerializer(many=True)
    completed_bookings_count = serializers.IntegerField()
