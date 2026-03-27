
import logging
import uuid
from django.utils import timezone
from django.db import transaction
from .models import Booking, Teacher, Student, Project, Member
from .google_calendar import GoogleCalendarService

logger = logging.getLogger(__name__)

class BookingService:
    """預約服務"""

    @staticmethod
    def create_booking(student_id, teacher_id, start_time, end_time,
                      booking_type, title, purpose=None):
        # Step 1: 建立 DB 預約記錄
        with transaction.atomic():
            student = Student.objects.get(role_id=student_id)
            teacher = Teacher.objects.get(role_id=teacher_id)

            # 衝突檢查
            if BookingService.check_booking_conflict(
                teacher_id=teacher_id,
                start_time=start_time,
                end_time=end_time,
            ):
                raise ValueError('該時段已有預約，請選擇其他時間。')

            booking = Booking.objects.create(
                id=uuid.uuid4(),
                student=student,
                teacher=teacher,
                start_time=start_time,
                end_time=end_time,
                booking_type=booking_type,
                title=title,
                purpose=purpose,
            )

        # Step 2: 建立 Google Calendar 活動（DB commit 後，失敗不影響預約）
        try:
            attendee_emails = []
            from .models import Member
            member = Member.objects.filter(role_id__contains=[str(student.role_id)]).first()
            if member and member.email:
                emails = member.email if isinstance(member.email, list) else [member.email]
                attendee_emails.extend(emails)

            result = GoogleCalendarService.create_event(
                title=title,
                description=purpose or f"Booking: {title}",
                start_time=start_time,
                end_time=end_time,
                attendee_emails=attendee_emails,
            )

            booking.meeting_id = result['event_id']
            booking.save(update_fields=['meeting_id'])

        except Exception as e:
            logger.error(
                "Google Calendar 活動建立失敗，booking_id=%s: %s",
                booking.id, str(e)
            )

        return booking
    
    @staticmethod
    def check_booking_conflict(teacher_id, start_time, end_time, exclude_booking_id=None):
        # 修正：外鍵欄位名稱為 teacher
        queryset = Booking.objects.filter(
            teacher_id=teacher_id, # 在 filter 中使用 teacher_id 是 OK 的
            start_time__lt=end_time,
            end_time__gt=start_time
        )
        if exclude_booking_id:
            queryset = queryset.exclude(id=exclude_booking_id)
        return queryset.exists()

    @staticmethod
    def check_student_has_pending_booking(student_id):
        now = timezone.now()
        # 修正：外鍵欄位名稱為 student
        return Booking.objects.filter(
            student_id=student_id,
            start_time__lte=now,
            end_time__gte=now
        ).exists()

    # ... cancel_booking 與 update_booking 邏輯類似，需確保 key 值不含 _id ...

