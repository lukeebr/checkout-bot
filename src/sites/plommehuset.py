#-------------------------------------
import asyncio, httpx, json, threading
from bs4 import BeautifulSoup
from utils import Module, createShort
#-------------IMPORTS-----------------

class Plommehuset(Module):
    def __init__(self, task, proxies, taskID, settings, taskData):
        #initialisere alle variablene for klassen vår
        super().__init__('Plommehuset', taskID)
        self.task = task
        self.proxies = proxies
        self.delay = float(self.task['Delay'])
        self.link = self.task['Link']
        self.taskData = taskData
        self.settings = settings

        #set payment ID
        if self.task['Payment'].lower() == 'vipps':
            self.paymentID = 'vipps'
        else:
            print(f'Unsupported payment method: {self.task["Payment"]}')
            return

    async def run(self):
        #kontroller for alle funksjonene
        await self.formatProxy()
        async with httpx.AsyncClient(proxies=self.proxy, timeout=None) as self.session:
            await self.monitor()
            await self.atc()
            await self.submitBilling()
            await self.submitShipping()
            await self.submitPaymentMethod()
            await self.submitOrder()

    async def checkTaskData(self):
        #sjekker om noen andre tasks har lagret informasjon om produktet slik at vi kan hente den der
        #veldig nyttig under høy traffik på nettsiden
        if self.link in self.taskData:
            self.product_image = self.taskData[self.link]['Image']
            self.product_name = self.taskData[self.link]['Name']
            self.product_price = self.taskData[self.link]['Price']
            return True
        else:
            return False

    async def monitor(self):
        while True:
            if await self.checkTaskData():
                return

            #hent produkt siden
            await self.pending('Getting product page')
            try:
                page = await self.session.get(self.link)
            except Exception as e:
                await self.error(f'Exception getting product page: {e}')
                await asyncio.sleep(self.delay)
                continue

            if page.status_code != 200:
                await self.error(f'Failed getting product page {[page.status_code]}')
                await asyncio.sleep(self.delay)
                continue
            else:
                try:
                    #lese teksten på siden med bs4
                    soup = BeautifulSoup(page.text, 'html.parser')
                except:
                    await self.error('Failed parsing product page')
                    await asyncio.sleep(self.delay)
                    continue

                try:
                    #sjekk om produktet er tilgjengelig
                    if 'Legg i handlekurv' in page.text:
                        #hent all informasjon om produktet
                        self.product_image = soup.find('a', {'class':'gallery'})['href']
                        self.product_name = soup.find('h1').text
                        self.product_price = soup.find('span',{'class':'product-price products_price'}).text
                        self.pid = soup.find('input', {'name':'products_id'})['value']
                            
                        #oppdater dicten om produkt informasjon
                        await self.updateTaskData(self.link, {'Image':self.product_image,'Name':self.product_name,'Price':self.product_price})
                        return
                    else:
                        await self.pending('Waiting for restock')
                        await asyncio.sleep(self.delay)
                        continue
                except:
                    await self.error('Failed parsing product data')
                    await asyncio.sleep(self.delay)
                    continue

    async def atc(self):
        while True:
            #data for å legge til produktet i handlevognen
            data = {
                'products_id': self.pid,
                'quantity': '1'
            }

            #legg til produtket i handlevognen
            await self.pending('Adding product to cart')
            try:
                atc = await self.session.post('https://www.plommehuset.no/ajax.php?ajaxfunc=cart_buy_now', data=data)
            except Exception as e:
                await self.error(f'Exception adding product to cart: {e}')
                await asyncio.sleep(self.delay)
                continue

            if atc.status_code != 200:
                await self.error(f'Failed adding product to cart [{str(atc.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                await self.updateStatusBar('cart')
                await self.success(f'Successfully added {self.product_name} to cart')
                return

    async def submitBilling(self):
        while True:
            #data for å sende faktureringsinformasjon
            data = {
                'action': 'setBillTo',
                'billing_email_address': self.task['Profile']['Email'],
                'billing_firstname': self.task['Profile']['First Name'],
                'billing_lastname': self.task['Profile']['Last Name'],
                'billing_gender': '',
                'billing_company': '',
                'company_number': '',
                'billing_street_address': self.task['Profile']['Address'],
                'billing_zipcode': self.task['Profile']['ZIP'],
                'billing_state': self.task['Profile']['State'],
                'billing_city': self.task['Profile']['City'],
                'billing_telephone': self.task['Profile']['Phone'],
                'password': '',
                'billing_country': self.task['Profile']['Country'],
                'billing_newsletter': '1'
            }

            
            #send faktureringsinformasjon til nettsiden
            await self.pending('Submitting billing')
            try:
                submit_billing = await self.session.post('https://www.plommehuset.no/checkout/?rType=ajax', data=data)
            except Exception as e:
                await self.error(f'Exception submitting billing: {e}')
                await asyncio.sleep(self.delay)
                continue

            if submit_billing.status_code != 200:
                await self.error(f'Failed submitting billing [{str(submit_billing.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                return

    async def submitShipping(self):
        while True:
            #frakt data
            data = {
                'action': 'setSendTo',
                'billing_email_address': self.task['Profile']['Email'],
                'billing_firstname': self.task['Profile']['First Name'],
                'billing_lastname': self.task['Profile']['Last Name'],
                'billing_gender': '',
                'billing_company': '',
                'company_number': '',
                'billing_street_address': self.task['Profile']['Address'],
                'billing_zipcode': self.task['Profile']['ZIP'],
                'billing_state': self.task['Profile']['State'],
                'billing_city': self.task['Profile']['City'],
                'billing_telephone': self.task['Profile']['Phone'],
                'password': '',
                'billing_country': self.task['Profile']['Country'],
                'billing_newsletter': '1'
            }
            
            #send frakt informasjon
            await self.pending('Submitting shipping')
            try:
                submit_shipping = await self.session.post('https://www.plommehuset.no/checkout/?rType=ajax', data=data)
            except Exception as e:
                await self.error(f'Exception submitting shipping: {e}')
                await asyncio.sleep(self.delay)
                continue

            if submit_shipping.status_code != 200:
                await self.error(f'Failed submitting shipping [{str(submit_shipping.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                break

        while True:
            #fraktmetode data
            data = {
                'action': 'setShippingMethod',
                'method': 'servicepakke_servicepakke'
            }
            
            #send fraktmetode
            await self.pending('Submitting shipping method')
            try:
                submit_shipping_method = await self.session.post('https://www.plommehuset.no/checkout/?rType=ajax', data=data)
            except Exception as e:
                await self.error(f'Exception submitting shipping method: {e}')
                await asyncio.sleep(self.delay)
                continue

            if submit_shipping_method.status_code != 200:
                await self.error(f'Failed submitting shipping method [{str(submit_shipping_method.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                return

    async def submitPaymentMethod(self):
        while True:
            #betalingsmetode data
            data = {
                'action': 'setPaymentMethod',
                'method': self.paymentID
            }
            
            #send betalingsmetode til siden
            await self.pending('Submitting payment method')
            try:
                submit_payment_method = await self.session.post('https://www.plommehuset.no/checkout/?rType=ajax', data=data)
            except Exception as e:
                await self.error(f'Exception submitting payment method: {e}')
                await asyncio.sleep(self.delay)
                continue

            if submit_payment_method.status_code != 200:
                await self.error(f'Failed submitting payment method [{str(submit_payment_method.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                return

    async def submitOrder(self):
        while True:
            #data for å fullføre ordren
            data = {
                'action': 'process',
                'discount_center_code': '',
                'phonenumber_lookup_input': '',
                'billing_email_address': self.task['Profile']['Email'],
                'billing_firstname': self.task['Profile']['First Name'],
                'billing_lastname': self.task['Profile']['Last Name'],
                'billing_gender': '',
                'billing_company': '',
                'company_number': '',
                'billing_street_address': self.task['Profile']['Address'],
                'billing_zipcode': self.task['Profile']['ZIP'],
                'billing_state': self.task['Profile']['State'],
                'billing_city': self.task['Profile']['City'],
                'billing_telephone': self.task['Profile']['Phone'],
                'password': self.task['Profile']['Password'],
                'billing_country': self.task['Profile']['Country'],
                'shipping_firstname': '',
                'shipping_lastname': '',
                'shipping_company': '',
                'shipping_country': self.task['Profile']['Country'],
                'shipping_street_address': '',
                'shipping_zipcode': '',
                'shipping_state': self.task['Profile']['State'],
                'shipping_city': '',
                'shipping': 'servicepakke_servicepakke',
                'payment': self.paymentID,
                'agree': 'true',
                'comments': '',
                'formUrl': 'https://www.plommehuset.no/checkout_process',
                'email_address': ''
            }

            #fullfør ordren
            await self.pending('Submitting order')
            try:
                submit_order = await self.session.post('https://www.plommehuset.no/checkout', data=data)
            except Exception as e:
                await self.error(f'Exception submitting order: {e}')
                await asyncio.sleep(self.delay)
                continue

            #om vi finner "vipps" i redirect urlen henter vi den og sender i webhook og logger til konsollen
            if 'vipps' in str(submit_order.url):
                self.checkout_url = await createShort(submit_order.url)
                await self.updateStatusBar('checkout')
                await self.success(f'Successfully checked out {self.product_name}: {self.checkout_url}')
                threading.Thread(target=self.sendWebhook, args=(True, True, False)).start()
                return
            else:
                await self.updateStatusBar('failed')
                await self.error('Failed submitting payment')
                threading.Thread(target=self.sendWebhook, args=(True, False, False)).start()
                return
