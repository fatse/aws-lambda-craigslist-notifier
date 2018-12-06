import os
from datetime import datetime
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
import datetime
import urllib3
import re
import boto3

class CraigsListPost(object):
	def __init__(self, listing_id, url, price, location, housing, name, date_time):
		self.listing_id = listing_id
		self.url = url
		self.price = price
		self.location = location
		self.housing = housing
		self.name = name
		self.date_time = date_time


# URL of the site to check, stored in the site environment variable
url = os.environ['url']
# ARN of the sns topic to which the notifications will be sent
arn = os.environ['arn']

snsClient = boto3.client('sns')
lambdaClient = boto3.client('lambda')

def make_soup(url):
    http = urllib3.PoolManager()
    r = http.request("GET", url)
    return BeautifulSoup(r.data,'html.parser')

def safe_text(tag):
	if not hasattr(tag, 'text'):
		return ''
	else:
		return re.sub('[\s+]', ' ', tag.text)

def get_listings(soup_object):
	apartments = soup_object.find_all('li', class_='result-row')

	listings = []
	for ap in apartments:
		apt_id = ap.attrs['data-pid']
		html_title = ap.find('a', class_='result-title')
		apt_url = html_title.attrs['href']
		apt_name = html_title.text
		apt_date = ap.find('time').attrs['title']
		apt_price = safe_text(ap.find(class_='result-price'))
		apt_housing = safe_text(ap.find(class_='housing'))
		apt_hood = safe_text(ap.find(class_='result-hood'))
		listing = CraigsListPost(apt_id, apt_url, apt_price, apt_hood, apt_housing, apt_name, apt_date)
		listings.append(listing)
	return listings

def build_message(listing):
	return "\n".join([listing.url, listing.price, listing.name, listing.location, listing.housing, listing.date_time])

def publish_to_sns(message):
	# print(message)
	response = snsClient.publish(TargetArn=arn, Message=message, MessageStructure='text')

def update_latest_id(listing_id, context):
	lambdaArn = context.invoked_function_arn
	response = lambdaClient.get_function_configuration(FunctionName=lambdaArn)
	variables = response['Environment']['Variables']

	variables['latest_listing'] = listing_id
	lambdaClient.update_function_configuration(
    	FunctionName=lambdaArn,
		Environment={
        	'Variables': variables
    	}
    )

def get_only_new_listings(listings):
	
	if 'latest_listing' in os.environ:
		latest_listing = os.environ['latest_listing']
		
		new_listings = []
		for listing in listings:
			if listing.listing_id == latest_listing:
				break
			else:
				new_listings.append(listing)
		return new_listings
	else:
		return listings

def main(context):
	soup = make_soup(url)
	listings = get_listings(soup)
	new_listings = get_only_new_listings(listings)
	message = "\n-----------\n".join([build_message(x) for x in new_listings])
	if len(new_listings) != 0:
		publish_to_sns(message)
		latest_id = listings[0].listing_id
		update_latest_id(latest_id, context)
	
def lambda_handler(event, context):
    main(context)


