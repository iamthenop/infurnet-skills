# [Brand Name] — Social Implementation

> Implements the brand defined in `brand-core-template.md` for social media. Every value here should trace back to a core value — this doc adapts those to fixed canvas sizes, safe zones, and per-platform lockups rather than making new brand decisions. If a color, font, or slogan isn't in the core doc, add it there first.

---

## 0. Source of Truth

| Core value | Defined in core doc as | Implemented here as |
|---|---|---|
| Hero color | `#[HEX]` | Profile/highlight accent color across all platforms |
| Primary tagline | "[Slogan]" | Bio line / channel description copy |

---

## 1. Logo — Per-Platform Lockups

| Platform | Format used | Dimensions | Safe zone | Notes |
|---|---|---|---|---|
| [Platform, e.g. Instagram] | [Icon mark only / profile crop] | [110x110px min] | [circular crop — keep mark within the inner 80% of a square canvas] | [avatar crops to a circle — test the mark against that crop] |
| [Platform, e.g. LinkedIn] | [Horizontal lockup] | [Company page banner: 1128x191px] | [keep logo clear of the profile photo overlap zone] | |
| [Platform, e.g. YouTube] | [Icon mark] | [800x800px, circular crop] | | |
| [Platform, e.g. X/Twitter] | [Icon mark] | [400x400px, circular crop] | | |

---

## 2. Crop Ratios & Safe Zones by Content Type

| Content type | Platform(s) | Ratio | Safe zone notes |
|---|---|---|---|
| Feed post (square) | [Instagram, Facebook] | [1:1] | [keep key content out of the bottom 15% — UI overlays crop it] |
| Feed post (portrait) | [Instagram] | [4:5] | |
| Story / vertical | [Instagram, TikTok, Snapchat] | [9:16] | [top ~14% and bottom ~20% covered by platform UI — keep text/logo out of those bands] |
| Landscape / video thumbnail | [YouTube, LinkedIn] | [16:9] | |
| Carousel | [Instagram, LinkedIn] | [1:1 or 4:5, consistent across all slides] | |

---

## 3. Color — Social Implementation

- **Profile elements:** [e.g. hero color used for highlight covers, story ring accents where the platform allows customization]
- **Overlay text on photography:** [e.g. always use the near-black or off-white from the core palette for text-on-image, never a raw accent color — legibility over branding here]

---

## 4. Typography — Social Implementation

- **In-graphic type:** [e.g. use the core heading typeface for quote graphics/announcement tiles; fall back to platform-native fonts for anything the platform renders as live text, like captions]
- **Caption formatting conventions:** [e.g. sentence case, no more than one emoji per caption, hashtags placed in first comment not caption body]

---

## 5. Voice — Per-Channel Notes

*Implements the core doc's voice/tone for each channel's norms — tone doesn't change, but register and format do.*

| Platform | Register notes |
|---|---|
| [LinkedIn] | [e.g. slightly more formal, no emoji in headlines, thought-leadership framing OK] |
| [Instagram/TikTok] | [e.g. more casual, first-person, can lean into humor more than other channels] |
| [X/Twitter] | [e.g. terse, can be more reactive/timely than other channels] |

**Hashtag & tagging rules:** [e.g. always include [#branded-hashtag]; never tag competitors]

---

## 6. Imagery — Social Implementation

- **Photography crop/treatment:** [e.g. always crop to the ratios in Section 2 at the source — don't rely on platform auto-crop]
- **Video specs:** [e.g. 1080x1920 vertical minimum resolution, captions burned in for accessibility]
- **Thumbnail rules:** [e.g. always include a face or the logo mark — thumbnails without either underperform]

---

## 7. Accessibility — Social Implementation

- **Alt text:** [required on every image post — core doc principle, resolved to: write descriptive alt text, don't rely on platform auto-alt-text]
- **Captions:** [required on all video content]
- **Contrast on graphics:** [text overlays must meet the core doc's contrast principle even against photography backgrounds — add a scrim/gradient if needed]
