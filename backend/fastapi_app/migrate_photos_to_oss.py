"""One-time migration for existing local clothing photos.

Run from backend/: python -m fastapi_app.migrate_photos_to_oss
Local source files are kept after migration so the operation is reversible.
"""

import mimetypes
import os

from fastapi_app import config, storage
from fastapi_app.database import SessionLocal
from fastapi_app.models import ClothingItem


def main() -> None:
    if not storage.oss_enabled():
        raise SystemExit("OSS credentials are not configured; no photos were changed.")

    db = SessionLocal()
    migrated = 0
    try:
        items = db.query(ClothingItem).filter(ClothingItem.photo_url.isnot(None)).all()
        for item in items:
            photo_ref = item.photo_url or ""
            if photo_ref.startswith(storage.OSS_PREFIX):
                continue

            filename = os.path.basename(photo_ref)
            local_path = os.path.join(config.UPLOAD_DIR, filename)
            if not os.path.isfile(local_path):
                print(f"Skipped clothing item {item.id}: local photo is missing")
                continue

            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            key = f"users/{item.user_id}/clothing/{item.id}/{filename}"
            with open(local_path, "rb") as source:
                photo_ref = storage.save_photo(key, source.read(), content_type)

            item.photo_url = photo_ref
            db.commit()
            migrated += 1
            print(f"Migrated clothing item {item.id}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Migration complete: {migrated} photo(s) moved to OSS.")


if __name__ == "__main__":
    main()
