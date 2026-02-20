import discord
from discord.ext import commands
from discord import ui, app_commands
import os
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Create bot with command prefix
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)


async def recently_sent(channel: discord.abc.Messageable, *, content: str | None = None, embed_title: str | None = None, seconds: int = 5) -> bool:
    """Return True if the bot has sent a message matching `content` or `embed_title` in `channel` within `seconds` seconds.

    This helps avoid duplicate messages when multiple bot processes are accidentally running.
    Ephemeral responses are not covered because they don't appear in channel history.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        async for msg in channel.history(limit=10, after=cutoff):
            if msg.author != bot.user:
                continue
            if content and msg.content == content:
                return True
            if embed_title and msg.embeds:
                try:
                    if msg.embeds[0].title == embed_title:
                        return True
                except Exception:
                    pass
    except Exception:
        # If history can't be read (e.g., DM channel or permissions), be conservative and return False
        return False
    return False


# Persistent config for join logging (guild_id -> channel_id)
CONFIG_PATH = Path('join_log_config.json')
try:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open('r', encoding='utf-8') as f:
            join_log_config: dict = json.load(f)
    else:
        join_log_config = {}
except Exception:
    join_log_config = {}


def save_join_config() -> None:
    try:
        with CONFIG_PATH.open('w', encoding='utf-8') as f:
            json.dump(join_log_config, f, indent=2)
    except Exception:
        pass


# Temporary Voice Room config (guild_id -> lobby_voice_channel_id)
TEMP_VC_CONFIG_PATH = Path('temp_vc_config.json')
try:
    if TEMP_VC_CONFIG_PATH.exists():
        with TEMP_VC_CONFIG_PATH.open('r', encoding='utf-8') as f:
            temp_vc_config: dict = json.load(f)
    else:
        temp_vc_config = {}
except Exception:
    temp_vc_config = {}


def save_temp_vc_config() -> None:
    try:
        with TEMP_VC_CONFIG_PATH.open('w', encoding='utf-8') as f:
            json.dump(temp_vc_config, f, indent=2)
    except Exception:
        pass


# Runtime map for created temporary channels (channel_id -> owner_id)
temp_vc_channels: dict[int, int] = {}



@bot.event
async def on_ready():
    """Called when bot successfully connects to Discord"""
    print(f'{bot.user} has connected to Discord!')
    print('------')
    # Register persistent views so old panel buttons still work after bot restarts.
    try:
        bot.add_view(AccountPanelView())
    except Exception:
        pass
    # Set bot status with command prefix
    activity = discord.Activity(type=discord.ActivityType.watching, name="!help_custom for commands")
    await bot.change_presence(activity=activity)
    # Register application (slash) commands
    try:
        await bot.tree.sync()
    except Exception:
        pass

@bot.event
async def on_member_join(member):
    """Called when a new member joins the server"""
    # Welcome DM (best-effort)
    try:
        await member.send(f'Halo {member.name}! Selamat datang di server!')
    except Exception:
        pass

    # Send join log to configured channel (if set)
    try:
        guild = member.guild
        guild_id = str(guild.id)
        channel_id = join_log_config.get(guild_id)
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                embed = discord.Embed(
                    title=f'👋 Anggota Baru: {member.name}',
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
                if member.avatar:
                    embed.set_thumbnail(url=member.avatar.url)
                embed.add_field(name='Nama', value=str(member), inline=False)
                embed.add_field(name='ID', value=member.id, inline=False)
                joined = member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else 'N/A'
                created = member.created_at.strftime('%Y-%m-%d %H:%M:%S') if member.created_at else 'N/A'
                embed.add_field(name='Joined Server', value=joined, inline=False)
                embed.add_field(name='Account Created', value=created, inline=False)
                embed.set_footer(text=f'User joined')
                if not await recently_sent(channel, embed_title=embed.title):
                    await channel.send(embed=embed)
    except Exception:
        pass

@bot.command(name='ping')
async def ping(ctx):
    """Check bot latency"""
    content = f'Pong! {round(bot.latency * 1000)}ms'
    if not await recently_sent(ctx.channel, content=content):
        await ctx.send(content)


@bot.tree.command(name='ping', description='Cek latency/ping bot ke Discord')
async def ping_slash(interaction: discord.Interaction):
    """Slash: Check bot latency"""
    content = f'Pong! {round(bot.latency * 1000)}ms'
    channel = interaction.channel
    if channel and await recently_sent(channel, content=content):
        await interaction.response.send_message('A similar message was recently sent; suppressed duplicate.', ephemeral=True)
        return
    await interaction.response.send_message(content)

@bot.command(name='hello')
async def hello(ctx):
    """Simple greeting command"""
    content = f'Halo {ctx.author.name}! Apa kabar? 👋'
    if not await recently_sent(ctx.channel, content=content):
        await ctx.send(content)


@bot.tree.command(name='hello', description='Bot memberikan salam kepada Anda')
async def hello_slash(interaction: discord.Interaction):
    content = f'Halo {interaction.user.name}! Apa kabar? 👋'
    channel = interaction.channel
    if channel and await recently_sent(channel, content=content):
        await interaction.response.send_message('A similar message was recently sent; suppressed duplicate.', ephemeral=True)
        return
    await interaction.response.send_message(content)

@bot.command(name='user')
async def user(ctx):
    """Get info about the user who called the command"""
    user = ctx.author
    embed = discord.Embed(title=f'User Info - {user.name}', color=discord.Color.blue())
    embed.add_field(name='ID', value=user.id, inline=False)
    embed.add_field(name='Joined Server', value=ctx.author.joined_at.strftime('%Y-%m-%d %H:%M:%S'), inline=False)
    embed.add_field(name='Account Created', value=user.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=False)
    embed.set_thumbnail(url=user.avatar.url)
    if not await recently_sent(ctx.channel, embed_title=embed.title):
        await ctx.send(embed=embed)


@bot.tree.command(name='user', description='Tampilkan informasi profil Anda')
async def user_slash(interaction: discord.Interaction):
    user = interaction.user
    embed = discord.Embed(title=f'User Info - {user.name}', color=discord.Color.blue())
    embed.add_field(name='ID', value=user.id, inline=False)
    embed.add_field(name='Joined Server', value=user.joined_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(user, 'joined_at') and user.joined_at else 'N/A', inline=False)
    embed.add_field(name='Account Created', value=user.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=False)
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    channel = interaction.channel
    if channel and await recently_sent(channel, embed_title=embed.title):
        await interaction.response.send_message('A similar message was recently sent; suppressed duplicate.', ephemeral=True)
        return
    await interaction.response.send_message(embed=embed)

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason='Tidak ada alasan'):
    """Kick a member from the server (requires kick_members permission)"""
    await member.kick(reason=reason)
    content = f'{member.mention} telah di-kick karena: {reason}'
    if not await recently_sent(ctx.channel, content=content):
        await ctx.send(content)


@bot.tree.command(name='kick', description='Kick user dari server (Admin)')
@app_commands.describe(member='User untuk di-kick', reason='Alasan (opsional)')
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = 'Tidak ada alasan'):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message('Anda tidak memiliki permission untuk melakukan kick.', ephemeral=True)
        return
    try:
        await member.kick(reason=reason)
        content = f'{member.mention} telah di-kick karena: {reason}'
        channel = interaction.channel
        if channel and await recently_sent(channel, content=content):
            await interaction.response.send_message('A similar message was recently sent; suppressed duplicate.', ephemeral=True)
            return
        await interaction.response.send_message(content)
    except Exception as e:
        await interaction.response.send_message(f'Gagal melakukan kick: {e}', ephemeral=True)

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason='Tidak ada alasan'):
    """Ban a member from the server (requires ban_members permission)"""
    await member.ban(reason=reason)
    content = f'{member.mention} telah di-ban karena: {reason}'
    if not await recently_sent(ctx.channel, content=content):
        await ctx.send(content)


@bot.tree.command(name='ban', description='Ban user dari server (Admin)')
@app_commands.describe(member='User untuk di-ban', reason='Alasan (opsional)')
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = 'Tidak ada alasan'):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message('Anda tidak memiliki permission untuk melakukan ban.', ephemeral=True)
        return
    try:
        await member.ban(reason=reason)
        content = f'{member.mention} telah di-ban karena: {reason}'
        channel = interaction.channel
        if channel and await recently_sent(channel, content=content):
            await interaction.response.send_message('A similar message was recently sent; suppressed duplicate.', ephemeral=True)
            return
        await interaction.response.send_message(content)
    except Exception as e:
        await interaction.response.send_message(f'Gagal melakukan ban: {e}', ephemeral=True)

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    """Delete messages (requires manage_messages permission)"""
    await ctx.channel.purge(limit=amount + 1)
    content = f'Berhasil menghapus {amount} pesan!'
    if not await recently_sent(ctx.channel, content=content):
        await ctx.send(content, delete_after=3)


@bot.tree.command(name='clear', description='Hapus sejumlah pesan di channel (Admin)')
@app_commands.describe(amount='Jumlah pesan yang akan dihapus (angka)')
async def clear_slash(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message('Anda tidak memiliki permission manage_messages.', ephemeral=True)
        return
    try:
        # purge requires a TextChannel object
        channel = interaction.channel
        await channel.purge(limit=amount + 1)
        await interaction.response.send_message(f'Berhasil menghapus {amount} pesan!', ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f'Gagal menghapus pesan: {e}', ephemeral=True)

# Channel Creation Modal
class ChannelModal(ui.Modal, title='Buat Channel Baru'):
    category_name = ui.TextInput(label='Nama Category', placeholder='Contoh: General', required=True)
    channel_name = ui.TextInput(label='Nama Channel', placeholder='Contoh: announcements', required=True)
    channel_type = ui.TextInput(label='Tipe Channel', placeholder='text atau voice', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        category_name = str(self.category_name)
        channel_name = str(self.channel_name)
        channel_type = str(self.channel_type).lower()
        
        # Validate channel type
        if channel_type not in ['text', 'voice']:
            embed = discord.Embed(
                title='❌ Error',
                description='Tipe channel harus "text" atau "voice"!',
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Find category
        category = discord.utils.get(interaction.guild.categories, name=category_name)
        if not category:
            embed = discord.Embed(
                title='❌ Error',
                description=f'Category "{category_name}" tidak ditemukan!',
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Create channel
            if channel_type == 'text':
                new_channel = await category.create_text_channel(name=channel_name)
            else:  # voice
                new_channel = await category.create_voice_channel(name=channel_name)
            
            embed = discord.Embed(
                title='✅ Channel Berhasil Dibuat!',
                description=f'Channel #{new_channel.name} telah dibuat di category {category.name}',
                color=discord.Color.green()
            )
            embed.add_field(name='Nama Channel', value=new_channel.name, inline=False)
            embed.add_field(name='Tipe Channel', value=channel_type.capitalize(), inline=False)
            embed.add_field(name='Category', value=category.name, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title='❌ Error',
                description=f'Gagal membuat channel: {str(e)}',
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

# Rename Category Modal
class RenameCategoryModal(ui.Modal, title='Edit Category'):
    change_name = ui.TextInput(label='Change Name', placeholder='Masukkan nama category baru', required=True, max_length=100)

    def __init__(self, category: discord.CategoryChannel):
        super().__init__()
        self.category = category
        self.change_name.default = category.name

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message('Command ini hanya bisa digunakan di server.', ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message('Anda tidak memiliki permission manage_channels.', ephemeral=True)
            return

        new_name = str(self.change_name).strip()
        if not new_name:
            await interaction.response.send_message('Nama category baru tidak boleh kosong.', ephemeral=True)
            return

        try:
            old_name = self.category.name
            await self.category.edit(name=new_name, reason=f'Category renamed by {interaction.user}')
            embed = discord.Embed(
                title='✅ Category Berhasil Diubah',
                description=f'`{old_name}` → `{new_name}`',
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message('Bot tidak punya izin untuk mengubah category.', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'Gagal mengubah category: {e}', ephemeral=True)


class CategorySelect(ui.Select):
    def __init__(self, guild: discord.Guild):
        options = []
        for category in guild.categories[:25]:
            options.append(discord.SelectOption(label=category.name, value=str(category.id)))

        super().__init__(
            placeholder='Pilih Category',
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message('Command ini hanya bisa digunakan di server.', ephemeral=True)
            return

        category_id = int(self.values[0])
        category = interaction.guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message('Category tidak ditemukan.', ephemeral=True)
            return

        await interaction.response.send_modal(RenameCategoryModal(category))


class EditCategoryView(ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        self.add_item(CategorySelect(guild))


# Channel Panel View
class ChannelPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='➕ Buat Channel', style=discord.ButtonStyle.blurple, emoji='📝')
    async def create_channel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ChannelModal())

    @ui.button(label='✏️ Edit Category', style=discord.ButtonStyle.gray, emoji='🗂️')
    async def edit_category(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.guild:
            await interaction.response.send_message('Command ini hanya bisa digunakan di server.', ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message('Anda tidak memiliki permission manage_channels.', ephemeral=True)
            return
        if not interaction.guild.categories:
            await interaction.response.send_message('Belum ada category di server ini.', ephemeral=True)
            return

        embed = discord.Embed(
            title='✏️ Edit Category',
            description='Pilih category pada kolom **Category**, lalu isi **Change Name**.',
            color=discord.Color.blurple()
        )
        view = EditCategoryView(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.command(name='channelpanel')
@commands.has_permissions(manage_channels=True)
async def channelpanel(ctx):
    """Tampilkan panel untuk membuat channel"""
    embed = discord.Embed(
        title='📋 Panel Pembuatan Channel',
        description='Klik tombol di bawah untuk membuat channel baru di server.',
        color=discord.Color.blurple()
    )
    embed.add_field(
        name='Cara Menggunakan:',
        value='Klik tombol "Buat Channel" → Isi form dengan:\n'
              '• Nama Category (harus sudah ada)\n'
              '• Nama Channel baru\n'
              '• Tipe: text atau voice\n\n'
              'Klik tombol "Edit Category" → Pilih Category → Isi "Change Name"',
        inline=False
    )
    embed.set_footer(text='Hanya user dengan permission manage_channels yang bisa membuat channel')
    
    view = ChannelPanelView()
    if not await recently_sent(ctx.channel, embed_title=embed.title):
        await ctx.send(embed=embed, view=view)


@bot.command(name='logserver')
@commands.has_permissions(administrator=True)
async def logserver(ctx, channel: discord.TextChannel):
    """Configure a channel to receive member-join logs (Admin only)"""
    try:
        join_log_config[str(ctx.guild.id)] = channel.id
        save_join_config()
        embed = discord.Embed(
            title='✅ Log Server Dikonfigurasi',
            description=f'Log anggota baru akan dikirim ke {channel.mention}',
            color=discord.Color.green()
        )
        if not await recently_sent(ctx.channel, embed_title=embed.title):
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f'Gagal mengatur channel log: {e}', ephemeral=True)


@bot.tree.command(name='logserver', description='Set channel untuk log anggota baru (Admin)')
@app_commands.describe(channel='Channel untuk menerima log anggota baru')
async def logserver_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        await interaction.response.send_message('Command hanya bisa dijalankan di server.', ephemeral=True)
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('Hanya administrator yang bisa menggunakan command ini.', ephemeral=True)
        return
    try:
        join_log_config[str(interaction.guild.id)] = channel.id
        save_join_config()
        embed = discord.Embed(
            title='✅ Log Server Dikonfigurasi',
            description=f'Log anggota baru akan dikirim ke {channel.mention}',
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f'Gagal mengatur channel log: {e}', ephemeral=True)


@bot.command(name='logserver_off')
@commands.has_permissions(administrator=True)
async def logserver_off(ctx):
    """Disable the configured join-log channel for this server"""
    try:
        gid = str(ctx.guild.id)
        if gid in join_log_config:
            del join_log_config[gid]
            save_join_config()
            embed = discord.Embed(
                title='✅ Log Server Dinonaktifkan',
                description='Log anggota baru telah dinonaktifkan untuk server ini.',
                color=discord.Color.orange()
            )
            if not await recently_sent(ctx.channel, embed_title=embed.title):
                await ctx.send(embed=embed)
        else:
            await ctx.send('Belum ada channel log yang dikonfigurasi untuk server ini.')
    except Exception as e:
        await ctx.send(f'Gagal menonaktifkan log: {e}')


@bot.tree.command(name='logserver_off', description='Disable join log for this server (Admin)')
async def logserver_off_slash(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message('Command hanya bisa dijalankan di server.', ephemeral=True)
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('Hanya administrator yang bisa menggunakan command ini.', ephemeral=True)
        return
    try:
        gid = str(interaction.guild.id)
        if gid in join_log_config:
            del join_log_config[gid]
            save_join_config()
            embed = discord.Embed(
                title='✅ Log Server Dinonaktifkan',
                description='Log anggota baru telah dinonaktifkan untuk server ini.',
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message('Belum ada channel log yang dikonfigurasi untuk server ini.', ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f'Gagal menonaktifkan log: {e}', ephemeral=True)


@bot.command(name='setvclobby')
@commands.has_permissions(manage_channels=True)
async def setvclobby(ctx, channel: discord.VoiceChannel):
    """Set voice lobby channel for auto-create temporary voice rooms."""
    try:
        temp_vc_config[str(ctx.guild.id)] = channel.id
        save_temp_vc_config()
        await ctx.send(f'✅ VC lobby diatur ke {channel.mention}. Masuk channel ini untuk membuat room pribadi.')
    except Exception as e:
        await ctx.send(f'Gagal mengatur VC lobby: {e}')


@bot.command(name='setvclobby_off')
@commands.has_permissions(manage_channels=True)
async def setvclobby_off(ctx):
    """Disable voice lobby auto-create for this server."""
    gid = str(ctx.guild.id)
    if gid in temp_vc_config:
        del temp_vc_config[gid]
        save_temp_vc_config()
        await ctx.send('🛑 Fitur auto-create VC dimatikan untuk server ini.')
    else:
        await ctx.send('Belum ada VC lobby yang dikonfigurasi.')


@bot.command(name='vclobby_status')
async def vclobby_status(ctx):
    """Show current VC lobby configuration."""
    gid = str(ctx.guild.id)
    channel_id = temp_vc_config.get(gid)
    if not channel_id:
        await ctx.send('Belum ada VC lobby yang dikonfigurasi.')
        return
    channel = ctx.guild.get_channel(int(channel_id))
    if channel and isinstance(channel, discord.VoiceChannel):
        await ctx.send(f'🎙️ VC lobby aktif: {channel.mention}')
    else:
        await ctx.send('VC lobby tersimpan tapi channel tidak ditemukan. Set ulang dengan `!setvclobby`.')


@bot.tree.command(name='channelpanel')
async def channelpanel_slash(interaction: discord.Interaction):
    """Slash command: show channel creation panel"""
    if not interaction.guild:
        await interaction.response.send_message('Command hanya bisa dijalankan di server.', ephemeral=True)
        return
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message('Anda tidak memiliki permission manage_channels.', ephemeral=True)
        return

    embed = discord.Embed(
        title='📋 Panel Pembuatan Channel',
        description='Klik tombol di bawah untuk membuat channel baru di server.',
        color=discord.Color.blurple()
    )
    embed.add_field(
        name='Cara Menggunakan:',
        value='Klik tombol "Buat Channel" → Isi form dengan:\n'
              '• Nama Category (harus sudah ada)\n'
              '• Nama Channel baru\n'
              '• Tipe: text atau voice\n\n'
              'Klik tombol "Edit Category" → Pilih Category → Isi "Change Name"',
        inline=False
    )
    embed.set_footer(text='Hanya user dengan permission manage_channels yang bisa membuat channel')
    view = ChannelPanelView()
    channel = interaction.channel
    if channel and await recently_sent(channel, embed_title=embed.title):
        await interaction.response.send_message('A similar panel was recently posted; suppressed duplicate.', ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, view=view)

# Update Log Modal
class UpdateLogModal(ui.Modal, title='Buat Log Update'):
    channel_name = ui.TextInput(label='Nama Channel', placeholder='Contoh: announcements', required=True)
    update_title = ui.TextInput(label='Judul Update', placeholder='Contoh: Version 1.0 Released', required=True)
    updates = ui.TextInput(label='Updates (pisahkan dengan koma)', placeholder='Update 1, Update 2', required=False)
    fixes = ui.TextInput(label='Fixes (pisahkan dengan koma)', placeholder='Bug 1, Bug 2', required=False)
    improves_removes = ui.TextInput(label='Improves & Removes (pisahkan dengan |)', placeholder='Improve 1 | Remove 1, Remove 2', required=False)

    async def on_submit(self, interaction: discord.Interaction):
        channel_name = str(self.channel_name)
        update_title = str(self.update_title)
        updates_list = [x.strip() for x in str(self.updates).split(',') if x.strip()]
        fixes_list = [x.strip() for x in str(self.fixes).split(',') if x.strip()]
        
        # Parse improves and removes separated by |
        improves_removes_str = str(self.improves_removes)
        improves_list = []
        removes_list = []
        
        if '|' in improves_removes_str:
            parts = improves_removes_str.split('|')
            if len(parts) > 0:
                improves_list = [x.strip() for x in parts[0].split(',') if x.strip()]
            if len(parts) > 1:
                removes_list = [x.strip() for x in parts[1].split(',') if x.strip()]
        else:
            improves_list = [x.strip() for x in improves_removes_str.split(',') if x.strip()]
        
        # Find the channel
        channel = discord.utils.get(interaction.guild.text_channels, name=channel_name)
        if not channel:
            embed = discord.Embed(
                title='❌ Error',
                description=f'Channel "{channel_name}" tidak ditemukan!',
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Create the update log embed
            embed = discord.Embed(
                title=f'📝 {update_title}',
                color=discord.Color.brand_green()
            )
            
            # Add updates
            if updates_list:
                updates_text = '\n'.join([f'[+] {item}' for item in updates_list])
                embed.add_field(name='✨ Updates', value=updates_text, inline=False)
            
            # Add fixes
            if fixes_list:
                fixes_text = '\n'.join([f'[!] {item}' for item in fixes_list])
                embed.add_field(name='🔧 Bug Fixes', value=fixes_text, inline=False)
            
            # Add improvements
            if improves_list:
                improves_text = '\n'.join([f'[^] {item}' for item in improves_list])
                embed.add_field(name='⬆️ Improvements', value=improves_text, inline=False)
            
            # Add removals
            if removes_list:
                removes_text = '\n'.join([f'[-] {item}' for item in removes_list])
                embed.add_field(name='🗑️ Removals', value=removes_text, inline=False)
            
            embed.set_footer(text=f'Update by {interaction.user.name}')
            
            # Send to channel (avoid duplicates)
            if await recently_sent(channel, embed_title=embed.title):
                await interaction.response.send_message('A similar update was recently posted; suppressed duplicate.', ephemeral=True)
            else:
                await channel.send(embed=embed)
                # Confirm to user
                confirm_embed = discord.Embed(
                    title='✅ Update Log Sent!',
                    description=f'Update log berhasil dikirim ke #{channel.name}',
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title='❌ Error',
                description=f'Gagal mengirim update log: {str(e)}',
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

# Update Log Panel View
class UpdateLogPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='📤 Buat Update Log', style=discord.ButtonStyle.green, emoji='📝')
    async def create_update_log(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(UpdateLogModal())


# Account Creation Modal
class AccountModal(ui.Modal, title='Buat Akun'):
    username = ui.TextInput(label='Username', placeholder='Masukkan username', required=True, max_length=20)
    year_of_birth = ui.TextInput(label='Year of Birth', placeholder='Contoh: 2005', required=True, max_length=4)
    aka = ui.TextInput(label='A.K.A', placeholder='Nama tengah (opsional)', required=False, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message('Command ini hanya bisa digunakan di server.', ephemeral=True)
            return

        year_text = str(self.year_of_birth).strip()
        if not year_text.isdigit():
            await interaction.response.send_message('`Year of Birth` harus berupa angka.', ephemeral=True)
            return

        username_text = str(self.username).strip()
        aka_text = str(self.aka).strip()

        nickname_parts = [username_text]
        if aka_text:
            nickname_parts.append(f'"{aka_text}"')
        nickname_parts.append(year_text)
        new_nickname = ' '.join(nickname_parts)

        if len(new_nickname) > 32:
            await interaction.response.send_message(
                'Nama terlalu panjang. Maksimal 32 karakter setelah digabungkan.',
                ephemeral=True
            )
            return

        try:
            guild = interaction.guild
            member = guild.get_member(interaction.user.id) if guild else None
            if member is None:
                await interaction.response.send_message(
                    'Member tidak ditemukan di server ini.',
                    ephemeral=True
                )
                return

            await member.edit(nick=new_nickname, reason='Account panel setup')

            role_id = 1364265183198969866
            role = guild.get_role(role_id) if guild else None
            role_status = 'Role tidak ditemukan di server.'
            if role:
                try:
                    bot_member = guild.me
                    if not bot_member:
                        role_status = 'Bot member tidak ditemukan.'
                    elif not bot_member.guild_permissions.manage_roles:
                        role_status = 'Bot tidak punya permission Manage Roles.'
                    elif role.managed:
                        role_status = 'Role target adalah managed role dan tidak bisa diberikan manual.'
                    elif role >= bot_member.top_role:
                        role_status = 'Posisi role target lebih tinggi/sama dengan role bot.'
                    elif role in member.roles:
                        role_status = f'Role sudah dimiliki: {role.mention}'
                    else:
                        await member.add_roles(role, reason='Account panel get role')
                        role_status = f'Role diberikan: {role.mention}'
                except discord.Forbidden:
                    role_status = 'Bot tidak punya izin untuk memberikan role.'
                except Exception as role_error:
                    role_status = f'Gagal memberi role: {role_error}'

            embed = discord.Embed(
                title='✅ Account Updated',
                description=f'Nickname kamu berhasil diubah menjadi:\n`{new_nickname}`',
                color=discord.Color.green()
            )
            embed.add_field(name='Role', value=role_status, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                'Bot tidak punya izin untuk mengubah nickname kamu.',
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f'Gagal mengubah nickname: {e}', ephemeral=True)


class AccountPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='➕Get Role', style=discord.ButtonStyle.green, custom_id='accountpanel_get_role')
    async def get_role(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AccountModal())

@bot.command(name='logupdate')
@commands.has_permissions(administrator=True)
async def logupdate(ctx):
    """Tampilkan panel untuk membuat log update"""
    embed = discord.Embed(
        title='📋 Panel Update Log',
        description='Klik tombol di bawah untuk membuat log update server.',
        color=discord.Color.brand_green()
    )
    embed.add_field(
        name='Format Legend:',
        value='[+] = Updates\n[!] = Bug Fixes\n[^] = Improvements\n[-] = Removals',
        inline=False
    )
    embed.add_field(
        name='Cara Input:',
        value='**Updates:** item1, item2, item3\n'
              '**Fixes:** bug1, bug2\n'
              '**Improves & Removes:** improve1, improve2 | remove1, remove2\n\n'
              '⚠️ Gunakan | (pipe) untuk memisahkan Improves dan Removes',
        inline=False
    )
    embed.set_footer(text='Hanya administrator yang bisa membuat update log')
    
    view = UpdateLogPanelView()
    if not await recently_sent(ctx.channel, embed_title=embed.title):
        await ctx.send(embed=embed, view=view)


@bot.command(name='accountpanel')
@commands.has_permissions(administrator=True)
async def accountpanel(ctx, channel: discord.TextChannel):
    """Kirim panel pembuatan akun ke channel target (Admin only)."""
    embed = discord.Embed(
        title='📌 Account Panel',
        description='Klik tombol **Get Role** untuk mengisi data akun.',
        color=discord.Color.blurple()
    )
    embed.add_field(
        name='Format Nickname',
        value='`Username A.K.A YearOfBirth`\nContoh: `Raven Shadow 2004`',
        inline=False
    )
    embed.add_field(
        name='Ketentuan',
        value='- Username anda (terserah)\n- Year of Birth wajib angka\n- A.K.A opsional (nama tengah)',
        inline=False
    )
    view = AccountPanelView()

    if not await recently_sent(channel, embed_title=embed.title):
        await channel.send(embed=embed, view=view)
    await ctx.send(f'Panel account berhasil dikirim ke {channel.mention}.')


@bot.tree.command(name='logupdate')
async def logupdate_slash(interaction: discord.Interaction):
    """Slash command: show update log panel (admin only)"""
    if not interaction.guild:
        await interaction.response.send_message('Command hanya bisa dijalankan di server.', ephemeral=True)
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('Hanya administrator yang bisa menggunakan command ini.', ephemeral=True)
        return

    embed = discord.Embed(
        title='📋 Panel Update Log',
        description='Klik tombol di bawah untuk membuat log update server.',
        color=discord.Color.brand_green()
    )
    embed.add_field(
        name='Format Legend:',
        value='[+] = Updates\n[!] = Bug Fixes\n[^] = Improvements\n[-] = Removals',
        inline=False
    )
    embed.add_field(
        name='Cara Input:',
        value='**Updates:** item1, item2, item3\n'
              '**Fixes:** bug1, bug2\n'
              '**Improves & Removes:** improve1, improve2 | remove1, remove2\n\n'
              '⚠️ Gunakan | (pipe) untuk memisahkan Improves dan Removes',
        inline=False
    )
    embed.set_footer(text='Hanya administrator yang bisa membuat update log')
    view = UpdateLogPanelView()
    channel = interaction.channel
    if channel and await recently_sent(channel, embed_title=embed.title):
        await interaction.response.send_message('A similar panel was recently posted; suppressed duplicate.', ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, view=view)

@bot.command(name='help_custom')
async def help_custom(ctx):
    """Show custom help message"""
    embed = discord.Embed(
        title='🤖 Bot Commands - irengG Bot',
        description='Berikut adalah daftar semua command yang tersedia. Gunakan prefix `!` untuk menjalankan command.',
        color=discord.Color.green()
    )
    embed.add_field(name='📊 **UTILITY COMMANDS**', value='', inline=False)
    embed.add_field(name='`!ping`', value='Cek latency/ping bot ke Discord', inline=False)
    embed.add_field(name='`!hello`', value='Bot memberikan salam kepada Anda', inline=False)
    embed.add_field(name='`!user`', value='Tampilkan informasi profil Anda', inline=False)
    embed.add_field(name='`!help`', value='Tampilkan daftar command ini', inline=False)
    embed.add_field(name='`!mood [hari]`', value='Lihat analisa mood server (positif/netral/negatif/toxic)', inline=False)
    
    embed.add_field(name='🎮 **GAMES** (Fun)', value='', inline=False)
    embed.add_field(name='`!blackjack`', value='Bermain Blackjack melawan Dealer', inline=False)
    embed.add_field(name='`!qq`', value='Bermain minigame kartu QQ (3 kartu)', inline=False)
    embed.add_field(name='`!tebakkata` / `!jawabkata <kata>`', value='Game acak huruf jadi kata (reply game: `!clue` / `!surrend`)', inline=False)
    embed.add_field(name='`!tebakgambar` / `!jawabgambar <jawaban>`', value='Tebak gambar dari emoji clue (reply game: `!clue` / `!surrend`)', inline=False)
    embed.add_field(name='`!trivia` / `!jawabtrivia <A/B/C/D>`', value='Quiz pilihan ganda', inline=False)
    embed.add_field(name='`!heist @user`', value='Coba curi poin dari user lain (ada cooldown)', inline=False)
    embed.add_field(name='`!sambungkata`, `!kata <kata>`, `!sambungstop`', value='Main sambung kata di channel', inline=False)
    embed.add_field(name='`!poin` / `!leaderboard`', value='Cek poin dan ranking', inline=False)
    
    embed.add_field(name='⚙️ **MODERATION COMMANDS** (Admin Only)', value='', inline=False)
    embed.add_field(name='`!kick @user [alasan]`', value='Kick user dari server', inline=False)
    embed.add_field(name='`!ban @user [alasan]`', value='Ban user dari server secara permanen', inline=False)
    embed.add_field(name='`!clear [jumlah]`', value='Hapus pesan tertentu di channel', inline=False)
    
    embed.add_field(name='🛠️ **SERVER MANAGEMENT** (Admin Only)', value='', inline=False)
    embed.add_field(name='`!channelpanel`', value='Buka panel interaktif untuk membuat channel', inline=False)
    embed.add_field(name='`!logupdate`', value='Buka panel untuk membuat log update server', inline=False)
    embed.add_field(name='`!accountpanel #channel`', value='Kirim panel pembuatan akun ke channel target', inline=False)
    embed.add_field(name='`!setvclobby #voice`', value='Set channel voice lobby untuk auto-create room pribadi', inline=False)
    embed.add_field(name='`!setvclobby_off` / `!vclobby_status`', value='Matikan atau cek status lobby VC', inline=False)
    embed.add_field(name='`!debat_mulai <detik> <round> <topik>`', value='Buat sesi debat terstruktur + timer giliran', inline=False)
    
    
    embed.set_footer(text='💡 Tip: Gunakan !command untuk menjalankan perintah')
    await ctx.send(embed=embed)

# ==================== BLACKJACK GAME ====================
import random

class Card:
    """Represents a playing card"""
    SUITS = ['♠️', '♥️', '♦️', '♣️']
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    
    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank
    
    def __str__(self) -> str:
        return f'{self.rank}{self.suit}'
    
    def value(self) -> int:
        """Return card value for blackjack"""
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11
        else:
            return int(self.rank)


class Deck:
    """Represents a deck of cards"""
    def __init__(self, num_decks: int = 1):
        self.cards = []
        for _ in range(num_decks):
            for suit in Card.SUITS:
                for rank in Card.RANKS:
                    self.cards.append(Card(suit, rank))
        random.shuffle(self.cards)
    
    def draw(self) -> Card:
        """Draw a card from the deck"""
        if len(self.cards) < 10:  # Reshuffle if getting low
            self.__init__()
        return self.cards.pop()


def calculate_hand_value(cards: list) -> tuple:
    """Calculate hand value and return (value, is_soft)
    is_soft = True if hand can be adjusted (has usable Ace)
    """
    total = 0
    aces = 0
    
    for card in cards:
        if card.rank == 'A':
            aces += 1
            total += 11
        else:
            total += card.value()
    
    # Adjust for Aces if needed
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    
    is_soft = aces > 0 and total + 10 <= 21
    return total, is_soft


class BlackjackGame:
    """Manages a Blackjack game"""
    def __init__(self, player_id: int):
        self.player_id = player_id
        self.deck = Deck(num_decks=1)
        self.player_hand = [self.deck.draw(), self.deck.draw()]
        self.dealer_hand = [self.deck.draw(), self.deck.draw()]
        self.game_over = False
        self.result = None
    
    def player_hit(self) -> Card:
        """Player draws a card"""
        card = self.deck.draw()
        self.player_hand.append(card)
        
        value, _ = calculate_hand_value(self.player_hand)
        if value > 21:
            self.game_over = True
            self.result = '❌ BUST! Kartu Anda melebihi 21!'
        
        return card
    
    def player_stand(self):
        """Player stands, dealer plays"""
        self.game_over = True
        self.play_dealer()
    
    def play_dealer(self):
        """Dealer plays their hand (hits until 17 or above)"""
        dealer_value, dealer_soft = calculate_hand_value(self.dealer_hand)
        
        while dealer_value < 17 or (dealer_value == 17 and dealer_soft):
            self.dealer_hand.append(self.deck.draw())
            dealer_value, dealer_soft = calculate_hand_value(self.dealer_hand)
        
        # Compare hands
        player_value, _ = calculate_hand_value(self.player_hand)
        
        if dealer_value > 21:
            self.result = f'✅ MENANG! Dealer BUST! Anda: {player_value} vs Dealer: BUST'
        elif player_value > dealer_value:
            self.result = f'✅ MENANG! Anda: {player_value} vs Dealer: {dealer_value}'
        elif player_value < dealer_value:
            self.result = f'❌ KALAH! Anda: {player_value} vs Dealer: {dealer_value}'
        else:
            self.result = f'🤝 SERI! Anda: {player_value} vs Dealer: {dealer_value}'
    
    def check_blackjack(self) -> bool:
        """Check if either player or dealer has blackjack"""
        player_value, _ = calculate_hand_value(self.player_hand)
        dealer_value, _ = calculate_hand_value(self.dealer_hand)
        
        if player_value == 21 and len(self.player_hand) == 2:
            self.game_over = True
            self.result = '⭐ BLACKJACK! Anda mendapatkan 21 dengan 2 kartu!'
            return True
        
        if dealer_value == 21 and len(self.dealer_hand) == 2:
            self.game_over = True
            self.result = '❌ Dealer mendapatkan Blackjack! Anda kalah.'
            return True
        
        return False


class BlackjackView(ui.View):
    """Game controls for Blackjack"""
    def __init__(self, game: BlackjackGame, channel: discord.abc.Messageable, user: discord.User):
        super().__init__(timeout=60)
        self.game = game
        self.channel = channel
        self.user = user
        self.message = None
    
    @ui.button(label='🎴 HIT', style=discord.ButtonStyle.primary, emoji='➕')
    async def hit_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.game.player_id:
            await interaction.response.send_message('Bukan giliran Anda!', ephemeral=True)
            return
        
        card = self.game.player_hit()
        embed = self.create_embed()
        
        if self.game.game_over:
            self.hit_button.disabled = True
            self.stand_button.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @ui.button(label='🛑 STAND', style=discord.ButtonStyle.danger, emoji='⏹️')
    async def stand_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.game.player_id:
            await interaction.response.send_message('Bukan giliran Anda!', ephemeral=True)
            return
        
        self.game.player_stand()
        embed = self.create_embed()
        
        self.hit_button.disabled = True
        self.stand_button.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    def create_embed(self) -> discord.Embed:
        """Create game embed"""
        player_value, player_soft = calculate_hand_value(self.game.player_hand)
        dealer_value, dealer_soft = calculate_hand_value(self.game.dealer_hand)
        
        embed = discord.Embed(
            title='🎰 BLACKJACK',
            color=discord.Color.green() if not self.game.game_over else discord.Color.gold()
        )
        
        # Dealer hand
        dealer_cards = ' '.join(str(card) for card in self.game.dealer_hand)
        if self.game.game_over:
            embed.add_field(
                name=f'🎴 Dealer [{dealer_value}]',
                value=dealer_cards,
                inline=False
            )
        else:
            # Hide first dealer card during game
            hidden_card = '🂠'
            visible_cards = ' '.join(str(card) for card in self.game.dealer_hand[1:])
            embed.add_field(
                name=f'🎴 Dealer [?]',
                value=f'{hidden_card} {visible_cards}',
                inline=False
            )
        
        # Player hand
        player_cards = ' '.join(str(card) for card in self.game.player_hand)
        soft_text = ' (Soft)' if player_soft else ''
        embed.add_field(
            name=f'👤 Anda [{player_value}]{soft_text}',
            value=player_cards,
            inline=False
        )
        
        # Status
        if self.game.game_over:
            embed.add_field(name='📊 Hasil', value=self.game.result, inline=False)
        else:
            embed.add_field(name='📊 Status', value='Pilih: Hit atau Stand', inline=False)
        
        embed.set_footer(text=f'Player: {self.user.name}')
        return embed


@bot.command(name='blackjack', aliases=['bj'])
async def blackjack(ctx):
    """Play Blackjack against the dealer"""
    game = BlackjackGame(ctx.author.id)
    
    # Check for initial blackjack
    if game.check_blackjack():
        embed = discord.Embed(
            title='🎰 BLACKJACK - GAME OVER',
            color=discord.Color.gold()
        )
        dealer_value, _ = calculate_hand_value(game.dealer_hand)
        player_value, _ = calculate_hand_value(game.player_hand)
        
        player_cards = ' '.join(str(card) for card in game.player_hand)
        dealer_cards = ' '.join(str(card) for card in game.dealer_hand)
        
        embed.add_field(name=f'🎴 Dealer [{dealer_value}]', value=dealer_cards, inline=False)
        embed.add_field(name=f'👤 Anda [{player_value}]', value=player_cards, inline=False)
        embed.add_field(name='📊 Hasil', value=game.result, inline=False)
        
        await ctx.send(embed=embed)
        return
    
    # Create game view
    view = BlackjackView(game, ctx.channel, ctx.author)
    
    # Create initial embed
    player_value, player_soft = calculate_hand_value(game.player_hand)
    
    embed = discord.Embed(
        title='🎰 BLACKJACK',
        description='Kalahkan Dealer! Dapatkan nilai tertinggi tanpa melebihi 21.',
        color=discord.Color.green()
    )
    
    # Dealer hand (hide first card)
    dealer_cards = ' '.join(str(card) for card in game.dealer_hand[1:])
    embed.add_field(
        name='🎴 Dealer [?]',
        value=f'🂠 {dealer_cards}',
        inline=False
    )
    
    # Player hand
    player_cards = ' '.join(str(card) for card in game.player_hand)
    soft_text = ' (Soft)' if player_soft else ''
    embed.add_field(
        name=f'👤 Anda [{player_value}]{soft_text}',
        value=player_cards,
        inline=False
    )
    
    embed.add_field(name='📊 Status', value='Pilih: Hit atau Stand', inline=False)
    embed.set_footer(text=f'Player: {ctx.author.name}')
    
    await ctx.send(embed=embed, view=view)


@bot.tree.command(name='blackjack', description='Bermain Blackjack melawan Dealer')
async def blackjack_slash(interaction: discord.Interaction):
    """Slash command: Play Blackjack"""
    game = BlackjackGame(interaction.user.id)
    
    # Check for initial blackjack
    if game.check_blackjack():
        embed = discord.Embed(
            title='🎰 BLACKJACK - GAME OVER',
            color=discord.Color.gold()
        )
        dealer_value, _ = calculate_hand_value(game.dealer_hand)
        player_value, _ = calculate_hand_value(game.player_hand)
        
        player_cards = ' '.join(str(card) for card in game.player_hand)
        dealer_cards = ' '.join(str(card) for card in game.dealer_hand)
        
        embed.add_field(name=f'🎴 Dealer [{dealer_value}]', value=dealer_cards, inline=False)
        embed.add_field(name=f'👤 Anda [{player_value}]', value=player_cards, inline=False)
        embed.add_field(name='📊 Hasil', value=game.result, inline=False)
        
        await interaction.response.send_message(embed=embed)
        return
    
    # Create game view
    view = BlackjackView(game, interaction.channel, interaction.user)
    
    # Create initial embed
    player_value, player_soft = calculate_hand_value(game.player_hand)
    
    embed = discord.Embed(
        title='🎰 BLACKJACK',
        description='Kalahkan Dealer! Dapatkan nilai tertinggi tanpa melebihi 21.',
        color=discord.Color.green()
    )
    
    # Dealer hand (hide first card)
    dealer_cards = ' '.join(str(card) for card in game.dealer_hand[1:])
    embed.add_field(
        name='🎴 Dealer [?]',
        value=f'🂠 {dealer_cards}',
        inline=False
    )
    
    # Player hand
    player_cards = ' '.join(str(card) for card in game.player_hand)
    soft_text = ' (Soft)' if player_soft else ''
    embed.add_field(
        name=f'👤 Anda [{player_value}]{soft_text}',
        value=player_cards,
        inline=False
    )
    
    embed.add_field(name='📊 Status', value='Pilih: Hit atau Stand', inline=False)
    embed.set_footer(text=f'Player: {interaction.user.name}')
    
    await interaction.response.send_message(embed=embed, view=view)

# =====================================================

# ====================== QQ CARD GAME ======================
def qq_card_value(card: Card) -> int:
    """Return card value for QQ game (10/J/Q/K=0, A=1, others face value)."""
    if card.rank in ['10', 'J', 'Q', 'K']:
        return 0
    if card.rank == 'A':
        return 1
    return int(card.rank)


def qq_hand_value(cards: list[Card]) -> int:
    """Return QQ hand value (sum mod 10)."""
    total = sum(qq_card_value(card) for card in cards)
    return total % 10


class QQGame:
    """Simple QQ game: deal 3 cards each, compare values."""
    def __init__(self, player_id: int):
        self.player_id = player_id
        self.deck = Deck(num_decks=1)
        self.player_hand = [self.deck.draw(), self.deck.draw(), self.deck.draw()]
        self.dealer_hand = [self.deck.draw(), self.deck.draw(), self.deck.draw()]
        self.player_value = qq_hand_value(self.player_hand)
        self.dealer_value = qq_hand_value(self.dealer_hand)
        self.result = self._resolve_result()

    def _resolve_result(self) -> str:
        if self.player_value > self.dealer_value:
            return f'MENANG! Anda: {self.player_value} vs Dealer: {self.dealer_value}'
        if self.player_value < self.dealer_value:
            return f'KALAH! Anda: {self.player_value} vs Dealer: {self.dealer_value}'
        return f'SERI! Anda: {self.player_value} vs Dealer: {self.dealer_value}'


def qq_value_label(value: int) -> str:
    """Human-friendly label for QQ value."""
    if value == 0:
        return 'QQ'
    return f'QQ {value}'


@bot.command(name='qq')
async def qq(ctx):
    """Play QQ card minigame (3 cards, sum mod 10)."""
    game = QQGame(ctx.author.id)

    player_cards = ' '.join(str(card) for card in game.player_hand)
    dealer_cards = ' '.join(str(card) for card in game.dealer_hand)

    embed = discord.Embed(
        title='QQ CARD',
        description='3 kartu: 10/J/Q/K=0, A=1, total mod 10.',
        color=discord.Color.green() if game.player_value >= game.dealer_value else discord.Color.red()
    )
    embed.add_field(
        name=f'Dealer [{qq_value_label(game.dealer_value)}]',
        value=dealer_cards,
        inline=False
    )
    embed.add_field(
        name=f'Anda [{qq_value_label(game.player_value)}]',
        value=player_cards,
        inline=False
    )
    embed.add_field(name='Hasil', value=game.result, inline=False)
    embed.set_footer(text=f'Player: {ctx.author.name}')

    if not await recently_sent(ctx.channel, embed_title=embed.title):
        await ctx.send(embed=embed)


@bot.tree.command(name='qq', description='Bermain minigame kartu QQ (3 kartu)')
async def qq_slash(interaction: discord.Interaction):
    """Slash command: Play QQ card minigame."""
    game = QQGame(interaction.user.id)

    player_cards = ' '.join(str(card) for card in game.player_hand)
    dealer_cards = ' '.join(str(card) for card in game.dealer_hand)

    embed = discord.Embed(
        title='QQ CARD',
        description='3 kartu: 10/J/Q/K=0, A=1, total mod 10.',
        color=discord.Color.green() if game.player_value >= game.dealer_value else discord.Color.red()
    )
    embed.add_field(
        name=f'Dealer [{qq_value_label(game.dealer_value)}]',
        value=dealer_cards,
        inline=False
    )
    embed.add_field(
        name=f'Anda [{qq_value_label(game.player_value)}]',
        value=player_cards,
        inline=False
    )
    embed.add_field(name='Hasil', value=game.result, inline=False)
    embed.set_footer(text=f'Player: {interaction.user.name}')

    channel = interaction.channel
    if channel and await recently_sent(channel, embed_title=embed.title):
        await interaction.response.send_message('A similar result was recently posted; suppressed duplicate.', ephemeral=True)
        return
    await interaction.response.send_message(embed=embed)

# ====================== MINI GAMES PACK (1,2,3,7,8) ======================
GAME_DATA_PATH = Path('game_data.json')

def load_game_data() -> dict:
    try:
        if GAME_DATA_PATH.exists():
            with GAME_DATA_PATH.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault('points', {})
                    data.setdefault('cooldowns', {})
                    return data
    except Exception:
        pass
    return {'points': {}, 'cooldowns': {}}

game_data = load_game_data()

def save_game_data() -> None:
    try:
        with GAME_DATA_PATH.open('w', encoding='utf-8') as f:
            json.dump(game_data, f, indent=2)
    except Exception:
        pass

def ensure_user_data(user_id: int) -> None:
    uid = str(user_id)
    game_data['points'].setdefault(uid, 0)
    game_data['cooldowns'].setdefault(uid, {})

def get_points(user_id: int) -> int:
    ensure_user_data(user_id)
    return int(game_data['points'][str(user_id)])

def add_points(user_id: int, amount: int) -> int:
    ensure_user_data(user_id)
    uid = str(user_id)
    game_data['points'][uid] = max(0, int(game_data['points'][uid]) + int(amount))
    save_game_data()
    return int(game_data['points'][uid])

def transfer_points(from_user_id: int, to_user_id: int, amount: int) -> int:
    ensure_user_data(from_user_id)
    ensure_user_data(to_user_id)
    amount = max(0, int(amount))
    from_uid = str(from_user_id)
    to_uid = str(to_user_id)
    real_amount = min(amount, int(game_data['points'][from_uid]))
    game_data['points'][from_uid] = int(game_data['points'][from_uid]) - real_amount
    game_data['points'][to_uid] = int(game_data['points'][to_uid]) + real_amount
    save_game_data()
    return real_amount

def set_cooldown(user_id: int, key: str, seconds: int) -> None:
    ensure_user_data(user_id)
    expiry = int(datetime.now(timezone.utc).timestamp()) + int(seconds)
    game_data['cooldowns'][str(user_id)][key] = expiry
    save_game_data()

def cooldown_remaining(user_id: int, key: str) -> int:
    ensure_user_data(user_id)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    expiry = int(game_data['cooldowns'][str(user_id)].get(key, 0))
    return max(0, expiry - now_ts)

def shuffle_word(word: str) -> str:
    chars = list(word)
    if len(chars) < 2:
        return word
    for _ in range(10):
        random.shuffle(chars)
        candidate = ''.join(chars)
        if candidate.lower() != word.lower():
            return candidate
    return ''.join(chars)

def build_word_clue(answer: str) -> str:
    if len(answer) <= 2:
        return answer
    middle_len = max(0, len(answer) - 2)
    return f'{answer[0]}{"_" * middle_len}{answer[-1]} ({len(answer)} huruf)'

tebak_kata_active: dict[int, dict] = {}
tebak_gambar_active: dict[int, dict] = {}
trivia_active: dict[int, dict] = {}
sambung_kata_active: dict[int, dict] = {}

WORD_BANK = [
    'komputer', 'discord', 'python', 'internet', 'keyboard', 'monitor',
    'program', 'database', 'jaringan', 'teknologi', 'aplikasi', 'algoritma'
]

EMOJI_CLUES = [
    ('pizza', '🍕🧀🍅'),
    ('hujan', '☁️🌧️☔'),
    ('kucing', '🐱🐾🐟'),
    ('pantai', '🏖️🌊☀️'),
    ('sekolah', '🏫📚📝'),
    ('pesawat', '✈️☁️🧳'),
    ('kopi', '☕🌙💻'),
    ('rumah', '🏠🛋️🚪')
]

TRIVIA_BANK = [
    {'question': 'Planet terbesar di tata surya adalah...', 'options': {'A': 'Mars', 'B': 'Jupiter', 'C': 'Bumi', 'D': 'Saturnus'}, 'answer': 'B'},
    {'question': 'Bahasa pemrograman yang kamu pakai sekarang untuk bot ini adalah...', 'options': {'A': 'Java', 'B': 'Go', 'C': 'Python', 'D': 'Rust'}, 'answer': 'C'},
    {'question': 'Siapa penemu lampu pijar yang populer secara komersial?', 'options': {'A': 'Nikola Tesla', 'B': 'Thomas Edison', 'C': 'Albert Einstein', 'D': 'Galileo Galilei'}, 'answer': 'B'},
    {'question': 'Hasil dari 9 x 8 adalah...', 'options': {'A': '72', 'B': '81', 'C': '64', 'D': '69'}, 'answer': 'A'}
]

@bot.command(name='poin')
async def poin(ctx):
    points = get_points(ctx.author.id)
    await ctx.send(f'🏆 {ctx.author.mention} punya **{points} poin**.')

@bot.tree.command(name='poin', description='Lihat total poin kamu')
async def poin_slash(interaction: discord.Interaction):
    points = get_points(interaction.user.id)
    await interaction.response.send_message(f'🏆 Kamu punya **{points} poin**.')

@bot.command(name='leaderboard')
async def leaderboard(ctx):
    points_map = game_data.get('points', {})
    if not points_map:
        await ctx.send('Belum ada data poin.')
        return
    sorted_users = sorted(points_map.items(), key=lambda x: int(x[1]), reverse=True)[:10]
    lines = []
    for i, (uid, pts) in enumerate(sorted_users, start=1):
        member = ctx.guild.get_member(int(uid)) if ctx.guild else None
        name = member.display_name if member else f'User {uid}'
        lines.append(f'{i}. {name} - {pts} poin')
    embed = discord.Embed(title='🏅 Leaderboard Poin', description='\n'.join(lines), color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.tree.command(name='leaderboard', description='Lihat leaderboard poin server')
async def leaderboard_slash(interaction: discord.Interaction):
    points_map = game_data.get('points', {})
    if not points_map:
        await interaction.response.send_message('Belum ada data poin.')
        return
    sorted_users = sorted(points_map.items(), key=lambda x: int(x[1]), reverse=True)[:10]
    lines = []
    guild = interaction.guild
    for i, (uid, pts) in enumerate(sorted_users, start=1):
        member = guild.get_member(int(uid)) if guild else None
        name = member.display_name if member else f'User {uid}'
        lines.append(f'{i}. {name} - {pts} poin')
    embed = discord.Embed(title='🏅 Leaderboard Poin', description='\n'.join(lines), color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.command(name='tebakkata')
async def tebak_kata(ctx):
    channel_id = ctx.channel.id
    answer = random.choice(WORD_BANK)
    scrambled = shuffle_word(answer)
    prompt = await ctx.send(f'🔤 Tebak kata: **{scrambled}**\nJawab dengan `!jawabkata <kata>`\nReply pesan ini dengan `!clue` atau `!surrend`')
    tebak_kata_active[channel_id] = {'answer': answer.lower(), 'prompt_id': prompt.id}

@bot.command(name='jawabkata')
async def jawab_kata(ctx, *, jawaban: str):
    channel_id = ctx.channel.id
    if channel_id not in tebak_kata_active:
        await ctx.send('Belum ada game tebak kata aktif. Mulai dengan `!tebakkata`.')
        return
    answer = tebak_kata_active[channel_id]['answer']
    if jawaban.strip().lower() == answer:
        new_pts = add_points(ctx.author.id, 10)
        del tebak_kata_active[channel_id]
        await ctx.send(f'✅ Benar, {ctx.author.mention}! +10 poin. Total kamu: **{new_pts}**')
    else:
        await ctx.send('❌ Salah. Coba lagi.')

@bot.tree.command(name='tebak_kata', description='Mulai game Tebak Kata')
async def tebak_kata_slash(interaction: discord.Interaction):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    answer = random.choice(WORD_BANK)
    scrambled = shuffle_word(answer)
    await interaction.response.send_message(f'🔤 Tebak kata: **{scrambled}**\nJawab dengan `/jawab_kata`')
    prompt = await interaction.original_response()
    tebak_kata_active[channel.id] = {'answer': answer.lower(), 'prompt_id': prompt.id}

@bot.tree.command(name='jawab_kata', description='Jawab game Tebak Kata')
@app_commands.describe(jawaban='Jawaban kamu')
async def jawab_kata_slash(interaction: discord.Interaction, jawaban: str):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    if channel.id not in tebak_kata_active:
        await interaction.response.send_message('Belum ada game tebak kata aktif di channel ini.')
        return
    answer = tebak_kata_active[channel.id]['answer']
    if jawaban.strip().lower() == answer:
        new_pts = add_points(interaction.user.id, 10)
        del tebak_kata_active[channel.id]
        await interaction.response.send_message(f'✅ Benar! +10 poin. Total kamu: **{new_pts}**')
    else:
        await interaction.response.send_message('❌ Salah. Coba lagi.')

@bot.command(name='tebakgambar')
async def tebak_gambar(ctx):
    channel_id = ctx.channel.id
    answer, clue = random.choice(EMOJI_CLUES)
    prompt = await ctx.send(f'🧩 Tebak gambar dari emoji ini: {clue}\nJawab dengan `!jawabgambar <jawaban>`\nReply pesan ini dengan `!clue` atau `!surrend`')
    tebak_gambar_active[channel_id] = {'answer': answer.lower(), 'prompt_id': prompt.id}

@bot.command(name='jawabgambar')
async def jawab_gambar(ctx, *, jawaban: str):
    channel_id = ctx.channel.id
    if channel_id not in tebak_gambar_active:
        await ctx.send('Belum ada game tebak gambar aktif. Mulai dengan `!tebakgambar`.')
        return
    answer = tebak_gambar_active[channel_id]['answer']
    if jawaban.strip().lower() == answer:
        new_pts = add_points(ctx.author.id, 10)
        del tebak_gambar_active[channel_id]
        await ctx.send(f'✅ Tepat! +10 poin, {ctx.author.mention}. Total: **{new_pts}**')
    else:
        await ctx.send('❌ Belum tepat. Coba lagi.')

@bot.tree.command(name='tebak_gambar', description='Mulai game Tebak Gambar dari emoji')
async def tebak_gambar_slash(interaction: discord.Interaction):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    answer, clue = random.choice(EMOJI_CLUES)
    await interaction.response.send_message(f'🧩 Tebak gambar dari emoji ini: {clue}\nJawab dengan `/jawab_gambar`')
    prompt = await interaction.original_response()
    tebak_gambar_active[channel.id] = {'answer': answer.lower(), 'prompt_id': prompt.id}

@bot.tree.command(name='jawab_gambar', description='Jawab game Tebak Gambar')
@app_commands.describe(jawaban='Jawaban kamu')
async def jawab_gambar_slash(interaction: discord.Interaction, jawaban: str):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    if channel.id not in tebak_gambar_active:
        await interaction.response.send_message('Belum ada game tebak gambar aktif di channel ini.')
        return
    answer = tebak_gambar_active[channel.id]['answer']
    if jawaban.strip().lower() == answer:
        new_pts = add_points(interaction.user.id, 10)
        del tebak_gambar_active[channel.id]
        await interaction.response.send_message(f'✅ Tepat! +10 poin. Total kamu: **{new_pts}**')
    else:
        await interaction.response.send_message('❌ Belum tepat. Coba lagi.')

async def get_replied_message(ctx):
    ref = ctx.message.reference
    if not ref or not ref.message_id:
        return None
    if isinstance(ref.resolved, discord.Message):
        return ref.resolved
    try:
        return await ctx.channel.fetch_message(ref.message_id)
    except Exception:
        return None

@bot.command(name='clue')
async def clue(ctx):
    replied = await get_replied_message(ctx)
    if not replied or replied.author != bot.user:
        await ctx.send('Gunakan `!clue` dengan cara reply pesan game dari bot.')
        return

    channel_id = ctx.channel.id
    kata_state = tebak_kata_active.get(channel_id)
    if kata_state and replied.id == kata_state.get('prompt_id'):
        answer = kata_state['answer']
        await ctx.send(f'💡 Clue Tebak Kata: `{build_word_clue(answer)}`')
        return

    gambar_state = tebak_gambar_active.get(channel_id)
    if gambar_state and replied.id == gambar_state.get('prompt_id'):
        answer = gambar_state['answer']
        await ctx.send(f'💡 Clue Tebak Gambar: diawali huruf **{answer[0].upper()}**, total **{len(answer)}** huruf.')
        return

    await ctx.send('Pesan yang kamu reply bukan sesi Tebak Kata/Tebak Gambar yang sedang aktif.')

@bot.command(name='surrend', aliases=['surrender'])
async def surrend(ctx):
    replied = await get_replied_message(ctx)
    if not replied or replied.author != bot.user:
        await ctx.send('Gunakan `!surrend` dengan cara reply pesan game dari bot.')
        return

    channel_id = ctx.channel.id
    kata_state = tebak_kata_active.get(channel_id)
    if kata_state and replied.id == kata_state.get('prompt_id'):
        answer = kata_state['answer']
        del tebak_kata_active[channel_id]
        await ctx.send(f'🏳️ Menyerah. Jawaban Tebak Kata: **{answer}**')
        return

    gambar_state = tebak_gambar_active.get(channel_id)
    if gambar_state and replied.id == gambar_state.get('prompt_id'):
        answer = gambar_state['answer']
        del tebak_gambar_active[channel_id]
        await ctx.send(f'🏳️ Menyerah. Jawaban Tebak Gambar: **{answer}**')
        return

    await ctx.send('Pesan yang kamu reply bukan sesi Tebak Kata/Tebak Gambar yang sedang aktif.')

@bot.command(name='trivia')
async def trivia(ctx):
    channel_id = ctx.channel.id
    q = random.choice(TRIVIA_BANK)
    trivia_active[channel_id] = q
    options_text = '\n'.join([f'**{k}.** {v}' for k, v in q['options'].items()])
    embed = discord.Embed(title='🧠 Trivia Quiz', description=q['question'], color=discord.Color.blurple())
    embed.add_field(name='Pilihan', value=options_text, inline=False)
    embed.set_footer(text='Jawab dengan !jawabtrivia <A/B/C/D>')
    await ctx.send(embed=embed)

@bot.command(name='jawabtrivia')
async def jawab_trivia(ctx, pilihan: str):
    channel_id = ctx.channel.id
    if channel_id not in trivia_active:
        await ctx.send('Belum ada trivia aktif. Mulai dengan `!trivia`.')
        return
    pilihan = pilihan.strip().upper()
    if pilihan not in ['A', 'B', 'C', 'D']:
        await ctx.send('Gunakan pilihan: A, B, C, atau D.')
        return
    q = trivia_active[channel_id]
    if pilihan == q['answer']:
        new_pts = add_points(ctx.author.id, 12)
        del trivia_active[channel_id]
        await ctx.send(f'✅ Jawaban benar! +12 poin. Total kamu: **{new_pts}**')
    else:
        await ctx.send('❌ Salah. Coba lagi.')

@bot.tree.command(name='trivia', description='Mulai Trivia Quiz')
async def trivia_slash(interaction: discord.Interaction):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    q = random.choice(TRIVIA_BANK)
    trivia_active[channel.id] = q
    options_text = '\n'.join([f'**{k}.** {v}' for k, v in q['options'].items()])
    embed = discord.Embed(title='🧠 Trivia Quiz', description=q['question'], color=discord.Color.blurple())
    embed.add_field(name='Pilihan', value=options_text, inline=False)
    embed.set_footer(text='Jawab dengan /jawab_trivia')
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='jawab_trivia', description='Jawab pertanyaan trivia aktif')
@app_commands.describe(pilihan='A / B / C / D')
async def jawab_trivia_slash(interaction: discord.Interaction, pilihan: str):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    if channel.id not in trivia_active:
        await interaction.response.send_message('Belum ada trivia aktif di channel ini.')
        return
    pilihan = pilihan.strip().upper()
    if pilihan not in ['A', 'B', 'C', 'D']:
        await interaction.response.send_message('Gunakan pilihan: A, B, C, atau D.')
        return
    q = trivia_active[channel.id]
    if pilihan == q['answer']:
        new_pts = add_points(interaction.user.id, 12)
        del trivia_active[channel.id]
        await interaction.response.send_message(f'✅ Benar! +12 poin. Total kamu: **{new_pts}**')
    else:
        await interaction.response.send_message('❌ Salah. Coba lagi.')

@bot.command(name='heist')
async def heist(ctx, target: discord.Member):
    if target.bot:
        await ctx.send('Tidak bisa nge-heist bot.')
        return
    if target.id == ctx.author.id:
        await ctx.send('Tidak bisa nge-heist diri sendiri.')
        return
    remain = cooldown_remaining(ctx.author.id, 'heist')
    if remain > 0:
        await ctx.send(f'⏳ Cooldown heist: {remain}s lagi.')
        return
    if get_points(ctx.author.id) == 0:
        add_points(ctx.author.id, 50)
    if get_points(target.id) == 0:
        add_points(target.id, 50)
    success = random.random() < 0.55
    set_cooldown(ctx.author.id, 'heist', 120)
    if success:
        amount = random.randint(10, 40)
        stolen = transfer_points(target.id, ctx.author.id, amount)
        await ctx.send(f'💰 {ctx.author.mention} berhasil nge-heist {target.mention} dan dapat **{stolen} poin**!')
    else:
        penalty = random.randint(8, 25)
        paid = transfer_points(ctx.author.id, target.id, penalty)
        await ctx.send(f'🚨 Heist gagal! {ctx.author.mention} ketahuan dan bayar denda **{paid} poin** ke {target.mention}.')

@bot.tree.command(name='heist', description='Coba curi poin dari user lain')
@app_commands.describe(target='Target heist')
async def heist_slash(interaction: discord.Interaction, target: discord.Member):
    if target.bot:
        await interaction.response.send_message('Tidak bisa nge-heist bot.')
        return
    if target.id == interaction.user.id:
        await interaction.response.send_message('Tidak bisa nge-heist diri sendiri.')
        return
    remain = cooldown_remaining(interaction.user.id, 'heist')
    if remain > 0:
        await interaction.response.send_message(f'⏳ Cooldown heist: {remain}s lagi.')
        return
    if get_points(interaction.user.id) == 0:
        add_points(interaction.user.id, 50)
    if get_points(target.id) == 0:
        add_points(target.id, 50)
    success = random.random() < 0.55
    set_cooldown(interaction.user.id, 'heist', 120)
    if success:
        amount = random.randint(10, 40)
        stolen = transfer_points(target.id, interaction.user.id, amount)
        await interaction.response.send_message(f'💰 Berhasil! Kamu nge-heist {target.mention} dan dapat **{stolen} poin**.')
    else:
        penalty = random.randint(8, 25)
        paid = transfer_points(interaction.user.id, target.id, penalty)
        await interaction.response.send_message(f'🚨 Gagal! Kamu bayar denda **{paid} poin** ke {target.mention}.')

def clean_word(word: str) -> str:
    return ''.join(ch for ch in word.lower().strip() if ch.isalpha())

@bot.command(name='sambungkata')
async def sambung_kata(ctx):
    channel_id = ctx.channel.id
    seed = random.choice(WORD_BANK)
    sambung_kata_active[channel_id] = {'last': seed, 'used': {seed}}
    await ctx.send(f'🔗 Sambung Kata dimulai!\nKata awal: **{seed}**\nLanjut pakai `!kata <kata>`')

@bot.command(name='kata')
async def kata(ctx, *, word: str):
    channel_id = ctx.channel.id
    if channel_id not in sambung_kata_active:
        await ctx.send('Belum ada game sambung kata aktif. Mulai dengan `!sambungkata`.')
        return
    state = sambung_kata_active[channel_id]
    last_word = state['last']
    used_words = state['used']
    cleaned = clean_word(word)
    if len(cleaned) < 3:
        await ctx.send('Kata minimal 3 huruf.')
        return
    if cleaned in used_words:
        await ctx.send('Kata itu sudah dipakai.')
        return
    required = last_word[-1]
    if cleaned[0] != required:
        await ctx.send(f'Harus dimulai huruf **{required.upper()}**.')
        return
    used_words.add(cleaned)
    state['last'] = cleaned
    new_pts = add_points(ctx.author.id, 2)
    await ctx.send(f'✅ Valid: **{cleaned}**\nKata berikutnya harus dimulai huruf **{cleaned[-1].upper()}**.\n+2 poin untuk {ctx.author.mention}. Total: **{new_pts}**')

@bot.command(name='sambungstop')
async def sambung_stop(ctx):
    channel_id = ctx.channel.id
    if channel_id in sambung_kata_active:
        del sambung_kata_active[channel_id]
        await ctx.send('🛑 Game sambung kata dihentikan.')
    else:
        await ctx.send('Tidak ada game sambung kata aktif di channel ini.')

@bot.tree.command(name='sambung_kata_start', description='Mulai game Sambung Kata')
async def sambung_kata_slash(interaction: discord.Interaction):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    seed = random.choice(WORD_BANK)
    sambung_kata_active[channel.id] = {'last': seed, 'used': {seed}}
    await interaction.response.send_message(f'🔗 Sambung Kata dimulai!\nKata awal: **{seed}**\nLanjut pakai `/kata`')

@bot.tree.command(name='kata', description='Masukkan kata untuk game Sambung Kata')
@app_commands.describe(word='Kata sambungan kamu')
async def kata_slash(interaction: discord.Interaction, word: str):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    if channel.id not in sambung_kata_active:
        await interaction.response.send_message('Belum ada game sambung kata aktif di channel ini.')
        return
    state = sambung_kata_active[channel.id]
    last_word = state['last']
    used_words = state['used']
    cleaned = clean_word(word)
    if len(cleaned) < 3:
        await interaction.response.send_message('Kata minimal 3 huruf.')
        return
    if cleaned in used_words:
        await interaction.response.send_message('Kata itu sudah dipakai.')
        return
    required = last_word[-1]
    if cleaned[0] != required:
        await interaction.response.send_message(f'Harus dimulai huruf **{required.upper()}**.')
        return
    used_words.add(cleaned)
    state['last'] = cleaned
    new_pts = add_points(interaction.user.id, 2)
    await interaction.response.send_message(f'✅ Valid: **{cleaned}**\nKata berikutnya harus diawali **{cleaned[-1].upper()}**.\n+2 poin. Total kamu: **{new_pts}**')

@bot.tree.command(name='sambung_kata_stop', description='Hentikan game Sambung Kata di channel ini')
async def sambung_stop_slash(interaction: discord.Interaction):
    channel = interaction.channel
    if not channel:
        await interaction.response.send_message('Channel tidak ditemukan.', ephemeral=True)
        return
    if channel.id in sambung_kata_active:
        del sambung_kata_active[channel.id]
        await interaction.response.send_message('🛑 Game sambung kata dihentikan.')
    else:
        await interaction.response.send_message('Tidak ada game sambung kata aktif di channel ini.')
# ==================== END MINI GAMES PACK ====================

# ==================== MOOD SERVER DETECTOR ====================
MOOD_DATA_PATH = Path('mood_data.json')

POSITIVE_WORDS = {
    'mantap', 'bagus', 'keren', 'thanks', 'thank you', 'makasih', 'wkwk',
    'haha', 'lucu', 'senang', 'happy', 'gas', 'nice', 'good', 'great'
}
NEGATIVE_WORDS = {
    'sedih', 'cape', 'capek', 'bad', 'jelek', 'kesal', 'marah',
    'kecewa', 'susah', 'anjir', 'aduh'
}
TOXIC_WORDS = {
    'tolol', 'goblok', 'anjing', 'bangsat', 'kontol', 'memek'
}


def load_mood_data() -> dict:
    try:
        if MOOD_DATA_PATH.exists():
            with MOOD_DATA_PATH.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


mood_data = load_mood_data()


def save_mood_data() -> None:
    try:
        with MOOD_DATA_PATH.open('w', encoding='utf-8') as f:
            json.dump(mood_data, f, indent=2)
    except Exception:
        pass


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def record_mood(guild_id: int, text: str) -> None:
    text_low = text.lower()
    score = Counter({'positive': 0, 'neutral': 0, 'negative': 0, 'toxic': 0})

    for w in POSITIVE_WORDS:
        if w in text_low:
            score['positive'] += 1
    for w in NEGATIVE_WORDS:
        if w in text_low:
            score['negative'] += 1
    for w in TOXIC_WORDS:
        if w in text_low:
            score['toxic'] += 1

    if score['positive'] == 0 and score['negative'] == 0 and score['toxic'] == 0:
        score['neutral'] = 1

    gid = str(guild_id)
    day = _today_key()
    mood_data.setdefault(gid, {})
    mood_data[gid].setdefault(day, {'positive': 0, 'neutral': 0, 'negative': 0, 'toxic': 0, 'messages': 0})

    mood_data[gid][day]['positive'] += score['positive']
    mood_data[gid][day]['negative'] += score['negative']
    mood_data[gid][day]['toxic'] += score['toxic']
    mood_data[gid][day]['neutral'] += score['neutral']
    mood_data[gid][day]['messages'] += 1
    save_mood_data()


def mood_summary(guild_id: int, days: int = 1) -> dict:
    gid = str(guild_id)
    if gid not in mood_data:
        return {'positive': 0, 'neutral': 0, 'negative': 0, 'toxic': 0, 'messages': 0}

    out = Counter({'positive': 0, 'neutral': 0, 'negative': 0, 'toxic': 0, 'messages': 0})
    for i in range(max(1, days)):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime('%Y-%m-%d')
        day_data = mood_data[gid].get(day)
        if day_data:
            out['positive'] += int(day_data.get('positive', 0))
            out['neutral'] += int(day_data.get('neutral', 0))
            out['negative'] += int(day_data.get('negative', 0))
            out['toxic'] += int(day_data.get('toxic', 0))
            out['messages'] += int(day_data.get('messages', 0))
    return dict(out)


def dominant_mood(data: dict) -> str:
    base = {
        'positive': int(data.get('positive', 0)),
        'neutral': int(data.get('neutral', 0)),
        'negative': int(data.get('negative', 0)),
        'toxic': int(data.get('toxic', 0))
    }
    top = max(base, key=base.get)
    mapping = {'positive': 'POSITIF', 'neutral': 'NETRAL', 'negative': 'NEGATIF', 'toxic': 'TOXIC'}
    return mapping[top]


@bot.command(name='mood')
async def mood_cmd(ctx, days: int = 1):
    if not ctx.guild:
        await ctx.send('Command ini hanya untuk server.')
        return
    data = mood_summary(ctx.guild.id, days)
    total = max(1, data['positive'] + data['neutral'] + data['negative'] + data['toxic'])

    embed = discord.Embed(
        title='📈 Mood Server Detector',
        description=f'Rekap {days} hari terakhir • {data["messages"]} pesan terpantau',
        color=discord.Color.blurple()
    )
    embed.add_field(name='🙂 Positif', value=f'{data["positive"]} ({(data["positive"]/total)*100:.1f}%)', inline=True)
    embed.add_field(name='😐 Netral', value=f'{data["neutral"]} ({(data["neutral"]/total)*100:.1f}%)', inline=True)
    embed.add_field(name='🙁 Negatif', value=f'{data["negative"]} ({(data["negative"]/total)*100:.1f}%)', inline=True)
    embed.add_field(name='☣ Toxic', value=f'{data["toxic"]} ({(data["toxic"]/total)*100:.1f}%)', inline=True)
    embed.add_field(name='Kesimpulan', value=f'Mood dominan: **{dominant_mood(data)}**', inline=False)
    await ctx.send(embed=embed)


@bot.tree.command(name='mood', description='Lihat ringkasan mood server')
@app_commands.describe(days='Jumlah hari yang dicek (default: 1)')
async def mood_slash(interaction: discord.Interaction, days: int = 1):
    if not interaction.guild:
        await interaction.response.send_message('Command ini hanya untuk server.', ephemeral=True)
        return
    data = mood_summary(interaction.guild.id, days)
    total = max(1, data['positive'] + data['neutral'] + data['negative'] + data['toxic'])

    embed = discord.Embed(
        title='📈 Mood Server Detector',
        description=f'Rekap {days} hari terakhir • {data["messages"]} pesan terpantau',
        color=discord.Color.blurple()
    )
    embed.add_field(name='🙂 Positif', value=f'{data["positive"]} ({(data["positive"]/total)*100:.1f}%)', inline=True)
    embed.add_field(name='😐 Netral', value=f'{data["neutral"]} ({(data["neutral"]/total)*100:.1f}%)', inline=True)
    embed.add_field(name='🙁 Negatif', value=f'{data["negative"]} ({(data["negative"]/total)*100:.1f}%)', inline=True)
    embed.add_field(name='☣ Toxic', value=f'{data["toxic"]} ({(data["toxic"]/total)*100:.1f}%)', inline=True)
    embed.add_field(name='Kesimpulan', value=f'Mood dominan: **{dominant_mood(data)}**', inline=False)
    await interaction.response.send_message(embed=embed)

# ==================== DEBATE REFEREE ====================
@dataclass
class DebateSession:
    guild_id: int
    channel_id: int
    topic: str
    turn_seconds: int
    rounds: int
    pro: list[int] = field(default_factory=list)
    kontra: list[int] = field(default_factory=list)
    points: list[tuple[int, str]] = field(default_factory=list)
    running: bool = False


debate_sessions: dict[int, DebateSession] = {}
debate_tasks: dict[int, asyncio.Task] = {}


def _side_of_user(s: DebateSession, uid: int) -> str | None:
    if uid in s.pro:
        return 'PRO'
    if uid in s.kontra:
        return 'KONTRA'
    return None


async def debate_runner(session: DebateSession):
    channel = bot.get_channel(session.channel_id)
    if not channel:
        return
    session.running = True
    await channel.send(
        f'🎤 Debat dimulai!\nTopik: **{session.topic}**\nDurasi tiap giliran: **{session.turn_seconds}s**'
    )

    for r in range(1, session.rounds + 1):
        for side_name, lineup in [('PRO', session.pro), ('KONTRA', session.kontra)]:
            for uid in lineup:
                if not session.running:
                    return
                await channel.send(f'🕒 Round {r}/{session.rounds} • Giliran {side_name}: <@{uid}> ({session.turn_seconds}s)')
                await asyncio.sleep(session.turn_seconds)

    session.running = False
    pro_points = [p for _, p in session.points if p == 'PRO']
    kontra_points = [p for _, p in session.points if p == 'KONTRA']
    await channel.send(
        '✅ Debat selesai.\n'
        f'Poin tercatat: PRO **{len(pro_points)}** | KONTRA **{len(kontra_points)}**\n'
        'Gunakan `!debat_ringkas` untuk lihat ringkasan.'
    )


@bot.command(name='debat_mulai')
@commands.has_permissions(manage_messages=True)
async def debat_mulai(ctx, turn_seconds: int, rounds: int, *, topic: str):
    if turn_seconds < 10 or rounds < 1:
        await ctx.send('Minimal `turn_seconds=10` dan `rounds>=1`.')
        return
    debate_sessions[ctx.channel.id] = DebateSession(
        guild_id=ctx.guild.id,
        channel_id=ctx.channel.id,
        topic=topic,
        turn_seconds=turn_seconds,
        rounds=rounds
    )
    await ctx.send(
        f'🧠 Sesi debat dibuat.\nTopik: **{topic}**\n'
        f'Turn: **{turn_seconds}s** • Rounds: **{rounds}**\n'
        'Join dengan `!debat_join pro` atau `!debat_join kontra`, lalu start `!debat_start`.'
    )


@bot.command(name='debat_join')
async def debat_join(ctx, side: str):
    s = debate_sessions.get(ctx.channel.id)
    if not s:
        await ctx.send('Belum ada sesi debat. Gunakan `!debat_mulai`.')
        return
    if s.running:
        await ctx.send('Debat sudah berjalan, tidak bisa join.')
        return

    side = side.lower().strip()
    if side not in ['pro', 'kontra']:
        await ctx.send('Pilih sisi: `pro` atau `kontra`.')
        return

    if ctx.author.id in s.pro:
        s.pro.remove(ctx.author.id)
    if ctx.author.id in s.kontra:
        s.kontra.remove(ctx.author.id)

    if side == 'pro':
        s.pro.append(ctx.author.id)
    else:
        s.kontra.append(ctx.author.id)

    await ctx.send(f'✅ {ctx.author.mention} masuk sisi **{side.upper()}**.')


@bot.command(name='debat_start')
@commands.has_permissions(manage_messages=True)
async def debat_start(ctx):
    s = debate_sessions.get(ctx.channel.id)
    if not s:
        await ctx.send('Belum ada sesi debat.')
        return
    if s.running:
        await ctx.send('Debat sudah berjalan.')
        return
    if not s.pro or not s.kontra:
        await ctx.send('Kedua sisi harus punya minimal 1 peserta.')
        return

    old_task = debate_tasks.get(ctx.channel.id)
    if old_task and not old_task.done():
        old_task.cancel()

    task = asyncio.create_task(debate_runner(s))
    debate_tasks[ctx.channel.id] = task
    await ctx.send('🚀 Timer debat dijalankan.')


@bot.command(name='debat_poin')
async def debat_poin(ctx, *, point: str):
    s = debate_sessions.get(ctx.channel.id)
    if not s:
        await ctx.send('Belum ada sesi debat.')
        return
    side = _side_of_user(s, ctx.author.id)
    if not side:
        await ctx.send('Kamu belum join sisi debat.')
        return
    s.points.append((ctx.author.id, side))
    await ctx.send(f'📝 Poin {side} dicatat dari {ctx.author.mention}: {point}')


@bot.command(name='debat_ringkas')
async def debat_ringkas(ctx):
    s = debate_sessions.get(ctx.channel.id)
    if not s:
        await ctx.send('Belum ada sesi debat.')
        return

    pro_count = len([1 for _, side in s.points if side == 'PRO'])
    kontra_count = len([1 for _, side in s.points if side == 'KONTRA'])
    embed = discord.Embed(title='📌 Ringkasan Debat', color=discord.Color.gold())
    embed.add_field(name='Topik', value=s.topic, inline=False)
    embed.add_field(name='Peserta PRO', value=', '.join([f'<@{u}>' for u in s.pro]) or '-', inline=False)
    embed.add_field(name='Peserta KONTRA', value=', '.join([f'<@{u}>' for u in s.kontra]) or '-', inline=False)
    embed.add_field(name='Jumlah Poin', value=f'PRO: **{pro_count}** | KONTRA: **{kontra_count}**', inline=False)
    embed.add_field(name='Status', value='Berjalan' if s.running else 'Selesai/Standby', inline=False)
    await ctx.send(embed=embed)


@bot.command(name='debat_stop')
@commands.has_permissions(manage_messages=True)
async def debat_stop(ctx):
    s = debate_sessions.get(ctx.channel.id)
    if not s:
        await ctx.send('Tidak ada sesi debat aktif.')
        return
    s.running = False
    task = debate_tasks.get(ctx.channel.id)
    if task and not task.done():
        task.cancel()
    del debate_sessions[ctx.channel.id]
    await ctx.send('🛑 Sesi debat dihentikan dan direset.')

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Auto create personal temporary voice room when user joins configured lobby VC."""
    try:
        guild = member.guild
        lobby_id = temp_vc_config.get(str(guild.id))

        # Joined voice channel
        if after.channel and lobby_id and after.channel.id == int(lobby_id):
            category = after.channel.category
            base_name = f'Room {member.display_name}'
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
                member: discord.PermissionOverwrite(manage_channels=True, move_members=True, mute_members=True)
            }

            new_channel = await guild.create_voice_channel(
                name=base_name,
                category=category,
                overwrites=overwrites,
                reason=f'Temporary VC created for {member}'
            )
            temp_vc_channels[new_channel.id] = member.id
            try:
                await member.move_to(new_channel, reason='Move to personal temporary VC')
            except Exception:
                pass

        # Cleanup old temporary channel if empty
        if before.channel and before.channel.id in temp_vc_channels:
            if len(before.channel.members) == 0:
                try:
                    del temp_vc_channels[before.channel.id]
                except Exception:
                    pass
                try:
                    await before.channel.delete(reason='Temporary VC empty')
                except Exception:
                    pass
    except Exception:
        pass


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.guild and message.content:
        record_mood(message.guild.id, message.content)
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""

    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title='Selamat Bermain',
            description=f'Command {ctx.message.content} tidak ada.\n\nGunakan !help_custom atau !help untuk melihat daftar command.',
            color=discord.Color.green()
        )
        if not await recently_sent(ctx.channel, embed_title=embed.title):
            await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title='❌ Argument kurang',
            description=f'Command ini memerlukan argument tambahan.\n\nGunakan `!help_custom` untuk bantuan.',
            color=discord.Color.red()
        )
        if not await recently_sent(ctx.channel, embed_title=embed.title):
            await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title='❌ Permission ditolak',
            description='Anda tidak memiliki permission untuk menggunakan command ini.',
            color=discord.Color.red()
        )
        if not await recently_sent(ctx.channel, embed_title=embed.title):
            await ctx.send(embed=embed)

