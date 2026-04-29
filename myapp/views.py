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
    tasks = list(
        Task.objects.filter(staff=staff)
            .prefetch_related('pauses', 'extension_requests')
    )
    for task in tasks:
        task.ext_req = task.extension_requests.order_by('-requested_on').first()
        task.awaiting_ext_resume = (
            task.status == 'paused'
            and task.ext_req is not None
            and task.ext_req.status == 'approved'
            and task.worked_before_extension is not None
            and not task.extension_resumed       
        )
    return render(request, 'my_tasks.html', {'tasks': tasks})


@login_required(login_url='user_login')
def start_task(request, id):
    task = get_object_or_404(Task, id=id)
    now = timezone.now()

    if task.status == 'pending':
        task.start_time = now
        task.status = 'started'

    elif task.status == 'paused':
        # Close any open pause record first
        open_pause = task.pauses.filter(pause_end__isnull=True).last()
        if open_pause:
            open_pause.pause_end = now
            open_pause.save()

        # ── Determine if this is the FIRST resume after extension approval ────
        #
        # extension_resumed=False → first-time "Continue Task" click → fresh clock
        # extension_resumed=True  → normal mid-session resume → keep accumulated time
        #
        latest_ext = task.extension_requests.order_by('-requested_on').first()
        is_first_extension_resume = (
            latest_ext is not None
            and latest_ext.status == 'approved'
            and task.worked_before_extension is not None
            and not task.extension_resumed           # ← only True on FIRST resume
        )

        if is_first_extension_resume:
            # ── Fresh clock for the extension window ──────────────────────────
            # Timer counts from 0 up to expected_time (= extra time granted).
            # worked_time is cleared so the JS timer shows the live extension tick.
            # worked_before_extension holds the pre-extension total for stop_task.
            task.start_time      = now
            task.total_pause     = timedelta(0)
            task.pause_time      = None
            task.worked_time     = None        # cleared → JS ticks from 0
            task.status          = 'started'
            task.extension_resumed = True      # ← mark as resumed; no more fresh-clock resets

        else:
            # ── Normal resume (including mid-extension-session pause/resume) ──
            # Recompute total_pause from all closed pause records.
            total_pause = sum(
                (p.duration for p in task.pauses.all() if p.pause_end),
                timedelta()
            )
            task.total_pause = total_pause
            task.pause_time  = None
            task.status      = 'started'
            # Note: worked_time stays None during extension session (set on complete).
            # During normal flow, worked_time is also None until complete.

    task.save()
    return redirect('my_tasks')


@login_required(login_url='user_login')
def pause_task(request, id):
    task = get_object_or_404(Task, id=id)
    if task.status == 'started':
        now = timezone.now()

        # ── Compute current worked time and save it ───────────────────────────
        # This is the KEY FIX for the "paused shows 0h 00m 00s" bug.
        # We calculate how much was worked in this session and save it to worked_time
        # so the paused display can show the correct time from the DB.
        if task.start_time:
            total_pause_so_far = task.total_pause or timedelta(0)
            session_worked = now - task.start_time - total_pause_so_far
            session_worked = max(session_worked, timedelta(0))

            # If in extension session, total worked = prior + this session
            prior = task.worked_before_extension or timedelta(0)

            if task.extension_resumed:
                # In extension session: save only the extension session time
                # (JS timer shows 0 → expected_time, so worked_time = session only)
                task.worked_time = session_worked
            else:
                # Normal session: total = prior (0 usually) + session
                task.worked_time = prior + session_worked

        task.pause_time = now
        task.status = 'paused'
        task.save()
        TaskPause.objects.create(task=task, pause_start=now)
    return redirect('my_tasks')


@login_required(login_url='user_login')
def stop_task(request, id):
    task = get_object_or_404(Task, id=id)
    if not task.start_time:
        return redirect('my_tasks')

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
    task.end_time    = now
    total_time       = task.end_time - task.start_time
    session_worked   = max(total_time - total_pause, timedelta(0))

    # Total = previous sessions (before extension) + current session
    prior        = task.worked_before_extension or timedelta(0)
    total_worked = prior + session_worked

    task.total_time  = total_time
    task.worked_time = total_worked

    # Compare against the full expected time.
    # After extension: expected_time = extra time only.
    # Full expected = worked_before_extension + expected_time.
    full_expected = prior + (task.expected_time or timedelta(0))

    if task.expected_time and total_worked > full_expected:
        task.exceeded_time = total_worked - full_expected
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

    started_tasks = Task.objects.filter(
        status='started', expected_time__isnull=False
    ).prefetch_related('pauses')

    for task in started_tasks:
        if not task.start_time:
            continue

        total_pause    = task.total_pause or timedelta(0)
        session_worked = now - task.start_time - total_pause
        prior          = task.worked_before_extension or timedelta(0)

        if session_worked >= task.expected_time:
            open_pause = task.pauses.filter(pause_end__isnull=True).last()
            if open_pause:
                open_pause.pause_end = now
                open_pause.save()

            total_pause = sum(
                (p.duration for p in task.pauses.all() if p.pause_end),
                timedelta()
            )
            task.total_pause   = total_pause
            task.end_time      = now
            total_time         = task.end_time - task.start_time
            session_worked     = max(total_time - total_pause, timedelta(0))
            total_worked       = prior + session_worked
            full_expected      = prior + task.expected_time

            task.total_time    = total_time
            task.worked_time   = total_worked
            task.exceeded_time = total_worked - full_expected
            task.status        = 'exceeded'
            task.save()
            stopped.append(task.id)

    return JsonResponse({'auto_stopped': stopped})


