from myapp.models import LeaveRequest
from myapp.models import Staff
from django.shortcuts import render
from datetime import datetime
from django.shortcuts import redirect, render,get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from myapp.models import * 
from django.contrib.auth.models import User,Group
from django.contrib.auth import authenticate,login, update_session_auth_hash
from myapp.models import *
from django.contrib.auth import authenticate, login,logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
# Create your views here.
def home(request):
    return render(request,'home.html')

def loginn(request):
    return render(request,'login.html')
def user_login_post(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            messages.error(request, "Both fields are required")
            return redirect('user_login')
        user = authenticate(request, username=username, password=password)
        if user is None:
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Invalid email or password")
            return redirect('user_login')

    return redirect('user_login')

def user_logout(request):
    logout(request)
    return redirect('user_login')

def staff_list(request):
    staff = Staff.objects.filter(authuser__is_superuser=False)
    return render(request, 'staff_list.html', {'staff': staff})
def staff_add(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        image = request.FILES.get('image')

        if User.objects.filter(username=username).exists():
            return render(request, 'staff_add.html', {'error': 'Username already exists'})

        if User.objects.filter(email=email).exists():
            return render(request, 'staff_add.html', {'error': 'Email already exists'})

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.is_staff = True 
        user.save()

        Staff.objects.create(
            authuser=user,
            phone=phone,
            address=address,
            image=image
        )

        return redirect('staff_list')

    return render(request, 'staff_add.html')

def staff_edit(request, id):
    staff = get_object_or_404(Staff, id=id)
    user = staff.authuser

    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')

        password = request.POST.get('password')
        if password:
            user.set_password(password)

        staff.phone = request.POST.get('phone')
        staff.address = request.POST.get('address')

        image = request.FILES.get('image')
        if image:
            staff.image = image

        user.save()
        staff.save()

        return redirect('staff_list')

    return render(request, 'staff_edit.html', {'staff': staff})

def staff_delete(request, id):
    staff = get_object_or_404(Staff, id=id)
    staff.authuser.delete()
    return redirect('staff_list')

@login_required(login_url='user_login')
def profile(request):
    staff, created = Staff.objects.get_or_create(authuser=request.user)

    if request.method == "POST":
        if 'name' in request.POST:
            staff.name = request.POST.get('name')
            staff.phone = request.POST.get('phone')
            staff.address = request.POST.get('address')
            staff.role = request.POST.get('role')
            staff.save()
            return JsonResponse({"status": "ok"})
        if request.FILES.get('image'):
            staff.image = request.FILES.get('image')
            staff.save()
            return JsonResponse({"status": "ok"})
        if 'old_password' in request.POST:
            old_password = request.POST.get('old_password')
            new_password = request.POST.get('new_password')

            user = request.user

            if not user.check_password(old_password):
                return JsonResponse({
                    "status": "error",
                    "message": "Old password is incorrect"
                })

            user.set_password(new_password)
            user.save()

            update_session_auth_hash(request, user)

            return JsonResponse({"status": "ok"})

        return JsonResponse({"status": "error"})

    return render(request, 'user-profile.html', {'staff': staff})



@login_required(login_url='user_login')
def assign_task(request):
    staff_list = Staff.objects.exclude(authuser__username='admin')

    if request.method == "POST":
        staff_id = request.POST.get('staff')
        title = request.POST.get('title')
        description = request.POST.get('description')

        hours = request.POST.get('hours')
        minutes = request.POST.get('minutes')

        expected_time = timedelta(
            hours=int(hours or 0),
            minutes=int(minutes or 0)
        )

        staff = Staff.objects.get(id=staff_id)

        Task.objects.create(
            staff=staff,
            title=title,
            description=description,
            expected_time=expected_time,  
            assigned_by=request.user  
        )

        return redirect('assign_task')

    return render(request, 'assign_task.html', {'staff_list': staff_list})

@login_required(login_url='user_login')
def my_tasks(request):
    staff = Staff.objects.get(authuser=request.user)
    tasks = Task.objects.filter(staff=staff).prefetch_related('pauses')
    return render(request, 'my_tasks.html', {'tasks': tasks})


@login_required(login_url='user_login')
def start_task(request, id):
    task = get_object_or_404(Task, id=id)

    if task.status == 'pending':
        task.start_time = timezone.now()
        task.status = 'started'

    elif task.status == 'paused':
        now = timezone.now()
        open_pause = task.pauses.filter(pause_end__isnull=True).last()
        if open_pause:
            open_pause.pause_end = now
            open_pause.save()
        total_pause = sum(
            (p.duration for p in task.pauses.all() if p.pause_end),
            timedelta()
        )
        task.total_pause = total_pause
        task.pause_time = None
        task.status = 'started'

    task.save()
    return redirect('my_tasks')


@login_required(login_url='user_login')
def pause_task(request, id):
    task = get_object_or_404(Task, id=id)
    if task.status == 'started':
        now = timezone.now()
        task.pause_time = now
        task.status = 'paused'
        task.save()
        TaskPause.objects.create(task=task, pause_start=now)
    return redirect('my_tasks')


@login_required(login_url='user_login')
def stop_task(request, id):
    task = get_object_or_404(Task, id=id)
    if task.start_time:
        now = timezone.now()
        if task.status == 'paused':
            open_pause = task.pauses.filter(pause_end__isnull=True).last()
            if open_pause:
                open_pause.pause_end = now
                open_pause.save()

        total_pause = sum(
            (p.duration for p in task.pauses.all() if p.pause_end),
            timedelta()
        )
        task.total_pause = total_pause
        task.end_time = now
        total_time = task.end_time - task.start_time
        worked_time = total_time - total_pause

        task.total_time = max(total_time, timedelta(0))
        task.worked_time = max(worked_time, timedelta(0))

        if task.expected_time and task.worked_time > task.expected_time:
            task.exceeded_time = task.worked_time - task.expected_time
            task.status = 'exceeded'
        else:
            task.exceeded_time = None
            task.status = 'completed'

        task.save()
    return redirect('my_tasks')


@login_required(login_url='user_login')
def auto_stop_exceeded_tasks(request):
    now = timezone.now()
    stopped = []

    started_tasks = Task.objects.filter(status='started', expected_time__isnull=False)

    for task in started_tasks:
        if not task.start_time:
            continue

        total_pause = task.total_pause or timedelta(0)
        worked = now - task.start_time - total_pause

        if worked >= task.expected_time:
            open_pause = task.pauses.filter(pause_end__isnull=True).last()
            if open_pause:
                open_pause.pause_end = now
                open_pause.save()

            total_pause = sum(
                (p.duration for p in task.pauses.all() if p.pause_end),
                timedelta()
            )
            task.total_pause = total_pause
            task.end_time = now
            total_time = task.end_time - task.start_time
            worked_time = total_time - total_pause

            task.total_time = max(total_time, timedelta(0))
            task.worked_time = max(worked_time, timedelta(0))
            task.exceeded_time = task.worked_time - task.expected_time
            task.status = 'exceeded'
            task.save()
            stopped.append(task.id)

    return JsonResponse({'auto_stopped': stopped})


def task_status_api(request):
    tasks = Task.objects.all()
    data = []
    for t in tasks:
        data.append({
            "id": t.id,
            "status": t.status,
            "start": t.start_time.isoformat() if t.start_time else None,
            "end": t.end_time.isoformat() if t.end_time else None,
            "pause": t.pause_time.isoformat() if t.pause_time else None,
            "total_pause": int(t.total_pause.total_seconds()) if t.total_pause else 0,
            "total_time": int(t.total_time.total_seconds()) if t.total_time else 0,
            "worked_time": int(t.worked_time.total_seconds()) if t.worked_time else 0,
        })
    return JsonResponse({'tasks': data})

@staff_member_required
def admin_task_view(request):
    tasks = Task.objects.select_related('staff', 'assigned_by').all().order_by('-id')
    return render(request, 'admin_tasks.html', {'tasks': tasks})


def task_detail(request, id):
    task = get_object_or_404(Task.objects.prefetch_related('pauses'), id=id)

    pauses = task.pauses.all()

    context = {
        'task': task,
        'pauses': pauses,
        'pause_count': pauses.count(),
    }

    return render(request, 'task_detail.html', context)

@login_required
def apply_leave(request):
    if request.method == 'POST':
        try:
            staff = Staff.objects.get(authuser=request.user)
            reason = request.POST.get('reason')
            from_date = request.POST.get('from_date')
            to_date = request.POST.get('to_date')
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
            if from_date > to_date:
                messages.error(request, "From date cannot be after To date!")
                return redirect('apply_leave')
            LeaveRequest.objects.create(
                staff=staff,
                reason=reason,
                from_date=from_date,
                to_date=to_date
            )
            messages.success(request, "Leave request submitted successfully!")
            return redirect('my_leave')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('apply_leave')
    return render(request, 'apply_leave.html')

@login_required
def my_leave(request):
    try:
        staff = Staff.objects.get(authuser=request.user)
        leaves = LeaveRequest.objects.filter(staff=staff).order_by('-id')
    except Staff.DoesNotExist:
        leaves = []
    return render(request, 'my_leave.html', {'leaves': leaves})

@login_required
def leave_requests(request):
    leaves = LeaveRequest.objects.all().order_by('-id')
    return render(request, 'admin leave_requests.html', {'leaves': leaves})

@login_required
def approve_leave(request, id):
    leave = get_object_or_404(LeaveRequest, id=id)

    if leave.status == 'pending':
        leave.status = 'approved'
        leave.save()
        messages.success(request, "Leave approved successfully!")
    else:
        messages.warning(request, "This leave is already processed.")
    return redirect('leave_requests')

@login_required
def reject_leave(request, id):
    leave = get_object_or_404(LeaveRequest, id=id)
    if leave.status == 'pending':
        leave.status = 'rejected'
        leave.save()
        messages.success(request, "Leave rejected.")
    else:
        messages.warning(request, "This leave is already processed.")

    return redirect('leave_requests')

@login_required
def get_notifications(request):
    try:
        staff = Staff.objects.get(authuser=request.user)
        tasks = Task.objects.filter(staff=staff).order_by('-id')[:20]
        seen_ids = request.session.get('seen_task_ids', [])
        unread = sum(1 for t in tasks if t.id not in seen_ids)
        data = [
            {
                'id': t.id,
                'message': f"Task assigned: {t.title}",
                'status': t.status,
                'is_read': t.id in seen_ids,
            }
            for t in tasks
        ]
        return JsonResponse({'notifications': data, 'unread': unread})
    except Staff.DoesNotExist:
        return JsonResponse({'notifications': [], 'unread': 0})


@login_required
def mark_notifications_read(request):
    try:
        staff = Staff.objects.get(authuser=request.user)
        task_ids = list(Task.objects.filter(staff=staff).values_list('id', flat=True))
        request.session['seen_task_ids'] = task_ids
        request.session.modified = True
        return JsonResponse({'status': 'ok'})
    except Staff.DoesNotExist:
        return JsonResponse({'status': 'error'}, status=400)