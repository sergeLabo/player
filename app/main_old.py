

# cd /media/data/3D/projets/player/app
# /media/data/3D/projets/player/server/mon_env/bin/python3 main.py

import os
from time import time, sleep
import datetime
import subprocess
from threading import Thread
from functools import partial
from pathlib import Path
import json
import urllib.parse

import kivy
kivy.require('2.0.0')

# Pour twisted: ajouter twisted dans les requirements de buildozer.spec
from kivy.support import install_twisted_reactor
install_twisted_reactor()
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, Factory, ReconnectingClientFactory


from kivy.animation import Animation
from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty, NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.utils import platform

from library_utils import dict_to_OrderdDict  #, get_tracks
from download_covers import DownloadFiles


global ANDROID

if platform == 'android':
    from android.storage import primary_external_storage_path
    ANDROID = True
else:
    ANDROID = False

print("Android is", ANDROID)


# La tablette n'est pas HD, le tél est HD
if ANDROID:
    Window.fullscreen = True
    Window.maximize()
else:
    k = 1.6
    Window.size = (int(1920/k), int(1200/k))


class MainScreen(Screen):
    info = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.app = App.get_running_app()
        self.info = ""

    def quit(self):
        self.app.do_quit()

    def shutdown(self):
        self.app.do_shutdown()



class Albums(Screen):

    def __init__(self, **kwargs):
        """Les albums sont les clé de library
        l = {'nom du dossier parent': { 'album': 'toto',
                                        'artist':,
                                        'cover':,
                                        'titres': { 0: ('tata', 'chemin abs'),
                                                    1: ('titi', 'chemin abs')}}}
        """

        super().__init__(**kwargs)
        self.app = App.get_running_app()

        self.album = ""

    def change_covers_path_in_library(self):
        """Chemins sur client != chemin sur serveur"""
        for key in self.app.library.keys():
            cover = self.app.library[key]['cover']
            cover_name = cover.split('/')[-1]
            local_cover = self.app.covers_path + '/' + cover_name
            # Player Cover: /data/data/org.test.player/files/app/covers/All The Way West.jpg
            self.app.library[key]['cover'] = local_cover

    def add_cover_buttons(self):
        """
        {'album': 'Ba Power',
        'artist': 'Bassekou Kouyaté & Ngoni Ba',
        'cover': '/home/pi/player/server/covers/Ba Power.jpg', chemin sur le server
        'titres': {'2':     ['Musow Fanga',
                            # fichier pas utilisé ici
                            '/media/pi/USB3x16Go/music/flacs/Bassekou Ko...anga.flac',
                            258],
                            ...}
                            }
        """
        print("Ajout des covers dans l'écran Albums")
        # Linux vs Android
        self.change_covers_path_in_library()

        self.size = (Window.width, Window.height)
        layout = GridLayout(cols=3,
                            spacing=(10, 10),
                            padding=(10, 10))
        layout.size_hint_y= None
        # Make sure the height is such that there is something to scroll.
        layout.bind(minimum_height=layout.setter('height'))

        for key in self.app.library.keys():
            # key = 'nom du dossier parent'
            album = key
            cover = self.app.library[key]['cover']

            try:
                button = Button(background_normal=cover,
                                background_down='covers/default_cover.png',
                                size_hint_y=None,
                                height=int((self.size[0]-280)/3))

                buttoncallback = partial(self.set_selected_album, album)
                button.bind(on_release=buttoncallback)
                layout.add_widget(button)
                # Bug affichage ? temps de chargement des images ?
                sleep(0.2)
                print(f"Bind de {cover}")
            except Exception as e:
                print("Erreur affichage image dans Albums:", e)

        try:
            self.ids.album_scroll.add_widget(layout)
        except:
            print("Les albums sont déjà ajoutés!")

    def set_selected_album(self, album, instance):
        self.album = album
        if album:
            # Lancement du player
            scrp = self.app.screen_manager.get_screen('Player')
            scrp.album = album
            scrp.track = 1
            scrp.play_track(album, 1)

            # Lancement des Tracks
            scrt = self.app.screen_manager.get_screen('Tracks')
            scrt.add_tracks()

            # Bascule sur écran Player
            self.app.screen_manager.transition.direction = 'left'
            self.app.screen_manager.current = 'Player'



