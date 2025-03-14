from dotenv import load_dotenv, get_key
import os

load_dotenv()

DISCORD_TOKEN = get_key(".env", "DISCORD_TOKEN")
ATERNOS_USERNAME = get_key(".env", "ATERNOS_USERNAME")
ATERNOS_PASSWORD = get_key(".env", "ATERNOS_PASSWORD")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is not set")

if not ATERNOS_USERNAME or not ATERNOS_PASSWORD:
    raise ValueError("Aternos credentials not properly configured")

# Aternos URLs
ATERNOS_LOGIN_URL = "https://aternos.org/go/"  # Direct login endpoint
ATERNOS_SERVER_LIST_URL = "https://aternos.org/server/"

# Discord Role Configuration
ADMIN_ROLE_NAME = "Minecraft Admin"