
# cd /media/data/3D/projets/player/simpleserver
# /media/data/3D/projets/player/simpleserver/mon_env/bin/python3 simpleserver.py

from time import time, sleep
import datetime
import subprocess
from threading import Thread
from functools import partial
import json
from pathlib import Path


from twisted.internet.protocol import Protocol
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor

from just_playback import Playback

from library import get_library, print_library
from player_utils import create_directory, create_json_file


MUSIC = '/media/pi/USB3x16Go/music/flacs'
print(f"le dossier MUSIC est {MUSIC}")

PORT = 8000
CURDIR = str(Path(__file__).parent.absolute())
print(f"Le dossier de ce script est: {CURDIR}")



class Player:
    global MUSIC, CURDIR

    def __init__(self):
        global MUSIC, CURDIR

        # Pour la 1ère excécution
        self.create_coversdir_libraryjson()

        # En pause ou pas
        self.pause = 0
        # Le numéro de piste à jouer ou en cours
        self.track = 1
        # La longueur de la piste
        self.lenght = 60

        # Fin de l'album
        self.end = 0
        self.block_end_thread = 0

        self.album = ""
        self.previous_album = ""
        # Un json avec toutes les infos des albums
        self.library = get_library(MUSIC, CURDIR)
        # # print_library(self.library)
        self.save_library_in_covers()

        # Liste des tracks joué pour debug
        self.played_track = []

        # Un seul lecteur
        self.playback = Playback()

    def create_coversdir_libraryjson(self):
        covers_dir = CURDIR + '/covers'
        create_directory(covers_dir)
        json_file = CURDIR + '/covers/library.json'
        create_json_file(json_file)

    def save_library_in_covers(self):
        """Le fichier library est dans /covers pour pouvoir être téléchargé
        avec les images de /covers.
        """
        library_file = CURDIR + '/covers/library.json'
        with open (library_file, "w") as fd:
            fd.write(json.dumps(self.library))

    def apply_msg_from_client(self, from_client):
        """Gestion du Player avec demande de l'application

        Message reçu: ['from_client', {'album': 'Luka Productions - Fasokan',
                                      'track': 4,
                                      'position': 10,
                                      'play_pause': 0,
                                      'quit': 0,
                                      'shutdown': 0,
                                      'http_on': 0}]

        http_on est geré par MyTCPServer
        Le reste par ici
        Réponse au message reçu: ['from server',
                                   92.3, curr_pos
                                   273, lenght
                                   played_track]
        """

        if 'album' in from_client:
            self.end = 0
            album = from_client['album']
            # Seulement si nouvel album
            if album != self.album:
                # # print(f"Nouvel Album demandé par l'appli: {album}")
                self.track = 1
                self.pause = 0
                self.block_end_thread = 1
                self.play_album(album)

        if 'new_track' in from_client:
            track = from_client['new_track']
            if track != 0:
                self.track = track
                print("new Track demandé par l'appli", self.track)
                self.block_end_thread = 1
                self.play_track_n(self.track)

        # Ne sert que pour se placer dans le track avec le slider
        if 'position' in from_client:
            position = from_client['position']
            if position != 0:
                print("nouvelle position demandée par l'appli")
                self.playback.seek(position)

        if 'play_pause' in from_client:
            if self.pause != from_client['play_pause']:
                self.pause = from_client['play_pause']
                print(f"pause demandée par l'appli: {self.pause}")
                if self.pause:
                    self.playback.pause()
                if not self.pause:
                    self.playback.resume()

        if 'quit' in from_client:
            if from_client['quit'] == 1:
                print("L'appli a quitté, je reste en attente")
                self.playback.stop()
                self.playback.seek(0)

        if 'shutdown' in from_client:
            if from_client['shutdown'] == 1:
                print("Shutdown demandé par l'appli")
                reactor.stop()
                self.shutdown()

    def play_album(self, album):
        """Lancement d'un nouvel album: album.
        Un autre peut être en cours, et ça peut être le même.
        Les tracks doivent s'enchaîner même si l'app est déconnectée.
        L'album est dans /media/pi/USB3x16Go/music/flacs/
        MUSIC =         '/media/pi/USB3x16Go/music/flacs'
        """
        if album:
            if album != self.previous_album:
                self.end = 0
                self.album = album
                self.previous_album = album
                # Nombre de clés dans le dict des 'titres'
                self.tracks_number = len(self.library[self.album]['titres'])

                print(f"Lecture de l'album: {self.album}")

                self.track = 1
                self.play_track_n(1)

    def play_track_n(self, nb):
        """Demande d'un premier track
        ou d'un nouveau track avec un autre en cours.
        Dans tous les cas, c'est sur l'abum en cours.
        """
        # J'arrête ce qui pourrait être en cours
        try:
            # On se place à zéro
            self.playback.seek(0)
            self.playback.stop()
        except:
            pass

        if self.album:
            self.played_track.append(nb)
            self.fichier_to_play = self.library[self.album]['titres'][nb][1]
            self.lenght =  self.library[self.album]['titres'][nb][2]
            f = self.fichier_to_play.split('/')[-1]
            print(f"Lecture du fichier: {f} de {self.lenght} secondes")
            self.playback.load_file(self.fichier_to_play)

            # On joue
            print(f"Play de la piste: {nb}\n")
            sleep(1)
            self.playback.play()
            self.block_end_thread = 0
            Thread(target=self.run_next_track_at_the_end_of_previous_thread).start()

    def run_next_track_at_the_end_of_previous_thread(self):
        """Ce thread est lancé par play_track_n."""

        while self.playback.active:
            sleep(0.1)

        # Avant la sortie du while précédent, des attributs ont été modifié
        # self.block_end_thread = 0 correspond à une fin d'album normale
        if not self.block_end_thread:
            if self.track < self.tracks_number:
                self.track += 1
                print(f"Thread - Le track est fini, track suivant: {self.track}")
                # play_track_n stoppe le Thread, et le relance
                self.play_track_n(self.track)
            else:
                print("Thread - Fin de l'album")
                self.end = 1
                self.track = 1
                self.album = ""
        # L'album n'est pas fini
        else:
            print("Thread - Le track n'est pas fini")

    def shutdown(self):
        subprocess.run(['sudo', 'shutdown', 'now'])



