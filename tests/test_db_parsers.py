from db.parsers import extract_property, parse_listing, parse_price, parse_size


def test_parse_price_brl_to_cents():
    assert parse_price("R$ 1.500") == 150000


def test_parse_price_invalid():
    assert parse_price("abc") is None


def test_parse_size():
    assert parse_size("70m²") == 70


def test_extract_property():
    properties = [
        {"name": "rooms", "value": "3"},
        {"name": "size", "value": "70m²"},
    ]
    assert extract_property(properties, "rooms") == "3"
    assert extract_property(properties, "bathrooms") is None


def test_parse_listing_from_raw_olx():
    raw = {
        "subject": "Alugo apt",
        "priceValue": "R$ 1.500",
        "origListTime": 1774110567,
        "professionalAd": False,
        "friendlyUrl": "https://al.olx.com.br/alagoas/imoveis/alugo-apt-1485946751",
        "listId": 1485946751,
        "categoryName": "Apartamentos",
        "listingCategoryId": "1002",
        "location": "Maceio, Jatiuca",
        "locationDetails": {
            "municipality": "Maceio",
            "ddd": "82",
            "neighbourhood": "Jatiuca",
            "uf": "AL",
        },
        "images": [{"original": "https://img1.jpg", "originalWebp": "https://img1.webp"}],
        "properties": [
            {"name": "real_estate_type", "value": "Aluguel - apartamento padrao"},
            {"name": "size", "value": "70m²"},
            {"name": "rooms", "value": "3"},
            {"name": "bathrooms", "value": "1"},
            {"name": "garage_spaces", "value": "1"},
            {"name": "re_complex_features", "value": "Condominio fechado"},
            {"name": "re_types", "value": "Padrao"},
        ],
    }
    parsed = parse_listing(raw)
    assert parsed["list_id"] == 1485946751
    assert parsed["current_price"] == 150000
    assert parsed["size_m2"] == 70
    assert parsed["rooms"] == 3
    assert parsed["images"][0]["position"] == 0

