import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os
from flask import Flask
from threading import Thread

# ---------------- CONFIGURATION FLASK ----------------
app = Flask('')

@app.route('/')
def home():
    return "Le bot STRASBOURG RP est en ligne !"

def run_flask():
    # Lance Flask sur le port 8080 (requis par Render)
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()
# ----------------------------------------------------

# Configuration des intents Discord
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class StrasbourgBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        await self.tree.sync()
        print("Commandes slash synchronisées !")

bot = StrasbourgBot()

# Base de données temporaire en mémoire
bot.config = {
    "salon_session": None,
    "salon_statut": None,
    "salon_ticket": None,
    "role_staff": None,
    "role_fondation": None,
    "cooldowns_staff": {}
}

@bot.event
def on_ready():
    print(f"Connecté en tant que {bot.user.name} (ID: {bot.user.id})")
    bot.loop.create_task(bot.change_presence(activity=discord.Game(name="STRASBOURG RP")))

---

## 🛠️ Commandes de Configuration

@bot.tree.command(name="config-session", description="Configure le salon des sessions et les rôles associés.")
@app_commands.describe(salon="Le salon où s'afficheront les sessions", role_staff="Le rôle du staff", role_fondation="Le rôle de la fondation")
async def config_session(interaction: discord.Interaction, salon: discord.TextChannel, role_staff: discord.Role, role_fondation: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Vous devez être administrateur pour utiliser cette commande.", ephemeral=True)
    
    bot.config["salon_session"] = salon.id
    bot.config["role_staff"] = role_staff.id
    bot.config["role_fondation"] = role_fondation.id
    
    await interaction.response.send_message(f"✅ **Configuration Session réussie !**\n• Salon : {salon.mention}\n• Staff : {role_staff.mention}\n• Fondation : {role_fondation.mention}", ephemeral=True)

@bot.tree.command(name="config-statut", description="Configure le salon où s'affichera le statut du serveur.")
@app_commands.describe(salon="Le salon du statut")
async def config_statut(interaction: discord.Interaction, salon: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Vous devez être administrateur pour utiliser cette commande.", ephemeral=True)
    
    bot.config["salon_statut"] = salon.id
    await interaction.response.send_message(f"✅ **Salon de statut configuré sur :** {salon.mention}", ephemeral=True)

@bot.tree.command(name="ticket-config", description="Configure le salon et l'accès pour le système de tickets.")
@app_commands.describe(salon="Le salon où envoyer le message de ticket")
async def ticket_config(interaction: discord.Interaction, salon: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Vous devez être administrateur pour utiliser cette commande.", ephemeral=True)
    
    if not bot.config["role_staff"] or not bot.config["role_fondation"]:
        return await interaction.response.send_message("❌ Veuillez d'abord configurer les rôles avec `/config-session`.", ephemeral=True)
    
    bot.config["salon_ticket"] = salon.id
    
    embed = discord.Embed(
        title="⚓ SUPPORT CITOYEN - STRASBOURG RP",
        description="Besoin d'assistance ou d'un dépôt de projet ? Choisissez la catégorie adaptée dans le menu ci-dessous :\n\n"
                    "❓ **Question** : Demandes d'informations.\n"
                    "👤 **Report Joueur** : Signaler un citoyen.\n"
                    "👮 **Report Staff** : Réclamation modération.\n"
                    "🤝 **Partenariat** : Collaborations.\n"
                    "👑 **Contacter la Direction** : Haute administration / Fondateurs.\n"
                    "📝 **Recrutement Staff** : Postuler dans l'équipe.\n"
                    "🥷 **Création de Gang** : Dossier illégal.\n"
                    "💼 **Création d'entreprise** : Projet légal / Économie.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Strasbourg RP")
    
    await salon.send(embed=embed, view=DropdownTicketView())
    await interaction.response.send_message(f"✅ Panel de tickets envoyé dans {salon.mention}", ephemeral=True)

---

## 📢 Système de Sessions & Statuts

def verif_acces_staff_ou_fondation():
    async def predicate(interaction: discord.Interaction) -> bool:
        r_staff = bot.config.get("role_staff")
        r_fondation = bot.config.get("role_fondation")
        if not r_staff or not r_fondation:
            await interaction.response.send_message("❌ Le système n'est pas encore configuré.", ephemeral=True)
            return False
        
        user_role_ids = [role.id for role in interaction.user.roles]
        if r_staff in user_role_ids or r_fondation in user_role_ids or interaction.user.guild_permissions.administrator:
            return True
        
        await interaction.response.send_message("❌ Vous n'avez pas le rôle requis pour faire cela.", ephemeral=True)
        return False
    return app_commands.check(predicate)

@bot.tree.command(name="session-start", description="Lance une session RP (Soumis au cooldown de 30 min pour le Staff).")
@verif_acces_staff_ou_fondation()
async def session_start(interaction: discord.Interaction):
    s_channel_id = bot.config.get("salon_session")
    if not s_channel_id:
        return await interaction.response.send_message("❌ Salon de session non configuré.", ephemeral=True)
    
    salon_session = bot.get_channel(s_channel_id)
    user = interaction.user
    is_fondation = bot.config["role_fondation"] in [r.id for r in user.roles] or user.guild_permissions.administrator
    
    if not is_fondation:
        now = datetime.datetime.now()
        last_time = bot.config["cooldowns_staff"].get(user.id)
        if last_time:
            diff = (now - last_time).total_seconds()
            if diff < 1800:
                temps_restant = int((1800 - diff) // 60)
                return await interaction.response.send_message(f"⏳ Vous devez attendre encore {temps_restant} minute(s) avant de lancer une nouvelle session.", ephemeral=True)
        bot.config["cooldowns_staff"][user.id] = now

    embed = discord.Embed(
        title="⚓ STRASBOURG RP",
        description="### Session RolePlay Ouverte\n🌊 Plongez au cœur de la cité alsacienne et écrivez votre propre histoire.\n\n"
                    "**Métiers disponibles**\n"
                    "👮 Police Nationale\n"
                    "🚑 SAMU\n"
                    "🚒 Sapeurs-Pompiers\n"
                    "🏛️ Mairie & Services Publics\n"
                    "📰 Journalisme\n"
                    "👥 Civils & Entrepreneurs\n\n"
                    "**Au programme**\n"
                    "• Interventions et enquêtes\n"
                    "• Événements réguliers\n"
                    "• Économie immersive\n"
                    "• RP sérieux et encadré\n"
                    "• Staff actif et à l'écoute\n\n"
                    "🔑 **Code de connexion**\n"
                    "`1x3ezed6`\n\n"
                    "📜 Respect du règlement obligatoire\n"
                    "🎙️ Microphone requis pour jouer",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Que vous soyez citoyen, fonctionnaire ou chef d'entreprise, votre aventure commence aujourd'hui à Strasbourg RP.")
    
    await salon_session.send(content="@everyone", embed=embed)
    await interaction.response.send_message("✅ Session lancée avec succès !", ephemeral=True)
    
    await maj_statut(ouvert=True)

@bot.tree.command(name="session-close", description="Ferme la session RP actuelle.")
@verif_acces_staff_ou_fondation()
async def session_close(interaction: discord.Interaction):
    s_channel_id = bot.config.get("salon_session")
    if not s_channel_id:
        return await interaction.response.send_message("❌ Salon de session non configuré.", ephemeral=True)
        
    salon_session = bot.get_channel(s_channel_id)
    
    embed = discord.Embed(
        title="🏙️ STRASBOURG RP",
        description="Les dernières lumières du centre s'éteignent peu à peu et les rues de Strasbourg retrouvent leur calme.\n\n"
                    "🔒 **SESSION TERMINÉE**\n**SERVEUR FERMÉ**\n\n"
                    "Merci à tous pour cette session RP.\n"
                    "⚓ Rendez-vous très bientôt pour une nouvelle aventure dans la cité.\n"
                    "Bonne soirée à tous.",
        color=discord.Color.red()
    )
    
    await salon_session.send(content="@everyone", embed=embed)
    await interaction.response.send_message("✅ Session fermée avec succès !", ephemeral=True)
    
    await maj_statut(ouvert=False)

async def maj_statut(ouvert: bool):
    statut_id = bot.config.get("salon_statut")
    if not statut_id:
        return
    salon_statut = bot.get_channel(statut_id)
    if not salon_statut:
        return
        
    if ouvert:
        embed = discord.Embed(
            title="⚓ STRASBOURG RP",
            description="📊 **Statut du serveur**\n🟢 **SERVEUR OUVERT**\n\nLa session RP est en cours ! Rejoignez-nous dès maintenant.",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="⚓ STRASBOURG RP",
            description="📊 **Statut du serveur**\n🔴 **SERVEUR FERMÉ**\n\nLa session RP est terminée.\nRéouverture annoncée prochainement.\n-------------------------",
            color=discord.Color.red()
        )
    await salon_statut.purge(limit=5)
    await salon_statut.send(embed=embed)

---

## 🎟️ Gestionnaire des Tickets

class DropdownTicket(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Question", description="Poser une question simple", emoji="❓", value="quest"),
            discord.SelectOption(label="Report un Joueur", description="Signaler un comportement interdit", emoji="👤", value="rep_joueur"),
            discord.SelectOption(label="Report un Staff", description="Signaler un abus ou manquement", emoji="👮", value="rep_staff"),
            discord.SelectOption(label="Partenariat", description="Proposer une collaboration", emoji="🤝", value="part"),
            discord.SelectOption(label="Contacter la Direction", description="Demande exclusive aux fondateurs", emoji="👑", value="dir"),
            discord.SelectOption(label="Recrutement Staff", description="Déposer une candidature", emoji="📝", value="recrut"),
            discord.SelectOption(label="Création de Gang", description="Dossier d'organisation criminelle", emoji="🥷", value="gang"),
            discord.SelectOption(label="Création d'entreprise", description="Dossier projet légal", emoji="💼", value="entreprise"),
        ]
        super().__init__(placeholder="Choisissez le type de ticket à ouvrir...", min_values=1, max_values=1, options=options, custom_id="ticket_select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        choix = self.values[0]
        
        role_staff_id = bot.config.get("role_staff")
        role_fondation_id = bot.config.get("role_fondation")
        
        if not role_staff_id or not role_fondation_id:
            return await interaction.response.send_message("❌ Le système de rôles des tickets n'est pas configuré.", ephemeral=True)
            
        role_staff = guild.get_role(role_staff_id)
        role_fondation = guild.get_role(role_fondation_id)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
        }
        
        if choix in ["dir", "rep_staff"]:
            overwrites[role_fondation] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            nom_ticket = f"👑-{interaction.user.name}"
            titre_embed = "Ticket Restreint - Direction"
        else:
            overwrites[role_staff] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            overwrites[role_fondation] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            nom_ticket = f"ticket-{interaction.user.name}"
            titre_embed = "Ticket"
            for o in self.options:
                if o.value == choix:
                    titre_embed = f"Ticket {o.label}"
                    
        ticket_channel = await guild.create_text_channel(name=nom_ticket, overwrites=overwrites)
        
        embed_ticket = discord.Embed(
            title=f"⚓ STRASBOURG RP - {titre_embed}",
            description=f"Bonjour {interaction.user.mention},\nMerci d'avoir ouvert un ticket. Veuillez décrire votre demande ici.\nL'équipe administrative va vous prendre en charge rapidement.",
            color=discord.Color.blue()
        )
        
        view_close = discord.ui.View()
        btn_close = discord.ui.Button(label="Fermer le ticket", emoji="🔒", style=discord.ButtonStyle.danger)
        
        async def close_callback(inter_close: discord.Interaction):
            await inter_close.response.send_message("🔒 Fermeture du ticket dans quelques secondes...")
            await ticket_channel.delete()
            
        btn_close.callback = close_callback
        view_close.add_item(btn_close)
        
        await ticket_channel.send(embed=embed_ticket, view=view_close)
        await interaction.response.send_message(f"✅ Votre ticket a été créé : {ticket_channel.mention}", ephemeral=True)

class DropdownTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DropdownTicket())

# --- DÉMARRAGE DU BOT ET DE FLASK ---
keep_alive()

# Récupération sécurisée via l'environnement Render
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Erreur : La variable d'environnement 'DISCORD_TOKEN' est introuvable.")
