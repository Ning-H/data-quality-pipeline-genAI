__all__ = ["run_enrichment", "get_narratives"]


def run_enrichment(*args, **kwargs):
    from .enricher import run_enrichment as _run_enrichment

    return _run_enrichment(*args, **kwargs)


def get_narratives(*args, **kwargs):
    from .enricher import get_narratives as _get_narratives

    return _get_narratives(*args, **kwargs)
