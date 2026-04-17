"""
Django REST Framework Views
"""

from django.contrib.auth.hashers import check_password
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time, parse_datetime

import logging
from django.conf import settings as django_settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import (
    Member, Staff, Teacher, TeacherSchedule, TeacherLeave, TeacherProject,
    Student, Booking, BookingCalendar, Project, ProjectCategory,
    MemberProject, CalendarSyncState
)
from .google_calendar import GoogleCalendarService

logger = logging.getLogger(__name__)

from .serializers import (
    MemberSerializer, MemberCreateSerializer,
    TeacherSerializer, TeacherScheduleSerializer, TeacherLeaveSerializer,
    TeacherProjectSerializer,
    StudentSerializer,
    BookingSerializer, BookingCalendarSerializer,
    ProjectSerializer, ProjectCategorySerializer,
    MemberProjectSerializer,
    TeacherDashboardSerializer,
    SetScheduleSerializer,
)
from .services import BookingService, TeacherScheduleService, TeacherService


# ── Response Helpers ──────────────────────────────────────────────────────────

def _success(data, status_code=200):
    return Response({'success': True, 'data': data}, status=status_code)


def _error(code, message, details=None, status_code=400):
    err = {'code': code, 'message': message}
    if details is not None:
        err['details'] = details
    return Response({'success': False, 'error': err}, status=status_code)


