
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
