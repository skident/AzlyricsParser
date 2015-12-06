# -*- coding: utf-8 -*-

import urllib2
import re
import httplib
import time
import sqlite3
import threading


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


# class ProxyParser(threading.Thread):
class ProxyParser():
    __conn = ""
    __threadconn = ""
    __dbName = 'AzLyrics.db'
    __proxyTableName = "Proxy"
    __locker = ""
    # __proxySite = "http://xseo.in/freeproxy"
    # data = dict(submit=u"Показать по 150 прокси на странице")

    # def __init__(self):
        # threading.Thread.__init__(self)
        # self.__locker = locker


        # print("ProxyParser.__init__()")
        # self.__conn = DbConnector.Instance().handle()
        # print("ProxyParser conn: ", self.__conn)


    # Update table with proxies
    def __processProxyList(self, freshProxyList, conn):

        if (len(freshProxyList) == 0):
            return

        cur = conn.cursor()
        cur.execute("SELECT url FROM " + self.__proxyTableName)
        rows = cur.fetchall()

        proxyList = set()
        for row in rows:
            proxyList.add(row[0])

        counter = 0
        for url in freshProxyList:
            try:
                conn.execute("INSERT INTO Proxy (url, isGood) VALUES ('"+url+"', 1)")
                counter += 1
            except Exception:
                # print('Can\'t insert')
                continue

        conn.commit()  # Update all data
        if counter > 0:
            print("*************Added " + str(counter) + " fresh proxy URL(s)**********************")
        else:
            print("*************Have no fresh proxy*************")


    # PARSE proxy from raw page
    def parseXseoIn(self):
        site = "http://xseo.in/freeproxy"
        parsedProxy = set()

        try:
            response = urllib2.urlopen(site)
            html = response.read()

            firstAnchor = '<table BORDER=0 CELLPADDING=0 CELLSPACING=0 width="100%" height="100%" style=\'border:0px\'>'
            secondAnchor = "</form>"

            pos = html.find(firstAnchor)
            if pos == -1:
                print("First anchor not found")
                return parsedProxy
            html = html[pos:html.find(secondAnchor, pos)]
            # print(html)

            proxies = re.findall(r'<font class=cls1>((\d{1,3}\.){3}\d{1,3}:\d{1,4})', html)

            for url in proxies:
                parsedProxy.add(url[0])

        except Exception:
            print('...EXCEPTION ON PROXY LOADING...')

        return parsedProxy


    def ParseProxyListOrg(self):
        site = "https://proxy-list.org/english/index.php"
        parsedProxy = set()

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

            for url in proxies:
                parsedProxy.add(url[0])

        except Exception:
            print('Proxy-list.org loading proxy exception')

        return parsedProxy


    def ParseSslProxies(self):
        site = "http://www.sslproxies.org/" #, "https://www.us-proxy.org/")
        parsedProxy = set()

        try:
            response = urllib2.urlopen(site)
            html = response.read()

            # <tr><td>152.2.81.209</td><td>8080</td>
            proxies = re.findall(r'<tr><td>(([0-9]{1,3}\.){3}[0-9]{1,3}</td><td>[0-9]{1,4})', html)

            delimiter = "</td><td>"
            for rawdata in proxies:
                data = rawdata[0]
                pos = data.find(delimiter)
                if pos == -1:
                    continue

                url = data[:pos] + ":" + data[pos+len(delimiter):]
                parsedProxy.add(url)

        except Exception:
            print(site, ' loading proxy exception')

        return parsedProxy


    def ParseGatherproxy(self):
        site = "http://www.gatherproxy.com/"
        parsedProxy = set()

        try:
            response = urllib2.urlopen(site)
            html = response.read()

            proxies = re.findall(r'"PROXY_IP":"(.+)","PROXY_REFS"', html)

            delimiter = '"'
            for data in proxies:
                try:
                    ip = data[:data.find(delimiter)]
                    port = int(data[data.rfind(delimiter)+1:], 16)
                    url = ip + ":" + str(port)
                    parsedProxy.add(url)
                except Exception:
                    print("---Something wrong with ["+data+"]")

        except Exception:
            print(site, ' loading proxy exception')

        return parsedProxy


    def ParseHideMyIp(self):
        site = "https://www.hide-my-ip.com/proxylist.shtml"
        parsedProxy = set()

        try:
            response = urllib2.urlopen(site)
            html = response.read()

            proxies = re.findall(r'{"i":"(.+)","c"', html)

            delimiter = '","p":"'
            for data in proxies:
                try:
                    pos = data.find(delimiter)
                    ip = data[:pos]
                    port = data[pos+len(delimiter):]
                    url = ip + ":" + port
                    # print(url)

                    parsedProxy.add(url)
                except Exception:
                    print("---Something wrong with [" + data + "]")
        except Exception:
            print(site, ' loading proxy exception')

        return parsedProxy



    # def run(self):
    def parse_proxy(self):
        urls = set()
        print("thread #1 started")
        while True:
            tmp = self.ParseProxyListOrg()
            urls |= tmp

            tmp = self.parseXseoIn()
            urls |= tmp

            tmp = self.ParseSslProxies()
            urls |= tmp

            tmp = self.ParseGatherproxy()
            urls |= tmp

            tmp = self.ParseHideMyIp()
            urls |= tmp


            print("Loaded ", len(urls), " proxy")

            # self.__locker.acquire()
            conn = sqlite3.connect(self.__dbName)
            self.__processProxyList(urls, conn)
            # self.__locker.release()

            # print("sleep for 1 min ...")
            # time.sleep(60)

            break

    def getProxy(self):
        # print("ProxyParser: Request for proxies")
        # self.loadProxy()

        # Select data
        # locker.acquire()
        conn = sqlite3.connect(self.__dbName)
        cur = conn.cursor()
        # cur = DbConnector.Instance().handle().cursor()
        cur.execute("SELECT url FROM " + self.__proxyTableName + " WHERE isGood = 1")
        rows = cur.fetchall()
        # locker.release()

        proxyList = list()
        for row in rows:
            proxyList.append(row[0])

        return proxyList

    # Mark proxy as bad (not working)
    def markAsBad(self, url, conn):
        # conn = sqlite3.connect(self.__dbName)
        conn.execute("UPDATE Proxy SET isGood = 0 WHERE url = '"+url+"'")
        conn.commit()

    def attach_locker(self, locker):
        self.__locker = locker





def main():
    proxyParser = ProxyParser()
    proxyParser.start()

    print("thread #2 started")
    proxyParser.join()
        # proxyList = proxyParser.getProxy()
        # proxyParser.MarkAsBad(proxyList[0])

        # print("TROLOL: ", proxyList)

# main()

