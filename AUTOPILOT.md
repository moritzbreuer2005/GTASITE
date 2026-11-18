# Autopilot: daily editor run

Instructions for the scheduled Claude routine that keeps this site's articles
up to date. Headlines refresh on their own every hour (GitHub Actions). This
routine handles the writing.

## Each run

1. **Check the news.** Search the web for GTA 6 news from the last 24 hours:
   Rockstar Newswire, official PlayStation, Xbox and Take-Two posts, and major
   gaming outlets. Only official sources or several reliable outlets count as
   confirmed. Anything else is a rumor and must be labelled as one.
2. **Update existing articles** in `content/en/posts/` when facts change, for
   example a PC announcement, GTA Online news, patches or price changes. Set
   `updated:` to today's date. Remove time-sensitive wording that is now wrong,
   such as "launches tomorrow" after launch.
3. **Write at most one new article** (English first) when there is a clear
   search demand. Good examples are a big patch, an official announcement or
   a guide topic many people are searching for. Skip the day if nothing
   qualifies. Never publish filler.
4. **Translate** every new or changed article into `content/de/posts/`,
   `content/es/posts/` and `content/fr/posts/`. Use the **same file name** in
   every language, a localized `slug:`, natural (not word-for-word) phrasing,
   and the same `[[ad]]` / `[[affiliate]]` markers. Link to other articles
   with `post:<file-name>` and to the news page with `page:news`.
5. **Check the build:** run `python build.py`. It must finish without errors.
6. **Commit and push** to `main` with a short message, such as
   "Update PC article; new guide: GTA 6 patch 1.02". GitHub publishes the
   site automatically.

## Rules

- Write everything in your own words. Never copy articles, never paste
  leaked or pirated material, and never use Rockstar's artwork or logos.
- Facts must be checkable. If unsure, say "reported" and name what is
  unconfirmed, or leave it out.
- Front matter must have `title`, `description` (one sentence, under 160
  characters), `date`, `updated` and `category`. Mark only one article per
  language `featured: true`: the most important story right now.
- Don't touch `site.json`, the legal pages or the code unless something is
  broken.
- Keep articles skimmable: a short direct answer first, then sections with
  `##` headings.
