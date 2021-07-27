import json, random, contextlib, httpx, asyncio, time, os, httpx
from urllib.parse import urlencode
from urllib.request import urlopen
from blessed import Terminal
from inquirer import themes
from colorama import init, Style
from termcolor import colored
from datetime import datetime
from dhooks import Webhook, Embed

#for vår custom user interface klasse
term = Terminal()

#lock som bare lar en oppgave printe til consoll om gangen for at de ikke skal overlappe
lock = asyncio.Lock()

#vi kaller denne funksjonen for at vi skal kunne bruke printing med farger på windows
init()

#globale variabler
CARTED = 0
CHECKOUT = 0
FAILED = 0

#parent klasse til moduler som lar dem blant annet printe output til consollen
class Module:
    def __init__(self, name, task_id):
        self.name = name
        self.task_id = task_id

    #printing av forskjellige meldinger til konsollen
    async def success(self, message):
        async with lock:
            print(str(datetime.now().strftime("%H:%M:%S.%f")) + ' | ' + colored(self.name + ' ' * (11 - len(str(self.name))) + ' - ' + 'TASK ' + str(self.task_id) + ' ' * (4 - len(str(self.task_id))), 'yellow') + ' | ' + colored(message, 'green'))

    async def error(self, message):
        async with lock:
            print(str(datetime.now().strftime("%H:%M:%S.%f")) + ' | ' + colored(self.name + ' ' * (11 - len(str(self.name))) + ' - ' + 'TASK ' + str(self.task_id) + ' ' * (4 - len(str(self.task_id))), 'yellow') + ' | ' + colored(message, 'red'))

    async def pending(self, message):
        async with lock:
            print(str(datetime.now().strftime("%H:%M:%S.%f")) + ' | ' + colored(self.name + ' ' * (11 - len(str(self.name))) + ' - ' + 'TASK ' + str(self.task_id) + ' ' * (4 - len(str(self.task_id))), 'yellow') + ' | ' + colored(message, 'yellow'))

    async def info(self, message):
        async with lock:
            print(str(datetime.now().strftime("%H:%M:%S.%f")) + ' | ' + colored(self.name + ' ' * (11 - len(str(self.name))) + ' - ' + 'TASK ' + str(self.task_id) + ' ' * (4 - len(str(self.task_id))), 'yellow') + ' | ' + colored(message, 'white'))

    async def updateTaskData(self, key, data):
        async with lock:
            self.taskData[key] = data

    #oppdater de globale variablene som vi displayer ovenfor i applikasjonen
    async def updateStatusBar(self, value):
        global CARTED, CHECKOUT, FAILED

        if 'cart' in value:
            CARTED += 1
        elif 'checkout' in value:
            CHECKOUT += 1
        elif 'failed' in value:
            FAILED += 1

        os.system(f'title Checkouts: {str(CHECKOUT)} / Carted: {str(CARTED)} / Failed: {str(FAILED)}')

    # formatere en proxy slik at vi kan bruke den i en session
    async def formatProxy(self):
        try:
            self.proxy = None
            if self.proxies == []:
                return None

            proxy = random.choice(self.proxies)
            proxy_parts = proxy.split(":")

            if len(proxy_parts) == 2:
                self.proxy = {"http://": "http://" + proxy, "https": "https://" + proxy}
                return None

            elif len(proxy_parts) == 4:
                ip, port, user, passw = proxy_parts[0], proxy_parts[1], proxy_parts[2], proxy_parts[3]
                self.proxy = {
                    "http://": "http://{}:{}@{}:{}".format(user, passw, ip, port),
                    "https://": "http://{}:{}@{}:{}".format(user, passw, ip, port)
                }
                return None
        except:
            return None

    
    #webhook enten med cookie, link eller bare melding med ordre nummer
    def sendWebhook(self, manual=False, success=True, cookie=False):

        hook = Webhook(self.settings['Webhook'])

        if success:
            if manual:
                title = 'Complete Payment!'
            elif cookie:
                title = 'Complete Checkout'
            else:
                title = 'Successful Checkout!'

            color = 1834808
        else:
            color = 16717600
            title = 'Checkout Failed!'

        embed = Embed(description='', color=color,timestamp='now',title=title)

        embed.add_field(name='Site', value=self.name, inline=False)
        embed.add_field(name='Profile', value=f'||{self.task["Profile Name"]}||', inline=False)
        embed.add_field(name='PID', value=self.pid, inline=False)
        embed.add_field(name='Product', value=self.product_name, inline=False)
        embed.add_field(name='Price', value=self.product_price, inline=False)
        embed.set_thumbnail(self.product_image)  

        if success:
            if manual:
                 embed.add_field(name='Payment Link', value=f'[Checkout Now]({self.checkout_url})', inline=False)
            elif cookie:
                embed.add_field(name=self.cookieName, value=f'||{self.cookieValue}||', inline=False)
            else:
                 embed.add_field(name='Order Number', value=f'[Checkout Now]({self.orderNumber})', inline=False)

        while True:
            try:
                hook.send(embed=embed)
                return
            except:
                time.sleep(1)
                continue

#klasse som gjør at vi kan selv velge hvilke farger interfacen skal være
class UITheme(themes.Theme):
    def __init__(self):
        super(UITheme, self).__init__()
        self.Question.mark_color = term.red
        self.Question.brackets_color = term.normal
        self.Question.default_color = term.normal
        self.Editor.opening_prompt_color = term.bright_black
        self.Checkbox.selection_color = term.red
        self.Checkbox.selection_icon = '>'
        self.Checkbox.selected_icon = 'X'
        self.Checkbox.selected_color = term.red + term.bold
        self.Checkbox.unselected_color = term.normal
        self.Checkbox.unselected_icon = 'o'
        self.List.selection_color = term.red
        self.List.selection_cursor = '>'
        self.List.unselected_color = term.normal

#denne funksjonen danner en kort url som vi kan passe inn i en discord webhook og i konsollen
async def createShort(url):
    async with httpx.AsyncClient() as session:
        get_checkout_url = await session.get(f'http://tinyurl.com/api-create.php?url={url}')
        return get_checkout_url.text
