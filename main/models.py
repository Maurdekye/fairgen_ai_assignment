from django.db import models
from django.forms import ValidationError
from django.conf import settings

class University(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Room(models.Model):
    name = models.CharField(max_length=100)
    university = models.ForeignKey(University, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class Time(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    registrant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.start} - {self.end}"

    def clean(self):
        if self.start >= self.end:
            raise ValidationError("End time must be after start time.")

        overlapping_times = Time.objects.filter(
            room=self.room,
            start__lt=self.end,
            end__gt=self.start
        ).exclude(pk=self.pk)

        if overlapping_times.exists():
            raise ValidationError("Time slot overlaps with an existing time.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)