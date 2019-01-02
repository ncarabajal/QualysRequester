import threading
import logging
import requests
import xmltodict
from io import StringIO, BytesIO
import json
import os
import signal
import sys
import queue
from time import sleep

# https://www.qualys.com/docs/qualys-api-quick-reference.pdf
# https://www.qualys.com/docs/qualys-api-v2-user-guide.pdf

class QualysRequester():
	headers = {
		'X-Requested-With': 'Report Requester: Qualys'
	}

	def signal_handler(self, sig, frame):
		print('You pressed Ctrl+C!')
		self.logout()
		sys.exit(0)

	def __init__(self, loglevel=logging.INFO):
		"""Initialization for requester."""
		# Init logging
		logging.basicConfig(level=loglevel, format='%(asctime)s - %(filename)s - %(threadName)s - %(levelname)s - %(message)s')
		logging.debug(sys.version)

		# Initialize needed variables for the class instance
		self.conf = {}
		self.reports = {}
		self.last_update = None
		self.download_queue = queue.Queue()
		# Always load config when created
		self.loadconfig()
		signal.signal(signal.SIGINT, self.signal_handler)

	def loadconfig(self, configname='config.json'):
		"""Loads main config from disk.
		Keyword arguments:
		configname -- Filename of config to load (default 'config.json')
		"""
		logging.info(f"Loading config from '{configname}'")
		with open(configname, 'r') as conffile:
			self.conf = json.load(conffile)

	def load_report_cache(self):
		"""Load cache of reports from disk."""
		logging.info('Loading Report Cache')
		logging.error('UNIMPLEMENTED: load_report_cache()')

	def run(self):
		"""The  main entrypoint for the requester"""
		logging.debug('Starting')
		self.load_report_cache()
		self.rs = requests.session()
		self.authenticate()
		# TODO - create worker pool
		while True:
			try:
				self.get_report_list()
				# TODO - figure out which reports need to be downloaded
				self.enqueue_reports()
				# TODO - add reports to queue
				self.download_reports()
			except Exception as e:
				logging.exception(e)
			break
			t = self.conf['reload_interval']
			logging.debug(f'Sleeping for {t} minute(s)')
			sleep(t * 60)
		self.logout()
		logging.debug('Stopping')

	def enqueue_reports(self):
		"""Figure out which reports still need to be downloaded."""
		# TODO - hash each report with something like sha256 for validation?
		logging.debug('Enqueing reports starting')
		for t,r in self.reports.items():
			logging.debug(f'Processing report {r}')
			if r['LAST_ID'] != r['ID']:
				logging.debug(f'Found undownloaded report {r}')
				if r['OUTPUT_FORMAT'] in self.conf['report_formats']:
					logging.debug(f'Enquing {r}')
					self.download_queue.put({'ID':r['ID'], 'TITLE':r['TITLE'], 'OUTPUT_FORMAT':r['OUTPUT_FORMAT']})
				else:
					logging.debug(f'Skipping Report {r} not TYPE HERE')
		logging.debug('Enqueing reports finished')

	def download_reports(self):
		while True:
			if not self.download_queue.empty():
				# TODO - make sure there is something try except in case another thread already got it
				# TODO - file handling
				rp = self.download_queue.get()
				filename = f"downloads/{rp['TITLE']}-{rp['ID']}-RAW.{rp['OUTPUT_FORMAT']}"
				# TODO - DO NOT CLOBBER FILES
				logging.info(f'Downloading report {rp} as {filename}')
				data = {
					'action': 'fetch',
					'id': rp['ID']
				}
				rs = self.qualys_post('report/', headers=self.headers, data=data)
				with open(filename, 'wb') as f:
					for chunk in rs.iter_content(chunk_size=1024):
						if chunk: # Filter out keep-alive new chunks
							f.write(chunk)
					# Don't need to close the file when using with like this
			else:
				logging.debug('Queue empty')
			t = self.conf['download_interval']
			logging.debug(f'Sleeping for {t} minute(s)')
			sleep(t * 60)

	def get_auth_data(self):
		return {
			'username': self.conf['username'],
			'password': self.conf['password']
		}

	def logout(self):
		logging.info('Logging out')
		data = {
			'action': 'logout'
		}
		r = self.qualys_post('session/', headers=self.headers, data=data)
		logging.debug(r.content)

	def get_report_list(self):
		logging.info('Downloading report list')
		data = {
			'action': 'list',
			'state': 'Finished'
		}
		r = self.qualys_post('report/', headers=self.headers, data=data)
		logging.debug(f'Report list response {r}')
		# Stream the data into the parser with BytesIO
		xdict = xmltodict.parse(BytesIO(r.content))
		# Iterate over every report and build or update the cache as needed
		for r in xdict['REPORT_LIST_OUTPUT']['RESPONSE']['REPORT_LIST']['REPORT']:
			# r keys 'ID', 'TITLE', 'TYPE', 'USER_LOGIN', 'LAUNCH_DATETIME', 'OUTPUT_FORMAT', 'SIZE', 'STATUS', 'EXPIRATION_DATETIME'
			# TODO - Configurable filter
			#if r['TITLE'].startswith('CUT'):
			if any(r['TITLE'].startswith(prf) for prf in self.conf['prefixes']):
				if r['TITLE'] not in self.reports:
					logging.debug(f"Adding new report {r['TITLE']}")
					self.reports[r['TITLE']] = r
					self.reports[r['TITLE']]['LAST_ID'] = None
				else:
					logging.debug(f"Updating report {r['TITLE']}")
					logging.error('Updating report unimplemented')
			else:
				logging.debug(f"Skipping report {r['TITLE']}")

	def get_report_list2(self):
		logging.info('Downloading report list')
		data = {}
		data['action'] = 'list'
		data['state'] = 'Finished'
		r = self.qualys_post('report/', headers=self.headers, data=data)
		#root = etree.parse(BytesIO(r.content))
		# TODO https://lxml.de/parsing.html #Error log
		#ro = objectify(r)
		#logging.debug()
		ro = objectify.fromstring(r.content)
		#ro = objectify.parse(BytesIO(r.content))
		root = ro.getroot()
		logging.debug(len(root))
		logging.debug(root.tag)
		for rep in root['REPORT_LIST_OUTPUT']['RESPONSE']['REPORT_LIST'].iter(tag="REPORT"):
			logging.debug(rep)

	def download_saved_report(self, reportid, reporttitle, reportformat):
		logging.info('Downloading saved report')
		data = {
			'action': 'fetch',
			'id': reportid
		}
		r = self.qualys_post('report/', headers=self.headers, data=data)
		with open(f'/reports/qualys/{reporttitle}.{reportformat}', 'wb') as handle:
			for chunk in r.iter_content(chunk_size=512):
				if chunk:
					handle.write(chunk)

	def authenticate(self):
		logging.info('Authenticating')
		data = {
			'username': self.conf['username'],
			'password': self.conf['password']
		}
		data['action'] = 'login'
		r = self.qualys_post('session/', headers=self.headers, data=data)
		logging.debug(f'Authentication response {r.content}')

	def authenticate2(self):
		logging.info('Authenticating')
		r = requests.post(url=self.conf['url']+'session/', headers=self.headers, data={'action':'login','username':self.conf['username'],'password':self.conf['password']})
		logging.debug(r)
		logging.debug(r.text)

	def qualys_post(self, endpoint, headers={}, data={}):
		url = self.conf['url']+endpoint
		logging.debug(f'Posting to {url}\tHeaders: {headers}\tData: {data}')
		#r = requests.post(url=url, headers=self.headers, data=data, stream=True)
		# stream=True keep memory usage down
		r = self.rs.post(url=url, headers=self.headers, data=data, stream=True)
		if r.status_code != requests.codes.ok:
			logging.error(f'Problem posting to {url}')
			logging.debug(r.content)
		return r

if __name__ == '__main__':
	level = logging.getLevelName(os.getenv('LOGLEVEL', 'INFO'))
	r = QualysRequester(level)
	r.run()
