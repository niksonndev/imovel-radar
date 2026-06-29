import json
from typing import TypedDict

from models import Listing


class HydratedListing(Listing, TypedDict):
    images: list[str]
    properties: list[dict]


def hydrate_listing(listing: Listing) -> HydratedListing:
    return {
        **listing,
        "images": json.loads(listing["images"]),
        "properties": json.loads(listing["properties"]),
    }
