import discord
from discord.ext import commands
from discord import app_commands, ButtonStyle
from discord.ui import Button, View
import sqlite3
from datetime import datetime
import os
from dotenv import load_dotenv

# --- ENV AYARLARI ---
load_dotenv()  # .env dosyasını yükle
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Token artık .env üzerinden alınıyor
GUILD_ID = 1270205121535672474
DATABASE_NAME = "users.db"
POINTS_PER_CLICK = 5

# --- ROL VE PUAN AYARLARI ---
LEVEL_ROLES = {
    "Level 3": 75,
    "Level 2": 50,
    "Level 1": 25,
}

TARGET_ROLES = {
    "OG": 300,
    "VanthList": 150,
}

# --- BOT İNTENTLERİ ---
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- VERİTABANI ---
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        click_count INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        last_click_date TEXT
    )
    ''')
    conn.commit()
    conn.close()

# --- ROL GÜNCELLEME ---
async def update_user_roles(member: discord.Member, user_points: int):
    guild = member.guild

    # Level rolleri
    current_level_roles = [role for role in member.roles if role.name in LEVEL_ROLES]
    highest_level_to_get = None
    for role_name, required_points in sorted(LEVEL_ROLES.items(), key=lambda item: item[1], reverse=True):
        if user_points >= required_points:
            highest_level_to_get = role_name
            break

    if highest_level_to_get:
        level_role_obj = discord.utils.get(guild.roles, name=highest_level_to_get)
        if level_role_obj and level_role_obj not in member.roles:
            if current_level_roles:
                await member.remove_roles(*current_level_roles)
            await member.add_roles(level_role_obj)
    elif current_level_roles:
        await member.remove_roles(*current_level_roles)

    # Hedef rolleri
    for role_name, required_points in TARGET_ROLES.items():
        if user_points >= required_points:
            target_role_obj = discord.utils.get(guild.roles, name=role_name)
            if target_role_obj and target_role_obj not in member.roles:
                await member.add_roles(target_role_obj)
                try:
                    await member.send(f"🎉 Congratulations! You have earned the **{target_role_obj.name}** role in {guild.name}!")
                except discord.Forbidden:
                    print(f"{member.display_name} kullanıcısına DM gönderilemiyor.")

# --- BUTON GÖRÜNÜMÜ ---
class ClaimButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Daily Points", style=ButtonStyle.primary, custom_id="daily_claim_button_v2")
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = interaction.user.id
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT last_click_date, click_count, points FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            last_click_date, click_count, points = result
            if last_click_date == today:
                await interaction.followup.send(f"You have already claimed your points for today. Your current points: **{points}**", ephemeral=True)
                conn.close()
                return
        else:
            click_count, points = 0, 0
        new_click_count = click_count + 1
        new_points = points + POINTS_PER_CLICK
        cursor.execute("""
        INSERT INTO users (user_id, click_count, points, last_click_date) VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET click_count = ?, points = ?, last_click_date = ?
        """, (user_id, new_click_count, new_points, today, new_click_count, new_points, today))
        conn.commit()
        conn.close()
        await interaction.followup.send(f"✅ Success! You have earned **{POINTS_PER_CLICK}** points.\nYour total points: **{new_points}**", ephemeral=True)
        await update_user_roles(interaction.user, new_points)

# --- BOT HAZIR OLUNCA ---
@bot.event
async def on_ready():
    init_db()
    bot.add_view(ClaimButtonView())
    print(f'Logged in as {bot.user}.')
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)

# --- KURULUM KOMUTU ---
@bot.tree.command(name="setup-panel", description="Puan toplama panelini kurar.", guild=discord.Object(id=GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    all_rewards = {**LEVEL_ROLES, **TARGET_ROLES}
    sorted_rewards = sorted(all_rewards.items(), key=lambda item: item[1])
    reward_text = ""
    for name, points in sorted_rewards:
        reward_text += f"- **{points} points** »  `{name}`\n"
    embed = discord.Embed(
        title="🌟 Daily Point Claim",
        description="Click the button below every day to earn points!\n\n"
                    f"**Rewards:**\n{reward_text}",
        color=discord.Color.purple()
    )
    view = ClaimButtonView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.followup.send("✅ Claim panel set up successfully.", ephemeral=True)

# --- BOTU ÇALIŞTIR ---
bot.run(BOT_TOKEN)
