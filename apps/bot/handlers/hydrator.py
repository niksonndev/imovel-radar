import json

from shared_models import HydratedListing, Listing, Properties


def hydrate_listing(listing: Listing) -> HydratedListing:
    properties: list[Properties] = (
        json.loads(listing.properties) if listing.properties else []
    )

    for item in properties:
        if "real_estate_type" in item:
            item["real_estate_type"] = item["real_estate_type"].split(" - ")[0]

    return HydratedListing(
        listId=listing.list_id,
        url=listing.url,
        title=listing.title,
        priceValue=listing.price_value,
        oldPrice=listing.old_price,
        municipality=listing.municipality,
        neighbourhood=listing.neighbourhood,
        category=listing.category,
        images=json.loads(listing.images),
        properties=properties,
    )