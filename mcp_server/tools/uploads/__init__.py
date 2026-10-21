"""Opt-in binary upload tools; never enable shell to use this package."""
import os

if os.environ.get("ENABLE_FILE_UPLOADS", "").strip().lower() in {"1", "true", "yes", "on"}:
    from .api import (begin_file_upload, append_file_chunk, finish_file_upload,
                      get_file_upload_status, cancel_file_upload, cleanup_file_uploads)
    __all__ = ["begin_file_upload", "append_file_chunk", "finish_file_upload",
               "get_file_upload_status", "cancel_file_upload", "cleanup_file_uploads"]
else:
    __all__ = []
