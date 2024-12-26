#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys
import re
import wget
import regex
from atproto import Client
from atproto import client_utils
from atproto import models
import requests
import feedparser
from bs4 import BeautifulSoup

your_handle = '***.bsky.social'
your_pwd = ''

feedsUrl = ['http://exemple.com/rss1.xml', 'http://exemple.com/rss2.xml']
hashtags = ['feedBluesky', 'Bluesky']

database = 'feedBluesky-db.txt'
tmpdir = 'tmp'
show_summary = [False, False]
show_picture = [False, False]
maxmsg = [2, 2]
maxchar = [300, 300]
logged = False

bluesky = Client()

for idx, feedUrl in enumerate(feedsUrl):
	nbmsg = 0
	feed = feedparser.parse(feedUrl)

	for item in reversed(feed.entries):
		send = True
		soup = BeautifulSoup(item.title, 'lxml')
		title = soup.text
		soup = BeautifulSoup(item.summary, 'lxml')
		summary = soup.text
		link = item.link
		imgEmbed = ''
		embed = ''

		msg = client_utils.TextBuilder()
		msg.text(title + '\n\n')

		if show_summary[idx]:
			msg.text('"' + summary + '"\n\n')

		msg.link(link, link)

		if hashtags:
			msg.text('\n\n')

		for idtag, tag in enumerate(hashtags):
			msg.tag('#' + tag + ' ', tag)

		msgtxt = regex.findall(r'\X', msg.build_text())

		if show_summary[idx] and len(msgtxt) > maxchar[idx] and len(summary) > (len(msgtxt) - maxchar[idx]) - 2:
			if hashtags:
				maxsum = len(summary) - (len(msgtxt) - maxchar[idx]) - 2
			else:
				maxsum = len(summary) - (len(msgtxt) - maxchar[idx]) - 1

			msg = client_utils.TextBuilder()
			msg.text(title + '\n\n')
			msg.text('"' + summary[:maxsum] + '…"\n\n')
			msg.link(link, link)

			msgtxt = regex.findall(r'\X', msg.build_text())

			if hashtags and len(msgtxt) <= maxchar[idx] - (len(hashtags) + 1):
				msg.text('\n\n')
				for idtag, tag in enumerate(hashtags):
					msg.tag('#' + tag + ' ', tag)
		elif len(msgtxt) > maxchar[idx] and len(title) > (len(msgtxt) - maxchar[idx]) - 1:
			maxtitle = len(title) - (len(msgtxt) - maxchar[idx]) - 1

			msg = client_utils.TextBuilder()
			msg.text(title[:maxtitle] + '…\n\n')
			msg.link('', link)

			msgtxt = regex.findall(r'\X', msg.build_text())

			if hashtags and len(msgtxt) <= maxchar[idx] - (len(hashtags) + 1):
				msg.text('\n\n')
				for idtag, tag in enumerate(hashtags):
					msg.tag('#' + tag + ' ', tag)

		msgtxt = regex.findall(r'\X', msg.build_text())

		if len(msgtxt) > maxchar[idx]:
			send = False

		if os.path.exists(database):
			db = open(database, "r+")
			entries = db.readlines()
		else:
			db = open(database, "a+")
			entries = []

		for entry in entries:
			if link in entry:
				send = False

		if send:
			if not logged:
				bluesky.login(your_handle, your_pwd)
				logged = True

			resp = requests.get(link)
			soup = BeautifulSoup(resp.text, "html.parser")
			imgEmbed = soup.find("meta", property="og:image")
			imgEmbed = imgEmbed["content"]

			if imgEmbed:
				thumbf = requests.get(imgEmbed, stream=True)

				if thumbf.status_code == 200:
					img_data = thumbf.raw.read()
					thumb = bluesky.upload_blob(img_data)

					embed = models.AppBskyEmbedExternal.Main(
						external=models.AppBskyEmbedExternal.External(
							title=title,
							description=summary,
							uri=link,
							thumb=thumb.blob,
						)
					)

			if show_picture[idx] and item.enclosures:
				if item.enclosures[0].type[:5] == 'image' and int(item.enclosures[0].length) <= 1000000:
					tmpfilename = item.enclosures[0].href.split('/')[-1]
					tmppath = tmpdir + '/' + tmpfilename
					picture = tmppath

					if not os.path.exists(tmpdir):
						os.mkdir(tmpdir)

					wget.download(item.enclosures[0].href, tmppath)

					with open(picture, 'rb') as f:
						img_data = f.read()

					bluesky.send_image(text=msg, image=img_data, image_alt='')

					os.remove(tmppath)
			elif embed:
				bluesky.send_post(msg, embed=embed)
			else:
				bluesky.send_post(msg)

			db.write(link + '\n')
			db.flush()

			nbmsg = nbmsg + 1
			if nbmsg >= maxmsg[idx]:
				break

		db.close()

if os.path.exists(tmpdir):
	os.rmdir(tmpdir)
