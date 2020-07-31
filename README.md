# MangaTosho

#### What is this?
A auto-download and organization tool for manga series. Add urls for series, MT will auto-download new chapters and keep track of your progress letting you easily see and read new chapters with a double-click

#### Dependencies
- Node.js is required to bypass cloudflare protection. It is bundled with the windows binaries.
- If you wish to use selenium to bypass cloudflare challenges, you must provide your own selenium driver somewhere in your PATH.
- On non-windows systems you will also need your own comic reader, you can enter the launch command in Settings > Change Reader.

#### How to Use
Binaries are available if you are on windows, see [Releases](https://github.com/NeverDecaf/MangaTosho/releases/latest).

* Double click a series to read starting from the latest unread chapter.
* Right click a series for some options, rollback is useful for dud chapters.
* Some sites require credentials before you can use them, add these through the Settings menu.
* The "Read" field can be manually edited by double clicking.
* Double click the rating field to assign a rating.

Closing the main window will simply minimize it to tray. Click the tray icon to bring it back. You can also right-click the tray icon for some quick-access options.

#### Supported sites:
- MangaDex
- MangaSee
- MangaHere
- DynastyScans
- MangaReader
- MangaPanda
- MangaPark
- MangaStream
- MangaKakalot
- MangaNelo
- MangaWindow
- KissManga
- SadPanda
- HeavenToon

###### Known Bugs
* Dynasty series with no chapter numbers will fail.
