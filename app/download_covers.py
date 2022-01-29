
from urllib.request import Request, urlopen, urlretrieve
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import iterparse


lines = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>Directory listing for /</title>
</head>
<body>
<h1>Directory listing for /</h1>
<hr>
<ul>
<li><a href="All%20The%20Way%20West.jpg">All The Way West.jpg</a></li>
<li><a href="Ba%20Power.jpg">Ba Power.jpg</a></li>
<li><a href="default_cover.png">default_cover.png</a></li>
<li><a href="Falaw.jpg">Falaw.jpg</a></li>
<li><a href="In%20Movement.jpg">In Movement.jpg</a></li>
<li><a href="Samba.jpg">Samba.jpg</a></li>
</ul>
<hr>
</body>
</html>
"""


class DownloadFiles:
    """Tout est fait avec
    from urllib.request import Request, urlopen, urlretrieve
    import xml.etree.ElementTree as ET
    """

    def __init__(self, url, root, covers_list):
        self.url = url
        self.root = root
        self.covers_list = [x.split('/')[-1] for x in covers_list]
        print(f"Nom des Covers existantes: {self.covers_list}")

    def download_url(self):
        req = Request(self.url)
        resp = urlopen(req, timeout=1).read()
        text = resp.decode('utf-8')
        return text

    def clean_text(self, text):
        """xml veut que toutes les balises soient fermées"""
        lines = text.splitlines()
        text_clean = ""
        for line in lines:
            if '<meta' not in line and '<hr>' not in line:
                text_clean += line + '\n'
        return text_clean

    def get_missing_covers(self, text):
        # # print(text)
        text = self.clean_text(text)
        root = ET.fromstring(text)

        for li in root.iter('li'):
            # # print(li)
            a = li.findall('a')
            # # print(a)
            for b in a:
                # # print(b)
                file_name = b.text
                self.save_img(file_name)

    def save_img(self, file_name):
        if file_name not in self.covers_list:
            file_url = self.url + file_name
            file_url = file_url.replace(" ", "%20")

            # Uniquement si pas dans le dossiers covers
            fichier = self.root + '/' + file_name
            urlretrieve(file_url, fichier)
            print("Enregistrement de", fichier)



if __name__ == '__main__':
    covers_list = ['/media/data/3D/projets/player/app/covers/default_cover.png']
    df = DownloadFiles('http://192.168.0.108:8080/',
                       '/media/data/3D/projets/player/app/covers',
                       covers_list)
    text = df.download_url()
    df.get_missing_covers(text)