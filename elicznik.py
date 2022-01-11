#!/usr/bin/env python

import requests
from requests import adapters
import ssl
from urllib3 import poolmanager
import datetime
import json


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
	headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:52.0) Gecko/20100101 Firefox/52.0'} 
	service = 'https://elicznik.tauron-dystrybucja.pl'
	
	def __init__(self, credentials_dict):
		self.username = credentials_dict['username']
		self.password = credentials_dict['password']
		self.meter_id = int(credentials_dict['meter_id'])
		
	def get_consumption(self, n_days=1):
		payload = { 
                'username': self.username,
                'password': self.password,
                'service': self.service
		}
		
		session = requests.session()
		session.mount('https://', TLSAdapter())

		p = session.request("POST", self.url, data=payload, headers=self.headers)
		p = session.request("POST", self.url, data=payload, headers=self.headers)

		chart = {
					#change timedelta to get data from another days (1 for yesterday)
						"dane[chartDay]": (datetime.datetime.now() - datetime.timedelta(n_days)).strftime('%d.%m.%Y'),
						"dane[paramType]": "day",
						"dane[smartNr]": self.meter_id,
					#comment if don't want generated energy data in JSON output:
						"dane[checkOZE]": "on"
		}

		r = session.request("POST", self.charturl, data=chart, headers=self.headers)
		return r.text

def main():
    with open('credentials.json', 'r') as cred:
        credentials = json.load(cred)
    licznik = Elicznik(credentials)
    txt = licznik.get_consumption(n_days=2)
    print(txt)


if __name__ == '__main__':
    main()


#Optionally write JSON to file
#with open('file.json', 'wb') as f:
#    f.write(r.content)
