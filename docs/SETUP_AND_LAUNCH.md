# ShelfSense Setup and Launch

## What to Download

| Item | Needed for |
| --- | --- |
| [Python](https://www.python.org/downloads/) 64-bit | Backend and inference. Current local verification used Python 3.10.12 on Ubuntu; Windows commands below use Python 3.11 and have not been run on Windows. |
| [Git](https://git-scm.com/downloads/) | Clone and update the project. GitHub Download ZIP is an alternative. |
| A current browser | Website, image upload, and camera access. |
| Packages from `requirements.txt` | FastAPI, Uvicorn, SQLAlchemy, PostgreSQL driver, Pillow, Ultralytics, OpenCV, and their dependencies. Install using the commands below. |

No Node.js, npm, Android Studio, separate SQLite installation, or dataset is needed to run the existing app. `models/best.pt` is tracked in Git and comes with the project. The app is a PWA, not a separate Android APK.

For a small local demo, plan for at least 8 GB RAM and roughly 15 GB free disk space as a working allowance, not a measured minimum. Training, CUDA packages, and large datasets need more. CPU inference works without an NVIDIA GPU. Internet is needed for initial installation; the interface also loads its icon library from a CDN.

## Your Existing Ubuntu Laptop

No reinstall is needed for each launch:

```bash
cd /home/ron/dharun
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Keep the terminal running. Press **Ctrl+C** in that terminal to stop. Add `--reload` only when developing.

If the site is already running, open it instead of starting a second instance. For `Address already in use`, stop your existing ShelfSense server or use `--port 8001` and open http://127.0.0.1:8001. Do not stop unrelated applications to free the port.

## Fresh Ubuntu System

Use a Python 3.10-3.12 environment for this project's older pinned runtime; newer Python versions have not been verified. The commands below use the distribution's `python3`, so check its version first. The existing installation was tested on 3.10.12.

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip libgl1 libglib2.0-0
python3 --version
git clone --depth 1 https://github.com/Ronnirvin2006/ShelfSense-AI-Retail-Shelf-Monitoring.git dharun
cd dharun
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir --upgrade pip
.venv/bin/python -m pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m scripts.create_admin
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The admin script asks for a username and a password of at least 12 characters. Password typing is hidden. Create the account once, then sign in through the website. Run commands from the project root, where `requirements.txt` lives.

## Fresh Windows System

Install 64-bit Python 3.11 from the Python download page and Git for Windows. Include the Python launcher when installing. Open a new PowerShell window afterward. These commands use the environment's interpreter directly; activation and PowerShell execution-policy changes are unnecessary.

```powershell
py -3.11 --version
git clone --depth 1 https://github.com/Ronnirvin2006/ShelfSense-AI-Retail-Shelf-Monitoring.git dharun
cd dharun
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir --upgrade pip
.\.venv\Scripts\python.exe -m pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.create_admin
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** and sign in. On later launches, run only `cd` to this folder and the final Uvicorn command. A fresh Windows installation still needs verification on that machine.

## If You Downloaded ZIP or Copied the Folder

Extract the ZIP, enter the folder containing `requirements.txt`, and follow the relevant setup block starting at virtual-environment creation. Skip `git clone` and `cd dharun` if already in that folder. Do not copy `.venv` between computers or operating systems; recreate it. A ZIP download does not contain Git history, so `git pull` will not work there.

## Check and Use the App

1. Visit http://127.0.0.1:8000/api/health. Expect `status: ok` and `model_available: true`.
2. Sign in. Open Inventory and configure shelf zones, expected counts, and thresholds for your image. The default layout is only a starting point.
3. Choose a shelf image, such as the included `test_1005.jpg`, then select Run scan.
4. Overview and Analysis show that scan's counts and zone availability. Monitor contains inference tuning, overlays, and camera controls.
5. Use Restock for assignments and Reports for saved history and export.

The SKU110K model detects generic shelf items, not individual brands. Tuning does not guarantee correct counts; check results against labelled images. The current inventory layout is shared across camera sources.

## Phone and Installed App

For a shared website/PWA, deploy with HTTPS and open that URL on the phone. Use the browser's Install or Add to Home Screen option where available. Website and PWA share the backend and database. `127.0.0.1` on a phone refers to the phone, not your laptop.

For a trusted local-network preview, create the administrator first and launch with `--host 0.0.0.0`. Open `http://LAPTOP_LAN_IP:8000` on a device on the same network; allow only trusted network access through your firewall. Plain LAN HTTP normally cannot use the browser camera and is not the production configuration. Use HTTPS for camera/PWA deployment; see [Deployment](DEPLOYMENT.md).

## Storage and Updates

SQLite creates `shelfsense.db` automatically. It stores accounts, saved layouts, scans, image evidence, and tasks. A fresh Git clone starts with no user accounts or saved scans. To migrate existing records, stop the server and use SQLite's backup facility or copy the database together with any remaining `shelfsense.db-wal` and `shelfsense.db-shm` files while it remains stopped. Treat the database as private data and do not commit it.

`sample_data/planogram.json` is the fallback layout. Layouts saved through Inventory are in the database. Back up local layout edits before updating; do not discard them to resolve a Git conflict.

For a Git checkout, stop the server and update from the project root:

```bash
git status
git pull --ff-only
```

Resolve or save your own changes if Git reports a conflict. Re-run your operating system's `pip install --no-cache-dir -r requirements.txt` command, then launch again. `--depth 1` avoids downloading old repository history, and `--no-cache-dir` avoids retaining package downloads. Do not delete `.venv`, model weights, or the database as routine cleanup.

## Optional Training and GPU

Only download the SKU110K dataset and install `requirements-training.txt` when retraining. Follow [Training on a Friend's Laptop](TRAINING_ON_FRIEND_LAPTOP.md). For NVIDIA acceleration, use the command from the official [PyTorch installer selector](https://pytorch.org/get-started/locally/) matching your OS and supported CUDA runtime instead of the CPU-only install above. Do not install CUDA packages just to view the website.

## Troubleshooting

| Message | Action |
| --- | --- |
| `No module named ...` | Install `requirements.txt` using the same `.venv` Python used to launch. |
| `No matching distribution found` | Check Python version, 64-bit architecture, internet access, and the package named in the error. Do not randomly remove version pins. |
| `libGL.so.1` missing on Ubuntu | Install `libgl1`; the Ubuntu setup block includes it. |
| `model_available: false` | Confirm `models/best.pt` exists in the project. Restore the repository model or your own trained weights. |
| Administrator required | Run `python -m scripts.create_admin` using the project's virtual environment. |
| Camera unavailable | Allow browser camera permission, use HTTPS or localhost, and close other applications using the camera. |
| No detections | Check the image and confidence threshold; a high confidence threshold can discard all detections. |
| Old interface after updating | Hard-refresh the browser. If needed, unregister the old service worker in browser developer tools and reload. |

Runtime dependencies are installed through `requirements.txt`. `requirements-dev.txt` is only for development tests. No fresh environment is fully locked: transitive packages such as PyTorch are resolved during installation, so check `pip check` and perform a real scan after setup.
