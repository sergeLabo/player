

# cd /media/data/3D/projets/player/app
# /media/data/3D/projets/player/server/mon_env/bin/python3 main.py

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


from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty, NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.utils import platform

from library_utils import dict_to_OrderdDict
from download_covers import DownloadFiles
from player_utils import create_json_file, save_library, load_library,\
                         create_directory, get_file_list


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



class MyTcpClient(Protocol):

    def __init__(self, app):
        """app est le self
        de                                                        ici
        reactor.connectTCP(self.ip, self.port, MyTcpClientFactory(self))
        """
        self.app = app
        print("Un protocol client créé")
        print(f"IP = {self.app.tcp_ip}, PORT = {self.app.tcp_port}")

    def connectionMade(self):
        print("Connection Made: début d'envoi des messages.")
        # Un premier envoi pour lancer les boucles réception/envoi
        # Attente que le serveur se lance
        sleep(0.5)
        self.transport.write(json.dumps([0]).encode('utf-8'))

    def connectionLost(self, reason):
        print("Connection Lost")

    def dataReceived(self, data):
        """Appelé à chaque réception:
        Répond aussitôt.
        """
        self.app.handle_message(data)
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
        try:
            self.app.root.ids.artist.text = "La Raspberry Pi n'est pas allumée ...."
        except:
            pass

    def buildProtocol(self, addr):
        print(f"MyTcpClientFactory buildProtocol {addr}")
        try:
            self.app.root.ids.artist.text = "Selectionnez un album"
        except:
            pass
        return MyTcpClient(self.app)

    def clientConnectionLost(self, connector, reason):
        print("Lost connection.  Reason:", reason)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        print("Connection failed. Reason:", reason)
        ReconnectingClientFactory.clientConnectionFailed(self,connector,reason)



