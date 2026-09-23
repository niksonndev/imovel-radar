import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  allNeighbourhoodParams,
  buildLocationCatalog,
  findNeighbourhood,
} from "../src/content/programmatic-seo/catalog";
import { neighbourhoodMetadata } from "../src/content/programmatic-seo/copy";
import {
  matchesNeighbourhoodSlug,
  neighbourhoodSlugFromName,
  slugifyLocation,
} from "../src/content/programmatic-seo/slugs";
import type { MarketSnapshot } from "../src/lib/market-stats";

const miniSnapshot: MarketSnapshot = {
  collected_at: "2026-01-01T12:00:00+00:00",
  min_sample: 15,
  cities: [
    {
      key: "maceio",
      municipality: "Maceió",
      kinds: {
        aluguel: {
          active_count: 10,
          inactive_count: 0,
          sample: 10,
          p25_price: 1000,
          median_price: 1500,
          p75_price: 2000,
          median_price_m2: 20,
          price_m2_sample: 10,
          new_count: 1,
          price_drop_count: 0,
          median_rent_plus_condo: 1800,
          by_category: [],
          neighbourhoods: [
            {
              name: "Ponta Verde",
              sample: 20,
              median_price: 3000,
              median_price_m2: 40,
              ranked: true,
            },
            {
              name: "Bairro Fino",
              sample: 5,
              median_price: 900,
              median_price_m2: 10,
              ranked: false,
            },
          ],
          rooms: [],
        },
        venda: {
          active_count: 10,
          inactive_count: 0,
          sample: 10,
          p25_price: 200_000,
          median_price: 350_000,
          p75_price: 500_000,
          median_price_m2: 5000,
          price_m2_sample: 10,
          new_count: 1,
          price_drop_count: 0,
          median_rent_plus_condo: null,
          by_category: [],
          neighbourhoods: [
            {
              name: "Ponta Verde",
              sample: 18,
              median_price: 600_000,
              median_price_m2: 8000,
              ranked: true,
            },
          ],
          rooms: [],
        },
      },
    },
  ],
};

describe("programmatic SEO slugs", () => {
  it("slugifies accents and spaces", () => {
    assert.equal(slugifyLocation("Ponta Verde"), "ponta-verde");
    assert.equal(neighbourhoodSlugFromName("Cruz das Almas"), "cruz-das-almas");
    assert.equal(matchesNeighbourhoodSlug("Ponta Verde", "ponta-verde"), true);
  });
});

describe("buildLocationCatalog", () => {
  it("excludes unranked-only neighbourhoods", () => {
    const catalog = buildLocationCatalog(miniSnapshot);
    const maceio = catalog.cities[0];
    assert.equal(maceio.neighbourhoods.length, 1);
    assert.equal(maceio.neighbourhoods[0].name, "Ponta Verde");
  });

  it("generates static params only for indexable bairros", () => {
    const catalog = buildLocationCatalog(miniSnapshot);
    const params = allNeighbourhoodParams(catalog);
    assert.deepEqual(params, [{ cidade: "maceio", bairro: "ponta-verde" }]);
  });

  it("resolves neighbourhood by slug", () => {
    const catalog = buildLocationCatalog(miniSnapshot);
    const nbhd = findNeighbourhood(catalog, "maceio", "ponta-verde");
    assert.ok(nbhd);
    assert.equal(nbhd.venda.stat?.median_price, 600_000);
  });
});

describe("neighbourhoodMetadata", () => {
  it("includes median in intro when ranked", () => {
    const catalog = buildLocationCatalog(miniSnapshot);
    const nbhd = findNeighbourhood(catalog, "maceio", "ponta-verde")!;
    const copy = neighbourhoodMetadata(nbhd);
    assert.match(copy.intro, /600\.000|600,000/);
    assert.match(copy.description, /Ponta Verde/);
  });
});
