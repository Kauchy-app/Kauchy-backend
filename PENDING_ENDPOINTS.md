# Pending Backend Endpoints

Features that were shipped on the frontend with a stopgap (or stubbed) because a
proper implementation needs **new backend work**. Each section is a proposal for
the endpoint(s) required to finish the feature properly.

---

## 1. Buy Now — direct (card/Paystack) checkout  ✅ IMPLEMENTED

**Status:** Done. Instead of a separate `/payment/buy-now/`, the existing
`POST /payment/create-order/` was extended to accept a direct `items` payload and
a `payment_method` (`wallet` | `card`). The frontend no longer needs the
add-to-cart + create-order workaround for Buy Now.

```
POST /payment/create-order/
Auth: required
Body (direct purchase):
{
  "items": [{ "product_id": 55, "quantity": 1 }],
  "payment_method": "card",          // "wallet" (default) or "card"
  "callback_url": "https://app/.../return"   // card only, optional
}

Wallet response (200): orders created immediately, buyer wallet debited.
{
  "message": "Orders created. Awaiting QR code validation.",
  "payment_method": "wallet",
  "total_amount_naira": 1500.00,
  "orders_created": 1,
  "orders": [{ "order_id": "ORD-abc1234", "vendor_id": 42, "amount": 1500.00, "status": "pending" }]
}

Card response (200): no order yet — redirect the buyer to Paystack.
{
  "message": "Payment initialized.",
  "payment_method": "card",
  "authorization_url": "https://checkout.paystack.com/abc123",
  "reference": "ref_abc123",
  "amount_naira": 1500.00
}
```

**Card confirmation (init-then-verify):**
```
GET /payment/verify-purchase/<reference>
Auth: required
```
Verifies the Paystack transaction and only then creates the Order(s) + HELD
escrow from the stashed `PendingPurchase`. Idempotent (safe to call twice). No
order exists until payment is confirmed.

**Notes:**
- `cart_id` still works exactly as before for cart checkout; `items` takes
  precedence when both are sent.
- Prices/vendors are read from live `Product` rows, never trusted from the client.
- Order materialization (orders + items + escrow + vendor notification) is shared
  between the wallet and card rails via `materialize_orders()` in
  `paymentapp/views.py`.

---

## 2. Bookmarks (server-side persistence)

**Why:** Bookmarks (save a Kauch post) are currently stored only in the browser
(`localStorage`), so they don't sync across devices or survive a cache clear.

**Need:** persist bookmarks per user.

```
POST   /kauch/posts/{post_id}/bookmark/   → toggle; returns { "bookmarked": true }
GET    /kauch/bookmarks/                   → list the user's bookmarked posts (Post objects)
```

**Notes:**
- New model: `Bookmark(user, post, created_at)` with `unique_together(user, post)`.
- Optionally add `is_bookmarked_by_user` to `PostSerializer` so the feed can show
  saved state without a second request.

---

## 3. Share count tracking

**Why:** The feed shows a share count, but it is always `0` — sharing isn't recorded
server-side. `shares_count` is hard-coded in the frontend mapping.

**Need:** record a share and expose the count.

```
POST /kauch/posts/{post_id}/share/   → increments; returns { "shares_count": 13 }
```

**Notes:**
- Add `shares_count` (PositiveIntegerField, default 0) to `PostModel` and include it
  in `PostSerializer`. Increment on share (optionally dedupe per user with a
  `PostShare` table if real metrics are wanted).

---

## 4. Kauch search (search page — Kauch tab)

**Why:** The search page has a **Kauch** tab, but there is no endpoint to search
Kauches by name. Products and Vendors are already covered by
`GET /usersearch/suggestions/?q=` (returns `suggested_products` + `suggested_vendors`);
Kauch has no equivalent.

**Need:** search Kauches by name/description.

```
GET /kauch/search/?q=sneakers
Auth: optional
Response (200): [ Kauch objects ]   // same shape as GET /kauch/{id}/
```

**Notes:**
- Filter `KauchModel` on `name__icontains` / `description__icontains`, order by
  `followers_count`, cap ~20, serialize with the existing `KauchSerializer`.
- Until this exists the search page's **Kauch tab** calls this path and shows an empty
  state on failure; the Products and Vendors tabs already work via the suggestions
  endpoint.

---

## 5. (Optional) Deep comment nesting

**Why:** Comment replies are intentionally **two levels** (a top-level comment and a
flat list of replies, TikTok-style). Replying to a reply stays in the same thread and
@mentions the user.

**Need (only if true unlimited nesting is desired):** the `parent` self-FK already
exists on `PostComment`, so the data model supports arbitrary depth — but the API
returns a flat list and the UI renders two levels. Supporting deep trees would mean
returning nested children (or a depth field) and a recursive UI. Flagged as a larger
change, not required for the current behaviour.
