from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from .views import answer_query, clear_rag_memory  # now using DRF's @api_view version

def healthz(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("api/answer_query/", answer_query, name="answer_query"),
    path("api/clear_rag_memory/", clear_rag_memory, name="clear_rag_memory"),
]
