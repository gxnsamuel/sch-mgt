from django.shortcuts import redirect
from django.urls import reverse
from authentication.models import CustomUser
from django.contrib import messages




def get_user_dashboard(request, user_id):

    user = request.user

    if user is None:
        return redirect(reverse("login"))

    if user.user_type == 'parent':
        return redirect(reverse("parent_dashboard", args=[user_id]))
    
    elif user.user_type == "teacher":
        return redirect(reverse("teacher_dashboard", args=[user_id]))
    
    elif user.user_type == "admin":
        return redirect(reverse("admin_dashboard", args=[user_id]))
    

def get_right_user_for_dashboard(request, user_id):
    user = request.user

    if user.pk != user_id:
        messages.error(request, "Access Not Allowed")
        get_user_dashboard(request, user_id=user.pk)
    pass



    




    