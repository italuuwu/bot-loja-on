import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os  # Adicionado para ler as variáveis de ambiente

from flask import Flask
from threading import Thread

# --- CONFIGURAÇÃO DO WEB SERVER PARA O RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Online 24/7!"

def run():
    # O Render exige que o servidor escute na porta que ele define dinamicamente
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
# -----------------------------------------------

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
    "bio": "A melhor loja de produtos digitais do Discord! Compre com total segurança de forma manual.",
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
                    description=f"R\$ {dados['preco']:.2f} - Estoque: {dados['estoque']}",
                    emoji="📦"
                ))

        super().__init__(placeholder="Selecione um produto para comprar...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if self.values[0] == "Nenhum produto cadastrado":
            await interaction.followup.send("❌ Nenhum produto disponível no momento.", ephemeral=True)
            return

        prod_id = self.values[0]
        produto = PRODUTOS.get(prod_id)

        if not produto:
            await interaction.followup.send("❌ Produto não encontrado.", ephemeral=True)
            return

        if produto['estoque'] <= 0:
            await interaction.followup.send("❌ Desculpe, este produto está esgotado no momento!", ephemeral=True)
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

        nome_canal = f"🛒-{interaction.user.name}-{prod_id}"
        canal_ticket = await guild.create_text_channel(name=nome_canal, category=categoria_vendas, overwrites=overwrites)

        await interaction.followup.send(f"✅ Seu carrinho foi aberto em {canal_ticket.mention}!", ephemeral=True)

        embed_ticket = discord.Embed(
            title=f"🛍️ Pedido: {produto['nome']}",
            description=f"Olá {interaction.user.mention},\n\n"
                        f"Você escolheu o produto **{produto['nome']}**.\n"
                        f"**Valor:** `R$ {produto['preco']:.2f}`\n\n"
                        f"⚠️ **PAGAMENTO MANUAL** ⚠️\n"
                        f"Por favor, envie o **comprovante de pagamento** neste chat.\n"
                        f"Um administrador irá validar o seu pagamento e liberar o produto.",
            color=discord.Color.gold()
        )
        embed_ticket.add_field(name="Descrição do Produto", value=produto['descricao'], inline=False)
        embed_ticket.set_author(name=CONFIG_BOT['nome'], icon_url=CONFIG_BOT['avatar'])
        embed_ticket.set_thumbnail(url=CONFIG_BOT['avatar'])

        view_ticket = BotoesTicket(prod_id, interaction.user.id)
        await canal_ticket.send(embed=embed_ticket, view=view_ticket)
        
        # Correção sutil: Se por acaso o bot não achar o ID do dono, evita dar erro
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

        produto = PRODUTOS.get(self.prod_id)
        if not produto or produto['estoque'] <= 0:
            await interaction.followup.send("❌ Erro: Produto não encontrado ou sem estoque suficiente.", ephemeral=True)
            return

        PRODUTOS[self.prod_id]['estoque'] -= 1
        cliente = interaction.guild.get_member(self.cliente_id)

        await interaction.channel.send("🔄 Processando aprovação e notificando o cliente...")

        if cliente:
            try:
                embed_cliente = discord.Embed(
                    title="🎉 Sua compra foi aprovada!",
                    description=f"Seu pagamento para o produto **{produto['nome']}** foi confirmado manualmente pela nossa equipe.\n\n"
                                f"Obrigado pela preferência!",
                    color=discord.Color.green()
                )
                embed_cliente.set_author(name=CONFIG_BOT['nome'], icon_url=CONFIG_BOT['avatar'])
                await cliente.send(embed=embed_cliente)
            except discord.Forbidden:
                await interaction.channel.send(f"⚠️ Não consegui enviar DM para {cliente.mention}, mas a compra está aprovada!")

        await interaction.channel.send("🔒 Este carrinho foi finalizado. O canal será deletado em 10 segundos...")
        await asyncio.sleep(10)
        await interaction.channel.delete()

    @discord.ui.button(label="Fechar Carrinho", style=discord.ButtonStyle.danger, custom_id="fechar_carrinho", emoji="✖️")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.cliente_id:
            await interaction.followup.send("❌ Você não tem permissão para fechar este carrinho.", ephemeral=True)
            return
        
        await interaction.channel.send("🗑️ Fechando e deletando o carrinho em 5 segundos...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

@bot.tree.command(name="config_perfil", description="Personalize o nome, bio, avatar e banner exibidos nos painéis.")
@app_commands.checks.has_permissions(administrator=True)
async def config_perfil(interaction: discord.Interaction, nome: str = None, bio: str = None, avatar_url: str = None, banner_url: str = None):
    await interaction.response.defer(ephemeral=True)
    if nome: CONFIG_BOT["nome"] = nome
    if bio: CONFIG_BOT["bio"] = bio
    if avatar_url: CONFIG_BOT["avatar"] = avatar_url
    if banner_url: CONFIG_BOT["banner"] = banner_url
    await interaction.followup.send("✅ Configurações de identidade visual updated!", ephemeral=True)

@bot.tree.command(name="add_produto", description="Cadastre um novo produto na sua loja virtual.")
@app_commands.checks.has_permissions(administrator=True)
async def add_produto(interaction: discord.Interaction, id_produto: str, nome: str, preco: float, descricao: str, estoque: int):
    await interaction.response.defer(ephemeral=True)
    PRODUTOS[id_produto] = {
        "nome": nome,
        "preco": preco,
        "descricao": descricao,
        "estoque": estoque
    }
    # --- FINALIZAÇÃO DO COMANDO QUE ESTAVA CORTADO ---
    await interaction.followup.send(f"✅ Produto **{nome}** (ID: `{id_produto}`) cadastrado com sucesso!", ephemeral=True)


# --- INICIALIZAÇÃO SEGURA DO BOT ---
if __name__ == "__main__":
    # Puxa o Token das configurações do Render primeiro
    TOKEN = os.getenv("DISCORD_TOKEN")
    
    if not TOKEN:
        print("❌ ERRO: A variável de ambiente 'DISCORD_TOKEN' não foi encontrada!")
    else:
        # 1. Liga o servidor web em segundo plano através da Thread primeiro
        keep_alive()  
        
        # 2. Agora liga o bot do Discord por último para ele não travar
        print("🤖 Iniciando conexão com o Discord...")
        bot.run(TOKEN)
