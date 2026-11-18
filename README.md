# Wanted Level: GTA 6 news site (EN / DE / ES / FR)

A fast GTA 6 news and guide site in four languages that runs by itself. It earns money through ads (Google AdSense), affiliate links (Amazon) and, optionally, a newsletter.

## How it stays up to date on its own

| What | How often | Who does it |
|---|---|---|
| News headlines in all 4 languages | Every hour | GitHub Actions (`.github/workflows/update-site.yml`), free |
| Rebuilding and publishing the site | Every hour and after every change | GitHub Actions |
| Updating articles, writing new ones, translating them | Daily | A scheduled Claude routine following `AUTOPILOT.md` |

Once it is on GitHub, you don't need to run anything.

## One-time setup

1. **GitHub:** Create a free account and a new **public** repository. Upload this folder to it.
2. In the repository, open **Settings > Pages** and set Source to **GitHub Actions**. The site goes live a few minutes later.
3. **Domain (recommended, about €10 a year):** Buy one, for example `wantedlevel.gg` or `wantedlevel.news`. Connect it in Settings > Pages, then set `base_url` in `site.json`.
4. **Daily editor:** Connect GitHub to Claude, then create a daily routine on this repository with the prompt: *"Follow AUTOPILOT.md."*

## Making money

Fill these in `site.json` once your accounts are approved:

| Setting | What it is |
|---|---|
| `adsense_client`, `ad_slots` | Google AdSense publisher ID and ad unit IDs. `ads.txt` is generated for you. |
| `amazon_tags` | Your Amazon tracking ID per store (amazon.com, .de, .es and .fr are separate programs). Tags and disclosures are added automatically. |
| `newsletter_url` | Signup page of your newsletter (for example beehiiv). A signup box appears automatically. |
| `goatcounter_code` | Free, cookie-free visitor stats (goatcounter.com). |
| `google_site_verification` | For Google Search Console. |
| `show_ad_placeholders` | Set to `false` before going live. |

**Before applying for AdSense:** fill in your details in the `content/*/pages/imprint.md` files (the Impressum is legally required in Germany), add your contact email in the about pages, and switch on Google's certified consent message in AdSense (required for EU visitors).

## Running it on your PC (optional)

```
python fetch_news.py      # fresh headlines
python build.py           # build into public/
python -m http.server 8765 --directory public   # preview at http://localhost:8765
```

`pip install pillow` additionally generates the social-share images.

## Files

| What | Where |
|---|---|
| Settings | `site.json` |
| Interface text and menu per language | `i18n.json` |
| Articles | `content/<lang>/posts/*.md` |
| About, privacy, imprint | `content/<lang>/pages/*.md` |
| Design | `static/style.css` |

## Writing an article

```
---
title: GTA 6 Best Cars Ranked
description: One sentence. This shows in Google results.
slug: gta-6-best-cars          (optional, defaults to the file name)
date: 2026-11-20
updated: 2026-11-20
category: Guide
featured: true                 (optional: pins it as the front-page lead)
---
Intro paragraph...

## A heading

- bullet

[[ad]]           an ad slot
[[affiliate]]    the "Where to buy" box
[[newsletter]]   the newsletter signup box
[link text](post:other-file-name)   link to another article, in the same language
<!-- notes to yourself are never published -->
```

Translations use the **same file name** in `content/de/posts/`, `content/es/posts/` and `content/fr/posts/`. The language switcher and Google's language tags connect them automatically.
