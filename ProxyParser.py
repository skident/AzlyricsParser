# -*- coding: utf-8 -*-

import urllib2
import re
import httplib
import time
import sqlite3


class Singleton:
    """
    A non-thread-safe helper class to ease implementing singletons.
    This should be used as a decorator -- not a metaclass -- to the
    class that should be a singleton.

    The decorated class can define one `__init__` function that
    takes only the `self` argument. Other than that, there are
    no restrictions that apply to the decorated class.

    To get the singleton instance, use the `Instance` method. Trying
    to use `__call__` will result in a `TypeError` being raised.

    Limitations: The decorated class cannot be inherited from.

    """

    def __init__(self, decorated):
        self._decorated = decorated

    def Instance(self):
        """
        Returns the singleton instance. Upon its first call, it creates a
        new instance of the decorated class and calls its `__init__` method.
        On all subsequent calls, the already created instance is returned.

        """
        try:
            return self._instance
        except AttributeError:
            self._instance = self._decorated()
            return self._instance

    def __call__(self):
        raise TypeError('Singletons must be accessed through `Instance()`.')

    def __instancecheck__(self, inst):
        return isinstance(inst, self._decorated)

@Singleton
class DbConnector:
    __dbConnetion = ""
    __dbName = 'AzLyrics.db'

    def __init__(self):
        self.__dbConnetion = sqlite3.connect(self.__dbName)

    def open(self):
        if self.__dbConnetion == "":
            self.__dbConnetion = sqlite3.connect(self.__dbName)

    def close(self):
        if self.__dbConnetion != "":
            self.__dbConnetion.close()

    def handle(self):
        return self.__dbConnetion

class ProxyParser:
    __conn = ""
    __dbName = 'AzLyrics.db'
    __proxyTableName = "Proxy"
    __proxySite = "http://xseo.in/freeproxy"
    data = dict(submit=u"Показать по 150 прокси на странице")

    def __init__(self):
        # print("ProxyParser.__init__()")
        self.__conn = DbConnector.Instance().handle()
        # print("ProxyParser conn: ", self.__conn)

    # PARSE proxy from raw page
    def __parseProxyList(self, html):
        # print("ProxyParser: Parsing raw page")
        firstAnchor = '<table BORDER=0 CELLPADDING=0 CELLSPACING=0 width="100%" height="100%" style=\'border:0px\'>'
        secondAnchor = "</form>"

        pos = html.find(firstAnchor)
        if pos == -1:
            print("First anchor not found")
            return set()
        html = html[pos:html.find(secondAnchor, pos)]
        # print(html)

        proxies = re.findall(r'<font class=cls1>((\d{1,3}\.){3}\d{1,3}:\d{1,4})', html)

        parsedProxy = set()
        for url in proxies:
            parsedProxy.add(url[0])

        print("Parsed "+ str(len(parsedProxy))+" URL(s)")
        # print(parsedProxy)
        return parsedProxy

    # Update table with proxies
    def __processProxyList(self, freshProxyList):
        # print("ProxyParser: Insert fresh proxies to table")

        cur = self.__conn.cursor()
        cur.execute("SELECT url FROM " + self.__proxyTableName)
        rows = cur.fetchall()

        proxyList = set()
        for row in rows:
            proxyList.add(row[0])

        # print("Count of proxy in table: ", len(proxyList))
        print("<<<<<<<<<<< Count of fresh proxy: ", len(freshProxyList))

        counter = 0
        for url in freshProxyList:
            try:
                self.__conn.execute("INSERT INTO Proxy (url, isGood) VALUES ('"+url+"', 1)")
                counter += 1
            except Exception:
                # print('Can\'t insert')
                continue

        self.__conn.commit()  # Update all data
        print("*************Added " + str(counter) + " fresh proxy URL(s)**********************")

    # Load html page from internet
    def loadProxy(self):
        # print("ProxyParser: Load page with proxy")

        try:
            response = urllib2.urlopen(self.__proxySite)
            html = response.read()

            # html = ""
            # file = open("proxy.html", "r")
            # for line in file:
            #     html += line
            # file.close()

            # print(html)
            urls = self.__parseProxyList(html)
            if (len(urls) > 0):
                self.__processProxyList(urls)
        except Exception:
            print('...EXCEPTION ON PROXY LOADING...')

    #
    def getProxy(self):
        # print("ProxyParser: Request for proxies")

        self.loadProxy()

        # Select data
        cur = self.__conn.cursor()
        cur.execute("SELECT url FROM " + self.__proxyTableName + " WHERE isGood = 1")
        rows = cur.fetchall()

        proxyList = list()
        for row in rows:
            proxyList.append(row[0])

        return proxyList

    # Mark proxy as bad (not working)
    def markAsBad(self, url):
        self.__conn.execute("UPDATE Proxy SET isGood = 0 WHERE url = '"+url+"'")
        self.__conn.commit()



def main():
    proxyParser = ProxyParser()
    proxyList = proxyParser.getProxy()
    # proxyParser.MarkAsBad(proxyList[0])

    # print("TROLOL: ", proxyList)

main()

