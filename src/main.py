#---------------------------------------------------------------
import asyncio, time, csv, codecs, glob, inquirer, sys, os, json
from utils import UITheme
from termcolor import colored
from inquirer import themes
from sites.power import Power
from sites.plommehuset import Plommehuset
from sites.proshop import Proshop
#----------------------------IMPORTS----------------------------

class TaskManager:
    def __init__(self, settings):
        #settings som vi gir til hver task
        self.settings = settings
        
        #dict for all informasjon vi henter og deretter gir til tasks og for display
        self.tasks = {
            'All Tasks':[],
            'CSV File':{},
            'Site':{},
            'Display':[],
            'Options':[]
        }

        #dict med moduler
        self.sites = {
            'Plommehuset':Plommehuset,
            'Power':Power,
            'Proshop':Proshop
        }


    async def startTasks(self):
        #hent tasks
        loadTasks = await self.loadTasks()

        #om vi ikke har tasks, gir vi melding og avslutter vi programmet
        if len(loadTasks['All Tasks']) == 0:
            print(colored('No Tasks Loaded', 'red'))
            await asyncio.sleep(10)
            sys.exit()

        questions = [
            inquirer.List('Tasks',
                          message="Please Select An Option",
                          choices=loadTasks['Display'],
                          ),
        ]

        answer = inquirer.prompt(questions, theme=UITheme())
        
        #hent tasks fra dicted ved gitt input
        allTasks = loadTasks['Options'][loadTasks['Display'].index(answer['Tasks'])]

        #liste med tasks
        tasks = []

        #taskid
        count = 0

        #en dict som vi gir til alle tasks, den kan endres hos en task og deretter endre også hos andre
        taskData = {}

        # start tasks

        for task in allTasks:
            # load proxies
            try:
                proxies = open(task['Proxy File'], 'r').read().splitlines()
            except:
                print(colored(f'Error Loading Proxies From {task["Proxy File"]}', 'red'))
                proxies = []

                
            #lag selve tasken med asyncio ut i fra dicten og gi den informasjon slik proxies, taskid, settings og taskdata
            newTask = asyncio.create_task(self.sites[task['Site']](task, proxies, count, self.settings, taskData).run())
            tasks.append(newTask)
            count += 1

        print(colored(f'Starting {str(count)} Task(s)...', 'yellow'))

        # starte alle taskene i vår task liste
        await asyncio.gather(*tasks)
        input()

    async def loadTasks(self):
        #hent alle csv filer
        taskFiles = glob.glob('tasks*.csv')
        for csv in taskFiles:
            #for hver csv fil, loader vi tasks fra den
            await self.loadFromFile(csv)
        if len(self.tasks['All Tasks']) == 0:
            #om det ikke er noen tasks går vi bare tibake
            return
        else:
            #append tasks til display og options
            #grunnen til at vi gjør det i to seperate lister er fordi de ser annerledes ut når vi skal vise dem i forhold til når de er loadet i programmet
            self.tasks['Display'].append(f'Start All Tasks [{str(len(self.tasks["All Tasks"]))} Tasks]')
            self.tasks['Options'].append(self.tasks['All Tasks'])

        if len(self.tasks['CSV File']) != 0:
            for file in self.tasks['CSV File']:
                self.tasks['Display'].append(f'Start Tasks From CSV: {file} [{str(len(self.tasks["CSV File"][file]))} Tasks]')
                self.tasks['Options'].append(self.tasks['CSV File'][file])

        if len(self.tasks['Site']) != 0:
            for site in self.tasks['Site']:
                self.tasks['Display'].append(f'Start {site} Tasks [{str(len(self.tasks["Site"][site]))} Tasks]')
                self.tasks['Options'].append(self.tasks['Site'][site])

        return self.tasks

    async def loadFromFile(self, file):
        #load tasks med codecs som dict for å kunne lese filer som inkluderer spesielle tegn som å, e
        with codecs.open(file, 'r', 'utf-8') as f:
            tasks = []
            readCSV = csv.reader(f, delimiter=',')
            next(readCSV)
            for row in readCSV:
                try:
                    #lag en dict ut i fra csv info
                    profile = {
                        'Site':row[0],
                        'Proxy File':row[1],
                        'Profile Name':row[2],
                        'Link': row[3],
                        'PID': row[4],
                        'Delay':row[5],
                        'Payment':row[6],
                        'Tasks':row[7],
                        'Mode':row[8]
                    }

                    #sjekk om task siden matcher uansett om det er storebokstaver, små bokstaver og mellomrom
                    if profile['Site'].lower().strip() in (k.lower() for k in self.sites):
                        #set site til verdien i dikten uansett om de ikke er bokstavelig like
                        profile['Site'] = (list(self.sites)[list(k.lower() for k in self.sites).index(profile['Site'].lower().strip())])
                        #hent profil ut i fra gitt profil navn
                        profile['Profile'] = await self.loadProfile(profile['Profile Name'])
                        #lag x tasks for gitt antall i csv
                        self.tasks['All Tasks'].extend(profile for x in range(int(profile['Tasks'])))
                        self.tasks['CSV File'].setdefault(file, []).extend(profile for x in range(int(profile['Tasks'])))
                        self.tasks['Site'].setdefault(profile['Site'], []).extend(profile for x in range(int(profile['Tasks'])))
                except:
                    continue
            f.close()

    async def loadProfile(self, profile_name):
        #hent profil fra profiles.csv med gitt profilnavn
        with codecs.open('profiles.csv', 'r', 'utf-8') as f:
            readCSV = csv.reader(f, delimiter=',')
            next(readCSV)
            for row in readCSV:
                if row[0] == profile_name:
                    #dict av csv info
                    profile = {
                        'Address': row[1],
                        'City': row[2],
                        'Email': row[3],
                        'Password':row[4],
                        'First Name': row[5],
                        'Last Name': row[6],
                        'Phone': row[7],
                        'ZIP': row[8],
                        'Country': row[9],
                        'State':row[10]
                    }
                    
                    return profile
            #om profilen ikke finnes, gir vi en error
            raise Exception

