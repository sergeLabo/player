
import os
from pathlib import Path
import json
from collections import OrderedDict
import urllib.parse

import mutagen
from mutagen.flac import Picture, FLAC



def get_library(library_path, current_dir):
    """Parcours le dossier library_path,
    trouve les dossiers albums, avec des fichiers .flac
    Retourne un dict:
    l = {'nom du dossier parent': {'album': 'toto',
                                   'artist':,
                                   'cover':,
                                   'titres': { 0: ('tata','chemin abs',lenght),
                                               1: ('titi','chemin abs',lenght)}}}
    l et 'titres' sont des un OrderedDict
    """
    library = {}
    for root, directories, fichiers in os.walk(library_path):
        for fichier in fichiers:
            # num sert si pas de tracknumber
            num = 0
            if fichier.endswith(".flac"):
                fichier_abs = os.path.join(root, fichier)
                # # print("Fichier trouvé:", fichier_abs, "\n   ", fichier)

                album_name = str(Path(fichier_abs).parent)

                title, album, artist, cover, tracknumber, lenght = \
                                        fichier_information(fichier_abs,
                                                            num,
                                                            current_dir)

                # Mise en forme et création de mes dict
                if album_name not in library:
                    library[album_name] = {}

                if 'album' not in library[album_name]:
                    library[album_name]['album'] = album

                if 'artist' not in library[album_name]:
                    library[album_name]['artist'] = artist

                if 'cover' not in library[album_name]:
                    library[album_name]['cover'] = cover

                if 'titres' not in library[album_name]:
                    library[album_name]['titres'] = {}

                # Ajout des titres
                library[album_name]['titres'][tracknumber] = (title,
                                                                fichier_abs,
                                                                lenght)
                num += 1

    return library


def print_library(library):
    """Le json met les int en str"""
    print(json.dumps(library, sort_keys=False, indent=4))


def fichier_information(fichier, num, current_dir):
    """Informations sur un fichier"""

    song = mutagen.File(fichier)
    file_extension = str(type(song))

    # if file is FLAC, extract meta data
    if 'mutagen.flac.FLAC' in file_extension:

        try:
            tracknumber = song['TRACKNUMBER'][0]
        except:
            tracknumber = num

        try:
            title = str(song['TITLE'][0])
        except:
            title = 'unknown'

        try:
            # Dans raw, Chars incompatible avec url
            album = str(song['ALBUM'][0])
        except:
            album = 'unknown'

        try:
            artist = str(song['ARTIST'][0])
        except:
            artist = 'unknown'

        try:
            lenght = int(song.info.length)
        except:
            lenght = 60

        cover = "default_cover.png"
        try:
            artwork = FLAC(fichier).pictures
            if artwork:
                album_quote = urllib.parse.quote_plus(album)
                if artwork[0].mime == 'image/jpeg':
                    cover = current_dir + '/covers/' + album_quote + '.jpg'
                elif artwork[0].mime == 'image/png':
                    cover = current_dir + '/covers/' + album_quote + '.png'
                p = Path(cover)
                if not p.is_file():
                    with open(cover, 'wb') as img:
                        img.write(artwork[0].data)
                        print(f"Save of cover: {cover}")
        except:
            print("Erreur fichier_information")
            
    else:
        title = "Unknow"
        album = "Unknow"
        artist = "Unknow"
        cover = "default_cover.png"
        tracknumber = 1
        lenght = 100
        
    return title, album, artist, cover, int(tracknumber), lenght


if __name__ == '__main__':
    library = get_library('/media/pi/USB3x16Go/music/flacs', '/home/pi/projets/simpleserver')
    print_library(library)