class Player(Screen):

    maxi = NumericProperty(100)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()

        # clé du dict self.app.library = 'nom du dossier parent'
        self.album = ""
        self.title = ""
        self.album_name = ""
        self.artist = ""
        self.cover = None
        self.maxi = 100
        self.track = 1
        self.pause = 0
        self.t_block = time()

    def play_track(self, album, track):
        """
        album =
        track =
        l = {'nom du dossier parent': {'album': 'toto', # nom sans chemin
                                       'artist':,
                                       'cover':,
                                       'titres': {1: ('tata','chemin abs',lenght),
                                                  2: ('titi','chemin abs',lenght)}}}
        """

        if album:
            self.album = album
            self.track = track
            self.app.msg_for_svr['position'] = 0
            self.app.msg_for_svr['track'] = self.track

            # Nombre de tracks dans l'album
            try:
                self.tracks = len(self.app.library[self.album]['titres'])
            except:
                self.tracks = 1
            print(f"Nombre de pistes dans l'album {album}: {self.tracks}")

            # Récup des infos
            self.title = self.app.library[self.album]['titres'][str(self.track)][0]
            self.album_name = urllib.parse.unquote_plus(self.app.library[self.album]['album'])
            self.artist = self.app.library[self.album]['artist']

            cover = self.app.library[self.album]['cover']
            name = str(cover.split('/')[-1])
            self.cover =  str(Path(cover).parent) + '/' + name
            print("Chemin du cover:", self.cover)

            self.maxi = self.app.library[self.album]['titres'][str(self.track)][2]

            # Infos à envoyer au server
            self.app.msg_for_svr['album'] = self.album

            print(f"Play de:\n  {self.track}: {self.title} de {self.album_name} par {self.artist} \n")

            self.ids.track_number.text = str(self.track)
            self.ids.play_pause.disabled = False

            self.music_information()
            self.ids.play_pause.background_normal = 'images/Pause-normal.png'

    def new_track(self, track):
        if self.album:
            self.track = int(track)
            self.play_track(self.album, self.track)
            self.app.msg_for_svr['track'] = self.track

    def previous(self):
        if self.album:
            if time() - self.t_block > 2:
                self.t_block = time()
                self.track -= 1
                if self.track < 1:
                    self.track = 1
                # # self.play_track(self.album, self.track)
                self.app.msg_for_svr['track'] = self.track

    def next(self):
        if self.album:
            if time() - self.t_block > 2:
                self.t_block = time()
                self.track += 1
                if self.track > self.tracks:
                    self.track = self.tracks
                # # self.play_track(self.album, self.track)
                self.app.msg_for_svr['track'] = self.track

    def play_pause(self):
        if time() - self.t_block > 2:
            self.t_block = time()
            if not self.pause:
                self.ids.play_pause.background_normal = 'images/Play-normal.png'
                self.ids.play_pause.background_down = 'images/Play-down.png'
                self.app.msg_for_svr['play_pause'] = 1
                self.pause = 1
            else:
                self.ids.play_pause.background_normal = 'images/Pause-down.png'
                self.ids.play_pause.background_down = 'images/Pause-normal.png'
                self.app.msg_for_svr['play_pause'] = 0
                self.pause = 0

    def change_position(self, value):
        print("Nouvelle position du slider:", value)
        self.app.msg_for_svr['position'] = int(value)

    def music_information(self):
        """Displays song duration, title, album and artist"""

        self.ids.title.text = self.title
        self.ids.album.text = self.album_name
        self.ids.artist.text = self.artist
        self.ids.album_art.source = self.cover
        self.ids.song_slider.max = self.maxi

        # Create an animated title that scrolls horizontally
        scrolling_effect = Animation(x=0, duration=1)  # opacity=0,
        scrolling_effect += Animation(x=600, duration=400)  #  opacity=1,
        scrolling_effect.repeat = True
        scrolling_effect.start(self.ids.title)



