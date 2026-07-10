from __future__ import annotations

from typing import Any, Callable

from .heuristic_proxy import annotate_candidate as heuristic_proxy_annotate_candidate


AnnotationProvider = Callable[[dict[str, Any], dict[str, dict[str, Any]], str], dict[str, Any]]


ANNOTATION_PROVIDERS: dict[str, AnnotationProvider] = {
    'heuristic_proxy_v1': heuristic_proxy_annotate_candidate,
}
