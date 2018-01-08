# MangaTosho

#### What is this?
A auto-download and organization tool for manga series. Add urls for series, MT will auto-download new chapters and keep track of your progress letting you easily see and read new chapters with a double-click

#### Dependencies
Node.js is now required to bypass cloudflare protection. It is bundled with the windows binaries.

#### How to Use
Binaries are available if you are on windows, see [Releases](https://github.com/NeverDecaf/MangaTosho/releases/latest).

* Double click a series to read starting from the latest unread chapter.
* Right click a series for some options, rollback is useful for dud chapters.
* Some sites require credentials before you can use them, add these through the file menu.
* The "Read" field can be manually edited by double clicking.

Closing the main window will simply minimize it to tray. Double-click the icon to bring it back. You can also right-click the tray icon for some quick-access options.

#### Series Color Guide
Blue: All good.  
Red: Parser error, MT needs an update.  
Green: Other error, most likely the series is missing an image/chapter, you can increment "Read" to bypass this  
Purple: licensed.  
Gray: Series has been marked as complete by either you or the site. (Newly added series also appear gray but this is a bug.)  

All colors will fade based on the amount of time since the last update. The darker the color the longer the time. A light green or red will likely fix itself over time but a darker one indicates a permanent problem.

#### Supported sites (likely outdated):
- mangakakalot
- mangastream
- mangawindow
- mangapark
- mangapanda
- mangareader
- kissmanga
- dynasty-scans
- mangahere
- mangaseeonline
- batoto
- exhentai

###### Known Bugs
* Readme sucks.
* Dynasty series with no chapter numbers will fail (red)