class Tracks(Screen):
    # Attribut de class, obligatoire pour appeler root.titre dans kv
    titre = StringProperty("toto")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.layout = None

    def add_tracks(self):
        """l = {'nom du dossier parent': {'album': 'toto',
                               'artist':,
                               'cover':,
                               'titres': { 0: ('tata','chemin abs',lenght),
                                           1: ('titi','chemin abs',lenght)}}}
        l et 'titres' sont des un OrderedDict
        """
        self.size = (Window.width, Window.height)

        # Remove widgets of previous album
        if self.layout:
            self.ids.tracks_scroll.remove_widget(self.layout)

        self.layout = GridLayout(cols=1,
                            spacing=(10, 10),
                            padding=(5, 5))
        self.layout.size_hint_y= None
        # Make sure the height is such that there is something to scroll.
        self.layout.bind(minimum_height=self.layout.setter('height'))

        scr = self.app.screen_manager.get_screen('Albums')
        dico = self.app.library[scr.album]['titres']

        for key in range(1, len(dico) +1):
            text = (f"{key}  :  {dico[str(key)][0]}")
            button = Button(size_hint_y=None,
                            background_color=(2.8, 2.8, 2.8, 1),
                            color=(0, 0, 0, 1),
                            font_size="24dp",
                            text=text)
            buttoncallback = partial(self.set_selected_track, key)
            button.bind(on_release=buttoncallback)
            self.layout.add_widget(button)

        self.ids.tracks_scroll.add_widget(self.layout)

    def set_selected_track(self, track, instance):
        """
        scr = self.app.screen_manager.get_screen('Player')
        scr.new_track(track)
        """

        # Le reset sera fait après l'envoi
        self.app.msg_for_svr['new_track'] = track
        self.app.screen_manager.transition.direction = 'right'
        self.app.screen_manager.current = 'Player'



SCREENS = { 0: (MainScreen, 'Main'),
            1: (Albums, 'Albums'),
            2: (Player, 'Player'),
            3: (Tracks, 'Tracks')}



class MyTcpClient(Protocol):

    def __init__(self, app):
        """app est le self
        de                                                        ici
        reactor.connectTCP(self.ip, self.port, MyTcpClientFactory(self))
        """
        self.app = app
        self.debug = 0
        # # self.send_thread = None
        print("Un protocol client créé")
        print(f"IP = {self.app.ip}, PORT = {self.app.port}")

    def connectionMade(self):
        print("connectionMade: début d'envoi des messages.")
        self.app.connected = 1
        # Un premier envoi pour lancer les boucles réception/envoi
        self.transport.write(json.dumps([0]).encode('utf-8'))

    def connectionLost(self, reason):
        self.app.connected = 0
        self.send_thread = None

    def dataReceived(self, data):
        self.app.handle_message(data)
        sleep(0.4)
        s = ['from_client', self.app.msg_for_svr]
        self.transport.write(json.dumps(s).encode('utf-8'))
        # Reset après envoi
        self.app.msg_for_svr['new_track'] = 0
        self.app.msg_for_svr['position'] = 0


class MyTcpClientFactory(ReconnectingClientFactory):

    maxDelay = 5

    def __init__(self, app):
        self.app = app

    def startedConnecting(self, connector):
        print("Essai de connexion ...")

    def buildProtocol(self, addr):
        print(f"MyTcpClientFactory buildProtocol {addr}")
        return MyTcpClient(self.app)

    def clientConnectionLost(self, connector, reason):
        print("Lost connection.  Reason:", reason)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        print("Connection failed. Reason:", reason)
        ReconnectingClientFactory.clientConnectionFailed(self,connector,reason)



