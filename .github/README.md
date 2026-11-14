# mc-recon-suite 

This README explains everything inside this repository.

---

## 1. What's inside this repository? (File-by-file map)

If you are new to Python programming, it is important to know that **you do not run every file directly**. Most files in a professional Python project are "helper modules." They store code for specific tasks to keep things organized. Out of all the files here, only **three specific files** are meant to be executed by you in the terminal.

### Files you actually run
1. **`src/mcrecon/__main__.py`** *(The main CLI entry point)*
   * **What it does:** This is the heart of the tool. When you type a command like `python3 -m mcrecon` in your terminal, Python looks for this exact file and executes it. It triggers `cli.py` to read the arguments you typed (like `--host`, `--mode`) and acts on them.
2. **`examples/run_recon.py`** *(The standalone demo script)*
   * **What it does:** A single, self-contained playground script. If you don't like typing long commands into the terminal, you can open this file in a text editor, type your server IP and password directly into the variables at the top, and run it to test three protocols at once.
3. **`tests/test_varint.py`** *(The automated self-test file)*
   * **What it does:** A diagnostic script. You run this to make sure your computer's Python installation is correctly packing and unpacking the raw network bytes before you ever try connecting to the internet.

### Files that run automatically behind the scenes (Do not run directly)
* **`src/mcrecon/__init__.py`**: A special empty file that tells Python "treat the `src/mcrecon/` folder as a package I can import code from." It also exposes the 4 main functions so they are easy to load.
* **`src/mcrecon/cli.py`**: The traffic cop. It reads the command-line flags (like `--host 127.0.0.1 --mode ping`), validates them, and routes the traffic to the correct protocol file below.
* **`src/mcrecon/utils/varint.py`**: Minecraft uses a special way to compress numbers over the network called a "VarInt". This file contains the complex math required to translate normal numbers into Minecraft bytes.
* **`src/mcrecon/protocols/ping.py`**: The raw networking code for **Mode 1 (Server list ping)**.
* **`src/mcrecon/protocols/query.py`**: The raw networking code for **Mode 2 (UDP GameSpy4 query)**.
* **`src/mcrecon/protocols/rcon.py`**: The raw networking code for **Mode 3 (RCON remote console)**.
* **`src/mcrecon/protocols/ghost.py`**: The raw networking code for **Mode 4 (Headless ghost client)**.

---

## 2. Step-by-step setup from scratch

### Step 1: Check your Python installation
Open your terminal (Terminal on macOS/Linux, Command Prompt or PowerShell on Windows, or an app like a-Shell on iPadOS). Verify you have **Python 3.8 or newer** installed by typing:

```bash
python3 --version
```
*(Note for Windows users: If `python3` gives you an error saying the command is not recognized, type `python --version` instead. If that works, replace `python3` with `python` in every command for the rest of this guide. If neither works, download Python from python.org).*

This project uses **only Python's built-in standard library**. That means you do **not** need to run `pip install`, download external packages, or set up virtual environments. It works right out of the box.

### Step 2: Download the repository to your device

**Option A — Using Git (Recommended):**
If you have Git installed, run this command to download the project and immediately move inside the new folder:
```bash
git clone [https://github.com/YOUR_USERNAME/mc-recon-suite.git](https://github.com/YOUR_USERNAME/mc-recon-suite.git)
cd mc-recon-suite
```

**Option B — Downloading the ZIP (No Git required):**
1. Click the green **Code** button at the top right of this GitHub page and click **Download ZIP**.
2. Unzip `mc-recon-suite-main.zip` on your computer.
3. Open your terminal and move into that extracted folder using the `cd` (change directory) command:
   ```bash
   cd path/to/mc-recon-suite-main
   ```

### Step 3: Verify you are in the correct folder (Crucial!)
**Every single command in this guide must be run from the main root folder (`mc-recon-suite/`)**. Do **not** `cd` inside `src/` or `protocols/`. If you run a command from the wrong folder, Python won't be able to find the code.

