# Hоw to Setup Telegram Bot for VacationManager

This guide describes how to configure and run the Telegram Bot and Mini App for the VacationManager project.

## 1. Create a Telegram Bot

1.  Open Telegram and search for **@BotFather**.
2.  Send the command `/newbot`.
3.  Follow the instructions to choose a name and username for your bot.
4.  **Important:** Copy the **HTTP API Token** provided by BotFather. You will need this for the `.env` file.

## 2. Configure the Project

1.  Open the `.env` file in the project root (or create one using `.env.example` as a template).
2.  Add or update the following variables:

```ini
# Enable the Telegram functionality
VM_TELEGRAM_ENABLED=True

# Your Bot Token from BotFather
VM_TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# URL for the Mini App
# For local development, this is your frontend URL.
# Note: To test on a real device, you will need a tunnel (like ngrok) to expose localhost.
VM_TELEGRAM_MINI_APP_URL=http://localhost:5174
```

## 3. Configure Mini App Menu Button (Optional)

To make it easy to open the Mini App, you can configure the "Menu" button in your bot:

1.  Go to **@BotFather**.
2.  Send `/mybots` and select your bot.
3.  Go to **Bot Settings** > **Menu Button** > **Configure Menu Button**.
4.  Send the URL of your Mini App (e.g., your ngrok URL or hosted URL).
5.  Give the button a title (e.g., "Vacation Manager").

## 4. Running the Application

### Backend

Ensure the backend is running to handle API requests.

```bash
# From the root directory
python -m uvicorn backend.main:app --reload
```

### Frontend (Mini App)

Ensure the frontend is running (default port is 5174).

```bash
# From the telegram-mini-app directory (or root if configured)
cd telegram-mini-app
npm run dev
```

## 5. Local Development & Tunneling (Extensive Guide)

Telegram requires **HTTPS** for both Webhooks and Mini Apps. Since `localhost` (or local IP `172.x.x.x`) is not accessible from the public internet (where Telegram servers are), you must use a tunneling service. **ngrok** is the recommended tool.

### Step 1: Install ngrok

1.  **Sign up** for a free account at [ngrok.com](https://ngrok.com).
2.  **Download** the ngrok agent for your OS.
    *   *Windows*: Extract the zip file and place `ngrok.exe` in a folder (e.g., `C:\ngrok`) and add it to your System PATH, or install via Chocolatey: `choco install ngrok`.
3.  **Authenticate** your client:
    ```bash
    ngrok config add-authtoken <YOUR_AUTH_TOKEN>
    ```
    (You can copy this command from your ngrok dashboard).

### Step 2: Setup a Static Domain (Recommended)

Free ngrok accounts now include **one free static domain**. This is crucial so you don't have to reconfigure your Telegram Bot and `.env` file every time you restart ngrok.

1.  Go to the [ngrok Dashboard](https://dashboard.ngrok.com/cloud-edge/domains).
2.  Claim your free static domain (e.g., `guppy-active-randomly.ngrok-free.app`).

### Step 3: Start the Tunnel

You usually need to tunnel the **Mini App** (Frontend). Even if you run the bot in Polling mode, the Mini App needs to be served over HTTPS to be visible inside Telegram.

**Frontend Tunnel (Mini App):**
Forward port 5174 (default Mini App port) using your static domain:

```bash
ngrok http 5174 --domain=<YOUR-STATIC-DOMAIN>
```

*Example:* `ngrok http 5174 --domain=guppy-active-randomly.ngrok-free.app`

### Step 4: Update Configuration

Once your tunnel is running, update your project configuration:

1.  **Update `.env` file:**
    ```ini
    # Use the HTTPS URL from ngrok
    VM_TELEGRAM_MINI_APP_URL=https://guppy-active-randomly.ngrok-free.app
    ```

2.  **Update BotFather:**
    *   Open **@BotFather**.
    *   Select your bot.
    *   **Menu Button** > **Configure Menu Button**.
    *   Enter the **exact same ngrok URL**: `https://guppy-active-randomly.ngrok-free.app`

### Troubleshooting

*   **"ERR_NGROK_6022":** You are using a static domain that is reserved but not attached to your account/tunnel properly. Check your command flags.
*   **"Visit Site" Warning:** When you first open an ngrok link, it shows a warning page. You can bypass this by adding a request header `ngrok-skip-browser-warning: true` or by signing in to ngrok in the browser. *Note:* For the Mini App, this warning might break the flow. It is better to rely on the static domain which sometimes has fewer restrictions, or upgrade if needed.
    *   *Tip:* The warning is usually only shown for `ngrok-free.app` domains when visiting standard HTML pages.


## 6. Accessing the Mini App

1.  Open your bot in Telegram.
2.  Click the **Menu** button (if configured) or open the configured Mini App URL directly.
3.  The app should load and attempt to authenticate using Telegram init data.
