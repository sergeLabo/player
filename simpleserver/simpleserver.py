
# cd /media/data/3D/projets/player/simpleserver
# /media/data/3D/projets/player/simpleserver/mon_env/bin/python3 simpleserver.py


from time import time, sleep
import datetime
import subprocess
from threading import Thread
from functools import partial
import json
from pathlib import Path
import platform

import psutil

from twisted.internet.protocol import Protocol
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor

from just_playback import Playback

from library import get_library, get_tracks, dict_to_OrderdDict

print(f"platform: {platform.platform()}")
if 'Linux-5.10.0-10-amd64-x86_64-with-glibc2.31' in platform.platform():
    MUSIC = '/media/data/3D/music/flacs'
else:
    MUSIC = '/media/pi/USB3x16Go/music/flacs'
print(f"le dossier MUSIC est {MUSIC}")

PORT = 8000
CURDIR = str(Path(__file__).parent.absolute())
print(f"Le dossier de ce script est: {CURDIR}")



class HttpServer:

    def __init__(self):
        self.debug = 1

    def run(self):
        """Run de la commande dans le dossier covers"""
        self.process = subprocess.Popen(    'python3 -m http.server 8080',
                                            shell=True,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            cwd=CURDIR + '/covers')
        if self.debug:
            print("Server HTTP is running ...")

    def stop(self):
        print("Fin du subprocess HTTP server ...")
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

        self.message = ""
        self.httpserver = None
        self.run_loop = 1
        self.debug = 1

    def connectionMade(self):
        """
        self.factory was set by the factory"s default buildProtocol
        self.transport.loseConnection() pour fermer
        """

        MyTCPServer.nb_protocol += 1
        print(f"connectionMade Nombre de protocol = {MyTCPServer.nb_protocol}")

    def connectionLost(self, reason):

        MyTCPServer.nb_protocol -= 1
        print(f"connectionLost Nombre de protocol = {MyTCPServer.nb_protocol}")

        # Kill du Httpserver
        try:
            self.httpserver.stop()
            del self.httpserver.process
            print("Fin du httpserver")
        except:
            print("httpserver is not running")

        # Fin playback
        if self.factory.player.playback.active:
            self.factory.player.playback.seek(0)
            self.factory.player.playback.stop()
            print(f"Fin du playback")

        self.factory.player.album = None
        self.factory.player.album_loop = 0
        self.factory.player.track = 1
        self.factory.player.end = 0

    def dataReceived(self, data):
        self.handle_message(data)

    def handle_message(self, data):
        # Pb avec paquet TCP passé par 2
        try:
            msg = json.loads(data.decode('utf-8'))
        except:
            msg = None

        resp = None

        if msg:
            print(f"\nMessage reçu: {msg}")
            if msg[0] == 'give me the libray please':
                resp = ['library', self.factory.player.library]

            elif msg[0] == 'start httpserver':
                if not self.httpserver:
                    self.httpserver = HttpServer()
                    self.httpserver.run()

            elif msg[0] == 'stop httpserver':
                if self.httpserver:
                    self.httpserver.stop()
                    del self.httpserver.process
                    self.httpserver = None
                    print("Le client a dit: Fin du httpserver")

            elif msg[0] == 'values from client':
                self.factory.player.apply_from_client(msg[1])
                resp = ['from server',
                        self.factory.player.playback.curr_pos,
                        self.factory.player.lenght,
                        self.factory.player.track,
                        self.factory.player.end]

        if resp:
            if self.debug:
                print(f"Réponse au message reçu: {resp}")
                print(f"    album {self.factory.player.album}")
                print(f"    pause {self.factory.player.pause}",
                      f"    track {self.factory.player.track}",
                      f"    positon {self.factory.player.positon}",
                      f"    lenght {self.factory.player.lenght}",
                      f"    end {self.factory.player.end}",
                      f"    album_loop {self.factory.player.album_loop}")

            self.transport.write(json.dumps(resp).encode('utf-8'))



