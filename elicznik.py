#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import json
import logging as log
import re
import ssl
from html.parser import HTMLParser

import requests
from requests import adapters
from urllib3 import poolmanager

ONE_DAY = datetime.timedelta(days=1)
TODAY = datetime.date.today()


class TauronMetersParser(HTMLParser):
    '''Based on an example from: https://docs.python.org/3.7/library/html.parser.html'''

    def __init__(self):
        super(TauronMetersParser, self).__init__()
        self.pobor_found = False
        self.date_found = False
        self.prod_found = False
        self.date = None
        self.pobr = []
        self.prod = []

    def handle_data(self, data):
        if data == 'Pobór:':
            self.pobor_found = True

        if data == 'Oddanie:':
            self.prod_found = True

        if self.pobor_found or self.prod_found:
            matched_date = re.match(r'([0-9]{2})\.([0-9]{2})\.([0-9]{4}) \(([0-9]{2}):([0-9]{2}):([0-9]{2})\)', data)
            if matched_date:
                datetime_ints = [int(x) for x in matched_date.groups()]
                found_dt = datetime.datetime(year=datetime_ints[2],
                                             month=datetime_ints[1],
                                             day=datetime_ints[0],
                                             hour=datetime_ints[3],
                                             minute=datetime_ints[4],
                                             second=datetime_ints[5],
                                             )
                self.date_found = True
                self.date = found_dt
        if (self.pobor_found or self.prod_found) and self.date_found and self.lasttag == 'span':
            matched_6digits = re.match(r'[0-9]{6}', data)
            if matched_6digits:
                if self.pobor_found:
                    self.pobr.append((self.date, int(matched_6digits.string)))
                if self.prod_found:
                    self.prod.append((self.date, int(matched_6digits.string)))

                self.pobor_found = False
                self.date_found = False
                self.prod_found = False
                # print("Encountered some data  :", data)


def dmy2date(str_):
    return datetime.date(int(str_.split('.')[2]), int(str_.split('.')[1]), int(str_.split('.')[0]))


# noinspection PyMethodOverriding
class TLSAdapter(adapters.HTTPAdapter):

    def init_poolmanager(self, connections, maxsize, block=False):
        """Create and initialize the urllib3 PoolManager."""
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_context=ctx)


class Elicznik:
    url = 'https://logowanie.tauron-dystrybucja.pl/login'
    charturl = 'https://elicznik.tauron-dystrybucja.pl/index/charts'
    meters_url = 'https://elicznik.tauron-dystrybucja.pl/odczyty'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:52.0) Gecko/20100101 Firefox/52.0'}
    service = 'https://elicznik.tauron-dystrybucja.pl'

    def __init__(self, credentials_dict):
        self.username = credentials_dict['username']
        self.password = credentials_dict['password']
        self.meter_id = int(credentials_dict['meter_id'])
        self.payload = {
            'username': self.username,
            'password': self.password,
            'service': self.service
        }

    def get_daily_raw(self, n_days=1):

        session = requests.session()
        session.mount('https://', TLSAdapter())

        p = session.request("POST", self.url, data=self.payload, headers=self.headers)
        p = session.request("POST", self.url, data=self.payload, headers=self.headers)

        chart = {
            # change timedelta to get data from another days (1 for yesterday)
            "dane[chartDay]": (datetime.datetime.now() - datetime.timedelta(n_days)).strftime('%d.%m.%Y'),
            "dane[paramType]": "day",
            "dane[smartNr]": self.meter_id,
            # comment if don't want generated energy data in JSON output:
            "dane[checkOZE]": "on"
        }

        r = session.request("POST", self.charturl, data=chart, headers=self.headers)
        return r.json()

    def pick_daily_stats(self, stats_dump):
        try:
            pobr_data = dmy2date(stats_dump['name']['chart'][-10:])
            prod_data = dmy2date(stats_dump['name']['OZE'][-10:])
        except KeyError:
            log.error('Pobrane dane sa niekompletne.')
            return
        pobr_kwh = stats_dump['sum']
        prod_kwh = stats_dump['OZEValue']
        is_full = stats_dump['isFull']
        if pobr_data == prod_data:
            return (pobr_data, pobr_kwh, prod_kwh, is_full)
        else:
            log.error('Daty produkcji i poboru sa rozne.')
            return

    def get_daily_info(self, n_days):
        daily_data_raw = self.get_daily_raw(n_days=n_days)
        daily_data = self.pick_daily_stats(daily_data_raw)
        if daily_data[0] + ONE_DAY * n_days == TODAY:
            if daily_data[3]:
                return daily_data
            else:
                log.error('Dane z {} dni temu sa niekompletne.'.format(n_days))
                return
        else:
            log.error('Brak danych z {} dni temu.'.format(n_days))
            return

    def get_last_meters_raw(self):

        session = requests.session()
        session.mount('https://', TLSAdapter())

        p = session.request("POST", self.url, data=self.payload, headers=self.headers)
        p = session.request("POST", self.url, data=self.payload, headers=self.headers)


        r = session.request("GET", self.meters_url, headers=self.headers)
        return r.text

    def parse_html(self, html_feed):
        htp = TauronMetersParser()
        htp.feed(html_feed)
        return htp.pobr, htp.prod

    def get_last_meters(self):
        return self.parse_html(self.get_last_meters_raw())


def main():
    with open('credentials.json', 'r') as cred:
        credentials = json.load(cred)
    licznik = Elicznik(credentials)
    pobranie, oddanie = licznik.get_last_meters()

    print(pobranie)
    print(oddanie)

    '''
    for n in range(1, 7):
        txt = licznik.get_daily_info(n)
        print(txt)
'''

if __name__ == '__main__':
    main()

# Optionally write JSON to file
# with open('file.json', 'wb') as f:
#    f.write(r.content)
