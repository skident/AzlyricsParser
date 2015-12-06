import urllib2
import re
import time
from ProxyParser import ProxyParser, DbConnector
import socket
import sqlite3
import threading

locker = threading.Lock()
proxy_loader = ProxyParser()
proxy_list = list()
pages_list = list()

def mark_as_bad(curr_proxy, conn):
    proxy_loader.markAsBad(curr_proxy, conn)

def get_proxy():
    global proxy_list

    curr_proxy = ""
    if len(proxy_list) <= 10:
        proxy_list = proxy_loader.getProxy()

    if len(proxy_list) > 0:
        curr_proxy = proxy_list[0]
        proxy_list.remove(curr_proxy)

    return curr_proxy


def return_proxy(curr_proxy):
    global proxy_list
    proxy_list.append(curr_proxy)



###############################
def get_pages(conn):
    global  pages_list

    if len(pages_list) == 0:
        cur = conn.cursor()
        query = "SELECT url, isProcessed FROM Pages WHERE isProcessed = 0"

        cur.execute(query)
        rows = cur.fetchall()

        pages_list = list()

        for row in rows:
            pages_list.append(row[0])

        print("--------------------------------------------")
        print("Unprocessed URLs count: ", len(pages_list))
        print("--------------------------------------------")

    curr_page = ""
    if len(pages_list) > 0:
        curr_page = pages_list[0]
        pages_list.remove(curr_page)
    return curr_page

def mark_page(currUrl, status, conn):
    conn.execute("UPDATE Pages SET isProcessed = "+ str(status) +" WHERE url = '"+currUrl+"'")
    conn.commit()


#############################################3

class AzLyrics(threading.Thread):
    __dbName = 'AzLyrics.db'
    __pagesTable = "Pages"

    # Open DB and get Processed and unprocessed URLs from it. Also prepare proxylist
    def __init__(self, limits):
        threading.Thread.__init__(self)

    # Main loop of parsing site. It takes next URL from unprocessed list and processing it.
    def run(self):
        global locker

        locker.acquire()
        conn = sqlite3.connect(self.__dbName)
        locker.release()

        need_new_page = True
        timeout = 10 # timeout in seconds
        socket.setdefaulttimeout(timeout)
        currUrl = ""

        # if unprocessed URL(s) exist - process they
        while True:
            # get proxy and page for processing
            locker.acquire()
            if need_new_page:
                currUrl = get_pages(conn)
            currProxy = get_proxy()
            locker.release()

            if currUrl == "":
                print("Have no URL(s) for processing")
                break

            # set proxy
            proxy = urllib2.ProxyHandler({'http': currProxy})
            opener = urllib2.build_opener(proxy)
            urllib2.install_opener(opener)

            # trace info
            print("[" +str(threading.currentThread())+ "] [" + time.strftime("%H:%M:%S") + "] "
                  "["+str(currProxy)+"] [" + currUrl + "]")
            rawdata = ""
            badProxy = True

            try:
                start_point = time.time()
                response = urllib2.urlopen(currUrl)
                end_point = time.time()

                # To slowwww
                if end_point - start_point > 20:
                    print("Timeout ...")
                    badProxy = True
                else:
                    rawdata = response.read()
                    badProxy = False

            except urllib2.HTTPError, e:
                print('HTTPError = ' + str(e.code))
                if e.code == 404:
                    locker.acquire()
                    mark_page(currUrl, 404, conn)
                    return_proxy(currProxy)
                    locker.release()

                    need_new_page = True
                    continue

            except Exception:
                badProxy = True

            if badProxy == True:
                print("--==BAD PROXY==--")
                locker.acquire()
                mark_as_bad(currProxy, conn)
                locker.release()

                need_new_page = False
                continue

            need_new_page = True

            locker.acquire()
            return_proxy(currProxy)
            mark_page(currUrl, 1, conn)
            locker.release()

            if rawdata == "":
                print("Page not loaded! Skip it and move forward ---->")
                continue

            # search lyrics and other URL(s) on this page
            urls = self.parseUrls(rawdata)
            author = self.__parseAuthor(rawdata)
            songName = self.__parseSongName(rawdata)
            lyrics = self.__parseLyrics(rawdata)

            locker.acquire()
            self.addUniqueUrls(urls, conn)
            self.insertLyrics(author, songName, lyrics, conn)

            conn.commit()
            locker.release()


        print("Thread ", threading.currentThread(), " has finished work")

    # update URL(s) list
    def addUniqueUrls(self, urls, conn):
        if len(urls) == 0:
            return

        unique = 0
        # Page already in table if exception, otherwise - all is ok
        for url in urls:
            try:
                conn.execute("INSERT INTO "+ self.__pagesTable +" (url, isProcessed) "
                                                          "VALUES ('" + url + "', 0)")
                unique += 1
            except Exception:
                print("URL ", url, " already exists in DB")
        print("Found " + str(len(urls)) + " unique URL(s)")


    # insert lyrics to DB (only unique lyrics will be inserted)
    def insertLyrics(self, author, songName, lyrics, conn):
        if author == "" or songName == "" or lyrics == "":
            return

        request = 'SELECT _id FROM Lyrics WHERE band = "'+author+'" AND  song = "'+songName+'"'
        cur = conn.cursor()
        cur.execute(request)
        rows = cur.fetchall()
        if len(rows) == 0:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            request = 'INSERT INTO Lyrics (band, song, lyrics, timestamp) ' \
                      'VALUES ("'+author+'","'+songName+'","'+lyrics+'", "'+timestamp+'")'
            conn.execute(request)
        else:
            print("UPS: Song already exists")

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


def main():
    global proxy_loader
    startId = 1
    endId = 200000

    conn = sqlite3.connect("AzLyrics.db")
    cur = conn.cursor()

    cur.execute('SELECT _id FROM Pages WHERE isProcessed = 0 LIMIT 1')
    rows = cur.fetchall()
    if len(rows) == 0:
        startId = rows[0]

    cur.execute('SELECT _id FROM Pages WHERE isProcessed = 0 ORDER BY _id DESC LIMIT 1')
    rows = cur.fetchall()
    if len(rows) == 0:
        endId = rows[0]


    threads = 6
    count_of_url = (endId - startId) / threads

    workers = []
    for i in range(1, threads+1):
        j = i + 1
        worker = AzLyrics((i*count_of_url, j*count_of_url))
        worker.start()
        workers.append(worker)

    # proxy_loader = ProxyParser()
    # proxy_loader.attach_locker(locker)
    # proxy_loader.start()

    while True:
        print("[" +str(threading.currentThread())+ "] [SLEEP FOR 2.5 MIN]")
        time.sleep(60)
        locker.acquire()
        proxy_loader.parse_proxy()
        locker.release()


main()
