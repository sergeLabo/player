
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

# # print(f"platform: {platform.platform()}")
# # # Ce truc est nul, car afux si maj du noyau
# # if 'Linux-5' in platform.platform():
     # # MUSIC = '/media/data/3D/music/flacs'
# # else:

MUSIC = '/media/pi/USB3x16Go/music/flacs'
print(f"le dossier MUSIC est {MUSIC}")

PORT = 8000
CURDIR = str(Path(__file__).parent.absolute())
print(f"Le dossier de ce script est: {CURDIR}")


class HttpServer:
    global CURDIR
    def __init__(self):
        global CURDIR
        self.debug = 1
        self.covers_dir = CURDIR + '/covers'

    def update_covers_directory(self):
        pass

    def save_img_in_covers_directory(self, file_name):
        pass

    def run(self):
        """Run de la commande dans le dossier covers"""
        # #
        print(f"Dossier des covers: {self.covers_dir}")
        self.process = subprocess.Popen('python3 -m http.server 8080',
                                        shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        cwd=self.covers_dir)
        if self.debug:
            print("Server HTTP is running ...")

    def stop(self):
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
        self.debug = 0

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
        self.kill_httpserver()
        
    def kill_httpserver(self):
        # Kill du Httpserver
        try:
            self.httpserver.stop()
            del self.httpserver.process
            print("Fin du httpserver")
        except:
            if self.debug:
                print("httpserver is not running")

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
            if self.debug:
                print(f"\nMessage reçu: {msg}")

            if msg[0] == 'from_client':
                self.factory.player.apply_from_client(msg[1])
                
                if self.factory.player.http_on == 1:
                    self.factory.player.http_on == 0
                    if not self.httpserver:
                        self.httpserver = HttpServer()
                        self.httpserver.run()
                    
                if self.factory.player.http_on == 0:
                    self.kill_httpserver()
                    
                if self.factory.player.send_library == 1:
                    resp = ['library', self.factory.player.library]
                    self.factory.player.send_library = 0

                else:
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
                      f"    end {self.factory.player.end}")

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
    global MUSIC, CURDIR

    def __init__(self):
        global MUSIC, CURDIR

        self.pause = 0
        self.track = 1
        self.positon = 0
        self.lenght = 60
        self.end = 0
        self.album = None
        self.library = get_library(MUSIC, CURDIR)
        self.playback = Playback()
        self.track_loop = 0
        self.t_block_track = time()
        self.t_block_end = time()
        # Suivi des réponses
        self.send_library = 0  # Si 1 il faut envoyer
        self.http_on = 0  # http server: 0 off 1 on
        
    def apply_from_client(self, from_client):
        """Modification apportée depuis l'app"""

        if from_client['library'] == 1:
            self.send_library = 1

        if from_client['http_on'] == 1:
            self.http_on = 1
            
        if from_client['http_on'] == 0:
            self.http_on = 0

        if self.album != from_client['album']:
            if time() - self.t_block_end > 10:
                self.album = from_client['album']
                
                # Nouvel album
                if self.album != 0:
                    print("Nouvel Album", self.album)
                    self.track = 1
                    self.position = 0
                    self.pause = 0
                    if self.album:
                        self.play_album(self.album)

        elif self.track != from_client['track']:
            if time() - self.t_block_track > 10:
                self.t_block_track = time()
                self.track = from_client['track']
                print("New Track", self.track)
                self.position = 0
                self.track = self.track
                self.play_track_n(self.track)

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
        """Lancement d'un nouvel album: album.
        Un autre peut être en cours, et ça peut être le même.
        Les tracks doivent s'enchaîner même si l'app est déconnectée.
        """

        self.album = album
        # Nombre de clés dans le dict des 'titres'
        self.tracks_number = len(self.library[self.album]['titres'])

        print(f"Lecture de l'album: {self.album}")

        self.track = 1
        self.play_track_n(self.track)

    def play_track_n(self, n):
        if self.album:
            self.fichier_to_play = self.library[self.album]['titres'][n][1]
            self.lenght =  self.library[self.album]['titres'][n][2]
            print(f"Lecture du fichier: {self.fichier_to_play}",
                  f"de {self.lenght} secondes")

            # Chargement du ficheir à lire
            print(f"Chargement du fichier: {self.fichier_to_play}")
            self.playback.load_file(self.fichier_to_play)
            print("Fichier chargé")
            # On se place à zéro
            self.playback.seek(0)
            # On joue
            print(f"Play de la piste: {n}")
            self.playback.play()
            sleep(2)
            self.next_track_thread()
        
    def next_track_thread(self):
        Thread(target=self.next_track).start()
        
    def next_track(self):
        while self.playback.active:
            sleep(3)

        if self.track < self.tracks_number:
            self.track += 1
            print(f"Play du track {self.track}")
            self.t_block_track = time()
            self.play_track_n(self.track)
        else:
            self.playback.stop()
            

endpoint = TCP4ServerEndpoint(reactor, PORT)
endpoint.listen(MyTCPServerFactory())
reactor.run()