class HttpServer:
    """Crée un serveur http, dans le dossier cwd.
    Une requête permet de télécharger les fichiers de ce dossier.
    Super usefull mais unsafe, donc il ne tourne que le temps du téléchargement.
    """
    global CURDIR

    def __init__(self):
        global CURDIR
        self.covers_dir = CURDIR + '/covers'

    def run(self):
        """Run de la commande dans le dossier covers"""

        print(f"Serveur HTTP lancé dans le dossier des covers: {self.covers_dir}")
        self.process = subprocess.Popen('python3 -m http.server 8080',
                                        shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        cwd=self.covers_dir)

    def stop(self):
        print("Stop du http serveur")
        self.process.terminate()



class MyTCPServer(Protocol):
    """ Attribut de class: nb_protocol
    Un protocol par client connecté,
    chaque protocol est  une  instance indépendante
    Cette classe accède à player avec self.factory.player
    """

    nb_protocol = 0

    def __init__(self):
        print("Twisted TCP Serveur créé")

        self.httpserver = None
        self.debug = 0

    def connectionMade(self):
        """self.factory was set by the factory"s default buildProtocol
        self.transport.loseConnection() pour fermer
        """

        MyTCPServer.nb_protocol += 1
        print(f"connectionMade Nombre de protocol = {MyTCPServer.nb_protocol}")

    def connectionLost(self, reason):

        MyTCPServer.nb_protocol -= 1
        print(f"connectionLost Nombre de protocol = {MyTCPServer.nb_protocol}")
        # Par sécurité
        self.kill_httpserver()

    def kill_httpserver(self):
        try:
            self.httpserver.stop()
            del self.httpserver.process
        except:
            pass
        self.httpserver = None

    def dataReceived(self, data):
        """A chaque réception, envoi d'une réponse 0.2 seconde plus tard.
        msg = ['from_client', {'album': 0, 'track': 1, 'position': 0,
                                'play_pause': 0, 'quit': 0, 'shutdown': 0,
                                'library': 0, 'http_on': 0}]
        """
        # Pb avec paquet TCP passé par 2
        try:
            msg = json.loads(data.decode('utf-8'))
        except:
            msg = None

        resp = [0]

        if msg:
            if self.debug:
                print(f"\nMessage reçu: {msg}")

            # Pas d'autres msgs envoyés !
            if msg[0] == 'from_client':
                from_app = msg[1]

                # Gestion du http serveur
                if 'http_on' in from_app:
                    if from_app['http_on']:
                        # # print("http on")
                        if not self.httpserver:
                            self.httpserver = HttpServer()
                            self.httpserver.run()
                    else:
                        # # print("http off")
                        self.kill_httpserver()

                # Gestion du lecteur, gére tout sauf library et http_on
                self.factory.player.apply_msg_from_client(from_app)

                # Création de la réponse
                resp = ['from server',
                        self.factory.player.playback.curr_pos,
                        self.factory.player.lenght,
                        self.factory.player.track,
                        self.factory.player.played_track]

        sleep(0.2)
        self.transport.write(json.dumps(resp).encode('utf-8'))

        if self.debug:
            print(f"Réponse au message reçu: {resp}")



class MyTCPServerFactory(Factory):

    # This will be used by the default buildProtocol to create new protocols:
    protocol = MyTCPServer

    def __init__(self, quote=None):
        print("MyTCPServerFactory créé")
        # Le player est dans le ServerFactory
        self.player = Player()

    def stop(self):
        self.stopFactory()



endpoint = TCP4ServerEndpoint(reactor, PORT)
endpoint.listen(MyTCPServerFactory())
reactor.run()
