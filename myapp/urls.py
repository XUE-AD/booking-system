from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MemberViewSet, RoleViewSet, TeacherViewSet, StudentViewSet,
    BookingViewSet, ProjectViewSet, TeacherAvailabilityViewSet,
    ProjectListViewSet, LoginView, CalendarWebhookView
)

# 建立 Router
router = DefaultRouter()
router.register(r'members', MemberViewSet, basename='member')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'teachers', TeacherViewSet, basename='teacher')
router.register(r'students', StudentViewSet, basename='student')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'teacher-availabilities', TeacherAvailabilityViewSet, basename='teacher-availability')
router.register(r'project-list', ProjectListViewSet, basename='project-list')


urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('calendar/webhook/', CalendarWebhookView.as_view(), name='calendar-webhook'),
]

"""
API 端點總覽：

會員管理：
- GET    /api/members/              - 列出所有會員
- POST   /api/members/              - 建立會員
- GET    /api/members/{id}/         - 查看會員詳情
- PUT    /api/members/{id}/         - 更新會員
- DELETE /api/members/{id}/         - 刪除會員

老師管理：
- GET    /api/teachers/             - 列出所有老師
- POST   /api/teachers/             - 建立老師
- GET    /api/teachers/{id}/        - 查看老師詳情
- PUT    /api/teachers/{id}/        - 更新老師
- DELETE /api/teachers/{id}/        - 刪除老師
- GET    /api/teachers/{id}/dashboard/          - 老師儀表板
- POST   /api/teachers/{id}/set_availability/   - 設定開放時段
- POST   /api/teachers/{id}/close_availability/ - 關閉開放時段

學生管理：
- GET    /api/students/             - 列出所有學生
- POST   /api/students/             - 建立學生
- GET    /api/students/{id}/        - 查看學生詳情
- PUT    /api/students/{id}/        - 更新學生
- DELETE /api/students/{id}/        - 刪除學生
- GET    /api/students/{id}/bookings/       - 查看學生預約
- POST   /api/students/{id}/create_booking/ - 學生建立預約

預約管理：
- GET    /api/bookings/             - 列出所有預約
- POST   /api/bookings/             - 建立預約（一般用）
- GET    /api/bookings/{id}/        - 查看預約詳情
- PUT    /api/bookings/{id}/        - 更新預約（一般用）
- DELETE /api/bookings/{id}/        - 刪除預約（一般用）
- POST   /api/bookings/{id}/cancel/        - 取消預約
- PATCH  /api/bookings/{id}/update_booking/ - 更新預約（業務邏輯）
- POST   /api/bookings/check_conflict/      - 檢查預約衝突

專案管理：
- GET    /api/projects/             - 列出所有專案
- POST   /api/projects/             - 建立專案
- GET    /api/projects/{id}/        - 查看專案詳情
- PUT    /api/projects/{id}/        - 更新專案
- DELETE /api/projects/{id}/        - 刪除專案

專案主題：
- GET    /api/project-topics/       - 列出所有專案主題
- POST   /api/project-topics/       - 建立專案主題
- GET    /api/project-topics/{id}/  - 查看專案主題詳情
- PUT    /api/project-topics/{id}/  - 更新專案主題
- DELETE /api/project-topics/{id}/  - 刪除專案主題

開放時段管理：
- GET    /api/teacher-availabilities/              - 列出所有開放時段
- POST   /api/teacher-availabilities/              - 建立開放時段
- GET    /api/teacher-availabilities/{id}/         - 查看開放時段詳情
- PUT    /api/teacher-availabilities/{id}/         - 更新開放時段
- DELETE /api/teacher-availabilities/{id}/         - 刪除開放時段
- GET    /api/teacher-availabilities/available_slots/ - 查詢可用時段
"""