@bot.command(name='logo')
async def logo(ctx, target: str = None):
    """Tampilkan logo user atau server.
    Contoh: !logo, !logo @user, !logo server
    """
    if target and target.lower() == 'server':
        if not ctx.guild:
            await ctx.send('Command `!logo server` hanya bisa digunakan di server.')
            return
        if not ctx.guild.icon:
            await ctx.send('Server ini tidak memiliki logo.')
            return

        embed = discord.Embed(
            title=f'Logo Server {ctx.guild.name}',
            color=discord.Color.blurple()
        )
        embed.set_image(url=ctx.guild.icon.url)
        embed.set_footer(text=f'Diminta oleh {ctx.author.display_name}')
        if not await recently_sent(ctx.channel, embed_title=embed.title):
            await ctx.send(embed=embed)
        return

    member = None
    if ctx.message.mentions:
        member = ctx.message.mentions[0]
    elif target:
        try:
            member = await commands.MemberConverter().convert(ctx, target)
        except commands.BadArgument:
            await ctx.send('User tidak ditemukan. Gunakan `!logo`, `!logo @user`, atau `!logo server`.')
            return
    else:
        member = ctx.author

    embed = discord.Embed(
        title=f'Logo {member.display_name}',
        color=discord.Color.blurple()
    )
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f'Diminta oleh {ctx.author.display_name}')

    if not await recently_sent(ctx.channel, embed_title=embed.title):
        await ctx.send(embed=embed)


# Run the bot
bot.run(TOKEN)
