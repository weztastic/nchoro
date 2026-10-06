# Recording games to a Google Sheet

One-time setup, about 5 minutes. You need a Google account.

1. Go to https://sheets.new to create a new spreadsheet. Name it, for example, **Nchoro games**.
2. In the spreadsheet: **Extensions → Apps Script**.
3. Delete what's in the editor, paste the full contents of `sheets/Code.gs`, and click **Save** (disk icon).
4. Click **Deploy → New deployment**.
   - Click the gear icon next to "Select type" and choose **Web app**.
   - Description: `Nchoro recorder`
   - Execute as: **Me**
   - Who has access: **Anyone**
   - Click **Deploy**.
5. Google asks you to authorise the script. Choose your account. On the "Google hasn't verified this app" screen,
   click **Advanced → Go to (project name) (unsafe)**. This is normal for your own scripts. Then click **Allow**.
   The script can only touch this one spreadsheet.
6. Copy the **Web app URL**. It looks like `https://script.google.com/macros/s/AKfy…/exec`.
7. Put it in `site.json` in the project root (or give it to Claude):

   ```json
   { "sheets_url": "https://script.google.com/macros/s/AKfy…/exec" }
   ```

   Then rebuild: `.venv/bin/python artifact/build.py`, and commit and push `docs/`.

The first game recorded creates a sheet tab called **games**, with one row per game.

## Reading the results

- Open the spreadsheet. Every row is one game.
- To check and summarise them: **File → Download → Comma-separated values (.csv)**, then
  `.venv/bin/python artifact/records.py ~/Downloads/Nchoro\ games\ -\ games.csv`

## If you change Code.gs later

**Deploy → Manage deployments → (pencil icon) → Version: New version → Deploy.** The URL stays the same.
