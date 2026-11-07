from celery import shared_task


@shared_task(acks_late=True, ignore_result=True)
def run_analysis(analysis_id: int) -> None:
    """Celery entry point. The pipeline records success or failure on the Analysis row itself."""
    from .models import Analysis
    from .services import pipeline

    analysis = Analysis.objects.filter(pk=analysis_id).first()
    if analysis is not None and analysis.status == "queued":
        pipeline.run(analysis)
