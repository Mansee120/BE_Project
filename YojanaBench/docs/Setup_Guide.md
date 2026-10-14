# YojanaBench — Setup Guide (Step by Step, Very Simple)

Follow these steps in order. If you get stuck, jump to the **Troubleshooting**
section at the end. Total time: about 10–15 minutes.

> This project runs **100% on your own laptop**. No database, no sign-up, no API
> keys, no paid services. You only need **Python** and a few **libraries**.

---

## Part 0 — What you need before starting (Requirements)

Please make sure your laptop has:

- **A computer** running Windows, macOS, or Linux.
- **Python version 3.10 or newer** (3.10, 3.11, 3.12 all work). We will check this
  in Step 1.
- **pip** — the tool that installs Python libraries. It comes automatically with
  Python, so you usually get it for free.
- **A text editor** — we recommend **VS Code** (free): <https://code.visualstudio.com>
- **About 500 MB** of free disk space.
- **Internet access for the first setup only** (to download the libraries). After
  that, the project runs offline.
- Optional: **Git** (only if you want to download the project with a `git clone`
  command instead of copying the folder).

You do **not** need:
- A database (data is stored in simple text/JSON files).
- Any AI account or API key.
- Docker or any cloud service.

---

## Part 1 — The libraries we need (what `requirements.txt` means)

The file **`requirements.txt`** in the project folder lists the libraries. Here is
what each one does, in simple words:

- **fastapi** — the web framework that runs the backend (the "engine room").
- **uvicorn** — the small server that actually starts FastAPI and listens for
  requests.
- **requests** — a helper for making web requests (used by a few background tasks).
- **pydantic** — checks and cleans the data that comes in and goes out.
- **deep_translator** — translates text for the multilingual voice assistant.
  *Optional* — the app still works in English without it.
- **pytest** — runs the automatic tests. *Optional* (only for testing).
- **httpx** — a helper that the tests use to call the API. *Optional* (only for
  testing).

So there are **4 must-have** libraries and **3 optional** ones. Installing all of
them is easiest, and that is exactly what one command does (Step 5).

---

## Part 2 — Step-by-Step Setup

### Step 1 — Install Python (if you don't have it)

**Check first.** Open a terminal and type:

```powershell
python --version
```

- If you see something like `Python 3.10.9`, you are ready — go to Step 2.
- If you see an error like *"python is not recognized"*, install Python:
  - Go to <https://www.python.org/downloads/> and download Python 3.10 or newer.
  - **Windows important:** on the installer's first screen, tick the checkbox
    **"Add Python to PATH"** before clicking Install. This is the most common
    mistake.
  - **macOS:** download the installer and run it. Or, if you use Homebrew:
    `brew install python`.
  - Close and reopen the terminal, then run `python --version` again.

### Step 2 — Get the project files

**Option A (simplest): copy or unzip.**
Copy the whole `YojanaBench` folder to your laptop, for example to
`C:\Users\YourName\YojanaBench` (Windows) or `~/YojanaBench` (Mac/Linux).

**Option B (if you have Git):**

```powershell
git clone <repository-url>
```

Either way, you should now have a folder named `YojanaBench`.

### Step 3 — Open a terminal inside the project folder

You must run the next commands **from inside the YojanaBench folder**.

- **Windows:** open the `YojanaBench` folder in File Explorer, click the address
  bar, type `powershell`, and press Enter. A terminal opens already inside the
  folder.
- **VS Code:** open the folder in VS Code, then use the menu
  **Terminal → New Terminal**. It starts inside the folder.
- **macOS/Linux:** open Terminal and type `cd` followed by the folder path, for
  example `cd ~/YojanaBench`.

**Check you are in the right place** by listing the files:

```powershell
dir        # Windows (PowerShell)
ls         # macOS / Linux
```

You should see `backend`, `frontend`, `data`, `run.py`, `requirements.txt`, etc.

### Step 4 — (Recommended) Create a private workspace ("virtual environment")

A **virtual environment** keeps this project's libraries separate from the rest of
your computer. It is optional but strongly recommended.

