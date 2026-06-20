from django.contrib import admin

from .models import PredictionRequest, PredictionResult


class PredictionResultInline(admin.StackedInline):
    model = PredictionResult
    extra = 0
    can_delete = False
    readonly_fields = (
        "model_used",
        "output_text",
        "confidence_score",
        "response_time_ms",
        "created_at",
    )


@admin.register(PredictionRequest)
class PredictionRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "input_type", "session_id", "created_at")
    list_filter = ("input_type", "created_at")
    search_fields = ("session_id", "user__username")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    inlines = (PredictionResultInline,)


@admin.register(PredictionResult)
class PredictionResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request",
        "model_used",
        "confidence_score",
        "response_time_ms",
        "created_at",
    )
    list_filter = ("model_used", "created_at")
    search_fields = ("output_text", "request__session_id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
