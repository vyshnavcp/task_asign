from myapp.models import Invoice
from myapp.models import Proposal
from myapp.models import Client
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
from django.urls import reverse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
# Create your views here.
def home(request):
    return render(request,'home.html')



@login_required
def global_search_api(request):
    q = request.GET.get('q', '').strip().lower()
    if not q:
        return JsonResponse([], safe=False)

    data = []

    for s in Staff.objects.select_related('authuser').all():
        label = s.authuser.get_full_name() or s.authuser.username
        if q in label.lower() or q in (s.phone or '').lower():
            data.append({
                'label': label,
                'type': 'Staff',
                'url': reverse('staff_list')
            })

    for t in Task.objects.select_related('staff__authuser').all():
        label = f'{t.title} — {t.staff.authuser.username}'
        if q in label.lower() or q in t.status.lower():
            data.append({
                'label': label,
                'type': 'Task',
                'url': reverse('task_detail', args=[t.id])
            })

    for c in Client.objects.all():
        label = f'{c.name} — {c.company_name}'
        if q in label.lower() or q in (c.phone or '').lower() or q in (c.email or '').lower():
            data.append({
                'label': label,
                'type': 'Client',
                'url': reverse('client_list')
            })

    for p in Proposal.objects.select_related('client').all():
        label = f'{p.proposal_number} — {p.client.name} — ₹{p.total_amount}'
        if q in label.lower() or q in p.status.lower() or q in str(p.total_amount):
            data.append({
                'label': label,
                'type': 'Proposal',
                'url': reverse('proposal_list')
            })

    return JsonResponse(data[:15], safe=False)

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
        task.total_pause = timedelta(0)
        task.pause_time = None
        task.save()

    elif task.status == 'paused':
        latest_ext = task.extension_requests.order_by('-requested_on').first()

        is_first_extension_resume = (
            latest_ext is not None
            and latest_ext.status == 'approved'
            and task.worked_before_extension is not None
            and not task.extension_resumed
        )

        if not is_first_extension_resume:
            open_pause = task.pauses.filter(pause_end__isnull=True).last()
            if open_pause:
                open_pause.pause_end = now
                open_pause.save()

        if is_first_extension_resume:
            # Save previous work before starting extension
            task.worked_before_extension = task.worked_time or timedelta(0)

            # Start fresh session
            task.start_time = now
            task.pause_time = None
            task.total_pause = timedelta(0)
            task.worked_time = timedelta(0)

            task.status = 'started'
            task.extension_resumed = True

        else:
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
        if task.start_time:
            total_pause_so_far = task.total_pause or timedelta(0)
            session_worked = now - task.start_time - total_pause_so_far
            session_worked = max(session_worked, timedelta(0))
            prior = task.worked_before_extension or timedelta(0)

            if task.extension_resumed:
                task.worked_time = session_worked
            else:
                task.worked_time = prior + session_worked

        task.pause_time = now
        task.status = 'paused'
        task.save()
        if not task.extension_resumed and task.status != 'exceeded':
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
    prior        = task.worked_before_extension or timedelta(0)
    total_worked = prior + session_worked

    task.total_time  = total_time
    task.worked_time = total_worked
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

    task_id = request.GET.get('task_id')
    started_tasks = Task.objects.filter(
        id=task_id,
        status='started',
        expected_time__isnull=False
    ).prefetch_related('pauses')

    for task in started_tasks:
        if not task.start_time:
            continue

        if task.extension_resumed:
            total_pause = timedelta(0)
        else:
            total_pause = task.total_pause or timedelta(0)
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
    task.worked_before_extension = task.worked_time or timedelta(0)
    task.expected_time = ext_req.requested_extra_time
    task.extension_resumed = False
    task.status        = 'paused'
    task.pause_time    = now
    task.end_time      = None
    task.exceeded_time = None
    task.save()
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

def client_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        company = request.POST.get('company_name')
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        email = request.POST.get('email')

        Client.objects.create(
            name=name,
            company_name=company,
            address=address,
            phone=phone,
            email=email
        )
        return redirect('client_list')

    return render(request, 'client_form.html')

def client_list(request):
    clients = Client.objects.all().order_by('id')
    return render(request,'client_list.html',{'clients':clients})


     
