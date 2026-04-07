from django.contrib import admin

# Register your models here.


from .models import Staff, Task, TaskPause, LeaveRequest


# ✅ Staff Admin
@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('id', 'authuser', 'phone')
    search_fields = ('authuser__username', 'phone')


# ✅ TaskPause Inline (shows pauses inside Task)
class TaskPauseInline(admin.TabularInline):
    model = TaskPause
    extra = 0


# ✅ Task Admin
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'staff', 'status', 'assigned_by', 'total_time')
    list_filter = ('status', 'assigned_by')
    search_fields = ('title', 'staff__authuser__username')
    inlines = [TaskPauseInline]


# ✅ TaskPause Admin (optional standalone view)
@admin.register(TaskPause)
class TaskPauseAdmin(admin.ModelAdmin):
    list_display = ('task', 'pause_start', 'pause_end')
    search_fields = ('task__title',)


# ✅ Leave Request Admin
@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('staff', 'from_date', 'to_date', 'status')
    list_filter = ('status',)
    search_fields = ('staff__authuser__username',)