class Player(FloatLayout):
    titre = StringProperty("")
    maxi = NumericProperty(100)

    def __init__(self, **kwargs):
        # Tous les agrguments, méthodes seront appelable avec self.app !
        super().__init__(**kwargs)

        self.app = App.get_running_app()
        self.titre = ""
        self.maxi = 100
        self.album = ""
        self.pause = 0
        self.layout_tracks = None
        self.layout_albums = None
        self.track = 1
        self.track_number = 1
        self.t_block = time()

    def play_track(self, track):
        """
        album =
        track =
        l = {'nom du dossier parent': {'album': 'toto', # nom sans chemin
                                       'artist':,
                                       'cover':,
                                       'titres': {1: ('tata','chemin abs',lenght),
                                                  2: ('titi','chemin abs',lenght)}}}
        """

        if self.album:
            # Récup des infos
            self.title = self.app.library[self.album]['titres'][str(track)][0]
            self.album_name = urllib.parse.unquote_plus(self.app.library[self.album]['album'])
            self.artist = self.app.library[self.album]['artist']
            tracks_number = len(self.app.library[self.album]['titres'])
            self.maxi = self.app.library[self.album]['titres'][str(track)][2]
            print("maxi", self.maxi)
            cover = self.app.library[self.album]['cover']
            name = str(cover.split('/')[-1])
            self.cover =  str(Path(cover).parent) + '/' + name

            self.app.msg_for_svr['album'] = self.album
            self.app.msg_for_svr['position'] = 0
            self.app.msg_for_svr['track'] = track

            print(f"Play de: {track}: {self.title} de {self.album_name} par {self.artist} \n")
            self.update_dispayed_text()

    def new_track(self, value):
        """Track suivant"""
        if self.album:
            self.track = int(value)
            self.play_track(self.track)
            self.app.msg_for_svr['track'] = self.track

    def next(self):
        if self.album:
            if time() - self.t_block > 2:
                self.t_block = time()
                self.track += 1
                if self.track > self.track_number:
                    self.track = self.track_number
                self.app.msg_for_svr['track'] = self.track

    def previous(self):
        """Track précédent"""
        if self.album:
            if time() - self.t_block > 2:
                self.t_block = time()
                self.track -= 1
                if self.track < 1:
                    self.track = 1
                self.play_track()
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
                self.ids.play_pause.background_normal = 'images/Play-down.png'
                self.ids.play_pause.background_down = 'images/Play-normal.png'
                self.app.msg_for_svr['play_pause'] = 0
                self.pause = 0

    def change_position(self, value):
        print("Nouvelle position du slider:", value)
        self.app.msg_for_svr['position'] = int(value)

    def update_dispayed_text(self):
        """Displays song duration, title, album and artist"""

        self.ids.track_number.text = f"{str(self.track)}"
        self.ids.title.text = self.title
        self.ids.album.text = self.album_name
        self.ids.artist.text = self.artist
        self.ids.album_art.source = self.cover
        self.ids.song_slider.max = self.maxi

    def reset(self):
        pass

    def set_selected_album(self, value, instance):
        self.album = value
        if self.album:
            # Affichage des Tracks
            self.add_tracks_buttons()

            # Lancement du player
            self.play_track(1)

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
        print("Ajout des covers")
        # Linux vs Android
        self.change_covers_path_in_library()
        self.size = (Window.width, Window.height)

        if self.layout_albums:
            self.ids.tracks_scroll.remove_widget(self.layout_albums)

        self.layout_albums = GridLayout(cols=2,
                            spacing=(10, 10),
                            padding=(10, 10))
        self.layout_albums.size_hint_y= None
        # Make sure the height is such that there is something to scroll.
        self.layout_albums.bind(minimum_height=self.layout_albums.setter('height'))

        for key in self.app.library.keys():
            # key = 'nom du dossier parent'
            album = key
            cover = self.app.library[key]['cover']

            try:
                button = Button(background_normal=cover,
                                background_down='covers/default_cover.png',
                                size_hint_y=None,
                                height=int((self.size[0]-280)/4.2))  # 219
                buttoncallback = partial(self.set_selected_album, album)
                button.bind(on_release=buttoncallback)
                self.layout_albums.add_widget(button)
                # Bug affichage ? temps de chargement des images ?
                sleep(0.2)
                #print(f"Bind de {cover}")
            except Exception as e:
                print("Erreur affichage image dans Albums:", e)

        try:

            self.ids.album_scroll.add_widget(self.layout_albums)
        except:
            print("Les albums sont déjà ajoutés!")

    def add_tracks_buttons(self):
        """l = {'nom du dossier parent': {'album': 'toto',
                               'artist':,
                               'cover':,
                               'titres': { 0: ('tata','chemin abs',lenght),
                                           1: ('titi','chemin abs',lenght)}}}
        l et 'titres' sont des un OrderedDict
        """
        self.size = (Window.width, Window.height)

        # Remove widgets of previous album
        if self.layout_tracks:
            self.ids.tracks_scroll.remove_widget(self.layout_tracks)

        self.layout_tracks = GridLayout(cols=1,
                                 spacing=(4, 4),
                                 padding=(4, 4))
        self.layout_tracks.size_hint_y= None
        # Make sure the height is such that there is something to scroll.
        self.layout_tracks.bind(minimum_height=self.layout_tracks.setter('height'))

        dico = self.app.library[self.album]['titres']
        for key in range(1, len(dico) +1):
            text = (f"{key}  :  {dico[str(key)][0]}")
            button = Button(size_hint_y=None,
                            background_color=(2.4, 2.4, 2.4, 1),
                            color=(0.5, 0.5, 0.5, 1),
                            font_size="24dp",
                            height=70,  # 50 40
                            text=text)
            buttoncallback = partial(self.set_selected_track, key)
            button.bind(on_release=buttoncallback)
            self.layout_tracks.add_widget(button)

        self.ids.tracks_scroll.add_widget(self.layout_tracks)

    def set_selected_track(self, value, instance):
        """Sélection d'un nouveau track"""
        self.track = int(value)
        self.update_dispayed_text()
        self.play_track(self.track)
        self.app.msg_for_svr['new_track'] = self.track

    def shutdown(self):
        self.app.do_shutdown()

    def quit(self):
        self.app.do_quit()

    def change_covers_path_in_library(self):
        """Chemins sur client != chemin sur serveur"""
        for key in self.app.library.keys():
            cover = self.app.library[key]['cover']
            cover_name = cover.split('/')[-1]
            local_cover = self.app.covers_path + '/' + cover_name
            # Player Cover: /data/data/org.test.player/files/app/covers/All The Way West.jpg
            self.app.library[key]['cover'] = local_cover



