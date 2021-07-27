#-------------------------------------
import asyncio, httpx, json, threading
from bs4 import BeautifulSoup
from utils import Module, createShort
#-------------IMPORTS-----------------

class Proshop(Module):
    def __init__(self, task, proxies, taskID, settings, taskData):
        #initialisere alle variablene for klassen vår
        super().__init__('Proshop', taskID)
        self.task = task
        self.proxies = proxies
        self.delay = float(self.task['Delay'])
        self.pid = self.task['PID']
        self.taskData = taskData
        self.settings = settings
        self.mode = self.task['Mode'].lower().strip()

    async def run(self):
        #siden er beskyttet av Cloudflare, bot protection
        #den er ikke tatt sterkt i bruk, så ved et enkelt bruk av headers kan vi komme oss forby uten å bli blokkert
        headers = {
            'authority': 'www.proshop.no',
            'sec-ch-ua': '^\\^',
            'sec-ch-ua-mobile': '?0',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'sec-fetch-site': 'none',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-user': '?1',
            'sec-fetch-dest': 'document',
            'accept-language': 'en-US,en;q=0.9'
        }
        await self.formatProxy()
        async with httpx.AsyncClient(proxies=self.proxy, headers=headers, timeout=None) as self.session:
            await self.monitor()
            await self.atc()

    async def checkTaskData(self):
        #sjekker om noen andre tasks har lagret informasjon om produktet slik at vi kan hente den der
        #veldig nyttig under høy traffik på nettsiden
        if self.pid in self.taskData:
            self.product_image = self.taskData[self.pid]['Image']
            self.product_name = self.taskData[self.pid]['Name']
            self.product_price = self.taskData[self.pid]['Price']
            return True
        else:
            return False


    async def monitor(self):
        while True:
            if self.mode == 'fast':
                self.product_image = None
                self.product_price = '?'
                self.product_name = '?'
                return

            if await self.checkTaskData():
                return

            #hent siden ved gitt link
            await self.pending('Getting product page')
            try:
                fetch_data = await self.session.get('https://www.proshop.no/' + self.pid)
            except Exception as e:
                await self.error(f'Exception getting product page: {e}')
                await asyncio.sleep(self.delay)
                continue

            if fetch_data.status_code != 200:
                await self.pending(f'Failed getting product page [{str(fetch_data.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                try:
                    #om vi kan legge til produktet i handlevognen henter vi all informasjonen om produktet
                    if 'addToBasket' in fetch_data.text:
                        soup = BeautifulSoup(fetch_data.text, 'html.parser')
                        data = json.loads(soup.find('script',{'type':'application/ld+json'}).string)
                        self.product_image = data['image'].replace('https:', 'https://www.proshop.no')
                        self.product_price = data['offers']['price']
                        self.product_name = data['name']
                        await self.updateTaskData(self.pid, {'Image':self.product_image,'Name':self.product_name,'Price':self.product_price})
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
            #legger til produktet i handlevognen
            await self.pending('Adding product to cart')
            try:
                atc = await self.session.post('https://www.proshop.no/Basket/AddItem', data={'productId': self.pid})
            except Exception as e:
                await self.error(f'Exception adding product to cart: {e}')
                await asyncio.sleep(self.delay)
                continue

            if atc.status_code != 200:
                await self.error(f'Failed adding product to cart [{str(atc.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                #om det ikke står at produktet ikke er tilgjengelig henter vi session cookien som vi kan bruke for å "gi" handlevognen til brukeren
                if 'is no longer available' not in atc.text:
                    await self.updateStatusBar('cart')
                    await self.success(f'Successfully added {self.product_name} to cart')
                    
                    self.cookieName = 'ASP.NET_SessionId'
                    self.cookieValue = self.session.cookies['ASP.NET_SessionId']
                    threading.Thread(target=self.sendWebhook, args=(False, True, True)).start()
                    return
                else:
                    await self.error('Failed adding product to cart')
                    await asyncio.sleep(self.delay)
                    continue
