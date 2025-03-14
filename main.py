import discord
from discord import app_commands
import asyncio
from config import DISCORD_TOKEN, ADMIN_ROLE_NAME
from logging_config import logger
from aternos_controller import AternosController
from queue_manager import queue_manager
import bs4

class MinecraftBot(discord.Client):
    def __init__(self):
        # Use default intents without privileged ones
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.aternos = AternosController()

    async def setup_hook(self):
        """Initialize AternosController when bot starts"""
        try:
            await self.aternos.initialize()
            await self.aternos.login()
            logger.info("Successfully initialized Aternos controller")
        except Exception as e:
            logger.error(f"Failed to initialize Aternos controller: {e}")
            raise

def check_admin_role(interaction: discord.Interaction):
    """Check if user has admin role"""
    has_role = any(role.name == ADMIN_ROLE_NAME for role in interaction.user.roles)
    if not has_role:
        logger.warning(f"User {interaction.user.name} attempted to use admin command without {ADMIN_ROLE_NAME} role")
    return has_role

client = MinecraftBot()

@client.tree.command(name="start", description="Start the Minecraft server")
@app_commands.describe(server_name="The name of the server to start (optional)")
async def start(interaction: discord.Interaction, server_name: str = None):
    if not check_admin_role(interaction):
        await interaction.response.send_message(
            f"❌ You need the '{ADMIN_ROLE_NAME}' role to use this command!\n"
            "Please ask a server administrator to give you this role.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    try:
        # Check if Aternos controller is initialized
        if not client.aternos._make_request:
            logger.info("Aternos controller not initialized, reinitializing...")
            await client.aternos.initialize()
            await client.aternos.login()
        
        # Warn user about possible wait time
        await interaction.followup.send("⏳ Processing your request... This may take a minute or two.", ephemeral=True)
        
        # Select server if name provided
        if server_name:
            await queue_manager.add_action("select", interaction.guild_id, interaction.user.id)
            try:
                await client.aternos.select_server(server_name)
                await interaction.followup.send(f"✅ Selected server: {server_name}", ephemeral=True)
            except Exception as select_error:
                logger.error(f"Error selecting server: {select_error}")
                await interaction.followup.send(f"⚠️ Could not find server '{server_name}'. Using default server instead.", ephemeral=True)
                # Try to select the first available server
                await client.aternos.select_server()

        # Get current status before trying to start
        current_status = await client.aternos.get_server_status()
        
        # Only start if not already running
        if current_status.lower() in ["online", "starting", "in queue"]:
            await interaction.followup.send(f"ℹ️ Server is already {current_status}. No need to start it again.", ephemeral=True)
            return
            
        await queue_manager.add_action("start", interaction.guild_id, interaction.user.id)
        status = await client.aternos.start_server()
        
        if status:
            await interaction.followup.send("✅ Server start initiated! Please wait a few minutes...", ephemeral=True)
            
            # Wait briefly and get updated status
            await asyncio.sleep(5)
            new_status = await client.aternos.get_server_status()
            await interaction.followup.send(f"📊 Current server status: **{new_status}**", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Server might be already running or in queue. Check status for more info.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await interaction.followup.send(f"❌ An error occurred while starting the server: {str(e)}", ephemeral=True)
        
        # Try to recover from login errors
        if "login" in str(e).lower() or "verification" in str(e).lower():
            try:
                await interaction.followup.send("🔄 Attempting to re-login...", ephemeral=True)
                await client.aternos.login()
                await interaction.followup.send("✅ Re-login successful. Please try your command again.", ephemeral=True)
            except Exception as login_error:
                logger.error(f"Re-login failed: {login_error}")
                await interaction.followup.send("❌ Re-login failed. Please try again later.", ephemeral=True)

@client.tree.command(name="stop", description="Stop the Minecraft server")
@app_commands.describe(server_name="The name of the server to stop (optional)")
async def stop(interaction: discord.Interaction, server_name: str = None):
    if not check_admin_role(interaction):
        await interaction.response.send_message(
            f"❌ You need the '{ADMIN_ROLE_NAME}' role to use this command!\n"
            "Please ask a server administrator to give you this role.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    try:
        # Check if Aternos controller is initialized
        if not client.aternos._make_request:
            logger.info("Aternos controller not initialized, reinitializing...")
            await client.aternos.initialize()
            await client.aternos.login()
        
        # Warn user about possible wait time
        await interaction.followup.send("⏳ Processing your request... This may take a minute or two.", ephemeral=True)
        
        # Select server if name provided
        if server_name:
            await queue_manager.add_action("select", interaction.guild_id, interaction.user.id)
            try:
                await client.aternos.select_server(server_name)
                await interaction.followup.send(f"✅ Selected server: {server_name}", ephemeral=True)
            except Exception as select_error:
                logger.error(f"Error selecting server: {select_error}")
                await interaction.followup.send(f"⚠️ Could not find server '{server_name}'. Using default server instead.", ephemeral=True)
                # Try to select the first available server
                await client.aternos.select_server()

        # Get current status before trying to stop
        current_status = await client.aternos.get_server_status()
        
        # Only stop if actually running
        if current_status.lower() in ["offline", "stopping"]:
            await interaction.followup.send(f"ℹ️ Server is already {current_status}. No need to stop it.", ephemeral=True)
            return
            
        await queue_manager.add_action("stop", interaction.guild_id, interaction.user.id)
        status = await client.aternos.stop_server()
        
        if status:
            await interaction.followup.send("✅ Server stop initiated!", ephemeral=True)
            
            # Wait briefly and get updated status
            await asyncio.sleep(5)
            new_status = await client.aternos.get_server_status()
            await interaction.followup.send(f"📊 Current server status: **{new_status}**", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Server might be already stopped. Check status for more info.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in stop command: {e}")
        await interaction.followup.send(f"❌ An error occurred while stopping the server: {str(e)}", ephemeral=True)
        
        # Try to recover from login errors
        if "login" in str(e).lower() or "verification" in str(e).lower():
            try:
                await interaction.followup.send("🔄 Attempting to re-login...", ephemeral=True)
                await client.aternos.login()
                await interaction.followup.send("✅ Re-login successful. Please try your command again.", ephemeral=True)
            except Exception as login_error:
                logger.error(f"Re-login failed: {login_error}")
                await interaction.followup.send("❌ Re-login failed. Please try again later.", ephemeral=True)

@client.tree.command(name="status", description="Get information about the Minecraft server")
@app_commands.describe(server_name="The name of the server to check (optional)")
async def status(interaction: discord.Interaction, server_name: str = None):
    await interaction.response.defer()

    try:
        # Check if Aternos controller is initialized
        if not client.aternos._make_request:
            logger.info("Aternos controller not initialized, reinitializing...")
            await client.aternos.initialize()
            await client.aternos.login()
        
        # Select server if name provided
        if server_name:
            try:
                await client.aternos.select_server(server_name)
                await interaction.followup.send(f"✅ Selected server: {server_name}", ephemeral=True)
            except Exception as select_error:
                logger.error(f"Error selecting server: {select_error}")
                await interaction.followup.send(f"⚠️ Could not find server '{server_name}'. Using default server instead.", ephemeral=True)
                # Try to select the first available server
                await client.aternos.select_server()

        # Get detailed server information
        await interaction.followup.send("⏳ Fetching server status...", ephemeral=True)
        
        status = await client.aternos.get_server_status()
        
        # Try to get server address (from server page)
        server_page = await client.aternos._make_request('get', client.aternos.selected_server)
        soup = bs4(server_page.text, 'html.parser')
        
        # Look for server address
        address = None
        for elem in soup.find_all(['div', 'span']):
            text = elem.get_text(strip=True)
            if '.aternos.me' in text:
                address = text
                break
        
        # Format the status message
        status_message = f"🔎 Server Status: **{status}**\n"
        
        if address:
            status_message += f"🌐 Server Address: `{address}`\n"
        
        # Look for online players
        players_info = soup.find(string=lambda s: s and "Players" in s and "/" in s)
        if players_info:
            players_text = players_info.parent.get_text(strip=True)
            status_message += f"👥 {players_text}\n"
        
        # Check if we need to add additional information about queue
        if status.lower() == "in queue":
            queue_info = soup.find(string=lambda s: s and "queue" in s.lower() and "#" in s)
            if queue_info:
                status_message += f"⏳ {queue_info.strip()}\n"
        
        await interaction.followup.send(status_message, ephemeral=True)
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await interaction.followup.send(f"❌ An error occurred while fetching server status: {str(e)}", ephemeral=True)
        
        # Try to recover from login errors
        if "login" in str(e).lower() or "verification" in str(e).lower():
            try:
                await interaction.followup.send("🔄 Attempting to re-login...", ephemeral=True)
                await client.aternos.login()
                await interaction.followup.send("✅ Re-login successful. Please try your command again.", ephemeral=True)
            except Exception as login_error:
                logger.error(f"Re-login failed: {login_error}")
                await interaction.followup.send("❌ Re-login failed. Please try again later.", ephemeral=True)

@client.tree.command(name="help", description="Get help with bot commands")
async def help(interaction: discord.Interaction):
    help_text = f"""
🤖 **Minecraft Server Bot Commands**

*Admin Commands* (requires '{ADMIN_ROLE_NAME}' role):
• `/start [server_name]` - Start the Minecraft server
• `/stop [server_name]` - Stop the Minecraft server

*General Commands*:
• `/status [server_name]` - Check current server status
• `/help` - Show this help message

Note: Server operations may take a few moments to complete.
The server_name parameter is optional. If not provided, the first available server will be used.
For support, contact the server administrator.
"""
    await interaction.response.send_message(help_text, ephemeral=True)

@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    try:
        logger.info("Starting to sync commands...")
        await client.tree.sync()
        logger.info("Successfully synced application commands")
        logger.info(f"Required admin role name: {ADMIN_ROLE_NAME}")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)