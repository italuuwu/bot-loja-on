import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import http.server
import threading

# --- MINI SERVIDOR WEB NATIVO (Sem Flask para não travar) ---
class WebServer(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot Online!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = http.server.HTTPServer(('0.0.0.0', port), WebServer)
    server.serve_forever()

# Inicia o servidor web em segundo plano imediatamente
threading.Thread(target=run_web_server, daemon=True).start()
# ------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class VendasBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        await self.tree.sync()
        print("🔄 Comandos de barra sincronizados com sucesso!")

bot = VendasBot()

CONFIG_BOT = {
    "nome": "Loja Virtual",
    "bio": "A melhor loja de produtos digitais do Discord!",
    "avatar": "https://imgur.com",
    "banner": "https://imgur.com"
}

PRODUTOS = {}

class DropdownProdutos(discord.ui.Select):
    def __init__(self):
        options = []
        if not PRODUTOS:
            options.append(discord.SelectOption(label="Nenhum produto cadastrado", description="Aguardando o dono configurar.", emoji="❌"))
        else:
            for prod_id, dados in PRODUTOS.items():
                options.append(discord.SelectOption(
                    label=dados['nome'],
                    value=prod_id,
                    description=f"R$ {dados['preco']:.2f} - Estoque: {dados['estoque']}",
                    emoji="📦"
                ))

        super().__init__(placeholder="Selecione um produto...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.values == "Nenhum produto cadastrado":
            await interaction.followup.send("❌ Nenhum produto disponível.", ephemeral=True)
            return

        prod_id = self.values
        produto = PRODUTOS.get(prod_id)
        if not produto or produto['estoque'] <= 0:
            await interaction.followup.send("❌ Produto indisponível.", ephemeral=True)
            return

        guild = interaction.guild
        categoria_vendas = discord.utils.get(guild.categories, name="🛒 CARRINHOS")
        if not categoria_vendas:
            categoria_vendas = await guild.create_category("🛒 CARRINHOS")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        canal_ticket = await guild.create_text_channel(name=f"🛒-{interaction.user.name}-{prod_id}", category=categoria_vendas, overwrites=overwrites)
        await interaction.followup.send(f"✅ Carrinho aberto em {canal_ticket.mention}!", ephemeral=True)

        embed_ticket = discord.Embed(title=f"🛍️ Pedido: {produto['nome']}", description=f"Olá {interaction.user.mention},\n\nEnvie o comprovante de pagamento neste chat.", color=discord.Color.gold())
        await canal_ticket.send(embed=embed_ticket, view=BotoesTicket(prod_id, interaction.user.id))

class PainelVendasView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DropdownProdutos())

class BotoesTicket(discord.ui.View):
    def __init__(self, prod_id, cliente_id):
        super().__init__(timeout=None)
        self.prod_id = prod_id
        self.cliente_id = cliente_id

    @discord.ui.button(label="Aprovar Entrega", style=discord.ButtonStyle.success, custom_id="aprovar_entrega", emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Permissão negada.", ephemeral=True)
            return
        await interaction.channel.send("🔒 Carrinho finalizado. Deletando canal em 10 segundos...")
        await asyncio.sleep(10)
        await interaction.channel.delete()

    @discord.ui.button(label="Fechar Carrinho", style=discord.ButtonStyle.danger, custom_id="fechar_carrinho", emoji="✖️")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.channel.send("🗑️ Deletando carrinho em 5 segundos...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

@bot.tree.command(name="config_perfil", description="Personalize o perfil da loja.")
@app_commands.checks.has_permissions(administrator=True)
async def config_perfil(interaction: discord.Interaction, nome: str = None, bio: str = None):
    await interaction.response.defer(ephemeral=True)
    if nome: CONFIG_BOT["nome"] = nome
    if bio: CONFIG_BOT["bio"] = bio
    await interaction.followup.send("✅ Identidade visual atualizada!", ephemeral=True)

@bot.tree.command(name="add_produto", description="Cadastre um novo produto.")
@app_commands.checks.has_permissions(administrator=True)
async def add_produto(interaction: discord.Interaction, id_produto: str, nome: str, preco: float, descricao: str, estoque: int):
    await interaction.response.defer(ephemeral=True)
    PRODUTOS[id_produto] = {"nome": nome, "preco": preco, "descricao": descricao, "estoque": estoque}
    await interaction.followup.send(f"✅ Produto {nome} cadastrado com sucesso!", ephemeral=True)

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        print("🤖 Iniciando conexão com o Discord...")
        bot.run(TOKEN)
    else:
        print("❌ Chave 'DISCORD_TOKEN' ausente.")