class PlayerApp(App):
    global ANDROID

    def build(self):
        """Exécuté après build_config, construit les écrans"""
        Window.clearcolor = (1, 1, 1, 1)

        self.screen_manager = ScreenManager()
        for i in range(len(SCREENS)):
            self.screen_manager.add_widget(SCREENS[i][0](name=SCREENS[i][1]))
        return self.screen_manager

    def build_config(self, config):
        print("Création du fichier *.ini si il n'existe pas")

        config.setdefaults( 'network', {'ip': '192.168.0.108',
                                        'port': 8000})

        config.setdefaults( 'httpserver', {'port': 8080})

        print("self.config peut maintenant être appelé")

    def build_settings(self, settings):
        """Construit l'interface de l'écran Options, pour MusicPlayer seul,
        Les réglages Kivy sont par défaut.
        Cette méthode est appelée par app.open_settings() dans .kv,
        donc si Options est cliqué !
        """
        print("Construction de l'écran Options")
        data = """[ {"type": "title", "title": "Music Player"},
                        {"type": "string",
                         "title": "IP TCP",
                         "desc": "192.168.0.108",
                         "section": "network",
                         "key": "ip"},
                        {"type": "numeric",
                         "title": "Port TCP",
                         "desc": "8000",
                         "section": "network",
                         "key": "port"},
                        {"type": "numeric",
                         "title": "Port HTTP",
                         "desc": "8080",
                         "section": "httpserver",
                         "key": "port"}
                    ]"""

        # self.config est le config de build_config
        settings.add_json_panel('MusicPlayer', self.config, data=data)

    def on_start(self):
        """Exécuté apres build()"""

        global ANDROID
        self.debug = 0  # pas de init!
        scrm = self.screen_manager.get_screen('Main')
        scrm.info = "Player On"

        # Création du client TCP
        self.connected = 0
        self.tcp_init()

        i = self.config.get('network', 'ip')
        p = self.config.get('httpserver', 'port')
        self.http_adress = 'http://' + str(i) + ':' + str(p) + '/'
        print("Adress http:", self.http_adress)
        # Les infos envoyées au serveur,
        # à chaque requête "hello" soit tous les 1/10 de seconde
        self.msg_for_svr_reset()

        # Création du dossier des covers
        if ANDROID:
            self.covers_path = primary_external_storage_path() + '/covers'
        else:
            self.covers_path = str(Path.cwd()) + '/covers'
        print(f"Dossier des covers: {self.covers_path}")
        # Ne fait rien si existant
        create_directory(self.covers_path)

        # Récupération de la library qui est dans covers
        if ANDROID:
            self.library_file = self.covers_path + '/library.json'
        else:
            self.library_file = './covers/library.json'
        print(f"Le fichier library = {self.library_file}")
        # Création si besoin
        create_json_file(self.library_file)
        # Sinon chargement
        self.library = load_library(self.library_file)

        # Chargement des covers dans le screen Albums
        if self.library:
            scra = self.screen_manager.get_screen('Albums')
            scra.add_cover_buttons()

        # Prêt pour jouer
        if self.connected:
            scrm.info = "Albums existants chargés"
        else:
            Thread(target=self.update_info).start()

    def update_info(self):
        scrm = self.screen_manager.get_screen('Main')
        while not self.connected:
            scrm.info = "Le serveur n'est pas accessible ..."
            sleep(1)
            scrm.info = "Allume le serveur ..."
            sleep(1)
        scrm.info = "Le Player est prêt"

    def msg_for_svr_reset(self):
        self.msg_for_svr = {}
        self.msg_for_svr['album'] = 0
        self.msg_for_svr['new_track'] = 0
        self.msg_for_svr['position'] = 0
        self.msg_for_svr['play_pause'] = 0
        self.msg_for_svr['quit'] = 0
        self.msg_for_svr['shutdown'] = 0
        self.msg_for_svr['http_on'] = 0

    def tcp_init(self):
        self.ip = self.config.get('network', 'ip')
        self.port = int(self.config.get('network', 'port'))
        reactor.connectTCP(self.ip, self.port, MyTcpClientFactory(self))

    def handle_message(self, msg):

        try:
            msg = json.loads(msg.decode('utf-8'))
        except:
            msg = None

        if msg:
            if self.debug:
                print("\nmsg", msg)

            if msg[0] == 'from server':
                scrp = self.screen_manager.get_screen('Player')

                timestamp = msg[1]
                current_lenght = msg[2]
                track = msg[3]
                end = msg[4]

                # Timestamp changée toutes les 2 secondes
                if timestamp:
                    if int(timestamp) % 2 == 0:
                        scrp.ids.song_slider.value = timestamp


                # Lenght
                ta = str(datetime.timedelta(seconds=timestamp))[2:7]
                track_len = str(datetime.timedelta(seconds=current_lenght))[2:7]
                scrp.ids.current_position.text = f"{ta} | {track_len}"

                # Changement de track
                if track != scrp.track:
                    scrp.track = track
                    print("New track demandé par le serveur:", track)
                    scrp.new_track(track)

                # Fin de l'album
                if end == 1:
                    scrp.track = 1
                    scrp.album = None
                    scrp.pause = 0
                    self.screen_manager.transition.direction = 'right'
                    self.screen_manager.current = 'Albums'
                    self.msg_for_svr_reset()

    def ask_for_library_and_covers_thread(self):
        """Demande par button sur Main de la lib et covers,
        thread pour ne pas bloquer l'affichage."""
        Thread(target=self.ask_for_library_and_covers).start()

    def ask_for_library_and_covers(self):
        """Demande de la lib et mise à jour,
        dans un thread
        """
        # Pour afficher des infos seulement
        scrm = self.screen_manager.get_screen('Main')
        scrm.info = "Mise à jour des albums ..."

        files_list = get_file_list(self.covers_path, ['jpg', 'png', 'json'])
        print("Fichiers des albums existants:")
        for img in files_list:
            print("    ", img)

        scrm.info = "Liste des albums:\n"
        for img in files_list:
            name = urllib.parse.unquote_plus(str(img.split('/')[-1]))
            scrm.info += name + "\n"
        scrm.info = scrm.info[16:]
        sleep(1)

        # Demande de mise en route du httpserver
        self.msg_for_svr['http_on'] = 1
        df = DownloadFiles(self.http_adress,
                           self.covers_path,
                           files_list)
        # Attente que le serveur démarre
        sleep(2)
        try:
            print(f"Téléchargement en htttp")
            text = df.download_url()
            df.get_missing_covers(text)
            scrm.info = "Albums mis à jour et chargés!"
        except:
            print("Le serveur HTTP n'est pas accessible !")
            scrm.info = "Le serveur HTTP n'est pas accessible !\nDémarrez le serveur !"

        # Demande de stop du httpserver
        self.msg_for_svr['http_on'] = 0
        # Reload the new library
        load_library(self.library_file)
        # Affichage des images dans l'écran album
        scra = self.screen_manager.get_screen('Albums')
        try:
            scra.add_cover_buttons()
        except:
            pass

    def do_quit(self):
        print("Quit final ...")
        self.msg_for_svr['quit'] = 1
        self.wait_before_quit_thread()

        print("Fin des threads ...")
        scrp = self.screen_manager.get_screen('Player')
        scrp.reprise_loop = 0
        sleep(1)

        print("Fin du TCP")
        reactor.stop()
        sleep(1)

        print("Fin de Kivy")
        PlayerApp.get_running_app().stop()

    def wait_before_quit_thread(self):
        """Pour permettre au serveur d'avoir le temps de recevoir"""
        Thread(target=self.wait_before_quit).start()

    def wait_before_quit(self):
        t = time()
        while time() - t < 2:
            print("Attente ...")
            sleep(0.1)
        print("Fin du thread wait_before_quit...")

    def do_shutdown(self):
        print("Shutdown ...")
        self.msg_for_svr['shutdown'] = 1
        self.wait_before_shutdown_thread()

    def wait_before_shutdown_thread(self):
         """Pour permettre au serveur d'avoir le temps de recevoir"""
         Thread(target=self.wait_before_shutdown).start()

    def wait_before_shutdown(self):
        t = time()
        while time() - t < 2:
            print("Attente ...")
            sleep(0.1)
        print("Fin du thread wait_before_shutdown ...")
        self.do_quit()



