"""Retention policy for clothing items moved to the recycle bin."""

import logging
from datetime import datetime, timedelta

from fastapi_app.database import SessionLocal
from fastapi_app import storage
from fastapi_app.models import ClothingItem

logger = logging.getLogger(__name__)
RETENTION_DAYS = 30


def expires_at(deleted_at: datetime) -> datetime:
    return deleted_at + timedelta(days=RETENTION_DAYS)


def purge_expired_items(now: datetime | None = None) -> int:
    """Hard-delete expired rows and photos; failed object deletes are retried later."""
    cutoff = (now or datetime.utcnow()) - timedelta(days=RETENTION_DAYS)
    db = SessionLocal()
    purged = 0
    try:
        items = db.query(ClothingItem).filter(
            ClothingItem.deleted_at.isnot(None),
            ClothingItem.deleted_at <= cutoff,
        ).all()
        for item in items:
            try:
                storage.delete_photo(item.photo_url)
            except Exception:
                logger.exception("Could not purge expired clothing photo for item %s", item.id)
                continue
            db.delete(item)
            purged += 1
        db.commit()
        return purged
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
