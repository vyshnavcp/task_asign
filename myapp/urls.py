
from unicodedata import name
from django.urls import include, path
from myapp import views
urlpatterns = [
    path('',views.home,name='home'),
    path('loginn/',views.loginn,name='user_login'),
    path('user_login_post/',views.user_login_post,name='user_login_post'),
    path('user_logout/',views.user_logout,name='user_logout'),
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_add, name='staff_add'),
    path('staff/edit/<int:id>/', views.staff_edit, name='staff_edit'),
    path('staff/delete/<int:id>/', views.staff_delete, name='staff_delete'),
    path('profile/',views.profile, name='profile'),
    path('assign-task/', views.assign_task, name='assign_task'),
    path('my-tasks/', views.my_tasks, name='my_tasks'),
    path('start/<int:id>/', views.start_task, name='start_task'),
    path('pause/<int:id>/', views.pause_task, name='pause_task'),
    path('stop/<int:id>/', views.stop_task, name='stop_task'),
    path('request-extension/<int:task_id>/', views.request_extension,name='request_extension'),
    path('extension-requests/', views.admin_extension_requests, name='admin_extension_requests'),
    path('extension-approve/<int:req_id>/', views.approve_extension, name='approve_extension'),
    path('extension-reject/<int:req_id>/',  views.reject_extension, name='reject_extension'),
    path('admin_task_view/',views.admin_task_view,name='admin_task_view'),
    path('task-detail/<int:id>/', views.task_detail, name='task_detail'),
    path('apply-leave/', views.apply_leave, name='apply_leave'),
    path('my-leave/', views.my_leave, name='my_leave'),
    path('leave-requests/', views.leave_requests, name='leave_requests'),
    path('approve-leave/<int:id>/', views.approve_leave, name='approve_leave'),
    path('reject-leave/<int:id>/', views.reject_leave, name='reject_leave'),
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('task-status-api/', views.task_status_api),
    path('auto-stop-exceeded/', views.auto_stop_exceeded_tasks, name='auto_stop_exceeded'),

]
