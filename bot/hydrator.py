import json

from models import Listing, HydratedListing, Properties


def hydrate_listing(listing: Listing) -> HydratedListing:
    properties: list[Properties] = (
        json.loads(listing["properties"]) if listing["properties"] else []
    )

    for item in properties:
        if "real_estate_type" in item:
            item["real_estate_type"] = item["real_estate_type"].split(" - ")[0]

    return HydratedListing(
        listId=listing["listId"],
        url=listing["url"],
        title=listing["title"],
        priceValue=listing["priceValue"],
        oldPrice=listing["oldPrice"],
        municipality=listing["municipality"],
        neighbourhood=listing["neighbourhood"],
        category=listing["category"],
        images=json.loads(listing["images"]),
        properties=properties,
    )
