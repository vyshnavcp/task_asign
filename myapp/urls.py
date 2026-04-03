
from unicodedata import name
from django.urls import include, path
from myapp import views
urlpatterns = [
    path('',views.home,name='home'),
    path('loginn/',views.loginn,name='user_login'),
    path('user_login_post/',views.user_login_post,name='user_login_post'),
    path('user_logout/',views.user_logout,name='user_logout'),
    path('staff/', views.staff_list, name='staff_list'),
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
    path('admin_task_view/',views.admin_task_view,name='admin_task_view')

]
