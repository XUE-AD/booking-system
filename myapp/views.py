"""
Django REST Framework Views
"""

from django.contrib.auth.hashers import check_password
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Member, Role, Staff, Teacher, Student,
    Project, Booking, ProjectList
)
from .serializers import (
    MemberSerializer, MemberCreateSerializer, RoleSerializer,
    TeacherSerializer,
    StudentSerializer,
    ProjectSerializer,
    BookingSerializer,
    TeacherDashboardSerializer,
    TeacherAvailabilitySerializer,
    SetAvailabilitySerializer, SetCycleTimeSerializer, AddOpenTimeSerializer,
    ProjectListSerializer,
)
from .services import BookingService, TeacherService, TeacherAvailabilityService


# ── Response Helpers ──────────────────────────────────────────────────────────

def _success(data, status_code=200):
    return Response({'success': True, 'data': data}, status=status_code)


def _error(code, message, details=None, status_code=400):
    err = {'code': code, 'message': message}
    if details is not None:
        err['details'] = details
    return Response({'success': False, 'error': err}, status=status_code)


def _fmt_errors(errors):
    """Convert DRF serializer errors dict → details list."""
    details = []
    if isinstance(errors, list):
        for msg in errors:
            details.append({'field': 'non_field_errors', 'message': str(msg)})
    elif isinstance(errors, dict):
        for field, messages in errors.items():
            if isinstance(messages, list):
                for msg in messages:
                    details.append({'field': field, 'message': str(msg)})
            elif isinstance(messages, dict):
                for sub_field, sub_msgs in messages.items():
                    sub_msgs = sub_msgs if isinstance(sub_msgs, list) else [sub_msgs]
                    for msg in sub_msgs:
                        details.append({'field': f'{field}.{sub_field}', 'message': str(msg)})
            else:
                details.append({'field': field, 'message': str(messages)})
    return details


def custom_exception_handler(exc, context):
    """統一所有未捕捉例外的回應格式。"""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ValidationError):
        details = _fmt_errors(exc.detail) if isinstance(exc.detail, dict) else \
                  [{'field': 'non_field_errors', 'message': str(exc.detail)}]
        return _error('VALIDATION_ERROR', 'Invalid input data.', details, response.status_code)
    if response.status_code == 404:
        return _error('NOT_FOUND', 'Resource not found.', status_code=404)
    if response.status_code == 401:
        return _error('UNAUTHORIZED', 'Authentication required.', status_code=401)
    if response.status_code == 405:
        return _error('METHOD_NOT_ALLOWED', 'Method not allowed.', status_code=405)
    return _error('ERROR', str(exc), status_code=response.status_code)


# ── Standard Response Mixin ───────────────────────────────────────────────────

