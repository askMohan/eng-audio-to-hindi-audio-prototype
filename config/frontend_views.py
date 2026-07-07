from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse


FRONTEND_ROOT = settings.BASE_DIR / "frontend"
FRONTEND_INDEX = settings.BASE_DIR / "index.html"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


def frontend_index(request):
    return _file_response(FRONTEND_INDEX)


def frontend_asset(request, path):
    requested_path = (FRONTEND_ROOT / path).resolve()
    frontend_root = FRONTEND_ROOT.resolve()
    if not str(requested_path).startswith(str(frontend_root)) or not requested_path.is_file():
        raise Http404("Frontend asset not found")
    return _file_response(requested_path)


def favicon(request):
    return _file_response(FRONTEND_ROOT / "favicon.svg")


def _file_response(path):
    if not path.is_file():
        raise Http404("Frontend file not found")
    return HttpResponse(path.read_bytes(), content_type=CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
