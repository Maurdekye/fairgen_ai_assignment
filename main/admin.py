from django.contrib import admin
from .models import University, Room, Time

@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'university')
    list_filter = ('university',)
    search_fields = ('name',)

@admin.register(Time)
class TimeAdmin(admin.ModelAdmin):
    list_display = ('start', 'end', 'room', 'registrant')
    list_filter = ('room__university', 'registrant')
    search_fields = ('room__name', 'registrant__username')