def client_delete(request,id):
    client=get_object_or_404(Client,id=id)
    client.delete()
    return redirect('client_list')

def generate_proposal_number():
    last = Proposal.objects.order_by('-id').first()
    if last:
        try:
            last_number = int(last.proposal_number.split('-')[-1])
        except:
            last_number = 0
        new_number = last_number + 1
    else:
        new_number = 1
    return f"PROP-{new_number:04d}"

def get_client(request):
    client_id = request.GET.get('client_id')
    client = get_object_or_404(Client, id=client_id)

    return JsonResponse({
        'name': client.name,
        'address': client.address
    })

def create_proposal(request):
    clients = Client.objects.all()

    if request.method == "POST":
        client_id = request.POST.get('client')

        proposal = Proposal.objects.create(
            client_id=client_id,
            proposal_number=generate_proposal_number(),
            proposal_title=request.POST.get('proposal_title'),
            overview=request.POST.get('overview'),
        )

        service_names = request.POST.getlist('service_name[]')
        quantities = request.POST.getlist('quantity[]')
        amounts = request.POST.getlist('amount[]')
        details = request.POST.getlist('service_detail[]')

        total = 0

        for i in range(len(service_names)):
            qty = int(quantities[i]) if quantities[i] else 0
            amt = float(amounts[i]) if amounts[i] else 0

            item = ProposalItem.objects.create(
                proposal=proposal,
                service_name=service_names[i],
                service_detail=details[i],
                quantity=qty,
                amount=amt,
            )

            total += item.line_total

        proposal.total_amount = total
        proposal.save()

        return redirect('proposal_list')

    return render(request, 'proposal_form.html', {
        'clients': clients,
        'proposal_number': generate_proposal_number(),
    })


from django.http import JsonResponse
from .models import Proposal

def proposal_list_api(request):

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        proposals = (
            Proposal.objects
            .select_related('client')
            .prefetch_related('items')
            .order_by('-id')
        )

        data = []
        for p in proposals:

            # ✅ CHECK IF INVOICE EXISTS
            has_invoice = hasattr(p, 'invoice') and p.invoice is not None

            data.append({
                'id': p.id,
                'proposal_number': p.proposal_number,
                'proposal_title': p.proposal_title or '',
                'client_name': p.client.name if p.client else '',
                'total_amount': str(p.total_amount),
                'status': p.status,
                'date': p.date.strftime('%Y-%m-%d') if p.date else '',

                # ✅ FIXED
                'has_invoice': has_invoice,
                'invoice_id': p.invoice.id if has_invoice else None,
            })

        return JsonResponse({'proposals': data})

    return render(request, 'proposal_list.html')


def proposal_delete(request,id):
    proposal=get_object_or_404(Proposal,id=id)
    proposal.delete()
    return redirect('proposal_list')

def proposal_view(request, id):
    proposal = get_object_or_404(
        Proposal.objects.prefetch_related('items', 'client'),
        id=id
    )
    return render(request, 'proposal_view.html', {'proposal': proposal})

def proposal_print(request, id):
    proposal = get_object_or_404(
        Proposal.objects.prefetch_related('items', 'client'),
        id=id
    )
    services = CompanyService.objects.all()  
    return render(request, 'proposal_print.html', {
        'proposal': proposal,
        'services': services,   
    })