class PlayerApp(App):
    global ANDROID

    def build(self):
        """Exécuté après build_config.
        Le self de Player est l'objet Player créé ici.
        """
        Window.clearcolor = (0.8, 0.8,0.8, 1)
        return Player()

    def build_config(self, config):
        """self.config peut être appelé à la fin de cette méthode.
        Création du fichier *.ini si il n'existe pas"
        """

        config.setdefaults( 'network', {'ip': '192.168.0.108',
                                        'port': 8000})

        config.setdefaults( 'httpserver', {'port': 8080})

    def build_settings(self, settings):
        """Construit l'interface de l'écran Options, pour Player seul.
        Les réglages Kivy sont par défaut.
        Cette méthode est appelée par app.open_settings() dans .kv,
        donc si Options est cliqué !
        """
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

        self.tcp_ip = self.config.get('network', 'ip')
        self.tcp_port = int(self.config.get('network', 'port'))
        self.http_port = int(self.config.get('httpserver', 'port'))
        self.http_adress = 'http://' + str(self.tcp_ip) + ':' + str(self.http_port) + '/'
        print("Adress http:", self.http_adress)
        # Création du client TCP
        self.tcp_init()

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

        # Chargement des covers dans le GUI
        if self.library:
            self.root.add_cover_buttons()

    def tcp_init(self):
        reactor.connectTCP(self.tcp_ip, self.tcp_port, MyTcpClientFactory(self))
        self.msg_for_svr_reset()

    def msg_for_svr_reset(self):
        """Appelé par tcp_init et end"""
        self.msg_for_svr = {}
        self.msg_for_svr['album'] = ""
        self.msg_for_svr['new_track'] = 1
        self.msg_for_svr['position'] = 0
        self.msg_for_svr['play_pause'] = 0
        self.msg_for_svr['quit'] = 0
        self.msg_for_svr['shutdown'] = 0
        self.msg_for_svr['http_on'] = 0
        self.msg_for_svr['end received'] = 0

    def handle_message(self, msg):

        try:
            msg = json.loads(msg.decode('utf-8'))
        except:
            msg = None

        if msg:
            if msg[0] == 'from server':

                timestamp = msg[1]
                current_lenght = msg[2]
                track = msg[3]
                end = msg[4]
                played_track = msg[5]

                # Timestamp changée toutes les 2 secondes
                if timestamp:
                    if int(timestamp) % 2 == 0:
                        self.root.ids.song_slider.value = timestamp

                # Lenght
                ta = str(datetime.timedelta(seconds=timestamp))[2:7]
                track_len = str(datetime.timedelta(seconds=current_lenght))[2:7]
                self.root.ids.current_position.text = f"{ta}  |  {track_len}"

                # Changement de track
                if track != self.root.track:
                    self.root.track = track
                    print("New track demandé par le serveur:", track)
                    self.root.new_track(track)

                # Fin de l'album: ne peut être reçu que si l'app tourne
                if end == 1:
                    print(f"Fin de l'abum {self.root.album}")
                    self.msg_for_svr_reset()
                    self.root.track = 1
                    self.root.album = ""
                    self.root.pause = 0
                    self.msg_for_svr_reset()
                    self.msg_for_svr['end received'] = 1

                # Liste
                l = played_track
                t = ""
                for i in l:
                    t += str(i) + " | "
                self.root.ids.debug.text = t

    def ask_for_library_and_covers(self):
        """Demande de la lib et mise à jour dans un thread."""

        # Fichiers à télécharger
        files_list = get_file_list(self.covers_path, ['jpg', 'png', 'json'])
        print("Fichiers des albums existants:")
        for img in files_list:
            print("    ", img)

        # Demande de mise en route du httpserver
        self.msg_for_svr['http_on'] = 1
        df = DownloadFiles(self.http_adress,
                           self.covers_path,
                           files_list)
        # Attente que le serveur démarre
        sleep(1)
        try:
            print(f"Téléchargement en htttp")
            text = df.download_url()
            df.get_missing_covers(text)
            scrm.info = "Albums mis à jour et chargés!"
        except:
            print("Le serveur HTTP n'est pas accessible !")

        # Demande de stop du httpserver
        self.msg_for_svr['http_on'] = 0
        # Reload the new library
        load_library(self.library_file)
        # Affichage des images dans l'écran album
        self.root.add_cover_buttons()

    def do_quit(self):
        print("Quit final ...")
        self.msg_for_svr['quit'] = 1
        self.wait_before_quit_thread()

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



if __name__ == '__main__':
    PlayerApp().run()
