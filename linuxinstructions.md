# WalkSafe Linux Host Setup

This guide is for moving the local WalkSafe stack to a fresh Pop!_OS machine and running it reliably with Linux tools.

What this guide covers:
- Git + repo clone
- Secrets and local-only files you must copy manually
- Docker + Docker Compose plugin
- Valhalla via the repo's `backend/docker-compose.yml`
- ngrok on Linux
- tmux
- Flutter on Linux
- Basic troubleshooting

Important note:
- `tmux` keeps terminal sessions alive if you close the terminal or disconnect from SSH.
- `tmux` does **not** keep services running when the machine actually suspends.
- If you want the host to stay available, keep the Pop!_OS machine awake while plugged in.

## 1. Secret and local-only files to copy manually

These files are **not** in Git and must be recreated or copied from your current machine:

### Required
- `backend/.env`
  - This is the most important one.
  - It contains `DATABASE_URL`, Supabase keys, `ADMIN_API_KEY`, `VALHALLA_BASE_URL`, and other backend config.

### Needed if you want to build/run the Flutter app from Linux
- `mobile/.env.local`
  - This contains your local `API_BASE_URL`.

### Optional but useful
- `~/.config/ngrok/ngrok.yml`
  - Only if you already configured ngrok and want to reuse the same authtoken/config.
  - If you do not copy this, just run `ngrok config add-authtoken ...` again on Linux.

### Optional and not secret, but can save time
- `backend/valhalla_tiles/`
  - This directory is generated locally and is not committed.
  - If you copy it from the old machine, Valhalla may start much faster.
  - If you do not copy it, Docker will build/download what it needs on first run.

## 2. Base packages on Pop!_OS

Open a terminal and run:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y \
  ca-certificates \
  curl \
  git \
  gnupg \
  lsb-release \
  software-properties-common \
  tmux \
  unzip \
  wget \
  xz-utils \
  zip \
  libglu1-mesa
```

If you plan to run Flutter on Linux desktop too, also install:

```bash
sudo apt install -y \
  clang \
  cmake \
  ninja-build \
  pkg-config \
  libgtk-3-dev \
  libstdc++-12-dev
```

## 3. Clone the repo

If you already use SSH with GitHub on this Linux machine:

```bash
cd ~
git clone git@github.com:TheGoodDevil00/cdxwalksafe.git
cd cdxwalksafe
```

If SSH is not set up yet, clone over HTTPS instead:

```bash
cd ~
git clone https://github.com/TheGoodDevil00/cdxwalksafe.git
cd cdxwalksafe
```

## 4. Restore the manual files

Copy these from your current working machine to the Linux host:

```text
backend/.env
mobile/.env.local            (only if building/running Flutter on Linux)
~/.config/ngrok/ngrok.yml    (optional)
backend/valhalla_tiles/      (optional, speeds up Valhalla)
```

After copying, verify the important backend file exists:

```bash
ls -la backend/.env
```

## 5. Install Docker Engine and Docker Compose plugin

On Pop!_OS, the Ubuntu Docker instructions usually work well.

Remove conflicting packages if they exist:

```bash
sudo apt remove -y docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc
```

Add Docker's official apt repository:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

Install Docker:

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Verify Docker:

```bash
sudo systemctl enable --now docker
sudo docker run hello-world
docker compose version
```

Optional: run Docker without `sudo`:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
docker ps
```

## 6. Start Valhalla from the repo

The repo already contains a Docker Compose file at `backend/docker-compose.yml`.

Start Valhalla:

```bash
cd ~/cdxwalksafe/backend
docker compose up -d valhalla
```

Check logs:

```bash
docker compose logs -f valhalla
```

Verify it responds:

```bash
curl http://localhost:8002/status
```

Notes:
- On first boot, Valhalla can take a while to download/build data.
- The tiles are stored in `backend/valhalla_tiles/`.

## 7. Install Python backend dependencies

The backend uses a local virtual environment.

Install Python tools:

```bash
sudo apt install -y python3 python3-pip python3-venv
```

Set up the backend venv:

```bash
cd ~/cdxwalksafe/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Sanity check:

```bash
python -c "from app.main import app; print('Import OK')"
```

## 8. Run the backend locally

Make sure `backend/.env` contains a working Linux-appropriate `VALHALLA_BASE_URL`.

For the same host machine, this is typically correct:

```text
VALHALLA_BASE_URL=http://localhost:8002
```

Start the backend:

```bash
cd ~/cdxwalksafe/backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/
```

Expected response:

```json
{"message":"WalkSafe API is running","status":"online"}
```

## 9. Install ngrok on Linux

Download the latest Linux ngrok archive from the official download page:

```text
https://download.ngrok.com/linux
```

Then install it:

```bash
cd ~/Downloads
tar -xzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/ngrok
ngrok version
```

If you did **not** copy `~/.config/ngrok/ngrok.yml`, add your authtoken:

```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

Run a tunnel to the backend:

```bash
ngrok http 8000
```

If you use a reserved/static ngrok domain:

```bash
ngrok http 8000 --url https://YOUR-NGROK-DOMAIN.ngrok-free.app
```

Verify from the public URL:

```bash
curl -H "ngrok-skip-browser-warning: true" https://YOUR-NGROK-DOMAIN.ngrok-free.app/
```

## 10. Use tmux for long-running sessions

Create a tmux session:

```bash
tmux new -s walksafe
```

Suggested windows:
- window 1: backend
- window 2: Valhalla logs
- window 3: ngrok

