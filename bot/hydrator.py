import json

from models import Listing, HydratedListing


def hydrate_listing(listing: Listing) -> HydratedListing:
    return {
        **listing,
        "images": json.loads(listing["images"]) if listing["images"] else None,
        "properties": json.loads(listing["properties"])
        if listing["properties"]
        else [],
    }
