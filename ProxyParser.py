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
    # __proxySite = "http://xseo.in/freeproxy"
    data = dict(submit=u"Показать по 150 прокси на странице")

    def __init__(self):
        # print("ProxyParser.__init__()")
        self.__conn = DbConnector.Instance().handle()
        # print("ProxyParser conn: ", self.__conn)


    # Update table with proxies
    def __processProxyList(self, freshProxyList):
        if (len(freshProxyList) == 0):
            return

        cur = self.__conn.cursor()
        cur.execute("SELECT url FROM " + self.__proxyTableName)
        rows = cur.fetchall()

        proxyList = set()
        for row in rows:
            proxyList.add(row[0])

        counter = 0
        for url in freshProxyList:
            try:
                self.__conn.execute("INSERT INTO Proxy (url, isGood) VALUES ('"+url+"', 1)")
                counter += 1
            except Exception:
                # print('Can\'t insert')
                continue

        self.__conn.commit()  # Update all data
        if counter > 0:
            print("*************Added " + str(counter) + " fresh proxy URL(s)**********************")
        else:
            print("*************Have no fresh proxy*************")


    # PARSE proxy from raw page
    def parseXseoIn(self):
        site = "http://xseo.in/freeproxy"

        try:
            response = urllib2.urlopen(site)
            html = response.read()

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

            print(site, " : Parsed "+ str(len(parsedProxy))+" URL(s)")
            self.__processProxyList(parsedProxy)

        except Exception:
            print('...EXCEPTION ON PROXY LOADING...')
            # print(parsedProxy)
            # return parsedProxy



    def ParseProxyListOrg(self):
        site = "https://proxy-list.org/english/index.php"
        try:
            response = urllib2.urlopen(site)
            html = response.read()

            firstAnchor = '<div class="table-wrap">'
            secondAnchor = '<div class="table-menu">'

            pos = html.find(firstAnchor)
            if pos == -1:
                print("First anchor not found")
                return set()
            html = html[pos:html.find(secondAnchor, pos)]
            # print(html)

            proxies = re.findall(r'<li class="proxy">((\d{1,3}\.){3}\d{1,3}:\d{1,4})', html)
            # print(proxies)

            parsedProxy = set()
            for url in proxies:
                parsedProxy.add(url[0])

            print(site, " : Parsed "+ str(len(parsedProxy))+" URL(s)")
            self.__processProxyList(parsedProxy)

        except Exception:
            print('Proxy-list.org loading proxy exception')


    def ParseSslProxies(self):
        # the same pages
        site = "http://www.sslproxies.org/" #, "https://www.us-proxy.org/")

        # for site in sites:
        try:
            response = urllib2.urlopen(site)
            html = response.read()

            # <tr><td>152.2.81.209</td><td>8080</td>
            proxies = re.findall(r'<tr><td>(([0-9]{1,3}\.){3}[0-9]{1,3}</td><td>[0-9]{1,4})', html)
            # print(proxies)

            parsedProxy = set()
            delimiter = "</td><td>"
            for rawdata in proxies:
                data = rawdata[0]
                pos = data.find(delimiter)
                if pos == -1:
                    continue

                url = data[:pos] + ":" + data[pos+len(delimiter):]
                parsedProxy.add(url)
            # print(parsedProxy)
            print(site, " : Parsed "+ str(len(parsedProxy))+" URL(s)")
            self.__processProxyList(parsedProxy)

        except Exception:
            print(site, ' loading proxy exception')


    def ParseGatherproxy(self):
        site = "http://www.gatherproxy.com/"

        try:
            response = urllib2.urlopen(site)
            html = response.read()
            # print(html)

            proxies = re.findall(r'"PROXY_IP":"(.+)","PROXY_REFS"', html)
            # print(proxies)

            parsedProxy = set()
            delimiter = '"'
            for data in proxies:
                try:
                    ip = data[:data.find(delimiter)]
                    port = int(data[data.rfind(delimiter)+1:], 16)
                    url = ip + ":" + str(port)
                    parsedProxy.add(url)
                except Exception:
                    print("---Something wrong with ["+data+"]")
            # print(parsedProxy)

            print(site, " : Parsed "+ str(len(parsedProxy))+" URL(s)")
            self.__processProxyList(parsedProxy)

        except Exception:
            print(site, ' loading proxy exception')

    def getProxy(self):
        # print("ProxyParser: Request for proxies")

        self.ParseProxyListOrg()
        self.parseXseoIn()
        self.ParseSslProxies()
        self.ParseGatherproxy()

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

