# Discord Bot Setup Guide

## Persyaratan
- Python 3.8 atau lebih tinggi
- pip (Python package manager)

## Langkah Instalasi

### 1. Buat Bot di Discord Developer Portal
- Kunjungi https://discord.com/developers/applications
- Klik "New Application"
- Beri nama aplikasi Anda
- Pergi ke tab "Bot" dan klik "Add Bot"
- Copy token bot Anda (jangan bagikan dengan siapa pun!)

### 2. Setup Permissions
- Di Discord Developer Portal, pergi ke "OAuth2" → "URL Generator"
- Pilih scopes: `bot`
- Pilih permissions yang dibutuhkan:
  - Send Messages
  - Read Messages/View Channels
  - Manage Messages
  - Kick Members
  - Ban Members
  - Embed Links
- Copy generated URL dan buka di browser untuk invite bot ke server Anda

### 3. Instalasi Dependencies
- Buka terminal/command prompt di folder project
- Jalankan:
  ```
  pip install -r requirements.txt
  ```

### 4. Setup Token
- Rename `.env.example` menjadi `.env`
- Buka `.env` dan ganti `your_bot_token_here` dengan token bot Anda

### 5. Jalankan Bot
- Jalankan command:
  ```
  python bot.py
  ```
- Anda akan melihat pesan "Bot has connected to Discord!" jika berhasil

## Daftar Commands (Prefix: !)

| Command | Fungsi |
|---------|--------|
| `!ping` | Cek latency bot |
| `!hello` | Salam dari bot |
| `!user` | Lihat informasi user |
| `!blackjack` | Bermain Blackjack melawan Dealer |
| `!kick @user [reason]` | Kick user dari server |
| `!ban @user [reason]` | Ban user dari server |
| `!clear [amount]` | Hapus pesan tertentu |
| `!channelpanel` | Buka panel untuk membuat channel (dengan tombol interaktif) |
| `!logupdate` | Buka panel untuk membuat log update server (admin only) |
| `!logserver #channel` | Set channel untuk menerima notifikasi saat anggota baru bergabung (Admin only) |
| `!logserver_off` | Menonaktifkan join-log untuk server ini (Admin only) |
| `!help_custom` | Tampilkan daftar commands |

## Tips
- Jangan pernah bagikan token bot Anda
- Gunakan `.env` untuk menyimpan token (jangan hardcode)
- Selalu tambahkan `error handling` di production
- Test commands di server development terlebih dahulu

## Resources
- Dokumentasi discord.py: https://discordpy.readthedocs.io/
- Discord Developer Docs: https://discord.com/developers/docs

Selamat mencoba! 🎉
## Tambahan Commands Terbaru

### Mood Server Detector
- `!mood [hari]` - Lihat analisa mood server (positif/netral/negatif/toxic)
- `/mood [days]` - Versi slash untuk analisa mood server

### Debate Referee
- `!debat_mulai <detik> <round> <topik>` - Buat sesi debat dan set timer giliran
- `!debat_join <pro|kontra>` - Join sisi debat
- `!debat_start` - Mulai sesi debat
- `!debat_poin <isi poin>` - Catat poin argumen
- `!debat_ringkas` - Lihat ringkasan debat
- `!debat_stop` - Hentikan dan reset sesi debat

### Auto Temporary Voice Room
- `!setvclobby #voice` - Set voice lobby untuk auto-create room
- `!setvclobby_off` - Matikan fitur auto-create voice room
- `!vclobby_status` - Cek status VC lobby aktif
