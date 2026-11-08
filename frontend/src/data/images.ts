const unsplash = (id: string, width: number, quality = 80) =>
  `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${width}&q=${quality}`;

/** Photos for the home page and neighbourhood cards (never used for a listing). */
export const IMAGES = {
  hero: unsplash("photo-1506377585622-bedcbb027afc", 1200),
  snug: unsplash("photo-1572534382971-f8ff4d4cb1c1", 900),
  leith: unsplash("photo-1604598073983-6ca9576890f0", 1000),
  marchmont: unsplash("photo-1587522537396-b572c1a39ae5", 1000),
  stockbridge: unsplash("photo-1679043465592-7f9a331906f6", 1000),
} as const;

/**
 * One stock photo per listing, and no photo is used for more than one listing (or anywhere
 * else in the app). Listings can't be added by renters, so every listing is in this table; add
 * a new, unused photo here whenever a listing is added to the seed.
 */
const LISTING_PHOTOS: Record<string, string> = {
  "seed-prop-leith": "photo-1493809842364-78817add7ffb",
  "seed-prop-marchmont": "photo-1505691938895-1758d7feb511",
  "seed-prop-gorgie": "photo-1586023492125-27b2c045efd7",
  "seed-prop-old-town": "photo-1707048736052-ba0dbf47637e",
  "seed-prop-craigleith": "photo-1515263487990-61b07816b324",
  "seed-prop-portobello": "photo-1502672260266-1c1ef2d93688",
  "seed-prop-gilmerton": "photo-1567496898669-ee935f5f647a",
  "seed-prop-bruntsfield": "photo-1494526585095-c41746248156",
  "seed-prop-dalry": "photo-1522708323590-d24dbb6b0267",
  "seed-prop-sighthill": "photo-1556020685-ae41abfc9365",
  "seed-prop-wester-hailes": "photo-1545324418-cc1a3fa10c00",
  "ill-prop-leith-flat": "photo-1460317442991-0ec209397118",
  "ill-prop-marchmont-flat": "photo-1536376072261-38c75010e6c9",
  "ill-prop-gorgie-flat": "photo-1574362848149-11496d93a7c7",
};

/** Unused spares, kept so a new listing can be given a photo nobody else has. */
export const SPARE_LISTING_PHOTOS = [
  "photo-1484154218962-a197022b5858",
  "photo-1554995207-c18c203602cb",
  "photo-1560448204-e02f11c3d0e2",
];

/** The listing's own photo. An unknown listing gets the Edinburgh skyline, not another home. */
export const listingImage = (propertyId: string, width = 1000) => {
  const id = LISTING_PHOTOS[propertyId];
  return id ? unsplash(id, width) : IMAGES.hero;
};
