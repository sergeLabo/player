
import os
import json
from pathlib import Path

def create_json_file(library_file):
    print(f"Création de {library_file} si inexistant")
    a = os.path.exists(library_file)
    if not os.path.exists(library_file):
        with open(library_file, 'w') as outfile:
            data = {}
            json.dump(data, outfile)
        print(f"Création de {library_file}")


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
