from django.shortcuts import render, redirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from .models import University, Room, Time
from .forms import RoomForm, TimeForm

@login_required
def create_room(request):
    if request.user.group not in ['admin', 'manager']:
        return redirect('room_list')
    if request.method == 'POST':
        form = RoomForm(request.POST) 
        if form.is_valid():
            room = form.save(commit=False)
            room.university = request.user.university
            room.save()
            return redirect('room_list')
    else:
        form = RoomForm()
    return render(request, 'main/create_room.html', {'form': form})

@login_required
def update_room(request, room_id):
    if request.user.group not in ['admin', 'manager']:
        return redirect('room_list')
    room = Room.objects.get(id=room_id)
    if request.user.group == 'manager' and request.user.university != room.university:
        return redirect('room_list')
    if request.user.university != room.university:
        return redirect('room_list')
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            return redirect('room_list')
    else:
        form = RoomForm(instance=room)
    return render(request, 'main/update_room.html', {'form': form})

@login_required
def create_time(request):
    if request.user.group not in ['admin', 'manager', 'personnel']:
        return redirect('time_list')
    if request.method == 'POST':
        form = TimeForm(request.POST)
        if form.is_valid():
            time = form.save(commit=False)
            time.registrant = request.user
            time.save()
            return redirect('time_list')
    else:
        form = TimeForm(user=request.user)
    return render(request, 'main/create_time.html', {'form': form})

@login_required
def update_time(request, time_id):
    if request.user.group not in ['admin', 'manager', 'personnel']:
        return redirect('time_list')
    time = Time.objects.get(id=time_id)
    if request.user.group == 'personnel' and request.user != time.registrant:
        return redirect('time_list')
    room = Room.objects.get(id=time.room)
    if request.user.group == 'manager' and request.user.university != room.university:
        return redirect('time_list')
    if request.method == 'POST':
        form = TimeForm(request.POST, instance=time, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('time_list')
    else:
        form = TimeForm(instance=time, user=request.user)
    return render(request, 'main/update_time.html', {'form': form})