class StandardResponseMixin:
    """將 ModelMixin 的預設回應包裝成統一 {success, data} 格式。"""

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return _success(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return _success(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return _error('VALIDATION_ERROR', 'Invalid input data.',
                          _fmt_errors(serializer.errors), 400)
        self.perform_create(serializer)
        return _success(serializer.data, 201)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return _error('VALIDATION_ERROR', 'Invalid input data.',
                          _fmt_errors(serializer.errors), 400)
        self.perform_update(serializer)
        return _success(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return _success(None)


# ── ViewSets ──────────────────────────────────────────────────────────────────

class RoleViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """角色 ViewSet"""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    filterset_fields = ['role_type']
    lookup_field = 'role_id'


class MemberViewSet(StandardResponseMixin,
                    mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    """會員 ViewSet（不提供 DELETE）"""
    queryset = Member.objects.all()
    search_fields = ['name']
    filterset_fields = ['deregistered_at']
    lookup_field = 'member_id'

    def get_serializer_class(self):
        if self.action == 'create':
            return MemberCreateSerializer
        return MemberSerializer

    def list(self, request, *args, **kwargs):
        """多 role member 展開為多筆，每筆只含單一 role"""
        queryset = self.filter_queryset(self.get_queryset())
        result = []
        for member in queryset:
            role_ids = member.role_id or []

            if not role_ids:
                result.append(MemberSerializer(member).data)
                continue

            from .models import Role as RoleModel
            roles = RoleModel.objects.filter(role_id__in=role_ids)
            role_map = {str(r.role_id): r.role_type for r in roles}

            for role_id in role_ids:
                role_type = role_map.get(role_id)
                if role_type:
                    data = MemberSerializer(member).data
                    data['role'] = {role_type: role_id}
                    result.append(data)

        return _success(result)



class TeacherViewSet(StandardResponseMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """老師 ViewSet（不提供 POST，請透過 /api/members/ 建立）"""
    queryset = Teacher.objects.select_related('role').all()
    serializer_class = TeacherSerializer
    search_fields = ['nick_name']
    filterset_fields = ['cooperation_project']
    lookup_field = 'role_id'

    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        try:
            dashboard_data = TeacherService.get_teacher_dashboard(pk)
            serializer = TeacherDashboardSerializer(dashboard_data)
            return _success(serializer.data)
        except Teacher.DoesNotExist:
            return _error('NOT_FOUND', 'Teacher not found.', status_code=404)

    @action(detail=True, methods=['put'])
    def set_availability(self, request, pk=None):
        """PUT /api/teachers/{id}/set_availability/ — 完整取代 open_time"""
        serializer = SetAvailabilitySerializer(data=request.data)
        if not serializer.is_valid():
            return _error('VALIDATION_ERROR', 'Invalid input data.',
                          _fmt_errors(serializer.errors), 400)
        try:
            teacher = TeacherAvailabilityService.set_open_time(
                role_id=pk,
                slots=serializer.validated_data['open_time'],
            )
            return _success(TeacherAvailabilitySerializer(teacher).data)
        except Teacher.DoesNotExist:
            return _error('NOT_FOUND', 'Teacher not found.', status_code=404)

    @action(detail=True, methods=['put'])
    def set_cycle_time(self, request, pk=None):
        """PUT /api/teachers/{id}/set_cycle_time/ — 完整取代 cycle_time"""
        serializer = SetCycleTimeSerializer(data=request.data)
        if not serializer.is_valid():
            return _error('VALIDATION_ERROR', 'Invalid input data.',
                          _fmt_errors(serializer.errors), 400)
        try:
            teacher = TeacherAvailabilityService.set_cycle_time(
                role_id=pk,
                slots=serializer.validated_data['cycle_time'],
            )
            return _success(TeacherAvailabilitySerializer(teacher).data)
        except Teacher.DoesNotExist:
            return _error('NOT_FOUND', 'Teacher not found.', status_code=404)

    def destroy(self, request, *args, **kwargs):
        teacher = self.get_object()
        Booking.objects.filter(teacher=teacher).delete()
        self.perform_destroy(teacher)
        return _success(None)


class StudentViewSet(StandardResponseMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """學生 ViewSet（不提供 POST，請透過 /api/members/ 建立）"""
    queryset = Student.objects.select_related('role').all()
    serializer_class = StudentSerializer
    search_fields = ['brand', 'classroom']
    filterset_fields = ['brand', 'classroom']
    lookup_field = 'role_id'

    def destroy(self, request, *args, **kwargs):
        student = self.get_object()
        Booking.objects.filter(student=student).delete()
        self.perform_destroy(student)
        return _success(None)

    @action(detail=True, methods=['get'])
    def bookings(self, request, pk=None):
        """查詢學生的預約"""
        try:
            student = self.get_object()
            booking_status = request.query_params.get('status', 'all')
            now = timezone.now()

            queryset = Booking.objects.filter(student=student)

            if booking_status == 'upcoming':
                queryset = queryset.filter(start_time__gte=now)
            elif booking_status == 'past':
                queryset = queryset.filter(end_time__lt=now)

            queryset = queryset.select_related('teacher').order_by('-start_time')
            serializer = BookingSerializer(queryset, many=True)
            return _success(serializer.data)
        except Student.DoesNotExist:
            return _error('NOT_FOUND', 'Student not found.', status_code=404)

    @action(detail=True, methods=['post'])
    def create_booking(self, request, pk=None):
        """為學生建立預約"""
        teacher_id    = request.data.get('teacher')
        start_time_str = request.data.get('start_time')
        end_time_str   = request.data.get('end_time')
        booking_type  = request.data.get('booking_type', 'regular')
        title         = request.data.get('title', '新預約')
        purpose       = request.data.get('purpose', '')

        missing = [f for f in ['teacher', 'start_time', 'end_time'] if not request.data.get(f)]
        if missing:
            return _error('BAD_REQUEST', 'Missing required fields.',
                          [{'field': f, 'message': 'This field is required.'} for f in missing], 400)

        try:
            from django.utils.dateparse import parse_datetime
            booking = BookingService.create_booking(
                student_id=pk,
                teacher_id=teacher_id,
                start_time=parse_datetime(start_time_str),
                end_time=parse_datetime(end_time_str),
                booking_type=booking_type,
                title=title,
                purpose=purpose,
            )
            return _success(BookingSerializer(booking).data, 201)

        except Student.DoesNotExist:
            return _error('NOT_FOUND', 'Student not found.', status_code=404)
        except Teacher.DoesNotExist:
            return _error('NOT_FOUND', 'Teacher not found.', status_code=404)
        except ValueError as e:
            return _error('BAD_REQUEST', str(e), status_code=400)
        except Exception as e:
            return _error('INTERNAL_ERROR', f'System error: {str(e)}', status_code=500)


class TeacherAvailabilityViewSet(viewsets.ViewSet):
    """
    GET  /api/teacher-availabilities/       — 列出所有老師的開放時段
    POST /api/teacher-availabilities/       — 追加 open_time 時段（body 需含 member_id）
    GET  /api/teacher-availabilities/{id}/  — 查詢單一老師的可用時段
    """

    def list(self, request):
        teachers = Teacher.objects.select_related('role').all()
        return _success(TeacherAvailabilitySerializer(teachers, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            teacher = Teacher.objects.select_related('role').get(role_id=pk)
        except Teacher.DoesNotExist:
            return _error('NOT_FOUND', 'Teacher not found.', status_code=404)
        return _success(TeacherAvailabilitySerializer(teacher).data)

    def create(self, request):
        """追加 open_time 時段到指定老師"""
        serializer = AddOpenTimeSerializer(data=request.data)
        if not serializer.is_valid():
            return _error('VALIDATION_ERROR', 'Invalid input data.',
                          _fmt_errors(serializer.errors), 400)
        try:
            teacher = TeacherAvailabilityService.add_open_time(
                role_id=serializer.validated_data['member_id'],
                slots=serializer.validated_data['open_time'],
            )
            return _success(TeacherAvailabilitySerializer(teacher).data)
        except Teacher.DoesNotExist:
            return _error('NOT_FOUND', 'Teacher not found.', status_code=404)


class ProjectViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """專案 ViewSet"""
    queryset = Project.objects.select_related('teacher', 'student', 'statement').all()
    serializer_class = ProjectSerializer
    filterset_fields = ['teacher', 'student', 'statement']


class ProjectListViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """專案清單 ViewSet"""
    queryset = ProjectList.objects.all()
    serializer_class = ProjectListSerializer
    filterset_fields = ['project_level', 'can_take_case']
    search_fields = ['topic', 'serial_number', 'description']


class BookingViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """預約 ViewSet"""
    queryset = Booking.objects.select_related('teacher', 'student').all()
    serializer_class = BookingSerializer
    filterset_fields = ['teacher', 'student', 'booking_type']

    @action(detail=False, methods=['post'])
    def check_conflict(self, request):
        teacher_id = request.data.get('teacher_id')
        start_time = request.data.get('start_time')
        end_time   = request.data.get('end_time')

        has_conflict = BookingService.check_booking_conflict(
            teacher_id=teacher_id,
            start_time=start_time,
            end_time=end_time,
        )
        return _success({'has_conflict': has_conflict})


class LoginView(APIView):
    """
    POST /api/auth/login/
    有 staff 身分 → 需驗證 password_hash；無 staff 身分 → email 存在即可
    """

    def post(self, request):
        email    = request.data.get('email')
        password = request.data.get('password')

        if not email:
            return _error('BAD_REQUEST', 'Email is required.',
                          [{'field': 'email', 'message': 'This field is required.'}], 400)

        # email 為 JSONField array，以第一個元素比對
        try:
            members = Member.objects.all()
            member = next(
                (m for m in members
                 if isinstance(m.email, list) and m.email and m.email[0].lower() == email.lower()),
                None
            )
            if member is None:
                raise Member.DoesNotExist
        except Member.DoesNotExist:
            return _error('UNAUTHORIZED', 'Invalid email or password.', status_code=401)

        role_ids = member.role_id or []

        staff = Staff.objects.filter(role_id__in=role_ids).first() if role_ids else None

        if staff:
            if not password:
                return _error('BAD_REQUEST', 'Password is required for staff.',
                              [{'field': 'password', 'message': 'This field is required for staff accounts.'}], 400)
            if not check_password(password, staff.password_hash):
                return _error('UNAUTHORIZED', 'Invalid email or password.', status_code=401)

        return _success(MemberSerializer(member).data)