def create_json_file(library_file):
    print(f"Création de {library_file} si inexistant")
    a = os.path.exists(library_file)
    if not os.path.exists(library_file):
        with open(library_file, 'w') as outfile:
            data = {}
            json.dump(data, outfile)
        print(f"Création de {library_file}")


def save_library(library, library_file):
    """Enregistrement de la library en json dans le dossier courrant"""

    with open(library_file, "w") as fd:
        fd.write(json.dumps(library))
    print(f"{library_file} enregistré")


def load_library(library_file):
    """Lecture de library_file"""
    with open(library_file) as fd:
        data = fd.read()
        library = json.loads(data)
    print(f"{library_file} chargé")
    return library


def create_directory(directory):
    """
    Crée le répertoire avec le chemin absolu.
    ex: /media/data/3D/projets/meteo/meteo_forecast/2017_06
    """

    try:
        Path(directory).mkdir(mode=0o777, parents=False)
        print(f"Création du répertoire: {directory}")
    except FileExistsError as e:
        print(f"Ce répertoire existe: {directory}")
    except PermissionError as e:
        print(f"Problème de droits avec le répertoire: {directory}")
    except:
        print(f"Erreur avec le répertoire: {directory}")


def get_file_list(directory, extentions):
    """Retourne la liste de tous les fichiers avec les extentions de
    la liste extentions
    extentions = liste = ["mid", "midi"]]

    Si directory est défini avec chemin relatif (idem avec absolu),
        les fichiers sont avec chemin relatif (idem avec absolu).

    Attention: subdirs comprend le dossier racine !
    """

    file_list = []
    for path, subdirs, files in os.walk(directory):
        for name in files:
            for extention in extentions:
                if name.endswith(extention):
                    file_list.append(str(Path(path, name)))

    return file_list



if __name__ == '__main__':
    PlayerApp().run()