def edit_proposal(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    clients = Client.objects.all()

    if request.method == "POST":
        proposal.client_id = request.POST.get('client')
        proposal.proposal_title = request.POST.get('proposal_title')
        proposal.overview = request.POST.get('overview')
        proposal.status = request.POST.get('status') or 'draft'

        # delete old items
        proposal.items.all().delete()

        service_names = request.POST.getlist('service_name[]')
        quantities = request.POST.getlist('quantity[]')
        amounts = request.POST.getlist('amount[]')
        details = request.POST.getlist('service_detail[]')

        total = 0

        for i in range(len(service_names)):
            if service_names[i]:  # avoid empty rows
                qty = int(quantities[i]) if quantities[i] else 0
                amt = float(amounts[i]) if amounts[i] else 0

                item = ProposalItem.objects.create(
                    proposal=proposal,
                    service_name=service_names[i],
                    service_detail=details[i],
                    quantity=qty,
                    amount=amt,
                )

                total += item.line_total

        proposal.total_amount = total
        proposal.save()

        return redirect('proposal_list')

    return render(request, 'proposal_form_edit.html', {
        'proposal': proposal,
        'clients': clients,
    })

def add_service(request):
    if request.method == "POST":
        title = request.POST.get('title')
        description = request.POST.get('description')

        CompanyService.objects.create(
            title=title,
            description=description
        )
        return redirect('service_list')

    return render(request, 'service_form.html')

def service_list(request):
    services = CompanyService.objects.all()
    return render(request, 'service_list.html', {'services': services})

def convert_to_invoice(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)

    # prevent duplicate
    if hasattr(proposal, 'invoice'):
        return redirect('view_invoice', pk=proposal.invoice.id)

    invoice = Invoice.objects.create(
        proposal=proposal,
        client=proposal.client,
        total_amount=proposal.total_amount,
        status='unpaid'
    )
    for item in proposal.items.all():
        InvoiceItem.objects.create(
            invoice=invoice,
            service_name=item.service_name,
            service_detail=item.service_detail,
            quantity=item.quantity,
            amount=item.amount
        )

    return redirect('view_invoice', pk=invoice.id)

def view_invoice(request,pk):
    invoice = get_object_or_404(Invoice,pk=pk)
    return render(request,'invoice_view.html',{'invoice':invoice})

def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    template = get_template('invoice_pdf.html')
    html = template.render({'invoice': invoice})

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'filename="invoice_{invoice.invoice_number}.pdf"'

    pisa.CreatePDF(BytesIO(html.encode("UTF-8")), dest=response)
    return response

def invoice_list(request):
    invoices = Invoice.objects.select_related('client').prefetch_related('items').order_by('-id')
    return render(request, 'invoice_list.html', {'invoices': invoices})


def create_invoice(request):
    clients = Client.objects.all()

    if request.method == 'POST':
        client_id = request.POST.get('client')
        due_date = request.POST.get('due_date')
        invoice = Invoice(
            client_id=client_id,
            due_date=due_date,
            status='unpaid'
        )
        invoice.save()  
        names = request.POST.getlist('service_name[]')
        details = request.POST.getlist('service_detail[]')
        qtys = request.POST.getlist('quantity[]')
        amounts = request.POST.getlist('amount[]')

        total = 0

        for i in range(len(names)):
            if names[i]:
                qty = int(qtys[i]) if qtys[i] else 1
                amt = float(amounts[i]) if amounts[i] else 0

                item = InvoiceItem.objects.create(
                    invoice=invoice,
                    service_name=names[i],
                    service_detail=details[i],
                    quantity=qty,
                    amount=amt
                )

                total += item.line_total
        invoice.total_amount = total
        invoice.save()

        return redirect('view_invoice', pk=invoice.id)

    return render(request, 'create_invoice.html', {
        'clients': clients
    })
    
def edit_invoice(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    clients = Client.objects.all()

    if request.method == 'POST':
        invoice.client_id = request.POST.get('client')
        invoice.due_date = request.POST.get('due_date')
        invoice.status = request.POST.get('status')
        invoice.save()
        invoice.items.all().delete()
        names = request.POST.getlist('service_name[]')
        details = request.POST.getlist('service_detail[]')
        qtys = request.POST.getlist('quantity[]')
        amounts = request.POST.getlist('amount[]')

        total = 0
        for i in range(len(names)):
            if names[i]:
                qty = int(qtys[i]) if qtys[i] else 1
                amt = float(amounts[i]) if amounts[i] else 0

                item = InvoiceItem.objects.create(
                    invoice=invoice,
                    service_name=names[i],
                    service_detail=details[i],
                    quantity=qty,
                    amount=amt
                )

                total += item.line_total


        invoice.total_amount = total
        invoice.save()

        return redirect('view_invoice', pk=invoice.id)

    return render(request, 'edit_invoice.html', {
        'invoice': invoice,
        'clients': clients
    })
    
@login_required
def delete_invoice(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    invoice.delete()
    return redirect('invoice_list')