class Main:
    def __init__(self):
        #versjonen av applikasjonen
        self.version = '1.0'
        #funksjon som lar oss tømme konsollen
        self.cls = lambda : os.system('cls')

    async def start(self):
        #load settings og deretter gå til menyen
        await self.loadSettings()
        await self.menu()

    async def menu(self):
        self.cls()
        
        options = {
            'Start Tasks':TaskManager(self.settings).startTasks,
            'Configure Settings':self.configureSettings
        }

        questions = [
            inquirer.List('Option',
                          message="Please Select An Option",
                          choices=['Start Tasks', 'Configure Settings'],
                          ),
        ]

        answer = inquirer.prompt(questions, theme=UITheme())

        self.cls()
        #hent gitt input og start den fra dicten
        await options[answer['Option']]()

    async def loadSettings(self):
        try:
            #åpne settings filen og loade den som et json objekt
            with open('settings.json', 'r') as f:
                self.settings = json.load(f)
                f.close()
        except:
            print(colored('Error Loading Settings!', 'red'))
            await asyncio.sleep(10)
            sys.exit()

    async def configureSettings(self):
        #alle mulige settings vi kan endre
        settings = [
            'Webhook'
        ]

        options = []
        
        #vise settings som vi har loadet allerede
        for setting in settings:
            options.append(f'{setting} - {self.settings.setdefault(setting, "")}')

        options.append('Back To Menu')

        questions = [
            inquirer.List('Option',
                          message="Please Select A Setting",
                          choices=options,
                          ),
        ]

        answer = inquirer.prompt(questions, theme=UITheme())

        if answer['Option'] == 'Back To Menu':
            await self.menu()
        else:
            #oppdater settings
            updateValue = settings[options.index(answer['Option'])]
            newValue = input('Please Enter New Value: ')

            try:
                #åpne settings filen og endre gitt navn, oppdater ny verdi i programmet slik at vi slipper å loade fra json igjen
                with open('settings.json', 'r') as f:
                    data = json.loads(f.read())
                    data[updateValue] = newValue
                    self.settings[updateValue] = newValue
                    f.close() 

                #save settings i json
                with open('settings.json', 'w') as f:
                    json.dump(data, f, indent=2)
                    f.close()
            except:
                print(colored('Error Updating Settings!', 'red'))
                await asyncio.sleep(10)
                sys.exit()

            #tilbake til options
            await self.configureSettings()


if __name__ == '__main__':
    #start programmet
    asyncio.run(Main().start())
