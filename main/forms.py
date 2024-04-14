from django import forms
from .models import Room, Time

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name']

class TimeForm(forms.ModelForm):
    class Meta:
        model = Time
        fields = ['start', 'end', 'room']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['room'].queryset = Room.objects.filter(university=user.university)