To double-check your current location, list the files in your terminal:
* **macOS / Linux / iPadOS:** Type `ls` and press Enter.
* **Windows:** Type `dir` and press Enter.

You **must** see `README.md`, `src`, `examples`, and `tests` in the output list. If you see them, you are in the exact right spot.

### Step 4: Tell Python where the `src` folder is
Because our code is neatly tucked away inside the `src/` subfolder, we have to set an "environment variable" to tell Python to look inside `src/` when searching for modules. Run the command below that matches your operating system:

* **macOS / Linux / iPadOS (Bash / Zsh / a-Shell):**
  ```bash
  export PYTHONPATH=src
  ```
* **Windows PowerShell:**
  ```powershell
  $env:PYTHONPATH="src"
  ```
* **Windows Command Prompt (CMD):**
  ```cmd
  set PYTHONPATH=src
  ```
*(Important note: Environment variables wipe out when you close the terminal. You must run this `PYTHONPATH` line once each time you open a brand-new terminal window).*

---

## 3. How to run the files (Step-by-step)

Ensure your terminal is still inside the main `mc-recon-suite/` root folder and you have set `PYTHONPATH=src` from Step 4.

### Run file 1: Automated self-test (`tests/test_varint.py`)
Before trying to scan an actual server, test that the core math logic works on your specific machine.

```bash
python3 tests/test_varint.py
```

**Expected output:**
```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.001s

OK
```
If you see `OK`, your computer is correctly processing binary data and you are ready to connect to servers!

---

### Run file 2: The main command-line tool (`src/mcrecon/__main__.py`)
By using the `-m` flag, you tell Python to run the `mcrecon` folder as a program. You control what the program does by changing the `--mode` flag at the end of the command.

#### 1. Run TCP server list ping (`ping` mode)
* **What it does:** Simulates a player opening the multiplayer menu. It grabs the MOTD (Message of the Day), the exact game version, the current player count, and a small sample of player names.
* **Server requirements:** Works on **any** public or local Minecraft Java server. No special admin settings are required.
* **Command:**
  ```bash
  python3 -m mcrecon --host 127.0.0.1 --port 25565 --mode ping
  ```
  *(Replace `127.0.0.1` with a real server IP, like `mc.hypixel.net`).*

#### 2. Run UDP GameSpy4 full query (`query` mode)
* **What it does:** Bypasses the 12-player sample limit of a normal ping. This UDP request forces the server to hand over a massive payload containing the server engine, every active plugin, the world map name, and an uncapped list of every single online player.
* **Server requirements:** The target server must explicitly have `enable-query=true` and `query.port=25565` set in its `server.properties` file. If this is off, the command will simply time out.
* **Command:**
  ```bash
  python3 -m mcrecon --host 127.0.0.1 --port 25565 --mode query
  ```

#### 3. Run TCP remote console (`rcon` mode)
* **What it does:** Opens an administrative tunnel to the server. You can execute raw server commands as if you were typing directly into the server host's console window.
* **Server requirements:** The target server must have `enable-rcon=true`, `rcon.port=25575`, and `rcon.password=...` configured in `server.properties`.
* **Command:**
  ```bash
  python3 -m mcrecon --host 127.0.0.1 --rcon-port 25575 --password "your_rcon_password" --cmd "list" --mode rcon
  ```
  *(You can swap `--cmd "list"` for any command the server recognizes, like `--cmd "tps"`, `--cmd "whitelist on"`, or `--cmd "say Hello world"`).*

#### 4. Run the offline headless ghost client (`ghost` mode)
* **What it does:** The ultimate scraper. This script actually logs into the server as a fake player, handles all the network compression, constantly replies to "Keep-Alive" checks so it isn't kicked, and streams every live chat message happening in the game directly to your terminal screen.
* **Server requirements:** Because this is a pure-Python script without Mojang encryption keys, the target server must be running in Offline Mode (`online-mode=false` in `server.properties`).
* **Command:**
  ```bash
  python3 -m mcrecon --host 127.0.0.1 --port 25565 --username "ReconBot" --duration 60 --mode ghost
  ```
  *(This keeps the bot connected for `60` seconds. You will see `[CHAT]` messages pop up in your terminal in real-time as players talk in-game).*

