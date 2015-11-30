import urllib2
import re
import httplib
import time
from ProxyParser import ProxyParser, DbConnector
import socket


class AzLyrics:
    __processed = list()
    __unprocessed = list()
    __proxyList = list()
    __conn = ""
    __dbPath = 'AzLyrics.db'
    __pagesTable = "Pages"
    __proxyParser = ProxyParser()

    # Open DB and get Processed and unprocessed URLs from it. Also prepare proxylist
    def __init__(self):
        self.__conn = DbConnector.Instance().handle()
        self.fillProxyList()

        cur = self.__conn.cursor()
        cur.execute("SELECT url, isProcessed FROM " + self.__pagesTable)
        rows = cur.fetchall()
        for row in rows:
            if row[1] == 1:
                self.__processed.append(row[0])
            else:
                self.__unprocessed.append(row[0])

        print("--------------------------------------------")
        print("Processed URLs count: ", len(self.__processed))
        print("Unprocessed URLs count: ", len(self.__unprocessed))
        print("--------------------------------------------")


    def fillProxyList(self):
        self.__proxyList = self.__proxyParser.getProxy()


    # Parse lyrics from raw html data
    def __parseLyrics(self, html):
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
    def __parseAuthor(self, html):
        authorAnchor = "ArtistName = \""
        startPos = html.find(authorAnchor)
        if (startPos == -1):
            return ""

        startPos += len(authorAnchor)
        author = html[startPos:html.find("\"", startPos)]

        return author

    # Parse name of song from raw html data
    def __parseSongName(self, html):
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
            if url.find(base) == -1 and url.find("http://") == -1:
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
            if url.find(base) == -1 and url.find("http://") == -1:
                newUrl.add(base + url)
            else:
                newUrl.add(url)

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
        conn = self.__conn
        i = 0

        # timeout in seconds
        timeout = 20
        socket.setdefaulttimeout(timeout)

        while len(self.__unprocessed) > 0:
            if i >= len(self.__proxyList):
                i = 0
                # print("]]]]]]]]------SLEEP FOR 10 SECOND-----[[[[[[[[[[[[[[")
                # time.sleep(timeout) # delays for N seconds

            while len(self.__proxyList) == 0:
                print("Proxy list is empty. Trying to load fresh proxies")
                self.fillProxyList()
                if len(self.__proxyList) == 0:
                    print("PROXY LOADING FAILED: sleep for 5 min.")
                    time.sleep(300)  # sleep 5 seconds and try again

            if i == 0:
                self.fillProxyList()
                print(""
                      "Proxies count: ", len(self.__proxyList))
            # else:
            #     time.sleep(2) # delays for N seconds


            proxy = urllib2.ProxyHandler({'http': self.__proxyList[i]})
            opener = urllib2.build_opener(proxy)
            urllib2.install_opener(opener)

            timestamp = time.strftime("%H:%M:%S")
            currUrl = self.__unprocessed[i]
            print("[" + timestamp + "] #" + str(i) + " Start processing URL: ", currUrl)
            html = ""
            isBadProxy = False

            try:
                print("--------Current proxy: ", self.__proxyList[i])
                # print("---------- Start loading ------------")
                response = urllib2.urlopen(currUrl)
                # print("---------- Stop loading ------------")
                html = response.read()
            except urllib2.HTTPError, e:
                print('HTTPError = ' + str(e.code))
                if e.code != 404:
                    isBadProxy = True
                else:
                    i += 1
                    print("URL REMOVED BUT NOT MARKED AS PROCESSED ---->>>>")
                    self.__unprocessed.remove(currUrl)
                    continue
            except Exception:
                print('generic exception: ')
                isBadProxy = True

            if isBadProxy == True:
                print("--==BAD PROXY==--")
                currProxy = self.__proxyList[i]
                self.__proxyParser.markAsBad(currProxy)
                self.__proxyList.remove(currProxy)

                continue #try to process this URL again

            self.__unprocessed.remove(currUrl)
            self.__processed.append(currUrl)
            conn.execute("UPDATE "+ self.__pagesTable +" SET isProcessed = 1 WHERE url = '"+currUrl+"'")

            if html == "":
                print("Page not loaded! Skip it and move forward ->")
                continue

            urls = self.parseUrls(html)
            author = self.__parseAuthor(html)
            songName = self.__parseSongName(html)
            lyrics = self.__parseLyrics(html)

            unique = 0
            for url in urls:
                if url not in self.__processed and url not in self.__unprocessed:
                    self.__unprocessed.append(url)
                    self.__conn.execute("INSERT INTO "+ self.__pagesTable +" (url, isProcessed) "
                                                                           "VALUES ('" + url + "', 0)")
                    unique += 1
            print("Found " + str(len(urls)) + " unique URL(s)")

            i += 1

            if author != "" and songName != "" and lyrics != "":
                # print("Author: ", author)
                # print("Song name: ", songName)
                # print("Lyrics: ", lyrics)
                # print(urls)

                print("!!!Lyrics found!!!")

                # add data to sqlite
                request = 'insert into Lyrics (band, song, lyrics) values ("'+author+'","'+songName+'","'+lyrics+'")'
                conn.execute(request)

            conn.commit()

    def firstInit(self):
        base = "http://www.azlyrics.com/"
        letters = 'abcdefghijklmnopqrstuvwxyz'
        for char in letters:
            url = base + char + ".html"
            self.__conn.execute("INSERT INTO UnprocessedUrls (url) VALUES ('" + url + "')")
        self.__conn.commit()


def main():
    lyrics = AzLyrics()
    lyrics.processUrls()


main()

