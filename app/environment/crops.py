"""Crop definitions for HarvestAgent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CropSpec:
    crop: str
    seed_item: str
    growth_days: int
    sell_price: int
    regrow_days: int | None = None


CROPS = {
    "turnip": CropSpec("turnip", "turnip_seed", growth_days=3, sell_price=45),
    "potato": CropSpec("potato", "potato_seed", growth_days=5, sell_price=90),
    "tomato": CropSpec(
        "tomato",
        "tomato_seed",
        growth_days=7,
        sell_price=80,
        regrow_days=2,
    ),
    "pumpkin": CropSpec("pumpkin", "pumpkin_seed", growth_days=9, sell_price=260),
}