class TeacherAvailabilityService:

    @staticmethod
    def _resolve_open_conflicts(slots):
        """
        解決 open_time 時段衝突：後面的 slot 優先，自動刪除或縮短先前衝突段。
        slots: list of dict，start/end 為 datetime 物件。
        回傳按 start 排序的乾淨清單。
        """
        result = []
        for new in slots:
            ns, ne = new['start'], new['end']
            trimmed = []
            for old in result:
                os, oe = old['start'], old['end']
                if oe <= ns or os >= ne:
                    trimmed.append(old)                    # 完全不重疊，保留
                elif ns <= os and ne >= oe:
                    pass                                   # 新段完全覆蓋舊段，丟棄舊段
                elif os < ns and oe > ne:
                    trimmed.append({**old, 'end': ns})     # 新段在舊段中間：保留左半
                    trimmed.append({**old, 'start': ne})   # 保留右半
                elif os < ne <= oe:
                    trimmed.append({**old, 'start': ne})   # 新段與舊段左側重疊：縮短舊段頭
                else:
                    trimmed.append({**old, 'end': ns})     # 新段與舊段右側重疊：縮短舊段尾
            trimmed.append(new)
            result = trimmed
        return sorted(result, key=lambda s: s['start'])

    @staticmethod
    def _resolve_cycle_conflicts(slots):
        """
        解決 cycle_time 時段衝突（同一天內）：後面的 slot 優先。
        slots: list of dict，start/end 為 time 物件。
        """
        by_day = {}
        for slot in slots:
            by_day.setdefault(slot['day'], []).append(slot)

        result = []
        for day_slots in by_day.values():
            resolved = []
            for new in day_slots:
                ns, ne = new['start'], new['end']
                trimmed = []
                for old in resolved:
                    os, oe = old['start'], old['end']
                    if oe <= ns or os >= ne:
                        trimmed.append(old)
                    elif ns <= os and ne >= oe:
                        pass
                    elif os < ns and oe > ne:
                        trimmed.append({**old, 'end': ns})
                        trimmed.append({**old, 'start': ne})
                    elif os < ne <= oe:
                        trimmed.append({**old, 'start': ne})
                    else:
                        trimmed.append({**old, 'end': ns})
                trimmed.append(new)
                resolved = trimmed
            result.extend(sorted(resolved, key=lambda s: s['start']))
        return result

    @staticmethod
    def _format_open_slots(slots):
        return [
            {
                'start': s['start'].isoformat() if hasattr(s['start'], 'isoformat') else s['start'],
                'end':   s['end'].isoformat()   if hasattr(s['end'],   'isoformat') else s['end'],
            }
            for s in slots
        ]

    @staticmethod
    def _format_cycle_slots(slots):
        return [
            {
                'day':   s['day'],
                'start': s['start'].strftime('%H:%M') if hasattr(s['start'], 'strftime') else s['start'],
                'end':   s['end'].strftime('%H:%M')   if hasattr(s['end'],   'strftime') else s['end'],
            }
            for s in slots
        ]

    @staticmethod
    def set_open_time(role_id, slots):
        """
        PUT set_availability：更新 open_time。
        enabled: true  → 保留 / 新增此時段
        enabled: false → 刪除此時段（不存入 DB）
        """
        teacher = Teacher.objects.get(role_id=role_id)
        active_slots = [s for s in slots if s.get('enabled', True)]
        resolved = TeacherAvailabilityService._resolve_open_conflicts(active_slots)
        teacher.open_time = TeacherAvailabilityService._format_open_slots(resolved)
        teacher.save(update_fields=['open_time'])
        return teacher

    @staticmethod
    def add_open_time(role_id, slots):
        """
        POST teacher-availabilities：追加 open_time。
        enabled: true  → 新增此時段（新段優先覆蓋舊衝突段）
        enabled: false → 忽略，不新增
        """
        from datetime import datetime
        teacher = Teacher.objects.get(role_id=role_id)

        active_slots = [s for s in slots if s.get('enabled', True)]

        existing_parsed = [
            {
                'start': datetime.fromisoformat(s['start']),
                'end':   datetime.fromisoformat(s['end']),
            }
            for s in (teacher.open_time or [])
        ]

        combined = existing_parsed + active_slots
        resolved = TeacherAvailabilityService._resolve_open_conflicts(combined)
        teacher.open_time = TeacherAvailabilityService._format_open_slots(resolved)
        teacher.save(update_fields=['open_time'])
        return teacher

    @staticmethod
    def set_cycle_time(role_id, slots):
        """
        PUT set_cycle_time：更新 cycle_time。
        enabled: true  → 保留 / 新增此時段
        enabled: false → 刪除此時段（不存入 DB）
        """
        teacher = Teacher.objects.get(role_id=role_id)
        active_slots = [s for s in slots if s.get('enabled', True)]
        resolved = TeacherAvailabilityService._resolve_cycle_conflicts(active_slots)
        teacher.cycle_time = TeacherAvailabilityService._format_cycle_slots(resolved)
        teacher.save(update_fields=['cycle_time'])
        return teacher


class TeacherService:
    @staticmethod
    def get_teacher_dashboard(teacher_id):
        # 修正：member_id 改為 member
        teacher = Teacher.objects.select_related('role').get(id=teacher_id)
        now = timezone.now()
        
        # 進行中的專案
        current_projects = Project.objects.filter(
            teacher_id=teacher_id,
            statement__statement='進行中'
        ).select_related('student__role', 'statement')
        
        # 即將到來的預約
        upcoming_bookings = Booking.objects.filter(
            teacher_id=teacher_id,
            start_time__gte=now
        ).select_related('student__role').order_by('start_time')[:10]
        
        completed_count = Booking.objects.filter(
            teacher_id=teacher_id,
            end_time__lt=now
        ).count()
        
        return {
            'teacher_info': teacher,
            'current_projects': current_projects,
            'upcoming_bookings': upcoming_bookings,
            'completed_bookings_count': completed_count
        }

# StudentService 依照 TeacherService 同理修正 (student_id 改為 student, member_id 改為 member)