---

### Run file 3: The all-in-one example script (`examples/run_recon.py`)
If you are testing a server you own and are tired of typing out your password and IP address into the terminal every time, you can edit this file instead.

1. Open `examples/run_recon.py` in a text editor (like VS Code, Notepad, or TextEdit).
2. Look at lines 8–11 at the top of the file and change the dummy data to your server's details:
   ```python
   TARGET_HOST = "127.0.0.1"
   TARGET_PORT = 25565
   RCON_PORT = 25575
   RCON_PASSWORD = "your_actual_password"
   ```
3. Save the file. Ensure your terminal is in the root `mc-recon-suite/` folder with `PYTHONPATH=src` set, and run:
   ```bash
   python3 examples/run_recon.py
   ```
   This script will automatically run Ping, Query, and RCON consecutively and neatly format the output.

---

## 4. Command-line arguments reference table

When running `python3 -m mcrecon`, you can combine these flags to customize your recon scan:

| Flag | Required? | Default value | What it controls |
| :--- | :--- | :--- | :--- |
| `--host` | **Yes** | *(None)* | The IP address (e.g., `127.0.0.1`) or web domain of the target server. |
| `--mode` | **Yes** | *(None)* | Which protocol to execute: `ping`, `query`, `rcon`, or `ghost`. |
| `--port` | No | `25565` | The standard game port. Used for `ping`, `query`, and `ghost` modes. |
| `--rcon-port` | No | `25575` | The separate admin port. Used only when `--mode rcon` is selected. |
| `--password` | For `rcon` | `""` | The RCON password. It is strictly required to authenticate in `--mode rcon`. |
| `--cmd` | No | `list` | The console command sent in `--mode rcon`. Do not include the forward slash `/`. |
| `--username` | No | `GhostBot` | The player name the bot assigns itself when joining in `--mode ghost`. |
| `--duration` | No | `30` | How many seconds the Ghost bot stays connected and listens for chat before cleanly disconnecting. |

---

## 5. Troubleshooting common beginner errors

If something breaks, don't panic. Read the error message carefully—it usually tells you exactly what went wrong.

* **`ModuleNotFoundError: No module named 'mcrecon'`**
  * **Cause:** Python doesn't know where your code is. Either your terminal is not inside the main `mc-recon-suite/` root folder, or you skipped Step 4.
  * **Fix:** Run `cd` to navigate back to the `mc-recon-suite/` root folder. Then, run the `export PYTHONPATH=src` command (or the Windows equivalent) and try again.

* **`socket.timeout: timed out` (Specifically in `--mode query`)**
  * **Cause:** Almost all Minecraft servers have UDP Query turned off by default for security reasons. If you send a query packet to a server that has it disabled, the server just ignores it, causing your script to wait until it times out.
  * **Fix:** This is normal behavior for secured servers. Only use `--mode query` on servers where you know for a fact `enable-query=true` is set.

* **`ConnectionRefusedError: [Errno 61] Connection refused`**
  * **Cause:** There is no Minecraft server running at the IP and lport you typed, the server is still booting up, or a firewall is actively blocking your connection.
  * **Fix:** Double-check your spelling for the server IP and the `--port`. If scanning a remote server, ensure their hosting provider has opened the port.

* **`PermissionError: RCON Authentication Failed: Invalid RCON password.`**
  * **Cause:** You successfully reached the RCON port, but the password provided with `--password` does not match the `rcon.password` inside the target's `server.properties`.
  * **Fix:** Verify the password. Note that some older server versions require a full restart (not just a `/reload`) for new RCON passwords to apply.

