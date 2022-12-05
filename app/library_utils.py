
import os
from pathlib import Path
import json
from collections import OrderedDict


def fichier_information(fichier, num, current_dir):
    """Informations sur un fichier"""

    song = mutagen.File(fichier)
    file_extension = str(type(song))

    # if file is FLAC, extract meta data
    if 'mutagen.flac.FLAC' in file_extension:

        try:
            tracknumber = song['TRACKNUMBER'][0]
        except KeyError:
            tracknumber = num

        try:
            title = str(song['TITLE'][0])
        except KeyError:
            title = 'unknown'

        try:
            album = str(song['ALBUM'][0])
        except KeyError:
            album = 'unknown'

        try:
            artist = str(song['ARTIST'][0])
        except KeyError:
            artist = 'unknown'

        try:
            lenght = str(song['LENGHT'][0])
        except KeyError:
            lenght = 60

        try:
            artwork = FLAC(fichier).pictures
            if artwork:
                if artwork[0].mime == 'image/jpeg':
                    cover = current_dir + '/covers/' + album + '.jpg'
                elif artwork[0].mime == 'image/png':
                    cover = current_dir + '/covers/' + album + '.png'
                p = Path(cover)
                if not p.is_file():
                    with open(cover, 'wb') as img:
                        img.write(artwork[0].data)
                        print(f"Save of cover: {cover}")
        except KeyError:
            cover = "covers/default_cover.png"

    else:
        title, album, artist, cover, tracknumber, lenght = ('unknown',
                                                            'unknown',
                                                            'unknown',
                                                            None,
                                                            0,
                                                            0)

    return title, album, artist, cover, int(tracknumber), lenght
