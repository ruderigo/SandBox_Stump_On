# Arborist

Fait d'une Freenove ESP32-S3-CAM un Stump, en met un à jour, change ses
réglages et le regarde démarrer : une seule page, sans internet et sans
rien à installer.

- `Arborist-<version>.html` — enregistrez-la sur un ordinateur, puis
  ouvrez le fichier enregistré dans Chrome ou Edge (ouverte depuis
  l'adresse de ce Stump, elle ne peut pas atteindre l'USB : les
  navigateurs ne le permettent que depuis un fichier enregistré ou une
  page sécurisée). Branchez la CAM en USB et suivez la page.

Elle contient MicroPython 1.28 (MIT) et la version de ce Stump, et
vérifie chaque fichier qu'elle écrit sur la carte. Fichiers et sommes de
contrôle : https://github.com/ruderigo/SandBox_Stump_On/releases
