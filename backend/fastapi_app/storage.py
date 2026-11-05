"""Photo storage with an OSS production backend and a local development fallback."""

import os
from functools import lru_cache

from fastapi_app import config

OSS_PREFIX = "oss://"


def oss_enabled() -> bool:
    return bool(config.OSS_BUCKET and config.OSS_ACCESS_KEY_ID and config.OSS_ACCESS_KEY_SECRET)


@lru_cache(maxsize=1)
def _oss_bucket():
    if not oss_enabled():
        raise RuntimeError("OSS is not fully configured")
    import oss2

    endpoint = config.OSS_ENDPOINT
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"
    auth = oss2.Auth(config.OSS_ACCESS_KEY_ID, config.OSS_ACCESS_KEY_SECRET)
    return oss2.Bucket(auth, endpoint, config.OSS_BUCKET)


def save_photo(key: str, data: bytes, content_type: str) -> str:
    """Save photo bytes and return a durable reference for the database."""
    if oss_enabled():
        _oss_bucket().put_object(key, data, headers={"Content-Type": content_type})
        return f"{OSS_PREFIX}{key}"

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    path = os.path.join(config.UPLOAD_DIR, os.path.basename(key))
    with open(path, "wb") as photo:
        photo.write(data)
    return f"/uploads/{os.path.basename(key)}"


def photo_url(photo_ref: str | None) -> str | None:
    """Resolve a stored reference to a URL suitable for the Mini Program."""
    if not photo_ref or not photo_ref.startswith(OSS_PREFIX):
        return photo_ref
    key = photo_ref[len(OSS_PREFIX):]
    return _oss_bucket().sign_url("GET", key, config.OSS_SIGNED_URL_TTL, slash_safe=True)


def delete_photo(photo_ref: str | None) -> None:
    """Delete a stored photo; missing local files and OSS objects are harmless."""
    if not photo_ref:
        return
    if photo_ref.startswith(OSS_PREFIX):
        _oss_bucket().delete_object(photo_ref[len(OSS_PREFIX):])
        return

    # Legacy/local development URLs are deliberately restricted to a basename.
    name = os.path.basename(photo_ref)
    try:
        os.remove(os.path.join(config.UPLOAD_DIR, name))
    except FileNotFoundError:
        pass
