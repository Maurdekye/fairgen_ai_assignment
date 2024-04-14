from django.urls import path
from . import views

urlpatterns = [
    path('create-room/', views.create_room, name='create_room'),
    path('update-room/<int:room_id>/', views.update_room, name='update_room'),
    path('create-time/', views.create_time, name='create_time'),
    path('update-time/<int:time_id>/', views.update_time, name='update_time'),
]