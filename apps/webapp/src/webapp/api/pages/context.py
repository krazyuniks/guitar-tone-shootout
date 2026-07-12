"""Shared ORM-to-dict template context mappers.

Canonical mapping functions used by all page handler modules.
Each function converts an ORM model into a plain dict suitable
for Jinja2 template rendering.
"""

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.shootout import DITrack, Shootout
from webapp.adapters.persistence.models.shootout_comment import ShootoutComment
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.templates import _relative_time


def format_duration(seconds: float | None) -> str:
    """Format seconds to mm:ss string."""
    if seconds is None:
        return "0:00"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def gear_to_browse_context(gear: Gear) -> dict[str, object]:
    """Map Gear ORM model to browse/card dict for templates."""
    platform = "nam"
    if gear.models:
        p = gear.models[0].platform
        platform = p.value if hasattr(p, "value") else str(p)

    return {
        "id": str(gear.id),
        "slug": gear.slug,
        "source_record_id": (gear.source.source_record_id if gear.source else ""),
        "title": gear.name,
        "gear_type": (
            gear.gear_type.value if hasattr(gear.gear_type, "value") else str(gear.gear_type)
        ).replace("_", "-"),
        "platform": platform,
        "image_url": gear.thumbnail_url,
        "downloads_count": gear.downloads_count,
        "favorites_count": gear.favorites_count,
        "models_count": len(gear.models),
        "saved_count": 0,
        "creator_username": gear.manufacturer,
        "creator_avatar": None,
        "relative_time": _relative_time(gear.source_created_at or gear.created_at),
    }


def gear_to_detail_context(gear: Gear) -> dict[str, object]:
    """Map Gear ORM model to detailed pack dict for detail template."""
    pack = gear_to_browse_context(gear)
    pack.update(
        {
            "description": gear.description,
            "tags": gear.tags,
            "makes": [],
            "videos": [],
            "external_links": [],
            "t3k_url": (
                f"https://www.tone3000.com/tones/{gear.source.source_record_id}"
                if gear.source
                else "#"
            ),
            "created_at": (gear.created_at.strftime("%B %d, %Y") if gear.created_at else None),
            "license_text": gear.license_text,
            "models": [gear_model_to_row_context(m, gear.name) for m in gear.models],
        }
    )
    return pack


def gear_model_to_row_context(
    model: GearModel, gear_name: str = "", *, is_saved: bool = False
) -> dict[str, object]:
    """Map GearModel ORM to row dict for model_row.html fragment."""
    size_value = model.size.value if hasattr(model.size, "value") else str(model.size)
    download_status_value = (
        model.download_status.value
        if hasattr(model.download_status, "value")
        else str(model.download_status)
    )
    return {
        "id": str(model.id),
        "name": f"{gear_name} ({size_value})" if gear_name else size_value,
        "model_size": size_value,
        "is_saved": is_saved,
        "download_status": download_status_value,
    }


def di_track_to_context(track: DITrack, *, is_public: bool = False) -> dict[str, object]:
    """Map DITrack ORM model to template context dict."""
    return {
        "id": str(track.id),
        "title": track.name,
        "description": track.description,
        "is_public": is_public,
        "duration_seconds": track.duration_seconds,
        "duration_formatted": format_duration(track.duration_seconds),
        "sample_rate": track.sample_rate,
        "guitar": track.guitar,
        "tuning": track.tuning,
        "pickups": track.pickup,
        "is_system_track": False,
        "relative_time": _relative_time(track.created_at),
    }


def di_track_to_wizard_context(track: DITrack) -> dict[str, object]:
    """Map DITrack ORM model to subset dict for shootout wizard."""
    return {
        "id": str(track.id),
        "title": track.name,
        "duration_seconds": track.duration_seconds,
        "sample_rate": track.sample_rate,
        "guitar": track.guitar,
        "description": track.description,
    }


def chain_to_library_context(chain: SignalChain) -> dict[str, object]:
    """Map SignalChain ORM model to library list context."""
    return {
        "id": str(chain.id),
        "name": chain.name,
        "description": chain.description,
        "platform": chain.platform.value,
        "created_at": chain.created_at,
        "relative_time": _relative_time(chain.created_at),
    }


def chain_to_wizard_context(chain: SignalChain) -> dict[str, object]:
    """Map SignalChain ORM model to shootout wizard context."""
    return {
        "id": str(chain.id),
        "name": chain.name,
        "block_count": chain.block_count,
        "platform": chain.platform.value,
    }


def shootout_to_card_context(shootout: Shootout) -> dict[str, object]:
    """Map Shootout ORM model to card context for lists."""
    return {
        "id": str(shootout.id),
        "name": shootout.name,
        "description": shootout.description,
        "status": shootout.status.value
        if hasattr(shootout.status, "value")
        else str(shootout.status),
        "chain_count": len(shootout.chains) if shootout.chains else 0,
        "relative_time": _relative_time(shootout.created_at),
    }


def shootout_detail_context(shootout: Shootout) -> dict[str, object]:
    """Build template context for shootout detail page/fragment."""
    chains = sorted(shootout.chains, key=lambda chain: chain.position)
    chain_items = [
        {
            "id": str(chain.id),
            "position": chain.position + 1,
            "label": chain.label,
            "chain_name": chain.signal_chain.name if chain.signal_chain else chain.label,
        }
        for chain in chains
    ]

    duration = format_duration(shootout.di_track.duration_seconds) if shootout.di_track else None
    di_track = (
        {
            "id": str(shootout.di_track.id),
            "name": shootout.di_track.name,
            "duration": duration,
        }
        if shootout.di_track
        else None
    )

    shootout_ctx = {
        "id": str(shootout.id),
        "name": shootout.name,
        "description": shootout.description,
        "status": shootout.status.value,
        "montage_available": shootout.output_path is not None,
        "video_path": shootout.video_path,
    }

    creator = (
        {
            "id": str(shootout.user.id),
            "username": shootout.user.username,
        }
        if shootout.user
        else None
    )

    return {
        "shootout": shootout_ctx,
        "creator": creator,
        "relative_time": _relative_time(shootout.created_at),
        "tone_count": len(chain_items),
        "di_track": di_track,
        "chains": chain_items,
        "is_owner": True,
    }


def job_to_context(job: object) -> dict[str, object]:
    """Map Job ORM model to template context dict."""
    return {
        "id": str(job.id),  # type: ignore[attr-defined]
        "job_type": job.job_type.value,  # type: ignore[attr-defined]
        "status": job.status.value,  # type: ignore[attr-defined]
        "progress": job.progress,  # type: ignore[attr-defined]
        "message": job.message,  # type: ignore[attr-defined]
        "error": job.error,  # type: ignore[attr-defined]
        "entity_id": str(job.entity_id) if job.entity_id else None,  # type: ignore[attr-defined]
        "created_at": job.created_at,  # type: ignore[attr-defined]
        "relative_time": _relative_time(job.created_at),  # type: ignore[attr-defined]
    }


def comment_to_context(comment: ShootoutComment, current_user: User | None) -> dict[str, object]:
    """Map ShootoutComment ORM model to template context dict."""
    return {
        "id": str(comment.id),
        "author": comment.user.username,
        "text": comment.content,
        "relative_time": _relative_time(comment.created_at),
        "is_own": current_user is not None and comment.user_id == current_user.id,
    }
