# Installer Nephtali sur Windows

1. Installe Python 3.11 ou plus recent depuis python.org en activant l'option `Add Python to PATH`.
2. Double-clique sur `install_nephtali.bat`.
3. Une fois l'installation terminee, double-clique sur `run_app.bat`.
4. Le navigateur s'ouvre sur `http://127.0.0.1:5000`.

Pour arreter l'application, ferme la fenetre du terminal qui execute Flask.

## Publication en ligne

Le fichier `render.yaml` permet de deployer l'application sur Render avec `gunicorn app:app`.
