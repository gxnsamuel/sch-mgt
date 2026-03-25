from django.shortcuts import render

# Create your views here.
def cover_page(request):
    return render (request, "dashboard/cover.html")



def parent_dashboard(request, user_id):
    user = request.user()

    
    return render(request, "parent_dashboard.html")
