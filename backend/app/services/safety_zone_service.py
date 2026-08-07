"""
Safety Zone Service - serves polygon zones from the cached backend dataset.
Never returns hardcoded, random, or point-based zones.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.safety_dataset_cache import safety_dataset_cache


async def get_safety_zones(
    db: AsyncSession,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
) -> dict:
    """
    Return GeoJSON FeatureCollection of safety zone polygons within the bounding box.
    """
    snapshot = await safety_dataset_cache.get_snapshot(db)
    return snapshot.zone_feature_collection(
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
    )
