    def old_play_album(self, album):
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

    def old_play_track(self):
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

    def old_run_tracks_thread(self):
        Thread(target=self.run_tracks).start()

    def old_run_tracks(self):

        while self.album_loop:
            if not self.playback.active:
                # si inactive, curr_pos = 0
                # Track suivant
                if self.track < self.tracks_number:
                    if time() - self.t_block_album > 10:
                        self.t_block_album = time()
                        self.t_block_track = time()
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
                    self.t_block_end = time()

            sleep(1)
