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


def assign_task(request):
    staff_list = Staff.objects.all()

    if request.method == "POST":
        staff_id = request.POST.get('staff')
        title = request.POST.get('title')
        description = request.POST.get('description')

        staff = Staff.objects.get(id=staff_id)

        Task.objects.create(
            staff=staff,
            title=title,
            description=description
        )

        return redirect('assign_task')

    return render(request, 'assign_task.html', {'staff_list': staff_list})



def my_tasks(request):
    staff = Staff.objects.get(authuser=request.user)
    tasks = Task.objects.filter(staff=staff)
    return render(request, 'my_tasks.html', {'tasks': tasks})

def start_task(request, id):
    task = get_object_or_404(Task, id=id)
    if task.status == 'pending':
        task.start_time = timezone.now()
        task.status = 'started'
    elif task.status == 'paused':
        if task.pause_time:
            pause_duration = timezone.now() - task.pause_time
            task.total_pause += pause_duration
        task.pause_time = None
        task.status = 'started'
    task.save()
    return redirect('my_tasks')

def pause_task(request, id):
    task = get_object_or_404(Task, id=id)
    if task.status == 'started':
        task.pause_time = timezone.now()
        task.status = 'paused'
        task.save()
    return redirect('my_tasks')

def stop_task(request, id):
    task = get_object_or_404(Task, id=id)
    if task.start_time:
        task.end_time = timezone.now()
        total = task.end_time - task.start_time - task.total_pause
        if total.total_seconds() < 0:
            total = timedelta(0)
        task.total_time = total
        task.status = 'completed'
        task.save()

    return redirect('my_tasks')

@staff_member_required
def admin_task_view(request):

    tasks = Task.objects.select_related('staff').all().order_by('-id')

    return render(request, 'admin_tasks.html', {'tasks': tasks})