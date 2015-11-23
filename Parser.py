import urllib2
import re
import httplib
import time
import sqlite3


class AzLyrics:
    __processed = set()
    __unprocessed = set()
    __proxyList = set()
    __dbConnetion = ""
    __dbPath = 'AzLyrics.db'
    __proxyFileName = "proxylist"

    # Open DB and get Processed and unprocessed URLs from it. Also prepare proxylist
    def __init__(self):
        self.fillProxyList()
        self.__dbConnetion = sqlite3.connect(self.__dbPath)

        cur = self.__dbConnetion.cursor()
        cur.execute("SELECT url FROM ProcessedUrls")
        rows = cur.fetchall()
        for row in rows:
            self.__processed.add(row)

        cur.execute("SELECT url FROM UnprocessedUrls")
        rows = cur.fetchall()
        for row in rows:
            self.__unprocessed.add(row[0])

        print("Processed URLs: ", self.__processed)
        print("Unprocessed URLs: ", self.__unprocessed)

    # Open already prepared file and get all proxy servers from it
    def fillProxyList(self):
        file = open(self.__proxyFileName, "r")
        for line in file:
            self.__proxyList.add(line[:-1])
        file.close()
        print(self.__proxyList)

    # Parse lyrics from raw html data
    def parseLyrics(self, html):
        startSong = "<!-- Usage of azlyrics.com content by any third-party lyrics provider is prohibited by our licensing agreement. Sorry about that. -->"
        endSong = "</div>"

        startPos = html.find(startSong)
        if (startPos == -1):
            return ""

        startPos += len(startSong)
        endPos = html.find(endSong, startPos)
        song = html[startPos:endPos]

        return song

    # Parse author from raw html data
    def parseAuthor(self, html):
        authorAnchor = "ArtistName = \""
        startPos = html.find(authorAnchor)
        if (startPos == -1):
            return ""

        startPos += len(authorAnchor)
        author = html[startPos:html.find("\"", startPos)]

        return author

    # Parse name of song from raw html data
    def parseSongName(self, html):
        songNameAnchor = "SongName = \""
        startPos = html.find(songNameAnchor)
        if (startPos == -1):
            return ""

        startPos += len(songNameAnchor)
        songName = html[startPos:html.find("\"", startPos)]

        return songName

    # Find block of bands URLs and parse it
    def __findBandsUrls(self, html):
        base = "http://www.azlyrics.com/"
        anchor = "<div class=\"container main-page\">"

        pos = html.find(anchor)
        if pos == -1:
            return set()

        html = html[pos:html.find("</div>", pos)]
        # print(html)

        urls = re.findall(r'"[^\s]+?(?:html)', html)

        newUrl = set()
        for url in urls:
            if url.find(base) == -1:
                newUrl.add(base + url[1:])
            else:
                newUrl.add(url[1:])

        return newUrl

    # Find block with songs URLs and parse it
    def __findSongsUrls(self, html):
        base = "http://www.azlyrics.com/"
        firstAnchor = "<!-- start of song list -->"
        secondAnchor = "<!-- end of song list -->"

        pos = html.find(firstAnchor)
        if pos == -1:
            return set()

        html = html[pos:html.find(secondAnchor, pos)]
        # print(html)

        urls = re.findall(r'\.\./lyrics/[^\s]+?(?:html)', html)

        newUrl = set()
        for url in urls:
            url = url[3:]
            if url.find(base) == -1:
                newUrl.add(base + url)
            else:
                newUrl.add(url)

        # print(newUrl)
        return newUrl

    # Parse needed URLs from raw html data
    def parseUrls(self, html):
        bands = self.__findBandsUrls(html)
        if len(bands) > 0:
            return bands

        songs = self.__findSongsUrls(html)
        return songs


    # Main loop of parsing site. It takes next URL from unprocessed list and processing it.
    def processUrls(self):
        i = 0
        while len(self.__unprocessed) > 0:
            if i >= len(self.__proxyList):
                i = 0
                time.sleep(10) # delays for 5 seconds

            proxy = urllib2.ProxyHandler({'http': list(self.__proxyList)[i]})
            opener = urllib2.build_opener(proxy)
            urllib2.install_opener(opener)

            currUrl = self.__unprocessed.pop()
            print(currUrl)
            html = ""

            try:
                response = urllib2.urlopen(currUrl)
                html = response.read()
            except urllib2.HTTPError, e:
                needChangeProxy = True
                print('HTTPError = ' + str(e.code))
            except urllib2.URLError, e:
                needChangeProxy = True
                print('URLError = ' + str(e.reason))
            except httplib.HTTPException, e:
                needChangeProxy = True
                print('HTTPException', e.message)
            except Exception:
                print('generic exception: ')
                needChangeProxy = True

            if needChangeProxy == True:
                if len(self.__proxyList) == 0:
                    print("Need more proxy!!!")
                    return
                else:
                    print("Need remove item #", i)

                # proxy = urllib2.ProxyHandler({'http': self.__proxyList.pop()})
                # opener = urllib2.build_opener(proxy)
                # urllib2.install_opener(opener)
                # needChangeProxy = False

            urls = self.parseUrls(html)
            author = self.parseAuthor(html)
            songName = self.parseSongName(html)
            lyrics = self.parseLyrics(html)

            self.__processed.add(currUrl)
            self.__dbConnetion.execute("INSERT INTO ProcessedUrls (url) VALUES ('"+str(currUrl)+"')")
            self.__dbConnetion.execute("DELETE ProcessedUrls WHERE url = '"+str(currUrl)+"'")



            for url in urls:
                if url not in self.__processed:
                    self.__unprocessed.add(url)
                    self.__dbConnetion.execute("INSERT INTO UnprocessedUrls (url) VALUES ('"+url+"')")


            i += 1


            if i % 10 == 0:
                print("URL # ", i)

            if author != "" and songName != "" and lyrics != "":
                print("Author: ", author)
                print("Song name: ", songName)
                print("Lyrics: ", lyrics)
                print(urls)

                # add data to sqlite
                request = 'insert into Lyrics (band, song, lyrics) values ("'+author+'","'+songName+'","'+lyrics+'")'
                self.__dbConnetion.execute(request)

            self.__dbConnetion.commit()  # Update all data

    def firstInit(self):
        base = "http://www.azlyrics.com/"
        letters = 'abcdefghijklmnopqrstuvwxyz'
        for char in letters:
            url = base + char + ".html"
            self.__dbConnetion.execute("INSERT INTO UnprocessedUrls (url) VALUES ('"+url+"')")
        self.__dbConnetion.commit()


def main():
    lyrics = AzLyrics()
    # lyrics.firstInit()
    # lyrics.fillProxyList();
    # lyrics.initUnprocessed();
    lyrics.processUrls()


main()

