import discord
from discord.ext import commands
from discord import app_commands
import os

TOKEN = os.getenv("TOKEN")  # .env에서 BOT TOKEN 불러오기
GUILD_ID = 1479470487494197371
VERIFY_ROLE_ID = 1479477742633484349
LOG_CHANNEL_ID = 1479479193975918764

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# 인증 코드, 초대 링크 사용 기록, 인증 시도
INVITE_CODES = []
invite_uses = {}
attempts = {}

# ===========================
# 인증 코드 지정 슬래시 명령어
# ===========================
@tree.command(name="인증코드지정", description="인증 코드를 지정합니다.")
@app_commands.describe(코드="사용할 인증 코드를 입력하세요")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def set_code(interaction: discord.Interaction, 코드: str):
    INVITE_CODES.append(코드.strip())
    await interaction.response.send_message(f"인증 코드 '{코드}' 가 등록되었습니다.", ephemeral=True)

# ===========================
# 봇 준비 시 초대 링크 초기화
# ===========================
@bot.event
async def on_ready():
    print(f"{bot.user} 로그인 완료")
    guild = bot.get_guild(GUILD_ID)
    invites = await guild.invites()
    for inv in invites:
        invite_uses[inv.code] = inv.uses
    print("초대 링크 정보 초기화 완료")
    try:
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        print("슬래시 명령어 동기화 완료")
    except Exception as e:
        print(e)

# ===========================
# 멤버 입장 처리
# ===========================
@bot.event
async def on_member_join(member):
    guild = bot.get_guild(GUILD_ID)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)

    # 사용된 초대 링크 확인
    invites = await guild.invites()
    used_invite = None
    for inv in invites:
        prev_uses = invite_uses.get(inv.code, 0)
        if inv.uses > prev_uses:
            used_invite = inv
        invite_uses[inv.code] = inv.uses

    if not used_invite:
        await log_channel.send(f"{member} 님이 초대 링크 없이 입장하여 강제 추방합니다.")
        await member.kick(reason="초대 링크 없음")
        return

    await log_channel.send(f"{member} 님이 초대 링크 {used_invite.code} 로 입장했습니다.")

    # DM으로 양식 안내
    try:
        await member.send(
            f"{member.name}님, 서버 인증을 위해 아래 양식을 작성해주세요.\n"
            f"양식: 인증코드, 들어온 이유\n"
            f"예시: ABC123, 친구 추천으로 들어왔습니다.\n"
            f"코드를 3번 틀리면 추방됩니다."
        )
    except discord.Forbidden:
        await log_channel.send(f"{member}님에게 DM을 보낼 수 없습니다. 추방 처리합니다.")
        await member.kick(reason="DM 불가")
        return

    attempts[member.id] = 0

# ===========================
# DM 양식 인증 처리
# ===========================
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        if message.author.id not in attempts:
            return  # 인증 대상 아님

        # 양식: "코드, 들어온 이유"
        content = message.content.strip().split(",", 1)
        if len(content) != 2:
            await message.author.send("양식이 잘못되었습니다. 인증코드, 들어온 이유 형식으로 보내주세요.")
            return

        code_input = content[0].strip()
        reason_input = content[1].strip()

        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(message.author.id)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)

        if code_input in INVITE_CODES:
            role = guild.get_role(VERIFY_ROLE_ID)
            if member and role:
                await member.add_roles(role)
                await message.author.send("인증 완료! 역할이 지급되었습니다.")
                await log_channel.send(
                    f"{member} 님이 인증을 완료했습니다.\n"
                    f"인증코드: {code_input}\n"
                    f"들어온 이유: {reason_input}\n"
                    f"사용한 초대 링크: {used_invite.code if 'used_invite' in locals() and used_invite else '알 수 없음'}"
                )
                del attempts[message.author.id]
        else:
            attempts[message.author.id] += 1
            remaining = 3 - attempts[message.author.id]
            if remaining <= 0:
                if member:
                    await member.kick(reason="인증 실패 3회")
                    await log_channel.send(f"{member} 님이 인증 3회 실패로 추방되었습니다.")
                del attempts[message.author.id]
            else:
                await message.author.send(f"인증 코드가 틀렸습니다. 남은 시도: {remaining}회")

bot.run(TOKEN)
