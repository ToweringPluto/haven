const unsplash = (id: string, width: number, quality = 80) =>
  `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${width}&q=${quality}`;

export const IMAGES = {
  hero: unsplash("photo-1506377585622-bedcbb027afc", 1200),
  snug: unsplash("photo-1572534382971-f8ff4d4cb1c1", 900),
  leith: unsplash("photo-1604598073983-6ca9576890f0", 1000),
  marchmont: unsplash("photo-1587522537396-b572c1a39ae5", 1000),
  stockbridge: unsplash("photo-1679043465592-7f9a331906f6", 1000),
  street: unsplash("photo-1707048736052-ba0dbf47637e", 1000),
} as const;

const AREA_IMAGES: Record<string, string> = {
  leith: IMAGES.leith,
  marchmont: IMAGES.marchmont,
  bruntsfield: IMAGES.marchmont,
  "old town": IMAGES.street,
  craigleith: IMAGES.stockbridge,
  stockbridge: IMAGES.stockbridge,
};

/**
 * Listings carry no photos yet, so cards show a photo of the *area*, captioned as such, never
 * passed off as the property itself.
 */
export const areaImage = (area: string | null) =>
  AREA_IMAGES[(area ?? "").toLowerCase()] ?? IMAGES.street;