Create it (once):

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1     # Windows (PowerShell)
source .venv/bin/activate        # macOS / Linux
```

When it is active you will see `(.venv)` at the start of every terminal line.

> If Windows blocks activation with a message about *"running scripts is
> disabled"*, run this once, then try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Step 5 — Install the libraries (the main "import" step)

This single command reads `requirements.txt` and installs everything:

```powershell
pip install -r requirements.txt
```

What this means: **pip** = Python's installer; **install** = download and set up;
**-r requirements.txt** = "read the list of libraries from this file".

> If `pip` is not recognized, try `python -m pip install -r requirements.txt`.
> If it fails on Windows, close and reopen the terminal first.

To install **only the must-have libraries** (a lighter option), you can instead run:

```powershell
pip install fastapi uvicorn requests pydantic
```

### Step 6 — Verify that everything installed correctly

List the installed libraries:

```powershell
pip list
```

You should see `fastapi`, `uvicorn`, `pydantic`, and `requests` in the list.

You can also do a quick import test:

```powershell
python -c "import fastapi, uvicorn, pydantic, requests; print('All good!')"
```

If you see `All good!`, the setup is complete.

### Step 7 — Start the project

Run the one launcher command:

```powershell
python run.py
```

You should see a banner, then a line like
`Uvicorn running on http://127.0.0.1:8000`. The launcher also tries to open your
browser automatically. **Leave this terminal open** — it is the running server.
Press **Ctrl + C** in the terminal to stop it later.

### Step 8 — Open it in the browser

If the browser did not open by itself, go to:

- **Dashboard (login first):** <http://127.0.0.1:8000>
- **Grievance & Money-Trace portal:** <http://127.0.0.1:8000/grievance>
- **API documentation:** <http://127.0.0.1:8000/docs>

On the dashboard you will see a **login screen first**. Use these demo accounts:

- Officer: **`officer / officer123`** (or `admin / admin123`)
- Citizen whose money was stolen: **`geeta / geeta123`**
- Citizen whose money arrived correctly: **`ravi / ravi123`**

### Step 9 — (Optional) Run the automatic tests

This proves the code is working on your machine:

```powershell
python -m pytest -q
```

You should see a line like `103 passed`. This is optional but a good confidence
check.

---

## Part 3 — Daily use (after the first setup)

Once installed, starting the project each day is just three lines:

```powershell
.\.venv\Scripts\Activate.ps1     # activate the workspace (Windows)
python run.py                    # start the server
# then open http://127.0.0.1:8000 in your browser
```

(On macOS/Linux use `source .venv/bin/activate`.)

---

## Part 4 — Troubleshooting (common problems)

**1. `python is not recognized` / `pip is not recognized`**
Python is not installed, or was installed without "Add to PATH". Reinstall Python
and tick **"Add Python to PATH"**. Then reopen the terminal. Try `python -m pip`
instead of plain `pip`.

**2. `ModuleNotFoundError: No module named 'fastapi'` (or similar)**
The libraries are not installed, or your virtual environment is not active. Activate
it (Step 4) and run `pip install -r requirements.txt` again.

**3. Running scripts is disabled on Windows (cannot activate `.venv`)**
Run this once, then retry activation:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**4. `[Errno 98] Address already in use` or the page shows old content**
Another server is already using port 8000 (maybe an old run). Close the old
terminal, or find and stop the process, then run `python run.py` again. On Windows:

```powershell
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

**5. The page looks outdated / a change is not showing**
The browser cached the old page. Do a **hard refresh** with **Ctrl + F5**
(Windows) or **Cmd + Shift + R** (Mac).

**6. The dashboard loads directly without asking to log in**
You were already signed in (the session is remembered). Click **Sign out** in the
top-right, or clear the site data, and the login screen will appear.

**7. The voice assistant does not speak**
It is optional. The app works fine without it. Make sure you are using a modern
browser (Chrome/Edge) and allow sound.

**8. Something else is broken**
Re-run the tests (`python -m pytest -q`) and read the first error message — it
usually names the exact missing piece.

---

## Part 5 — Uninstall / clean up

To remove the project's libraries, just delete the `.venv` folder inside the
project (if you created one). To remove the project, delete the whole `YojanaBench`
folder. Nothing else on your computer is changed.

---

## Part 6 — Quick reference card (one screen)

```powershell
# 1. go into the project folder
cd C:\Users\YourName\YojanaBench

# 2. create + activate a workspace (first time only)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. install the libraries (first time only)
pip install -r requirements.txt

# 4. run the project
python run.py

# 5. open in the browser
#    http://127.0.0.1:8000          (dashboard - login first)
#    http://127.0.0.1:8000/grievance (money-trace portal)
```

Demo logins: `officer / officer123`, `geeta / geeta123`, `ravi / ravi123`.
