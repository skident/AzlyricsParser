import urllib2
import re
import httplib
import time
from ProxyParser import ProxyParser, DbConnector
import socket

import threading
import thread

class PseudoLocker:
    def acquire(self):
        return

    def release(self):
        return

class AzLyrics:
    __processed = list()
    __unprocessed = list()
    __proxyList = list()
    __conn = ""
    __dbPath = 'AzLyrics.db'
    __pagesTable = "Pages"
    __proxyParser = ProxyParser()

    # __lock = threading.Lock()
    __lock = PseudoLocker()

    # Open DB and get Processed and unprocessed URLs from it. Also prepare proxylist
    def __init__(self):
        self.__conn = DbConnector.Instance().handle()
        # self.fillProxyList()
        self.getPages()

    def getPages(self):
        cur = self.__conn.cursor()
        cur.execute("SELECT url, isProcessed FROM " + self.__pagesTable + " WHERE isProcessed = 0 LIMIT 25")
        rows = cur.fetchall()

        # clear before using
        self.__unprocessed = list()
        self.__processed = list()

        for row in rows:
            if row[1] == 0 or row[1] == None:
                self.__unprocessed.append(row[0])
            else:
                self.__processed.append(row[0])

        print("--------------------------------------------")
        print("Processed URLs count: ", len(self.__processed))
        print("Unprocessed URLs count: ", len(self.__unprocessed))
        print("--------------------------------------------")

    # def Start(self):
        # Create two threads as follows
        # try:
           # thread.start_new_thread( self.processUrls, (self, "Thread 1") )
           # thread.start_new_thread( self.processUrls, ("Thread 2") )
           #  thread1 = threading.Thread(self.processUrls, ("Thread #1")).start()

        # except:
        #    print "Error: unable to start thread"

    def fillProxyList(self):
        self.__lock.acquire()
        self.__proxyList = self.__proxyParser.getProxy()
        self.__lock.release()

    # Main loop of parsing site. It takes next URL from unprocessed list and processing it.
    def processUrls(self):
        print("Hello I'm thread")
        print(threading.currentThread())
        time.sleep(2)

        conn = self.__conn
        i = 0
        j = 0

        # timeout in seconds
        timeout = 10
        socket.setdefaulttimeout(timeout)

        while len(self.__unprocessed) > 0:
            if i >= len(self.__proxyList):
                i = 0

            if j >= len(self.__unprocessed):
                j = 0

            if len(self.__unprocessed) <= 1:
                self.getPages()
                self.fillProxyList()
                print("Proxies count: ", len(self.__proxyList))

            while len(self.__proxyList) == 0:
                print("Proxy list is empty. Trying to load fresh proxies")
                self.fillProxyList()
                if len(self.__proxyList) == 0:
                    print("PROXY LOADING FAILED: sleep for 5 min.")
                    time.sleep(300)  # sleep 5 seconds and try again

            self.__lock.acquire()
            currUrl = self.__unprocessed[j]
            currProxy = self.__proxyList[i]
            self.__lock.release()

            proxy = urllib2.ProxyHandler({'http': currProxy})
            opener = urllib2.build_opener(proxy)
            urllib2.install_opener(opener)

            print("[" + time.strftime("%H:%M:%S") + "] [#" + str(i) + "] Start processing URL: ", currUrl)
            rawdata = ""
            badProxy = True

            try:
                print("--------Current proxy: ", currProxy)

                self.__lock.acquire()
                response = urllib2.urlopen(currUrl)
                self.__lock.release()

                rawdata = response.read()
                badProxy = False

            except urllib2.HTTPError, e:
                print('HTTPError = ' + str(e.code))
                if e.code == 404:
                    i += 1
                    print("URL MARKED AS 404 ---->>>>")
                    # conn.execute("UPDATE "+ self.__pagesTable +" SET isProcessed=404 WHERE url = '"+currUrl+"'")
                    # conn.commit()
                    # self.__unprocessed.remove(currUrl)
                    self.markUrl(currUrl, 404)
                    continue

            except Exception:
                print('generic exception: ')

            if badProxy == True:
                print("--==BAD PROXY==--")
                self.__lock.acquire()
                self.__proxyParser.markAsBad(currProxy)
                self.__proxyList.remove(currProxy)
                self.__lock.release()

                continue #try to process this URL again

            self.markUrl(currUrl, 1)

            if rawdata == "":
                print("Page not loaded! Skip it and move forward ->")
                continue

            urls = self.parseUrls(rawdata)
            author = self.__parseAuthor(rawdata)
            songName = self.__parseSongName(rawdata)
            lyrics = self.__parseLyrics(rawdata)

            self.addUniqueUrls(urls)
            self.insertLyrics(author, songName, lyrics)

            conn.commit()

            j += 1
            i += 1

    def markUrl(self, currUrl, status):
        conn = self.__conn

        self.__lock.acquire()
        self.__unprocessed.remove(currUrl)
        self.__processed.append(currUrl)
        conn.execute("UPDATE "+ self.__pagesTable +" SET isProcessed = "+ str(status) +" WHERE url = '"+currUrl+"'")
        conn.commit()
        self.__lock.release()

    def addUniqueUrls(self, urls):
        if len(urls) == 0:
            return

        conn = self.__conn
        unique = 0

        self.__lock.acquire()
        for url in urls:
            try:
                if url not in self.__processed and url not in self.__unprocessed:
                    self.__unprocessed.append(url)
                    conn.execute("INSERT INTO "+ self.__pagesTable +" (url, isProcessed) "
                                                                           "VALUES ('" + url + "', 0)")
                    unique += 1
            except Exception:
                print("URL ", url, " already exists in DB")

        self.__lock.release()
        print("Found " + str(len(urls)) + " unique URL(s)")


    def insertLyrics(self, author, songName, lyrics):
        if author == "" or songName == "" or lyrics == "":
            return

        # print("Author: ", author)
        # print("Song name: ", songName)
        # print("Lyrics: ", lyrics)
        # print(urls)

        print("!!!Lyrics found!!!")
        conn = self.__conn

        self.__lock.acquire()

        request = 'SELECT _id FROM Lyrics WHERE band = "'+author+'" AND  song = "'+songName+'"'
        cur = conn.cursor()
        cur.execute(request)
        rows = cur.fetchall()
        if len(rows) == 0:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            request = 'insert into Lyrics (band, song, lyrics, timestamp) ' \
                      'values ("'+author+'","'+songName+'","'+lyrics+'", "'+timestamp+'")'
            conn.execute(request)
        else:
            print("UPS: Song already exists")

        self.__lock.release()


    def firstInit(self):
        base = "http://www.azlyrics.com/"
        letters = 'abcdefghijklmnopqrstuvwxyz'
        for char in letters:
            url = base + char + ".html"
            self.__conn.execute("INSERT INTO UnprocessedUrls (url) VALUES ('" + url + "')")
        self.__conn.commit()



    ################################################
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

    ################################################
    def Test(self):
        print("ssdf")

def main():
    lyrics = AzLyrics()
    lyrics.processUrls()

    # try:
        # th1 = threading.Thread(target=lyrics.processUrls(), args=())
        # th2 = threading.Thread(target=lyrics.Test(), args=())
        # th2 = threading.Thread(target=lyrics.processUrls(), args=())
        #
        # th2.start()
        # th1.start()
        # th1.join()
        # th2.join()
    #     pass
    # except:
    #    print "Error: unable to start thread"


main()


import threading

def foo(a, b):
    print(threading.currentThread())
    print("I'm thread")
    pass

# threading.Thread(target=foo, args=("some", "args")).start()
# threading.Thread(target=foo, args=("some", "args")).start()