@login_required(login_url='user_login')
def request_extension(request, task_id):
    task  = get_object_or_404(Task, id=task_id)
    staff = get_object_or_404(Staff, authuser=request.user)

    if task.staff != staff:
        messages.error(request, "You are not authorised to request an extension for this task.")
        return redirect('my_tasks')

    if task.status != 'exceeded':
        messages.error(request, "Extension requests are only allowed for exceeded tasks.")
        return redirect('my_tasks')

    pending_exists = task.extension_requests.filter(status='pending').exists()
    if pending_exists:
        messages.warning(request, "You already have a pending extension request for this task.")
        return redirect('my_tasks')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        hours  = int(request.POST.get('extra_hours',  0) or 0)
        mins   = int(request.POST.get('extra_minutes', 0) or 0)

        if not reason:
            messages.error(request, "Please provide a reason.")
            return render(request, 'request_extension.html', {'task': task})

        if hours == 0 and mins == 0:
            messages.error(request, "Please request at least 1 minute of extra time.")
            return render(request, 'request_extension.html', {'task': task})

        TimeExtensionRequest.objects.create(
            task=task, staff=staff, reason=reason,
            requested_extra_time=timedelta(hours=hours, minutes=mins),
        )
        messages.success(request, "Extension request submitted successfully.")
        return redirect('my_tasks')

    return render(request, 'request_extension.html', {'task': task})


# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN VIEWS
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='user_login')
def admin_extension_requests(request):
    if not request.user.is_staff:
        return redirect('my_tasks')

    requests_qs = TimeExtensionRequest.objects.select_related(
        'task', 'staff__authuser'
    ).order_by('-requested_on')

    return render(request, 'admin_extension_requests.html',
                  {'extension_requests': requests_qs})


@login_required(login_url='user_login')
def approve_extension(request, req_id):
    if not request.user.is_staff:
        return redirect('my_tasks')

    ext_req = get_object_or_404(TimeExtensionRequest, id=req_id)

    if ext_req.status != 'pending':
        messages.warning(request, "This request has already been reviewed.")
        return redirect('admin_extension_requests')

    task = ext_req.task
    now  = timezone.now()

    # ── Store how much was already worked ─────────────────────────────────────
    task.worked_before_extension = task.worked_time or timedelta(0)

    # ── Set expected_time = ONLY the extra time granted ───────────────────────
    task.expected_time = ext_req.requested_extra_time

    # ── Reset extension_resumed so "Continue Task" shows again ───────────────
    # This is important if this is a SECOND extension on the same task.
    task.extension_resumed = False

    # ── Pause so staff must click "Continue Task" ─────────────────────────────
    task.status        = 'paused'
    task.pause_time    = now
    task.end_time      = None
    task.exceeded_time = None
    # Keep worked_time so the paused display shows historical time
    task.save()

    # Open pause record — closed when staff resumes
    TaskPause.objects.create(task=task, pause_start=now)

    ext_req.status      = 'approved'
    ext_req.reviewed_on = now
    ext_req.save()

    messages.success(
        request,
        f"Extension approved (+{ext_req.requested_extra_time}). "
        f"Staff can now resume task '{task.title}'."
    )
    return redirect('admin_extension_requests')


@login_required(login_url='user_login')
def reject_extension(request, req_id):
    if not request.user.is_staff:
        return redirect('my_tasks')

    ext_req = get_object_or_404(TimeExtensionRequest, id=req_id)

    if ext_req.status != 'pending':
        messages.warning(request, "This request has already been reviewed.")
        return redirect('admin_extension_requests')

    remark = request.POST.get('admin_remark', '').strip()
    ext_req.status       = 'rejected'
    ext_req.admin_remark = remark or None
    ext_req.reviewed_on  = timezone.now()
    ext_req.save()

    messages.success(request, "Extension request rejected.")
    return redirect('admin_extension_requests')

 
 
def task_status_api(request):
    tasks = Task.objects.all()
    data = []
    for t in tasks:
        data.append({
            "id": t.id,
            "status": t.status,
            "start": t.start_time.isoformat() if t.start_time else None,
            "end":   t.end_time.isoformat()   if t.end_time   else None,
            "pause": t.pause_time.isoformat()  if t.pause_time else None,
            "total_pause":  int(t.total_pause.total_seconds())  if t.total_pause  else 0,
            "total_time":   int(t.total_time.total_seconds())   if t.total_time   else 0,
            "worked_time":  int(t.worked_time.total_seconds())  if t.worked_time  else 0,
        })
    return JsonResponse({'tasks': data})
 

@staff_member_required
def admin_task_view(request):
    tasks = Task.objects.select_related(
        'staff__authuser', 'assigned_by'
    ).prefetch_related(
        'extension_requests'      
    ).all().order_by('-id')
    for task in tasks:
        task.latest_ext = task.extension_requests.order_by('-requested_on').first()
    return render(request, 'admin_tasks.html', {'tasks': tasks})

def task_detail(request, id):
    task = get_object_or_404(Task.objects.prefetch_related('pauses', 'extension_requests'), id=id)
    pauses = task.pauses.all()
    extension_requests = task.extension_requests.all().order_by('-requested_on')

    context = {
        'task': task,
        'pauses': pauses,
        'pause_count': pauses.count(),
        'extension_requests': extension_requests,
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