from rest_framework import serializers
from .models import (
    Member, Role, Staff, Teacher, Student,
    ProjectStatement, Project, Booking, ProjectList
)
import uuid
from django.contrib.auth.hashers import make_password


# ── Helper ───────────────────────────────────────────────────────────────────

def _get_member_by_role_id(role_id):
    """透過 role_id 精確查詢 Member（member.role_id 為 JSON array）"""
    if not role_id:
        return None
    return Member.objects.filter(role_id__contains=[str(role_id)]).first()


# ── Role ─────────────────────────────────────────────────────────────────────

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['role_id', 'role_type']
        read_only_fields = ['role_id']


# ── Member ───────────────────────────────────────────────────────────────────

class MemberSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            'member_id', 'id', 'name', 'role', 'email',
            'created_at', 'updated_at', 'logged_at', 'deregistered_at', 'phone'
        ]
        read_only_fields = ['member_id', 'id']

    def get_role(self, obj):
        role_ids = obj.role_id or []
        if not role_ids:
            return {}
        roles = Role.objects.filter(role_id__in=role_ids)
        return {r.role_type: str(r.role_id) for r in roles}


VALID_ROLES = {'op', 'staff', 'student', 'teacher'}


class MemberCreateSerializer(serializers.Serializer):
    """建立 Member（同時建立 Role 及對應 profile table）"""
    name  = serializers.CharField()
    email = serializers.ListField(child=serializers.EmailField(), min_length=1)
    role  = serializers.ListField(
        child=serializers.ChoiceField(choices=list(VALID_ROLES)),
        min_length=1,
    )
    # ── 各角色必填欄位（依 role 內容決定是否必填）──
    password_hash        = serializers.CharField(required=False, allow_blank=True)
    cooperation_project  = serializers.JSONField(required=False)
    brand                = serializers.ListField(child=serializers.CharField(), required=False)
    classroom            = serializers.CharField(required=False, allow_blank=True)

    def validate_cooperation_project(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('cooperation_project 必須為 JSON 物件，例如 {"專案A": true, "專案B": false}')
        return value

    def validate_email(self, value):
        # 檢查 array 內部是否有重複
        normalized = [e.lower() for e in value]
        if len(normalized) != len(set(normalized)):
            raise serializers.ValidationError('Email 列表中有重複的項目')
        # 檢查每個 email 是否已存在於 DB
        for e in value:
            if Member.objects.filter(email__icontains=e).exists():
                raise serializers.ValidationError(f'{e} 已被使用')
        return value

    def validate(self, data):
        roles  = data.get('role', [])
        errors = {}

        if 'staff' in roles and not data.get('password_hash'):
            errors['password_hash'] = 'staff 角色為必填'
        if 'teacher' in roles and data.get('cooperation_project') is None:
            errors['cooperation_project'] = 'teacher 角色為必填'
        if 'student' in roles:
            if not data.get('brand'):
                errors['brand'] = 'student 角色為必填'
            if not data.get('classroom'):
                errors['classroom'] = 'student 角色為必填'

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        from django.db import transaction

        roles = validated_data['role']

        with transaction.atomic():
            role_map = {}  # role_type -> role_id string

            for role_type in roles:
                role = Role.objects.create(
                    role_id=uuid.uuid4(),
                    role_type=role_type,
                )
                role_map[role_type] = str(role.role_id)

                if role_type == 'staff':
                    Staff.objects.create(
                        role=role,
                        password_hash=make_password(validated_data['password_hash']),
                    )
                elif role_type == 'teacher':
                    Teacher.objects.create(
                        role=role,
                        cooperation_project=validated_data.get('cooperation_project'),
                    )
                elif role_type == 'student':
                    Student.objects.create(
                        role=role,
                        brand=validated_data.get('brand', []),
                        classroom=validated_data.get('classroom', ''),
                    )

            member = Member.objects.create(
                member_id=uuid.uuid4(),
                name=validated_data['name'],
                email=validated_data['email'],
                status=','.join(roles),
                role_id=list(role_map.values()),
            )
            member._role_map = role_map

        return member

    def to_representation(self, instance):
        data = MemberSerializer(instance).data
        # Override role field with key-value map from creation
        if hasattr(instance, '_role_map'):
            data['role'] = instance._role_map
        return data


# ── Staff ─────────────────────────────────────────────────────────────────────

class StaffSerializer(serializers.ModelSerializer):
    role_type   = serializers.CharField(source='role.role_type', read_only=True)
    member_name  = serializers.SerializerMethodField()
    member_email = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            'id', 'role', 'role_type', 'member_name', 'member_email',
            'auth_permission', 'password_hash',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'password_hash': {'write_only': True}}

    def get_member_name(self, obj):
        member = _get_member_by_role_id(obj.role_id)
        return member.name if member else None

    def get_member_email(self, obj):
        member = _get_member_by_role_id(obj.role_id)
        return member.email if member else None


# ── Teacher ───────────────────────────────────────────────────────────────────