def _fmt_errors(errors):
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
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return _success(self.get_serializer(queryset, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return _success(self.get_serializer(self.get_object()).data)

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
        self.perform_destroy(self.get_object())
        return _success(None)


# ── ViewSets ──────────────────────────────────────────────────────────────────

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

    def get_serializer_class(self):
        return MemberCreateSerializer if self.action == 'create' else MemberSerializer


class TeacherViewSet(StandardResponseMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """老師 ViewSet（建立請透過 /api/members/）"""
    queryset = Teacher.objects.select_related('member').all()
    serializer_class = TeacherSerializer
    search_fields = ['nick_name']

    @action(detail=True, methods=['get'])
    def dashboard(self, request, **kwargs):
        try:
            data = TeacherService.get_teacher_dashboard(self.kwargs['pk'])
            return _success(TeacherDashboardSerializer(data).data)
        except Teacher.DoesNotExist:
            return _error('NOT_FOUND', 'Teacher not found.', status_code=404)

    @action(detail=True, methods=['put'])
    def set_schedule(self, request, **kwargs):
        """PUT /api/teachers/{id}/set_schedule/ — 完整取代老師週排班"""
        serializer = SetScheduleSerializer(data=request.data)
        if not serializer.is_valid():
            return _error('VALIDATION_ERROR', 'Invalid input data.',
                          _fmt_errors(serializer.errors), 400)
        try:
            teacher = TeacherScheduleService.set_schedules(
                teacher_id=self.kwargs['pk'],
                slots=serializer.validated_data['schedules'],
            )
            schedules = TeacherSchedule.objects.filter(teacher=teacher)
            return _success(TeacherScheduleSerializer(schedules, many=True).data)
        except Teacher.DoesNotExist:
            return _error('NOT_FOUND', 'Teacher not found.', status_code=404)

    def destroy(self, request, *args, **kwargs):
        teacher = self.get_object()
        Booking.objects.filter(teacher=teacher).delete()
        self.perform_destroy(teacher)
        return _success(None)


class TeacherScheduleViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """老師週排班 CRUD（teacher_schedules 表）"""
    queryset = TeacherSchedule.objects.select_related('teacher').all()
    serializer_class = TeacherScheduleSerializer
    filterset_fields = ['teacher']


class TeacherLeaveViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """老師請假 CRUD（teacher_leaves 表）"""
    queryset = TeacherLeave.objects.select_related('teacher').all()
    serializer_class = TeacherLeaveSerializer
    filterset_fields = ['teacher']


class TeacherProjectViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """老師負責專案 CRUD（teacher_projects 表）"""
    queryset = TeacherProject.objects.select_related('teacher', 'project').all()
    serializer_class = TeacherProjectSerializer
    filterset_fields = ['teacher', 'project', 'status']


class StudentViewSet(StandardResponseMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """學生 ViewSet（建立請透過 /api/members/）"""
    queryset = Student.objects.select_related('member').all()
    serializer_class = StudentSerializer
    search_fields = ['brand']
    filterset_fields = ['brand']

    def destroy(self, request, *args, **kwargs):
        student = self.get_object()
        Booking.objects.filter(student=student).delete()
        self.perform_destroy(student)
        return _success(None)

    @action(detail=True, methods=['get'])
    def bookings(self, request, **kwargs):
        student = self.get_object()
        booking_status = request.query_params.get('status', 'all')
        today = timezone.now().date()

        qs = Booking.objects.filter(student=student).select_related('teacher__member')
        if booking_status == 'upcoming':
            qs = qs.filter(start_date__gte=today)
        elif booking_status == 'past':
            qs = qs.filter(start_date__lt=today)
        qs = qs.order_by('-start_date', '-start_time')
        return _success(BookingSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def create_booking(self, request, **kwargs):
        """為學生建立預約"""
        student_id = self.kwargs['pk']
        required = ['teacher', 'calendar', 'start_date', 'start_time',
                    'end_time', 'booked_by_email']
        missing = [f for f in required if not request.data.get(f)]
        if missing:
            return _error('BAD_REQUEST', 'Missing required fields.',
                          [{'field': f, 'message': 'This field is required.'} for f in missing], 400)

        try:
            booking = BookingService.create_booking(
                student_id=student_id,
                teacher_id=request.data['teacher'],
                calendar_id=request.data['calendar'],
                start_date=parse_date(request.data['start_date']),
                start_time=parse_time(request.data['start_time']),
                end_date=parse_date(request.data['end_date']) if request.data.get('end_date') else None,
                end_time=parse_time(request.data['end_time']),
                booked_by_email=request.data['booked_by_email'],
                status=request.data.get('status', 'confirmed'),
                notes=request.data.get('notes'),
                member_project_id=request.data.get('member_project'),
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


class BookingCalendarViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """Google Calendar 對應表 CRUD"""
    queryset = BookingCalendar.objects.all()
    serializer_class = BookingCalendarSerializer
    filterset_fields = ['brand']
    search_fields = ['title', 'brand']


class BookingViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """預約 ViewSet"""
    queryset = Booking.objects.select_related(
        'teacher__member', 'student__member', 'calendar'
    ).all()
    serializer_class = BookingSerializer
    filterset_fields = ['teacher', 'student', 'status', 'start_date']

    def create(self, request, *args, **kwargs):
        required = ['teacher', 'student', 'calendar',
                    'start_date', 'start_time', 'end_time', 'booked_by_email']
        missing = [f for f in required if not request.data.get(f)]
        if missing:
            return _error('BAD_REQUEST', 'Missing required fields.',
                          [{'field': f, 'message': 'This field is required.'} for f in missing], 400)
        try:
            booking = BookingService.create_booking(
                student_id=request.data['student'],
                teacher_id=request.data['teacher'],
                calendar_id=request.data['calendar'],
                start_date=parse_date(request.data['start_date']),
                start_time=parse_time(request.data['start_time']),
                end_date=parse_date(request.data['end_date']) if request.data.get('end_date') else None,
                end_time=parse_time(request.data['end_time']),
                booked_by_email=request.data['booked_by_email'],
                status=request.data.get('status', 'confirmed'),
                notes=request.data.get('notes'),
                member_project_id=request.data.get('member_project'),
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

    def destroy(self, request, *args, **kwargs):
        booking = self.get_object()
        if booking.google_event_id:
            try:
                GoogleCalendarService.delete_event(booking.google_event_id)
            except Exception as e:
                logger.error('Google Calendar delete failed for booking %s: %s', booking.id, e)
        booking.delete()
        return _success(None)

    @action(detail=False, methods=['post'])
    def check_conflict(self, request):
        teacher_id = request.data.get('teacher_id')
        start_date = parse_date(request.data.get('start_date', ''))
        start_time = parse_time(request.data.get('start_time', ''))
        end_date = parse_date(request.data.get('end_date', '')) if request.data.get('end_date') else start_date
        end_time = parse_time(request.data.get('end_time', ''))

        has_conflict = BookingService.check_booking_conflict(
            teacher_id=teacher_id,
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
        )
        return _success({'has_conflict': has_conflict})


class ProjectCategoryViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """專案分類 CRUD"""
    queryset = ProjectCategory.objects.all()
    serializer_class = ProjectCategorySerializer
    search_fields = ['name', 'key']


class ProjectViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """專案目錄 ViewSet"""
    queryset = Project.objects.select_related('category').all()
    serializer_class = ProjectSerializer
    filterset_fields = ['category', 'level', 'sale', 'take_cases']
    search_fields = ['topic', 'description']


class MemberProjectViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """學生專案分配記錄 ViewSet"""
    queryset = MemberProject.objects.select_related(
        'student__member', 'teacher__member', 'project', 'course'
    ).all()
    serializer_class = MemberProjectSerializer
    filterset_fields = ['teacher', 'student', 'project', 'status']


class ProfileByEmailView(APIView):
    """
    POST /api/profile/by-email/
    Body: { "email": "teacher@example.com" }
    回傳該 email 對應的 member 資料
    """
    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return _error('BAD_REQUEST', 'email is required.',
                          [{'field': 'email', 'message': 'This field is required.'}], 400)

        member = Member.objects.filter(emails__contains=[email]).first()
        if not member:
            # 大小寫不分的 fallback
            for m in Member.objects.all():
                if any(e.lower() == email for e in (m.emails or [])):
                    member = m
                    break

        if not member:
            return _error('NOT_FOUND', 'Member not found.', status_code=404)

        return _success(MemberSerializer(member).data)


class LoginView(APIView):
    """
    POST /api/auth/login/
    有 staff 身分 → 需驗證 password_hash；無 staff 身分 → email 存在即可
    """

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password')

        if not email:
            return _error('BAD_REQUEST', 'Email is required.',
                          [{'field': 'email', 'message': 'This field is required.'}], 400)

        # 查找 member（members.emails 是 text[]）
        member = Member.objects.filter(emails__contains=[email]).first()
        if not member:
            # 大小寫不分 fallback
            for m in Member.objects.all():
                if any(e.lower() == email for e in (m.emails or [])):
                    member = m
                    break

        if not member:
            return _error('UNAUTHORIZED', 'Invalid email or password.', status_code=401)

        # 若有 staff 角色，驗證密碼
        if 'staff' in (member.roles or []):
            staff = member.staff_profiles.first()
            if staff:
                if not password:
                    return _error('BAD_REQUEST', 'Password is required for staff.',
                                  [{'field': 'password',
                                    'message': 'This field is required for staff accounts.'}], 400)
                if not check_password(password, staff.password_hash):
                    return _error('UNAUTHORIZED', 'Invalid email or password.', status_code=401)

        member.logged_at = timezone.now()
        member.save(update_fields=['logged_at'])

        return _success(MemberSerializer(member).data)


# ── Google Calendar Webhook ───────────────────────────────────────────────────

def _sync_event_to_booking(event):
    """將 Google Calendar 事件異動同步回 Booking DB。"""
    event_id = event.get('id')
    if not event_id:
        return

    booking = Booking.objects.filter(google_event_id=event_id).first()
    if not booking:
        return

    if event.get('status') == 'cancelled':
        logger.info("Booking %s deleted due to Google Calendar cancellation", booking.id)
        booking.delete()
        return

    updated = False
    summary = event.get('summary')
    # notes 欄位同步 description
    description = event.get('description')
    if description is not None and description != booking.notes:
        booking.notes = description
        updated = True

    if updated:
        booking.save()
        logger.info("Booking %s synced from Google Calendar (event_id=%s)", booking.id, event_id)


@method_decorator(csrf_exempt, name='dispatch')
class CalendarWebhookView(APIView):
    """
    POST /api/calendar/webhook/
    接收 Google Calendar Push Notification，同步異動到 Booking DB。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        token = request.headers.get('X-Goog-Channel-Token', '')
        state = request.headers.get('X-Goog-Resource-State', '')
        channel_id = request.headers.get('X-Goog-Channel-Id', '')

        if token != django_settings.CALENDAR_WEBHOOK_TOKEN:
            return Response(status=403)

        if state == 'sync':
            return Response(status=200)

        try:
            sync_state = CalendarSyncState.objects.get(channel_id=channel_id)
        except CalendarSyncState.DoesNotExist:
            logger.warning("Calendar webhook: unknown channel_id=%s", channel_id)
            return Response(status=200)

        if not sync_state.sync_token:
            return Response(status=200)

        try:
            changed_events, new_sync_token = GoogleCalendarService.get_changed_events(
                sync_state.sync_token
            )
            sync_state.sync_token = new_sync_token
            sync_state.save(update_fields=['sync_token', 'updated_at'])

            for event in changed_events:
                _sync_event_to_booking(event)

        except Exception as e:
            logger.error("Calendar webhook processing error: %s", e)

        return Response(status=200)
