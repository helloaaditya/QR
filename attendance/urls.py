from django.urls import path
from . import views

urlpatterns = [
    path('favicon.ico', views.favicon),
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/delete/<str:code>', views.delete_session, name='delete_session'),
    path('login/', views.teacher_login, name='teacher_login'),
    path('reports/', views.reports, name='reports'),
    path('settings/students/', views.settings_students, name='settings_students'),
    path('settings/students/toggle', views.settings_students_toggle, name='settings_students_toggle'),
    path('settings/students/delete', views.settings_students_delete, name='settings_students_delete'),
    path('settings/teachers/add', views.settings_teachers_add, name='settings_teachers_add'),
    path('settings/teachers/delete', views.settings_teachers_delete, name='settings_teachers_delete'),
    path('settings/subjects/add', views.settings_subjects_add, name='settings_subjects_add'),
    path('settings/subjects/delete', views.settings_subjects_delete, name='settings_subjects_delete'),
    path('start/', views.start_session, name='start_session'),
    path('t/<str:code>/', views.teacher_session, name='teacher_session'),
    path('t/<str:code>/records.json', views.session_records_json, name='session_records_json'),
    path('t/<str:code>/delete', views.delete_record, name='delete_record'),
    path('qr/<str:code>.png', views.qr_image, name='qr_image'),
    path('scan/<str:code>', views.scan, name='scan'),
    path('stop/<str:code>', views.stop_session, name='stop_session'),
]

