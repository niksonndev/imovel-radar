import config
from db.cache import deactivate_missing, get_active_listings, upsert_listing
from db.database import init_db


def _sample_listing(list_id: int, price: int = 150000, neighbourhood: str = "Jatiuca"):
    return {
        "list_id": list_id,
        "title": "Apto teste",
        "url": f"https://al.olx.com.br/imovel-{list_id}",
        "location": "Maceio",
        "municipality": "Maceio",
        "neighbourhood": neighbourhood,
        "uf": "AL",
        "ddd": "82",
        "current_price": price,
        "real_estate_type": "Apartamento",
        "size_m2": 70,
        "rooms": 3,
        "bathrooms": 1,
        "garage_spaces": 1,
        "re_complex_features": "Portaria",
        "re_type": "Padrao",
        "category_id": 1002,
        "category_name": "Apartamentos",
        "is_professional": False,
        "orig_list_time": 1774110567,
        "images": [
            {
                "url": "https://img1.jpg",
                "url_webp": "https://img1.webp",
                "position": 0,
            }
        ],
    }


def test_upsert_create_unchanged_updated_and_filters(monkeypatch, tmp_path):
    db_file = tmp_path / "cache.db"
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    init_db()

    created = upsert_listing(_sample_listing(1, 150000, "Jatiuca"))
    assert created == "created"

    unchanged = upsert_listing(_sample_listing(1, 150000, "Jatiuca"))
    assert unchanged == "unchanged"

    updated = upsert_listing(_sample_listing(1, 180000, "Jatiuca"))
    assert updated == "updated"

    active = get_active_listings({"municipality": "Maceio", "min_price": 160000, "rooms": 3})
    assert len(active) == 1
    assert active[0]["current_price"] == 180000


def test_deactivate_missing(monkeypatch, tmp_path):
    db_file = tmp_path / "cache.db"
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    init_db()

    upsert_listing(_sample_listing(1))
    upsert_listing(_sample_listing(2))

    count = deactivate_missing([1])
    assert count == 1

    active = get_active_listings()
    assert [row["list_id"] for row in active] == [1]

