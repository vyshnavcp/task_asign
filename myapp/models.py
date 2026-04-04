from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
# Create your models here.
from django.db import models
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
        ('pending', 'Pending'),
        ('started', 'Started'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
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

    def __str__(self):
        return self.title

    def get_total_work_time(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time - (self.total_pause or timedelta(0))
        return None

    @property
    def total_pause_seconds(self):
        """Returns total paused seconds as integer for JS"""
        if self.total_pause:
            return int(self.total_pause.total_seconds())
        return 0