Useful tmux keys:
- `Ctrl+b c` new window
- `Ctrl+b n` next window
- `Ctrl+b p` previous window
- `Ctrl+b d` detach

Reattach later:

```bash
tmux attach -t walksafe
```

Remember:
- tmux survives terminal close
- tmux does **not** survive machine suspend as an availability solution

## 11. Keep Pop!_OS awake while hosting

If this machine is acting like a local server:

### GUI settings
- Open **Settings -> Power**
- Set automatic suspend to **Off** while plugged in

### Lid-close behavior
If you want to keep services running with the lid closed, you must stop the machine from suspending on lid close.

Edit:

```bash
sudo nano /etc/systemd/logind.conf
```

Set:

```ini
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleSuspendKey=ignore
```

Then restart logind:

```bash
sudo systemctl restart systemd-logind
```

Do this only if you understand the tradeoff:
- the machine will stay awake and consume power/heat when closed

## 12. Install Flutter on Linux

If you want Flutter on this Linux machine:

Download and extract the stable SDK:

```bash
mkdir -p ~/develop
cd ~/develop
```

Download the current Linux stable archive from the Flutter SDK archive, then extract it. Example shape:

```bash
tar -xf ~/Downloads/flutter_linux_*.tar.xz -C ~/develop/
```

Add Flutter to your shell path:

```bash
echo 'export PATH="$HOME/develop/flutter/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verify:

```bash
flutter doctor -v
flutter devices
```

If Linux desktop tooling is missing:

```bash
sudo apt install -y clang cmake ninja-build pkg-config libgtk-3-dev libstdc++-12-dev
flutter doctor -v
```

## 13. Optional: run the mobile app from Linux

If you also copied `mobile/.env.local`:

```bash
cd ~/cdxwalksafe/mobile
flutter pub get
flutter analyze lib/
flutter test
```

To run on Linux desktop:

```bash
flutter run -d linux
```

To build Android from Linux later, you will also need:
- Android Studio or Android SDK command-line tools
- Java
- an accepted Android SDK license set

This guide does not fully cover Android SDK setup.

## 14. Recommended local hosting workflow

For a stable Linux-hosted demo:

1. Keep the host plugged in.
2. Disable suspend while plugged in.
3. Start Valhalla:

```bash
cd ~/cdxwalksafe/backend
docker compose up -d valhalla
```

4. Start backend:

```bash
cd ~/cdxwalksafe/backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. Start ngrok:

```bash
ngrok http 8000 --url https://YOUR-NGROK-DOMAIN.ngrok-free.app
```

6. Rebuild the mobile app with:

```text
API_BASE_URL=https://YOUR-NGROK-DOMAIN.ngrok-free.app
```

## 15. Troubleshooting

### Docker permission denied

Symptom:
- `permission denied while trying to connect to the Docker daemon socket`

Fix:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
docker ps
```

### Docker Compose command not found

Use:

```bash
docker compose version
```

Not:

```bash
docker-compose version
```

### Valhalla won't start

Check logs:

```bash
cd ~/cdxwalksafe/backend
docker compose logs -f valhalla
```

Common causes:
- first tile build still running
- low disk space
- old or partially copied `backend/valhalla_tiles/`

If the local tiles are broken and you want a rebuild:

```bash
cd ~/cdxwalksafe/backend
docker compose down
rm -rf valhalla_tiles
docker compose up -d valhalla
```

### Backend import fails because env vars are missing

Make sure `backend/.env` exists:

```bash
ls -la ~/cdxwalksafe/backend/.env
```

Check for the important variables:
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `ADMIN_API_KEY`
- `VALHALLA_BASE_URL`

### Route requests fail but `/` works

That usually means the backend is up but Valhalla is not reachable.

Check:

```bash
curl http://localhost:8002/status
```

Then confirm `backend/.env` contains:

```text
VALHALLA_BASE_URL=http://localhost:8002
```

### ngrok says auth token missing

Run:

```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

### ngrok tunnel works, but mobile app still hits the wrong backend

Check the mobile-side API base URL in the file you copied manually:

```text
mobile/.env.local
```

Or, if building with `--dart-define`, make sure you rebuilt using the current ngrok URL.

### Machine goes offline when lid closes

That means Pop!_OS is suspending.

Fix:
- turn off suspend in Settings -> Power
- adjust `/etc/systemd/logind.conf`
- keep the machine on AC power

### Flutter doctor shows Linux toolchain issues

Run:

```bash
sudo apt update
sudo apt install -y clang cmake ninja-build pkg-config libgtk-3-dev libstdc++-12-dev
flutter doctor -v
```

### Git clone over SSH fails

Either:
- set up your GitHub SSH key on Linux

or:

- clone with HTTPS instead

```bash
git clone https://github.com/TheGoodDevil00/cdxwalksafe.git
```

## 16. Useful validation checklist

Run these after setup:

```bash
cd ~/cdxwalksafe/backend
docker compose ps
curl http://localhost:8002/status
source .venv/bin/activate
python -c "from app.main import app; print('Import OK')"
curl http://localhost:8000/
ngrok version
tmux -V
```

If Flutter was installed:

```bash
flutter doctor -v
flutter devices
```

## 17. Suggested long-term improvement

If this Linux machine becomes your main demo host, move from `tmux` to `systemd` services for:
- backend
- ngrok
- optional health-check scripts

That will be more reliable than manual terminal sessions and easier to recover after reboot.
