import logging
import uuid
from datetime import datetime, date as date_type, time as time_type
from django.db import transaction
from django.utils import timezone
import pytz

from .models import (
    Booking, Teacher, TeacherSchedule, Student, MemberProject,
    Member, BookingCalendar
)
from .google_calendar import GoogleCalendarService

logger = logging.getLogger(__name__)

TZ = pytz.timezone('Asia/Taipei')


def _combine_dt(d, t):
    """date + time → timezone-aware datetime（Asia/Taipei）。"""
    return TZ.localize(datetime.combine(d, t))


class BookingService:

    @staticmethod
    def create_booking(student_id, teacher_id, calendar_id,
                       start_date, start_time, end_date, end_time,
                       booked_by_email, status='confirmed', notes=None,
                       member_project_id=None):
        """建立預約並同步 Google Calendar。
        start_date / end_date: date 物件
        start_time / end_time: time 物件
        """
        with transaction.atomic():
            student = Student.objects.select_related('member').get(id=student_id)
            teacher = Teacher.objects.select_related('member').get(id=teacher_id)
            calendar = BookingCalendar.objects.get(id=calendar_id)

            if BookingService.check_booking_conflict(
                teacher_id=teacher_id,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date or start_date,
                end_time=end_time,
            ):
                raise ValueError('該時段已有預約，請選擇其他時間。')

            booking = Booking.objects.create(
                id=uuid.uuid4(),
                student=student,
                teacher=teacher,
                calendar=calendar,
                member_project_id=member_project_id,
                booked_by_email=booked_by_email,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=end_time,
                google_event_id='',
                meet_url='',
                event_url='',
                status=status,
                notes=notes,
            )

        # Google Calendar 建立（DB commit 後，失敗不影響預約）
        try:
            attendee_emails = []
            if student.member.emails:
                attendee_emails.append(student.member.emails[0])
            if teacher.member.emails:
                attendee_emails.append(teacher.member.emails[0])

            start_dt = _combine_dt(start_date, start_time)
            end_dt = _combine_dt(end_date or start_date, end_time)
            title = f'{teacher.nick_name or "老師"} × {student.member.name}'

            result = GoogleCalendarService.create_event(
                title=title,
                description=notes or '',
                start_time=start_dt,
                end_time=end_dt,
                attendee_emails=attendee_emails,
            )

            booking.google_event_id = result.get('event_id', '')
            booking.meet_url = result.get('meet_url', '')
            booking.event_url = result.get('event_url', '')
            booking.save(update_fields=['google_event_id', 'meet_url', 'event_url'])

        except Exception as e:
            logger.error("Google Calendar 建立失敗，booking_id=%s: %s", booking.id, e)

        return booking

    @staticmethod
    def check_booking_conflict(teacher_id, start_date, start_time,
                               end_date, end_time, exclude_booking_id=None):
        """簡單衝突檢查：同老師同日期時間重疊。"""
        queryset = Booking.objects.filter(
            teacher_id=teacher_id,
            start_date=start_date,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if exclude_booking_id:
            queryset = queryset.exclude(id=exclude_booking_id)
        return queryset.exists()


class TeacherScheduleService:
    """老師排班服務（操作 teacher_schedules 表）。"""

    @staticmethod
    def set_schedules(teacher_id, slots):
        """完整取代老師的所有週循環排班。
        slots: list of {day_of_week: [int], start_time: time, end_time: time|None}
        """
        teacher = Teacher.objects.get(id=teacher_id)

        with transaction.atomic():
            TeacherSchedule.objects.filter(teacher=teacher).delete()
            for slot in slots:
                TeacherSchedule.objects.create(
                    id=uuid.uuid4(),
                    teacher=teacher,
                    day_of_week=slot['day_of_week'],
                    start_time=slot['start_time'],
                    end_time=slot.get('end_time'),
                )
        return teacher


class TeacherService:

    @staticmethod
    def get_teacher_dashboard(teacher_id):
        teacher = Teacher.objects.select_related('member').prefetch_related('schedules').get(id=teacher_id)
        now = timezone.now()
        today = now.date()

        current_member_projects = MemberProject.objects.filter(
            teacher_id=teacher_id,
            status='active',
        ).select_related('student__member', 'project').order_by('start_at')

        upcoming_bookings = Booking.objects.filter(
            teacher_id=teacher_id,
            start_date__gte=today,
        ).select_related('student__member').order_by('start_date', 'start_time')[:10]

        completed_count = Booking.objects.filter(
            teacher_id=teacher_id,
            start_date__lt=today,
        ).count()

        return {
            'teacher_info': teacher,
            'current_member_projects': list(current_member_projects),
            'upcoming_bookings': list(upcoming_bookings),
            'completed_bookings_count': completed_count,
        }
