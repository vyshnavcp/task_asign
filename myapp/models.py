from email.policy import default
from enum import unique
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone

User = get_user_model()


class Staff(models.Model):
    authuser = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    image = models.ImageField(upload_to='staff_images/', null=True, blank=True)

    def __str__(self):
        return self.authuser.username


class Task(models.Model):
    STATUS_CHOICES = (
        ('pending',   'Pending'),
        ('started',   'Started'),
        ('paused',    'Paused'),
        ('completed', 'Completed'),
        ('exceeded',  'Exceeded'),
    )

    staff = models.ForeignKey('Staff', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    pause_time = models.DateTimeField(null=True, blank=True)
    total_pause = models.DurationField(default=timedelta(seconds=0))
    total_time = models.DurationField(null=True, blank=True)
    worked_time = models.DurationField(null=True, blank=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='assigned_tasks')
    expected_time = models.DurationField(null=True, blank=True)
    exceeded_time = models.DurationField(null=True, blank=True)
    worked_before_extension = models.DurationField(null=True, blank=True)

    extension_resumed = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def get_total_work_time(self):
        if self.worked_time:
            return self.worked_time
        if self.start_time:
            current = self.end_time or timezone.now()
            return current - self.start_time - (self.total_pause or timedelta(0))
        return None

    @property
    def total_pause_seconds(self):
        return int(self.total_pause.total_seconds()) if self.total_pause else 0

    @property
    def worked_seconds(self):
        return int(self.worked_time.total_seconds()) if self.worked_time else 0

    @property
    def worked_before_extension_seconds(self):
        return int(self.worked_before_extension.total_seconds()) if self.worked_before_extension else 0

    @property
    def expected_seconds(self):
        return int(self.expected_time.total_seconds()) if self.expected_time else 0

    @property
    def exceeded_seconds(self):
        return int(self.exceeded_time.total_seconds()) if self.exceeded_time else 0

    @property
    def is_time_exceeded(self):
        if self.worked_time and self.expected_time:
            return self.worked_time > self.expected_time
        return False

    @property
    def is_time_reached(self):
        if self.worked_time and self.expected_time:
            return self.worked_time >= self.expected_time
        return False
    @property
    def approved_extension_time(self):
        """Total approved extension duration"""
        from datetime import timedelta
        total = timedelta(0)
        for ext in self.extension_requests.filter(status='approved'):
            total += ext.requested_extra_time
        return total

    @property
    def total_worked_with_extension(self):
        """worked_before_extension + approved extension time"""
        from datetime import timedelta
        base = self.worked_before_extension or timedelta(0)
        return base + self.approved_extension_time


class TaskPause(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='pauses')
    pause_start = models.DateTimeField()
    pause_end = models.DateTimeField(null=True, blank=True)

    @property
    def duration(self):
        if self.pause_start and self.pause_end:
            return self.pause_end - self.pause_start
        return timedelta(0)

    def __str__(self):
        return f"Pause for '{self.task.title}' | {self.pause_start} → {self.pause_end or 'ongoing'}"


class LeaveRequest(models.Model):
    STATUS_CHOICES = (
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    reason = models.TextField()
    from_date = models.DateField()
    to_date = models.DateField()
    applied_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.staff.authuser.username} - {self.status}"


class TimeExtensionRequest(models.Model):
    STATUS_CHOICES = (
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    task = models.ForeignKey(Task, on_delete=models.CASCADE,
                             related_name='extension_requests')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    reason = models.TextField()
    requested_extra_time = models.DurationField()
    requested_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_remark = models.TextField(blank=True, null=True)
    reviewed_on = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.staff.authuser.username} → '{self.task.title}' [{self.status}]"
    
class Client(models.Model):
    name=models.CharField(max_length=150)
    company_name=models.CharField(max_length=200)
    address=models.TextField()
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.name} ({self.company_name})"
class Proposal(models.Model):
    STATUS_CHOICES =[
        ('draft','Draft'),
        ('accepted','Accepted'),
        ('rejected','Rejected'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='proposals')
    proposal_number= models.CharField(max_length=20,unique=True)
    proposal_title = models.CharField(max_length=255, blank=True, default='') 
    overview = models.TextField(blank=True, default='')
    date=models.DateField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    def __str__(self):
        return self.proposal_number
    @property
    def half_amount(self):
        return self.total_amount / 2
    
class ProposalItem(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='items')
    service_name=models.CharField(max_length=255)
    service_detail = models.TextField(blank=True)
    quantity=models.IntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    @property
    def line_total(self):
        return self.quantity * self.amount

class CompanyService(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.title


    
    
