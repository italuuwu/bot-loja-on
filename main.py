import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import http.server
import threading

# --- MINI SERVIDOR WEB NATIVO ---
# Necessário para o Render aceitar o bot no plano gratuito sem desligar por falta de porta web
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
        # Limpa o cache antigo e força a sincronização global de todos os comandos de barra
        await self.tree.sync()
        print("🔄 Comandos de barra sincronizados com sucesso globalmente!")

bot = VendasBot()

# --- CONFIGURAÇÃO PREDEFINIDA DA SUA LOJA ---
CONFIG_BOT = {
    "nome": "LOJA VIRTUAL",
    "bio": "A melhor loja de produtos digitais do Discord! Compre com total segurança de forma manual.",
    "avatar": "https://imgur.com",  # Substitua pelo link do logo da sua loja
    "banner": "https://imgur.com"   # Substitua pelo link do banner da sua loja
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
                    description=f"R\$ {dados['preco']:.2f} - Estoque: {dados['estoque']}",
                    emoji="📦"
                ))

        super().__init__(placeholder="Selecione o produto desejado...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.values[0] == "Nenhum produto cadastrado":
            await interaction.followup.send("❌ Nenhum produto disponível no momento.", ephemeral=True)
            return

        prod_id = self.values[0]
        produto = PRODUTOS.get(prod_id)
        if not produto or produto['estoque'] <= 0:
            await interaction.followup.send("❌ Produto indisponível ou esgotado.", ephemeral=True)
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
        await interaction.followup.send(f"✅ Seu carrinho foi aberto em {canal_ticket.mention}!", ephemeral=True)

        embed_ticket = discord.Embed(
            title=f"🛍️ Pedido: {produto['nome']}",
            description=f"Olá {interaction.user.mention},\n\n"
                        f"Você escolheu o produto **{produto['nome']}**.\n"
                        f"**Valor:** `R$ {produto['preco']:.2f}`\n\n"
                        f"➡️ **PAGAMENTO MANUAL**\n"
                        f"Por favor, envie o **comprovante de pagamento** neste chat.\n"
                        f"Um administrador irá validar o seu pagamento e liberar o seu produto.",
            color=discord.Color.gold()
        )
        await canal_ticket.send(embed=embed_ticket, view=BotoesTicket(prod_id, interaction.user.id))
        
        owner_mention = f"<@&{guild.owner_id}>" if guild.owner_id else "@here"
        await canal_ticket.send(f"🔔 {owner_mention} Um novo cliente abriu um carrinho! Aguardando comprovante.")

class PainelVendasView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DropdownProdutos())

class BotoesTicket(discord.ui.View):
    def __init__(self, prod_id, cliente_id):
        super().__init__(timeout=None)
        self.prod_id = prod_id
        self.cliente_id = cliente_id

    @discord.ui.button(label="Aprovar Entrega Manual", style=discord.ButtonStyle.success, custom_id="aprovar_entrega", emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Apenas administradores podem aprovar este pagamento!", ephemeral=True)
            return
        await interaction.channel.send("🔒 Este carrinho foi finalizado. O canal será deletado em 10 segundos...")
        await asyncio.sleep(10)
        await interaction.channel.delete()

    @discord.ui.button(label="Fechar Carrinho", style=discord.ButtonStyle.danger, custom_id="fechar_carrinho", emoji="✖️")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.channel.send("🗑️ Fechando e deletando o carrinho em 5 segundos...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- COMANDO DO PAINEL PREMIUM ---
@bot.tree.command(name="enviar_painel", description="Envia o painel de compras premium da loja.")
@app_commands.checks.has_permissions(administrator=True)
async def enviar_painel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    embed_loja = discord.Embed(
        title=f"🏪 {CONFIG_BOT['nome']}",
        description=f"> {CONFIG_BOT['bio']}\n\n"
                    f"**✨ Por que comprar conosco?**\n"
                    f"💳 ・ Pagamento facilitado via Pix\n"
                    f"⚡ ・ Entrega manual rápida e garantida\n"
                    f"🔒 ・ Ambiente 100% seguro por ticket\n\n"
                    f"👇 *Selecione o produto abaixo para abrir seu carrinho:*",
        color=discord.Color.from_rgb(88, 101, 242) # Cor oficial Blurple do Discord
    )
    
    # Adiciona a imagem pequena (Logo) no canto superior direito
    if CONFIG_BOT['avatar'] and "http" in CONFIG_BOT['avatar']:
        embed_loja.set_thumbnail(url=CONFIG_BOT['avatar'])
    
    # Adiciona o banner grande centralizado embaixo do texto
    if CONFIG_BOT['banner'] and "http" in CONFIG_BOT['banner']:
        embed_loja.set_image(url=CONFIG_BOT['banner'])
        
    embed_loja.set_footer(text="Atendimento Manual • Todos os direitos reservados", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    
    view = PainelVendasView()
    await interaction.channel.send(embed=embed_loja, view=view)
    await interaction.followup.send("✅ Painel premium enviado com sucesso!", ephemeral=True)

# --- COMANDO PARA CONFIGURAR AS IMAGENS DO BANNER E PERFIL ---
@bot.tree.command(name="config_perfil", description="Personalize a identidade da loja incluindo os links do banner e avatar.")
@app_commands.checks.has_permissions(administrator=True)
async def config_perfil(interaction: discord.Interaction, nome: str = None, bio: str = None, avatar_url: str = None, banner_url: str = None):
    await interaction.response.defer(ephemeral=True)
    if nome: CONFIG_BOT["nome"] = nome.upper()
    if bio: CONFIG_BOT["bio"] = bio
    if avatar_url: CONFIG_BOT["avatar"] = avatar_url
    if banner_url: CONFIG_BOT["banner"] = banner_url
    await interaction.followup.send("✅ Configurações de identidade visual premium atualizadas!", ephemeral=True)

# --- COMANDO PARA ADICIONAR PRODUTOS ---
@bot.tree.command(name="add_produto", description="Cadastre um novo produto na sua loja virtual.")
@app_commands.checks.has_permissions(administrator=True)
async def add_produto(interaction: discord.Interaction, id_produto: str, nome: str, preco: float, descricao: str, estoque: int):
    await interaction.response.defer(ephemeral=True)
    PRODUTOS[id_produto] = {"nome": nome, "preco": preco, "descricao": descricao, "estoque": estoque}
    await interaction.followup.send(f"✅ Produto **{nome}** (ID: `{id_produto}`) cadastrado com sucesso!", ephemeral=True)

# --- INICIALIZAÇÃO SEGURA DO BOT ---
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        print("🤖 Iniciando conexão com o Discord...")
        bot.run(TOKEN)
    else:
        print("❌ Chave 'DISCORD_TOKEN' ausente nas variáveis de ambiente do Render.")
