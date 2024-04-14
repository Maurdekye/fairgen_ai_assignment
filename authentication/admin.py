from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("username", "email", "group", "university", "is_staff", "is_active",)
    list_filter = ("group", "university", "is_staff", "is_active",)
    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        ("Permissions", {"fields": ("group", "university", "is_staff", "is_active")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "group", "university", "is_staff", "is_active")}
        ),
    )
    search_fields = ("username", "email", "university",)
    ordering = ("username",)

admin.site.register(User, CustomUserAdmin)