class TeacherSerializer(serializers.ModelSerializer):
    role_type    = serializers.CharField(source='role.role_type', read_only=True)
    member_name  = serializers.SerializerMethodField()
    member_email = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = [
            'id', 'role', 'role_type', 'member_name', 'member_email',
            'nick_name', 'cooperation_project', 'cycle_time', 'open_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_member_name(self, obj):
        member = _get_member_by_role_id(obj.role_id)
        return member.name if member else None

    def get_member_email(self, obj):
        member = _get_member_by_role_id(obj.role_id)
        return member.email if member else None


# ── Student ───────────────────────────────────────────────────────────────────

class StudentSerializer(serializers.ModelSerializer):
    role_type    = serializers.CharField(source='role.role_type', read_only=True)
    member_name  = serializers.SerializerMethodField()
    member_email = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'role', 'role_type', 'member_name', 'member_email',
            'brand', 'classroom', 'advisor_email',
            'deal_at', 'contract_start_time', 'service_duration_months',
            'revoked_at', 'is_course_start_email_sent', 'vacation_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_member_name(self, obj):
        member = _get_member_by_role_id(obj.role_id)
        return member.name if member else None

    def get_member_email(self, obj):
        member = _get_member_by_role_id(obj.role_id)
        return member.email if member else None


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectSerializer(serializers.ModelSerializer):
    teacher_name   = serializers.CharField(source='teacher.nick_name', read_only=True)
    student_name   = serializers.SerializerMethodField()
    statement_text = serializers.CharField(source='statement.statement', read_only=True)

    class Meta:
        model = Project
        fields = [
            'project_id', 'project_topic_id', 'start_time', 'end_time',
            'teacher', 'teacher_name', 'student', 'student_name',
            'statement', 'statement_text', 'classroom',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['project_id', 'created_at', 'updated_at']

    def get_student_name(self, obj):
        if not obj.student:
            return None
        member = _get_member_by_role_id(obj.student.role_id)
        return member.name if member else None


# ── Booking ───────────────────────────────────────────────────────────────────

class BookingSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.nick_name', read_only=True)
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'meeting_id', 'title', 'booked_by',
            'start_time', 'end_time', 'teacher', 'teacher_name',
            'student', 'student_name', 'purpose', 'booking_type',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'booked_by': {'required': False, 'allow_null': True}}

    def get_student_name(self, obj):
        if not obj.student:
            return None
        member = _get_member_by_role_id(obj.student.role_id)
        return member.name if member else None



# ── Availability Serializers ──────────────────────────────────────────────────

class OpenTimeSlotSerializer(serializers.Serializer):
    """單筆 open_time 時段（指定日期時間）"""
    start   = serializers.DateTimeField()
    end     = serializers.DateTimeField()
    enabled = serializers.BooleanField(default=True)

    def validate(self, data):
        if data.get('enabled', True) and data['end'] <= data['start']:
            raise serializers.ValidationError("結束時間必須晚於開始時間")
        return data


class CycleTimeSlotSerializer(serializers.Serializer):
    """單筆 cycle_time 時段（週循環）day: 1=週一 … 7=週日"""
    day     = serializers.IntegerField(min_value=1, max_value=7)
    start   = serializers.TimeField()
    end     = serializers.TimeField()
    enabled = serializers.BooleanField(default=True)

    def validate(self, data):
        if data['end'] <= data['start']:
            raise serializers.ValidationError("結束時間必須晚於開始時間")
        return data


class TeacherAvailabilitySerializer(serializers.ModelSerializer):
    """老師可用時段（唯讀）"""
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = ['id', 'member_name', 'nick_name', 'cycle_time', 'open_time']
        read_only_fields = ['id', 'member_name', 'nick_name', 'cycle_time', 'open_time']

    def get_member_name(self, obj):
        member = _get_member_by_role_id(obj.role_id)
        return member.name if member else None


class SetAvailabilitySerializer(serializers.Serializer):
    """PUT /api/teachers/{id}/set_availability/"""
    open_time = OpenTimeSlotSerializer(many=True)


class SetCycleTimeSerializer(serializers.Serializer):
    """PUT /api/teachers/{id}/set_cycle_time/"""
    cycle_time = CycleTimeSlotSerializer(many=True)


class AddOpenTimeSerializer(serializers.Serializer):
    """POST /api/teacher-availabilities/"""
    member_id = serializers.UUIDField()
    open_time = OpenTimeSlotSerializer(many=True)


# ── Dashboard Serializers ─────────────────────────────────────────────────────

class TeacherDashboardSerializer(serializers.Serializer):
    teacher_info             = TeacherSerializer()
    current_projects         = ProjectSerializer(many=True)
    upcoming_bookings        = BookingSerializer(many=True)
    completed_bookings_count = serializers.IntegerField()



# ── Project Serializers ───────────────────────────────────────────────────────

class ProjectStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectStatement
        fields = ['id', 'statement', 'created_at']
        read_only_fields = ['id', 'created_at']



class ProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectList
        fields = ['id', 'points', 'can_take_case', 'project_level', 'serial_number', 'topic', 'description']
        read_only_fields = ['id']
