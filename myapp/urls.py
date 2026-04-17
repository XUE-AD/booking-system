from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MemberViewSet,
    TeacherViewSet, TeacherScheduleViewSet, TeacherLeaveViewSet, TeacherProjectViewSet,
    StudentViewSet,
    BookingViewSet, BookingCalendarViewSet,
    ProjectViewSet, ProjectCategoryViewSet, MemberProjectViewSet,
    LoginView, CalendarWebhookView, ProfileByEmailView,
)

router = DefaultRouter()
router.register(r'members', MemberViewSet, basename='member')
router.register(r'teachers', TeacherViewSet, basename='teacher')
router.register(r'teacher-schedules', TeacherScheduleViewSet, basename='teacher-schedule')
router.register(r'teacher-leaves', TeacherLeaveViewSet, basename='teacher-leave')
router.register(r'teacher-projects', TeacherProjectViewSet, basename='teacher-project')
router.register(r'students', StudentViewSet, basename='student')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'booking-calendars', BookingCalendarViewSet, basename='booking-calendar')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'project-categories', ProjectCategoryViewSet, basename='project-category')
router.register(r'member-projects', MemberProjectViewSet, basename='member-project')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('calendar/webhook/', CalendarWebhookView.as_view(), name='calendar-webhook'),
    path('profile/by-email/', ProfileByEmailView.as_view(), name='profile-by-email'),
]

"""
API 端點總覽：

會員管理：
- GET    /api/members/              - 列出所有會員
- POST   /api/members/              - 建立會員（同步建立 teacher/student/staff profile）
- GET    /api/members/{id}/         - 查看會員詳情
- PUT    /api/members/{id}/         - 更新會員

老師管理：
- GET    /api/teachers/             - 列出所有老師
- GET    /api/teachers/{id}/        - 查看老師詳情
- PUT    /api/teachers/{id}/        - 更新老師
- DELETE /api/teachers/{id}/        - 刪除老師（含其預約）
- GET    /api/teachers/{id}/dashboard/   - 老師儀表板
- PUT    /api/teachers/{id}/set_schedule/ - 完整取代老師的週排班

老師週排班（teacher_schedules）：
- GET    /api/teacher-schedules/          - 列出（可 filter ?teacher=）
- POST   /api/teacher-schedules/          - 新增
- GET    /api/teacher-schedules/{id}/     - 查看
- PUT    /api/teacher-schedules/{id}/     - 更新
- DELETE /api/teacher-schedules/{id}/     - 刪除

老師請假（teacher_leaves）：
- GET    /api/teacher-leaves/             - 列出（可 filter ?teacher=）
- POST   /api/teacher-leaves/             - 新增
- GET    /api/teacher-leaves/{id}/        - 查看
- PUT    /api/teacher-leaves/{id}/        - 更新
- DELETE /api/teacher-leaves/{id}/        - 刪除

老師負責專案（teacher_projects）：
- GET    /api/teacher-projects/           - 列出
- POST   /api/teacher-projects/           - 新增
- GET    /api/teacher-projects/{id}/      - 查看
- PUT    /api/teacher-projects/{id}/      - 更新
- DELETE /api/teacher-projects/{id}/      - 刪除

學生管理：
- GET    /api/students/                   - 列出所有學生
- GET    /api/students/{id}/              - 查看學生詳情
- PUT    /api/students/{id}/              - 更新學生
- DELETE /api/students/{id}/              - 刪除學生（含其預約）
- GET    /api/students/{id}/bookings/     - 查看學生預約
- POST   /api/students/{id}/create_booking/ - 學生建立預約

預約管理：
- GET    /api/bookings/                   - 列出（可 filter ?teacher=&student=&status=&start_date=）
- POST   /api/bookings/                   - 建立預約
- GET    /api/bookings/{id}/              - 查看
- PUT    /api/bookings/{id}/              - 更新
- DELETE /api/bookings/{id}/              - 刪除（同步刪除 Google Calendar 事件）
- POST   /api/bookings/check_conflict/    - 檢查預約衝突

Google Calendar 對應：
- GET    /api/booking-calendars/          - 列出
- POST   /api/booking-calendars/          - 新增
- GET    /api/booking-calendars/{id}/     - 查看
- PUT    /api/booking-calendars/{id}/     - 更新
- DELETE /api/booking-calendars/{id}/     - 刪除

專案目錄：
- GET    /api/project-categories/         - 列出分類
- GET    /api/projects/                   - 列出專案
- GET    /api/member-projects/            - 列出學生專案分配記錄

認證：
- POST   /api/auth/login/                 - 登入
- POST   /api/profile/by-email/           - 透過 email 查詢會員資料

Google Calendar Webhook：
- POST   /api/calendar/webhook/           - 接收 Google Calendar 推播通知
"""
