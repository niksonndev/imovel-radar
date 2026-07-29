import json

from pydantic import TypeAdapter
from shared_models import HydratedListing, Listing, Properties

_properties_adapter = TypeAdapter(list[Properties])


def hydrate_listing(listing: Listing) -> HydratedListing:
    raw: list[dict] = json.loads(listing.properties) if listing.properties else []
    properties = _properties_adapter.validate_python(raw)

    for item in properties:
        if item.real_estate_type:
            item.real_estate_type = item.real_estate_type.split(" - ")[0]

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
