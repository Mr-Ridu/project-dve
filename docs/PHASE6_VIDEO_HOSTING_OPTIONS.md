# Phase 6 — Video hosting decision (DECIDED)

> **Decision recorded (user-approved via structured questions, October 2026):**
> **Bunny Stream**, signed-token protection only (no DRM), scale ~20 h / ≤100
> viewers. Account/key provisioning was approved with consent — keys are stored
> as server secrets, never in chat or VCS.

Previous state: STOP gate requiring approval. Phase 5 shipped the
provider-agnostic authorization endpoint, so Bunny plugs in without rework.

Researched October 2026 via web sources; full source list at the bottom.

## Baseline honesty (unchanged from Phase 1)

- No HTML player can stop screen recording; signed URLs are bearer links valid
  until expiry. DRM raises the bar but isn't absolute (Widevine L3 has no
  capture protection on its own).
- HLS protection must cover **every playlist and segment**, not just the master.

## Decision-relevant scale

Current plan: ~20 h library, 50–200 learners, cPanel+Django host. Billed by
usage, so the Expected number of viewers matters.

## Options (concrete numbers)

| | Bunny Stream | Cloudflare Stream | VdoCipher | Mux | DIY R2 + presigned |
|---|---|---|---|---|---|
| Storage | $0.01/GB/mo (Frankfurt) | $5/1,000 min/mo ⇒ **$10/mo** for 20 h | $149 Starter/yr: 1 TB bandwidth, 100 GB storage | $0.0024 stored min/mo (≤720p) | $0.015/GB-mo; 10 GB free |
| Delivery | $0.005/GB Volume ⇒ **~$3–27/mo** for full-library viewing by 50–200 learners | $1/1,000 delivered min ⇒ **~$60–240/mo** if every learner watches everything (subtract plan allowances if you use Pro/Business) | Included in plan bandwidth | $0.0008 delivered min; **100k free min/mo** ⇒ likely $20-ish credit plan covers 20–60 viewers/mo | Free egress; $0.36/M GETs |
| Minimum | $1/mo | none (usage) | annual prepaid | $20 credit plan | pay-as-you-go |
| Token protection | Embed token (SHA-256)+ advanced CDN tokens covering HLS playlists **and segments**; Python signing example in their docs | Signed URLs; `/token` API (1 h default) or self-signed RS256 locally; AllowedOrigins | Server OTP API (`POST /videos/{id}/otp`, TTL ≥300 s, Python example) | Signed playback JWT (RS256, `exp`, 15-min→7-day examples) | Presigned per object (max 7 days) — **HLS needs every segment signed** |
| DRM | Enterprise DRM **$99/mo/library** + licenses (Widevine+FairPlay), contact-sales activation | none documented | **Widevine + FairPlay + dynamic per-viewer watermark** — strongest anti-redistribution story | $100/mo + per-license (widevine/fairplay/playready) | none |
| Player | own iframe player | own player or HLS/DASH | iframe or own player | Mux Player / HLS | own player needed |

## Recommendation

- **Practical default: Bunny Stream** — lowest delivery cost at this scale
  (~$3–6/mo for 50 full-course viewers), segment-covering tokens, Python
  signing documented, $1/mo minimum. Caveat: account in Bangladesh means
  delivery region matters; Standard network in Asia is $0.03/GB versus Volume
  $0.005/GB — worth confirming which network your library uses.
- **If budget predictability beats price: Cloudflare Stream** — minute-based,
  simple, but delivery is the biggest bill if learners rewatch a lot.
- **If the content is commercial/medical and redistribution is a real concern:
  VdoCipher Starter ($149/yr)** with Widevine+FairPlay and per-viewer dynamic
  watermarking — the only shortlisted provider that deters copying meaningfully
  out of the box. (Add-on note: Bunny Enterprise DRM costs $99/mo ≈ $1,188/yr —
  VdoCipher is cheaper for real DRM.)
- **DIY R2** is genuinely cheap but requires signing every segment request and
  a custom player — more moving parts for marginal saving over Bunny.

## Your decision is needed on:

1. **Provider** — Bunny / Cloudflare / VdoCipher / Mux / R2 (or decide later).
2. **Is DRM/watermark needed?** This decides Bunny vs VdoCipher outright.
3. **Expected scale** — library size (hours) and viewer count estimate.
4. **Am I allowed to create the account/provision keys** (or you'll sign up
   yourself and paste the key)?

## Phase 6 integration plan once you choose

`playback_authorize` stays as-is; a new `tutorials/providers/<name>.py` redeems
our Stage-A token into that provider's signed playback object:
` Tututorial.video_provider` selects the module. Revocation blocks *new* tokens
(already tested); already-issued provider tokens expire on their TTL.

## Sources

- Bunny Stream pricing docs: https://bunny.net/docs/stream/pricing ,
  https://bunny.net/pricing/stream/
- Bunny token security: https://bunny.net/docs/stream/token-authentication ,
  https://bunny.net/docs/cdn/security/token-authentication/advanced ,
  https://bunny.net/docs/stream/security
- Bunny DRM: https://bunny.net/docs/stream/drm
- Cloudflare Stream pricing: https://developers.cloudflare.com/stream/pricing/
- Cloudflare signed URLs: https://developers.cloudflare.com/stream/viewing-videos/securing-your-stream/
- Cloudflare own-player: https://developers.cloudflare.com/stream/viewing-videos/using-own-player/
- VdoCipher pricing: https://www.vdocipher.com/site/pricing/
- VdoCipher OTP API: https://www.vdocipher.com/docs/server/playbackauth/otp/
- VdoCipher DRM/watermark:
  https://www.vdocipher.com/dynamic-watermarking/ ,
  https://www.vdocipher.com/developer/
- Mux pricing: https://www.mux.com/pricing and
  https://www.mux.com/docs/pricing/overview
- Mux signed playback: https://www.mux.com/docs/guides/secure-video-playback
- R2 presigned URLs: https://developers.cloudflare.com/r2/api/s3/presigned-urls/
- R2 pricing: https://developers.cloudflare.com/r2/pricing/
- B2 pricing: https://www.backblaze.com/cloud-storage/pricing
- CloudFront signed cookies: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-cookies.html
