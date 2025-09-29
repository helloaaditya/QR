from django.db import models
from django.utils import timezone


class Teacher(models.Model):
    full_name = models.CharField(max_length=128)

    def __str__(self) -> str:
        return self.full_name


class Subject(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self) -> str:
        return self.name


class Student(models.Model):
    student_id = models.CharField(max_length=32, unique=True)
    full_name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.student_id} - {self.full_name}"


class AttendanceSession(models.Model):
    title = models.CharField(max_length=128)
    code = models.CharField(max_length=64, unique=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    date = models.DateField(default=timezone.now)
    time_slot = models.CharField(max_length=64, default="")
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.title} ({self.code})"

    @property
    def is_open(self) -> bool:
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at

    @property
    def present_count(self) -> int:
        return self.records.count()

    @property
    def unique_devices_count(self) -> int:
        return self.records.values('device_fingerprint').distinct().count()


class AttendanceRecord(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance')
    scanned_at = models.DateTimeField(auto_now_add=True)
    device_fingerprint = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        unique_together = (
            ('session', 'student'),
            ('session', 'device_fingerprint'),
        )

    def __str__(self) -> str:
        return f"{self.student_id} @ {self.session_id}"
