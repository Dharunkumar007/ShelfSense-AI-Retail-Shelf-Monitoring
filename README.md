# ShelfSense AI

Retail shelf monitoring with YOLO product detection, per-image availability charts, camera snapshots, restock tasks, reports, and an installable website/PWA.

**This README is the complete starting guide for a new computer.** Run commands from the project folder, which contains `requirements.txt`. The trained model at `models/best.pt` is included in GitHub. You do not need to download a dataset or retrain the model just to run the app.

## 1. Downloads and System Requirements

| Download or resource | Purpose |
| --- | --- |
| [Python, 64-bit](https://www.python.org/downloads/) | Runs the backend and AI model. Windows commands below use Python 3.11. The existing Ubuntu installation was verified with Python 3.10.12. |
| [Git](https://git-scm.com/downloads/) | Downloads the repository and lets you pull updates. Optional if using GitHub Download ZIP. |
| A current web browser | Opens the dashboard. Chrome or Edge can also offer PWA installation. |
| Internet during setup | Downloads Python dependencies. The interface also loads its icon library from a CDN. |
| A shelf image or camera | Provides input for detection. Sample images are included in the repository. |

Use Python 3.10-3.12 for this older pinned project runtime; newer versions have not been verified. Windows 3.11 setup is documented but has not been executed on a Windows machine. macOS setup has not been verified.

For a small demo, allow roughly **8 GB RAM and 15 GB free storage** as planning estimates, not measured minimums. CPU inference works without an NVIDIA GPU. Training and GPU packages need additional resources.

**Not required for normal use:** Node.js, npm, Android Studio, a separate SQLite server, a Kaggle account, the training dataset, or a CUDA installation. The app is a PWA, not a separate Android APK.

Dependencies are downloaded by pip, rather than installed individually:

| File | When to install | Main packages |
| --- | --- | --- |
| `requirements.txt` | Always, to run the app | FastAPI, Uvicorn, SQLAlchemy, psycopg, Pillow, Ultralytics, OpenCV |
| `requirements-training.txt` | Only when training a model | Ultralytics, OpenCV, pandas, Pillow, PyYAML, tqdm |
| `requirements-dev.txt` | Only for automated development tests | Runtime packages plus pytest, httpx, Playwright |

PyTorch and other dependencies are installed automatically or by the CPU-only command below. Transitive package versions are not fully locked; finish installation with `pip check` and a real scan.

## 2. Get the Project

### Option A: Clone GitHub

Run in PowerShell on Windows or Terminal on Ubuntu:

```bash
git clone --depth 1 https://github.com/Ronnirvin2006/ShelfSense-AI-Retail-Shelf-Monitoring.git dharun
cd dharun
```

`--depth 1` saves space by avoiding old Git history. Use a new folder; do not clone over your existing project.

### Option B: Import a ZIP or Copied Folder

Use GitHub **Code → Download ZIP**, extract it, and open a terminal inside the extracted folder containing `requirements.txt`. If copying from another computer, copy project files and the model, but recreate `.venv` on the new system. Virtual environments are not portable between computers or operating systems.

A ZIP does not include Git history, so `git pull` will not work there. A fresh clone or ZIP also does not contain your private accounts, saved layouts, or scan history. See the migration section if you need those records.

## 3. First-Time Ubuntu Setup

Install system prerequisites:

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip libgl1 libglib2.0-0
python3 --version
```

Check the Python version against the range above. Clone or extract the project using section 2, then run these commands from its root folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir --upgrade pip
.venv/bin/python -m pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m scripts.create_admin
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The CPU-only command avoids unnecessary CUDA packages. `--no-cache-dir` avoids keeping extra package downloads on disk.

## 4. First-Time Windows Setup

Install **64-bit Python 3.11** and Git for Windows from the download links above. Include the Python launcher during installation. Open a new **PowerShell** window, clone or extract the project, and enter its root folder.

```powershell
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir --upgrade pip
.\.venv\Scripts\python.exe -m pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.create_admin
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

These commands use the virtual environment directly. You do not need to activate it or change PowerShell's execution policy.

## 5. Create Your Account and Open the App

The `scripts.create_admin` command asks for a username, a password of at least **12 characters**, and password confirmation. Password typing is hidden. Create your administrator once; there is no shared default password. A fresh local database permits initial setup from localhost, but create an account before remote access.

With Uvicorn running, open:

```text
http://127.0.0.1:8000
```

Sign in with the account you created. Keep the server terminal open while using the application. To confirm the backend and model are available, visit:

```text
http://127.0.0.1:8000/api/health
```

For the default local installation, expect:

```json
{"status":"ok","model_available":true,"storage":"sqlite"}
```

## 6. Launch Again After Setup

Do not recreate the environment, reinstall everything, or create another administrator each time.

Ubuntu, from your project folder:

```bash
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell, from your project folder:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

On the original laptop, first run `cd /home/ron/dharun`. On another machine, use the location where you cloned or extracted the project.

Stop with **Ctrl+C** in the server terminal. For development only, add `--reload`. Run a single worker: inference coordination and login throttling are process-local.

If port 8000 is occupied, open the already-running app or use `--port 8001` and visit **http://127.0.0.1:8001**. Do not terminate unrelated applications to free the port.

## 7. First Shelf Inspection

1. Open **Inventory** as an administrator. Configure each zone's name, expected visible item count, stock thresholds, and image bounds. Bounds are percentages: left/top are 0, right/bottom are 100. Left must be less than right, top less than bottom, and the critical threshold must be lower than the low-stock threshold.
2. Select **Save layout**. The supplied layout is only an example; use zones appropriate for the shelf in your image. The current layout is shared across all camera sources.
3. Select **Choose image**, then choose a JPEG, PNG, or WebP file. Start with the included `test_1005.jpg` for a workflow check. The app accepts up to 12 MB and 24 megapixels; hosted services may impose a smaller upload limit.
4. Select **Run scan**. Overview shows visible items, missing quantities, shelf health, and zone availability calculated from that image.
5. Open **Monitor**. Hover, focus, or tap a product box to see the model's confidence percentage. Zones are off by default. The **Original / Detections** slider below the image controls how much of the detection overlay is visible; it does not rerun inference.
6. Use **Restock** to track work and **Reports** to open saved scans or export records.

The current inspection starts empty after reloading the page, even when history exists. Old records remain available through explicit selection in Recent scans or Reports. Changing the theme does not change scan results.

**Confidence is not stock percentage.** Product confidence is the model's detection score. Zone availability compares detected items with the configured expected count. The current SKU110K model detects generic shelf products; it does not recognize each brand or SKU. Product metadata in Inventory is a configured reference, not automatic brand identification.

## 8. What Each Section Does

| Section | How to use it |
| --- | --- |
| Overview | Review the selected scan's metrics, zone bars, priority tasks, and recent scans. |
| Monitor | Inspect product confidence, reveal the original image, toggle overlays, tune inference, and run camera snapshots. |
| Analysis | Filter zones by name/status and compare two saved scans. Different models, settings, or layouts can affect comparisons. |
| Restock | Filter by severity/assignee; acknowledge, assign, progress, or resolve tasks. Manual resolution requires a completion note. |
| Inventory | Edit expected counts, thresholds, product references, and zone boundaries; save the layout as an administrator. |
| Reports | Filter saved records, open scans, export CSV, or use Print / Save PDF. CSV export requires manager or admin access. |
| Admin | Inspect model status and configured cameras, and create administrator, manager, staff, or viewer accounts. |

Viewers cannot scan or modify records. Staff can scan and update restock tasks; staff assignment is limited to themselves or unassigned. Administrators manage accounts and layouts. The project is one shared workspace, not a multi-tenant service.

## 9. Camera Monitoring and Detection Tuning

For a laptop/webcam: open Monitor, select Browser camera, choose an interval, select Start, and allow camera permission. Select Stop to end capture. Camera access requires localhost or HTTPS. Leaving Monitor or hiding the browser tab also stops capture.

For an IP camera, configure an **HTTP JPEG snapshot URL**, not an RTSP stream. Set this environment variable before starting the server:

Ubuntu:

```bash
export SHELFSENSE_CAMERAS='{"aisle-1":"http://192.168.1.20/snapshot.jpg"}'
```

Windows PowerShell:

```powershell
$env:SHELFSENSE_CAMERAS='{"aisle-1":"http://192.168.1.20/snapshot.jpg"}'
```

Replace the example with your camera's actual endpoint. The backend must reach that network. Keep camera credentials private. Variables set this way apply to that terminal session; `.env` files are not automatically loaded by these launch commands.

Tuning controls apply to the **next scan**:

- Confidence is sent to YOLO as `conf` (default `0.25`); higher values reject more uncertain detections and can also miss products.
- IoU is sent as `iou` (default `0.70`) and controls suppression of overlapping boxes.
- Resolution is sent as `imgsz` (default `640`); larger inputs cost more processing time and memory.
- Detection limit is sent as `max_det` (default `500`) and caps the number of returned objects.
- Minimum box area is applied by backend post-processing as a percentage of the image area; excessive filtering removes distant products.
- Contrast enhancement applies OpenCV CLAHE before inference; evaluate it on your own images.

The controls are active, not sample UI. The browser validates and submits them with each upload or camera request, FastAPI validates the ranges, and the detector records the exact settings with the saved scan. The line beneath the controls shows the values that the next scan will use.

Do not assume higher settings give better accuracy. Compare counts against labelled images, select settings using validation data, and evaluate once on held-out test data. Live camera task updates require two matching observations within 120 seconds. See [Operations](docs/OPERATIONS.md) for evaluation commands.

## 10. Website and Phone App

The website and installed PWA use the same backend, accounts, and database. For mobile use, deploy through HTTPS, open that URL, and choose the browser's **Install app** or **Add to Home Screen** option where supported. The backend must remain running. Offline application files do not provide offline AI scanning.

For a trusted local-network preview, create the administrator first, then replace `--host 127.0.0.1` with `--host 0.0.0.0`. Open `http://LAPTOP_LAN_IP:8000` on another device on the same network and allow the port through your firewall only for that trusted network. `127.0.0.1` on a phone means the phone itself. Ordinary LAN HTTP generally does not provide browser camera/PWA capabilities; use HTTPS for those.

Vercel/hosted deployment needs persistent `DATABASE_URL` storage, suitable model/dependency capacity, and HTTPS settings. A GitHub push does not itself verify deployment. Follow [Deployment](docs/DEPLOYMENT.md) before publishing.

For a production HTTPS deployment, set these environment variables at the hosting provider:

```text
SHELFSENSE_ORIGIN=https://your-domain.example
FORCE_HTTPS=1
COOKIE_SECURE=1
DATABASE_URL=postgresql+psycopg://...
```

`SHELFSENSE_ORIGIN` is also used for sitemap URLs and origin checks. Never put passwords, database URLs, model-provider keys, or camera credentials in `static/`, browser JavaScript, Git, or a public `.env` file. The application contains no frontend API secret. Keep deployment secrets in the provider's encrypted environment settings.

## 11. Move Existing Data to Another Computer

Code and model weights come from GitHub. Private application data does not.

| Item | Transfer when |
| --- | --- |
| `models/best.pt` | You have custom weights newer than the repository model. |
| `shelfsense.db` | You want existing accounts, layouts, images, scans, and tasks. |
| `sample_data/planogram.json` | You customized the fallback layout without saving it through Inventory. |
| Environment configuration | You use PostgreSQL, IP cameras, or deployment-specific settings. Transfer securely, not through public GitHub. |

For SQLite, stop the old server before copying. Use SQLite's backup facility, or copy the database together with any remaining `shelfsense.db-wal` and `shelfsense.db-shm` files while the server remains stopped. Keep a separate backup. With the new server stopped, place the transferred database in the project root before launching. Migrated accounts keep their passwords; do not rerun first-admin setup unless creating an additional account.

Never copy `.venv` as a replacement for installing dependencies. Never publish databases, passwords, camera credentials, or private images to the public repository. PostgreSQL installations require a database backup/restore appropriate to the provider.

## 12. Update and Manage Storage

Stop the app, back up private data and local changes, then run from a Git checkout:

```bash
git status
git pull --ff-only
```

If Git reports local changes or conflicts, preserve and resolve them; do not discard your layout just to make the pull work. Run your platform's `pip install --no-cache-dir -r requirements.txt` command again, then launch. Reload the browser once; versioned assets prevent old CSS and JavaScript from mixing with the updated interface.

Do not delete the virtual environment, trained model, or database as routine cleanup. Preview retention using the virtual environment's Python:

```bash
.venv/bin/python -m scripts.prune_history --days 90
```

On Windows use `.\.venv\Scripts\python.exe` instead. Add `--apply` only after reviewing the preview and taking a backup. Scans referenced by tasks are preserved, and SQLite may reuse freed space without shrinking the file.

## 13. Optional Model Training and Testing

For training, install `requirements-training.txt`, download/extract SKU110K, prepare YOLO labels, train, and copy the resulting weights to `models/best.pt`. Follow the complete [friend-laptop training guide](docs/TRAINING_ON_FRIEND_LAPTOP.md). Dataset downloads are not part of ordinary app setup.

For GPU acceleration, use the official [PyTorch installation selector](https://pytorch.org/get-started/locally/) for your operating system and GPU instead of the CPU-only command. Do not download CUDA packages for a CPU-only machine.

Developer checks on Ubuntu:

```bash
.venv/bin/python -m pip install --no-cache-dir -r requirements-dev.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests -q
.venv/bin/python tests/browser_smoke.py
.venv/bin/python tests/browser_cache_upgrade.py
```

The browser scripts currently use Google Chrome at `/usr/bin/google-chrome`; they are Ubuntu-oriented and need an executable-path adjustment for another OS. They use temporary databases. The runtime app does not require these development tests or Playwright.

## 14. Troubleshooting

| Problem | What to do |
| --- | --- |
| `python`, `py`, or `git` not found | Install the tool, include Python's launcher/PATH option, and reopen the terminal. |
| `No module named ...` | Install requirements using the same `.venv` interpreter used to launch. |
| `No matching distribution found` | Check 64-bit Python version, network access, and the package named in the error. Do not randomly remove version pins. |
| `libGL.so.1` missing | Install `libgl1` on Ubuntu; the setup command includes it. |
| `Address already in use` | Open the existing app, stop your earlier server, or use port 8001. |
| `model_available: false` | Restore the real `models/best.pt`. Missing weights return an error; there is no mock fallback. |
| Administrator required | Run the admin creation command from the project root using its virtual environment. |
| No detected products | Check lighting, image quality, and confidence/area filters. High confidence can discard every box. |
| Wrong occupancy | Configure expected counts and zone bounds for the image. Generic detections are not a SKU inventory feed. |
| Slider disabled | Run a scan or explicitly open a saved one first. The slider is beneath the Monitor image. |
| Camera unavailable | Allow permission, use localhost/HTTPS, and close other applications using the device. |
| Old or misaligned interface | Reload once after updating. If an older deployment persists, verify the server is running this checkout, then hard-refresh. |
| ROS-related errors in `pip check` | Your shell may inject unrelated packages through `PYTHONPATH`. On Ubuntu, check the project alone with `env -u PYTHONPATH .venv/bin/python -m pip check`. |

## 15. Project Files and Delivery Status

```text
backend/                 API, detection, database, and account logic
static/                  Website, themes, logo, PWA, and policy pages
models/best.pt           Trained detection model
sample_data/planogram.json  Default shelf layout
scripts/                 Admin setup, training, evaluation, retention
tests/                   Backend and browser checks
docs/                    Deployment, training, operations, status
requirements.txt         Application dependencies
main.py                  Hosting entry point
```

The local workflows have automated coverage, including empty startup, theme colors, product hover, sliders, and cached-browser updates. Store-specific accuracy, physical IP cameras, Windows setup, hosted PostgreSQL/Vercel, and sustained production load still require target-system validation. Notification integrations, per-camera layouts, and multi-store isolation are not implemented.

Read [Implementation Status](docs/IMPLEMENTATION_STATUS.md) for the current scope. Project Terms and Privacy pages need operator-specific review before a commercial deployment.
