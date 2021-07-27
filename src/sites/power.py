#-------------------------------------
import asyncio, httpx, json, threading
from utils import Module, createShort
#-------------IMPORTS-----------------

class Power(Module):
    def __init__(self, task, proxies, taskID, settings, taskData):
        #initialisere alle variablene for klassen vår
        super().__init__('Power', taskID)
        self.task = task
        self.proxies = proxies
        self.delay = float(self.task['Delay'])
        self.pid = self.task['PID']
        self.taskData = taskData
        self.settings = settings

        #set payment ID som vi bruker senere
        if self.task['Payment'].lower() == 'vipps':
            self.paymentID = 11
        elif self.task['Payment'].lower() == 'card':
            self.paymentID = 20
        else:
            print(f'Invalid payment method: {self.task["Payment"]}')
            return

    async def run(self):
        #kontroller for alle funksjonene
        await self.formatProxy()
        async with httpx.AsyncClient(proxies=self.proxy, timeout=None) as self.session:
            await self.monitor()
            await self.atc()
            await self.submitShipping()
            await self.submitPayment()

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
            if await self.checkTaskData():
                return

            #hent informasjon om produktet gjennom Power sin API
            await self.pending('Getting product page')
            try:
                fetch_data = await self.session.get('https://www.power.no/umbraco/api/product/getproductsbyids?ids=' + self.pid)
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
                    #gjør produkt informasjonen om til json
                    product_data = json.loads(fetch_data.text)[0]
                    self.product_image = product_data['PrimaryImage2']
                    self.product_name = product_data['Title']
                    self.product_price = str(product_data['Price'])

                    #om produktet kan legges til i handlevognen og er ikke for høy pris, oppdaterer vi produkt informasjonen i dicten og går videre til add to cart
                    if product_data['CanAddToCart'] and float(self.product_price) != 99999.0:
                        await self.updateTaskData(self.pid, {'Image':self.product_image,'Name':self.product_name,'Price':self.product_price})
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
            #legg til produktet i handlevognen
            await self.pending('Adding product to cart')
            try:
                atc = await self.session.post('https://www.power.no/api/basket/products', json={"ProductId": self.pid, "DeltaQuantity": 1})
            except Exception as e:
                await self.error(f'Exception adding product to cart: {e}')
                await asyncio.sleep(self.delay)
                continue

            if atc.status_code != 200:
                await self.error(f'Failed adding product to cart [{str(atc.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                if 'Errors' not in atc.text:
                    await self.updateStatusBar('cart')
                    await self.success(f'Successfully added {self.product_name} to cart')
                    return
                else:
                    await self.error('Failed adding product to cart')
                    await asyncio.sleep(self.delay)
                    continue

    async def submitShipping(self):
        while True:
            await self.pending('Submitting shipping info')

            payload = {
                    "DeliveryInformation": {"Address": self.task['Profile']['Address'], "City": self.task['Profile']['City'],
                    "Email": self.task['Profile']['Email'], "FirstName": self.task['Profile']['First Name'],
                    "LastName": self.task['Profile']['Last Name'], "Phone": self.task['Profile']['Phone'],
                    "PostalCode": self.task['Profile']['ZIP'], "Company": None,
                    "CompanyVATNumber": None, "SSN": None},
                    "ReceiptInformation": {
                        "Address": self.task['Profile']['Address'], "City": self.task['Profile']['City'],
                        "Email": self.task['Profile']['Email'], "FirstName": self.task['Profile']['First Name'],
                        "LastName": self.task['Profile']['Last Name'], "Phone": self.task['Profile']['Phone'],
                        "PostalCode": self.task['Profile']['ZIP'], "Company": None,
                        "CompanyVATNumber": None, "SSN": None
                    },
                "NewsletterSubscription": False,
                "Validate": True, "MyPowerClubSubscription": False
            }

            #sende inn informasjon om levering samt navn til power sin API
            try:
                submit_shipping = await self.session.post('https://www.power.no/api/basket/contactinfo', json=payload)
            except Exception as e:
                await self.error(f'Exception submitting shipping info: {e}')
                await asyncio.sleep(self.delay)
                continue

            if submit_shipping.status_code != 200:
                await self.error(f'Failed submitting shipping info [{str(submit_shipping.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                if 'Errors' not in submit_shipping.text:
                    break
                else:
                    await self.error('Failed submitting shipping info')
                    await asyncio.sleep(self.delay)
                    continue

        while True:
            #send leveringsmetode
            await self.pending('Submitting shipping method')
            try:
                submit_shipping_method = await self.session.post('https://www.power.no/api/basket/freight',json={"BasketFreightId": 1, "FreightId": 40})
            except Exception as e:
                await self.error(f'Exception submitting shipping method: {e}')
                await asyncio.sleep(self.delay)
                continue

            if submit_shipping_method.status_code != 200:
                await self.error(f'Failed submitting shipping method [{str(submit_shipping_method.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                if 'Errors' not in submit_shipping_method.text:
                    return
                else:
                    await self.error('Failed submitting shipping method')
                    await asyncio.sleep(self.delay)
                    continue

    async def submitPayment(self):
        #send inn paymentID som vi erklærte istad
        while True:
            await self.pending('Submitting payment method')
            try:
                submit_payment_method = await self.session.post('https://www.power.no/api/basket/paymentMethod',json=self.paymentID)
            except Exception as e:
                await self.error(f'Exception submitting payment method: {e}')
                await asyncio.sleep(self.delay)
                continue

            if submit_payment_method.status_code != 200:
                await self.error(f'Failed submitting payment method [{str(submit_payment_method.status_code)}]')
                await asyncio.sleep(self.delay)
                continue
            else:
                if 'Errors' not in submit_payment_method.text:
                    break
                else:
                    await self.error('Failed submitting payment method')
                    await asyncio.sleep(self.delay)
                    continue

        while True:
            #til slutt sender vi betalingen
            await self.pending('Submitting payment')
            try:
                submit_payment = await self.session.post('https://www.power.no/api/basket/pay', json={"PaymentMethodId":self.paymentID, "PaymentDetails": []})
            except Exception as e:
                await self.error(f'Exception submitting payment: {e}')
                await asyncio.sleep(self.delay)
                continue

            #om vi finner "vipps" for vipps betaling eller "psp-ecommerce" for kort betaling i teksten returnerer vi payment urlen.
            if 'vipps' in submit_payment.text or 'psp-ecommerce' in submit_payment.text:
                payment_url = json.loads(submit_payment.text)['PaymentUrl']
                self.checkout_url = await createShort(payment_url)
                await self.updateStatusBar('checkout')
                await self.success(f'Successfully checked out {self.product_name}: {self.checkout_url}')
                threading.Thread(target=self.sendWebhook, args=(True, True, False)).start()
                return
            else:
                await self.error('Failed submitting payment')
                await self.updateStatusBar('failed')
                threading.Thread(target=self.sendWebhook, args=(True, False, False)).start()
                return
