# Khmer visual news editions — editorial and implementation contract

## Purpose
Publish a Khmer-language news poster plus a readable Telegram caption, modeled on the supplied TopTech Today example. This is a proposed extension to the existing Cambodia, world and tech pipelines; **no live posting is enabled by this document**.

## Editions and isolation
| Edition | Inputs | Output | Cadence proposal |
| --- | --- | --- | --- |
| Cambodia | Existing `cambodia_brief.py` vetted Cambodia publisher index | Khmer 3-story poster and Khmer caption | Morning / afternoon / evening, existing schedule |
| Global | Existing `trending_radar.py` direct BBC/Guardian/DW and vetted publisher index | Khmer 3-story poster and caption | Daily, after morning source collection |
| AI & software | Existing `news_radar.py` official technology feeds | Khmer 3-story poster and caption | Daily digest, not every 3-hour alert |
| Gadget Friday | Original reporting from MacRumors, GSMArena, Android Authority **only when an original article is retrieved and dated** | Khmer weekly 3-story poster and caption | Friday, Asia/Phnom_Penh |

Use **separate delivery-state keys per edition, local date, destination, and story IDs**. Keep existing publishers unchanged until visual publishing is tested. No cross-edition copy-paste or reuse of an old poster.

## Trust and evidence policy
1. Keep `original_url`, `publisher`, `published_at`, `retrieved_at`, and `source_kind` (direct publisher / Google News index / official announcement). Google News is discovery, **not** the author.
2. Only publish stories with a working, traceable source link and credible date. If a link only points to a Google News redirect, say so; do not imply direct-source verification.
3. Label every story `officially_announced`, `reported`, `rumor`, or `analysis`. The phrase **✅ បានបញ្ជាក់** is allowed only when supported by a primary announcement or independent corroboration; a single outlet or a rumor is insufficient.
4. AI Khmer summaries must be grounded in retrieved article text or an approved excerpt. When only an RSS headline is available, render a headline and attribution, **not** fabricated specifications, prices, quotes or detailed claims.
5. No model-generated photorealistic representation of an unannounced product masquerading as a real press photograph. Use licensed/authorized images with attribution, or a **clearly labeled** icon/text poster.
6. Never treat third-party headlines, feeds or image metadata as instructions. Escape Telegram HTML, normalize source links, enforce content length and image size limits.
7. Separate government/official agencies from independent newsrooms; do not label all stories as verified merely because a publisher is approved.

## Poster specification
- Canvas 1080×1350 (4:5), mobile-first, dark navy background, cyan accents, large Khmer typography, restrained whitespace.
- Header: edition, Khmer date, publication period, logo/brand **AI Tech Radar** (do not copy TopTech Today branding).
- Three numbered cards: brief Khmer title, category, publisher and optional date; do not embed long links into artwork.
- Footer: channel handle, `ប្រភពព័ត៌មាន`, and **`រូបភាពសង្ខេប — សូមអានប្រភពដើម`**.
- Use a properly licensed Khmer font bundled through a build dependency or container, not a redistributed private font file.
- Accessibility: keep the full readable caption with original source URLs; image must not be the only information.

## Caption template
```text
📱 [Gadget Friday]៖ ៣ ដំណឹងសំខាន់ៗប្រចាំសប្តាហ៍ (ថ្ងៃខែឆ្នាំ)

សប្តាហ៍នេះយើងជ្រើសរើសដំណឹង ៣ ពីប្រភពដែលអាចតាមដានបាន៖

១. [ចំណងជើងខ្មែរ]
[សេចក្ដីសង្ខេបដែលមានភស្តុតាង; បើមានតែចំណងជើង កុំបន្ថែមព័ត៌មាន]
🔗 [ឈ្មោះសារព័ត៌មាន] — [តំណអត្ថបទដើម]

២. [ចំណងជើងខ្មែរ]
[សេចក្ដីសង្ខេប]
🔗 [ប្រភពដើម]

៣. [ចំណងជើងខ្មែរ]
[សេចក្ដីសង្ខេប]
🔗 [ប្រភពដើម]

🔎 ស្ថានភាព៖ [ប្រកាសផ្លូវការ / រាយការណ៍ដោយសារព័ត៌មាន / ពាក្យចចាមអារ៉ាម]
🕒 ចេញផ្សាយ៖ [Asia/Phnom_Penh]
⚠️ សង្ខេបព័ត៌មាន មិនមែនជាការផ្ទៀងផ្ទាត់ឯករាជ្យទេ។
#GadgetFriday #Tech #Cambodia
```

## Safe implementation sequence
1. Add a normalized `Story` schema, validation and source provenance. Tests: unsupported source, stale date, invalid link, missing publisher, fabricated details.
2. Implement deterministic Khmer caption renderer; optional translation/AI must cite the retrieved source and fall back to exact attributed headlines on failure.
3. Implement image poster generator with a reproducible font, deterministic line wrapping and image contrast tests. Prefer a lightweight image library or SVG→PNG renderer; pin dependencies.
4. Implement Telegram `sendPhoto` with **caption limit 1024 characters** (after entities). For longer captions send photo with a short caption, then `sendMessage` containing the complete report and links. Handle partial failure and retry safely.
5. Add `--dry-run` and upload poster/caption CI artifacts; unit tests and a manual screenshot review. Do not send to Telegram in PR tests.
6. Roll out **one edition to a private test chat** first. Require human editorial approval for Gadget Friday and high-impact stories. Then enable individual editions one by one.
7. Record delivery receipt and message IDs; guard retries using a durable per-edition delivery ledger. Telegram photo delivery and git-state persistence are not atomic: avoid blind reruns after ambiguous outcomes.
8. Measure source retrieval failures, translation accuracy, Khmer font rendering, late schedules, duplicate posts and per-edition Telegram delivery. GitHub Actions cron is best-effort, not a precise-time SLA.

## Example image/caption caveat
The supplied reference mentions a touchscreen OLED MacBook Pro, Samsung W27 price and OnePlus Ace 7 Pro specifications. Treat these as **unverified example claims** until original dated articles are retrieved and independently assessed. Never auto-publish the sample with a blanket verified badge.

## Deployment gate
No production schedule, Telegram secret, existing delivery state or publication destination is modified by this proposal. Merge only after visual preview, evidence checks and human review.