class MyTCPServerFactory(Factory):

    # This will be used by the default buildProtocol to create new protocols:
    protocol = MyTCPServer

    def __init__(self, quote=None):
        print("MyTCPServerFactory créé")
        # Le player est dans le ServerFactory
        self.player = Player()

    def stop(self):
        self.stopFactory()



class Player:

    def __init__(self):

        self.pause = 0
        self.track = 1
        self.positon = 0
        self.lenght = 60
        self.album = None
        self.end = 0
        self.library = get_library(MUSIC, CURDIR)
        self.playback = Playback()
        self.album_loop = 1

    def apply_from_client(self, from_client):

        if self.album != from_client['album']:
            self.album = from_client['album']
            # Nouvel album
            print("Nouvel Album", self.album)
            if self.album:
                self.play_album(self.album)

        elif self.track != from_client['track']:
            self.track = from_client['track']
            print("New Track", self.track)
            self.position = 0
            self.play_track()

        elif from_client['position'] != 0:
            self.positon = from_client['position']
            print("New Position", self.positon)
            self.playback.seek(from_client['position'])
            self.position = 0

        elif self.pause != from_client['play_pause']:
            self.pause = from_client['play_pause']
            print("Pause", self.pause)
            if self.pause:
                self.playback.pause()
            if not self.pause:
                self.playback.resume()

        elif from_client['quit'] == 1:
            print("Quit demandé par le client")
            self.playback.stop()
            self.playback.seek(0)

        elif from_client['shutdown'] == 1:
            print("Shutdown demandé par le client")
            reactor.stop()
            self.shutdown()

    def shutdown(self):
        subprocess.run(['sudo', 'shutdown', 'now'])

    def play_album(self, album):
        """Lancement d'un album, un autre peut être en cours"""

        self.album = album
        # Reset de la fin de l'album précédent
        self.end = 0

        # Nombre de clés dans le dict des 'titres'
        self.tracks_number = len(self.library[self.album]['titres'])
        self.album_loop = 0
        self.track = 1

        if self.playback.active:
            self.playback.stop()
            # Attente de la fin du thread run_tracks
            sleep(0.2)

        # Lancement de self.track qui enchainera les autres
        self.play_track()

    def play_track(self):
        """
        l = {'nom du dossier parent': {  'album': 'toto',
                                                'artist':,
                                                'cover':,
                                                'titres': { 0: ('tata',
                                                                'chemin abs',
                                                                lenght),
                                                            1: ('titi',
                                                                'chemin abs',
                                                                lenght)}}}
        l et 'titres' sont des un OrderedDict
        """

        # Reset de la fin de l'album précédent, répétition !
        self.end = 0

        if self.album:
            name = self.library[self.album]['titres'][self.track][0]
            print("    Play track", self.track, name, "de", self.album)

            self.fichier_to_play = self.library[self.album]['titres'][self.track][1]
            self.lenght =  self.library[self.album]['titres'][self.track][2]

            self.playback.stop()
            self.playback.load_file(self.fichier_to_play)
            self.playback.seek(0)
            self.playback.play()

            # Pour enchainer les track
            self.album_loop = 1
            self.run_tracks_thread()

    def run_tracks_thread(self):
        Thread(target=self.run_tracks).start()

    def run_tracks(self):

        while self.album_loop:
            if not self.playback.active:
                # si inactive, curr_pos = 0
                # Track suivant
                if self.track < self.tracks_number:
                    self.track += 1
                    print("\nLancement du track:", self.track)
                    self.play_track()

                else:
                    print("Fin de l'album")
                    self.album = None
                    self.album_loop = 0
                    self.playback.seek(0)
                    self.playback.stop()
                    self.track = 1
                    self.end = 1

            sleep(1)



endpoint = TCP4ServerEndpoint(reactor, PORT)
endpoint.listen(MyTCPServerFactory())
reactor.run()
