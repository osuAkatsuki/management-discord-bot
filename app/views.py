from urllib import parse
import discord

from app import settings

from discord.ext import commands
from app.repositories import users

class ReportForm(discord.ui.Modal):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__(title="Report a user for rule breaking!")

        self.user_url = discord.ui.TextInput(
            label="Akatsuki profile URL",
            placeholder="https://akatsuki.gg/u/999",
            min_length=20,
            max_length=70,
            required=True,
        )
        self.add_item(self.user_url)

        self.reason = discord.ui.TextInput(
            label="Reason",
            style=discord.TextStyle.long,
            max_length=2000,
            required=True,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        parsed_url = parse.urlparse(self.user_url.value)

        if not parsed_url.hostname in ("akatsuki.gg", "akatsuki.pw"):
            await interaction.followup.send(
                """\
                You must provide a valid Akatsuki profile URL.
                Valid syntax: `https://akatsuki.gg/u/999`
                """,
                ephemeral=True,
            )
            return

        user_id = parsed_url.path[3:].split("?")[0]  # remove args.
        url_type = "id"
        if not user_id.isnumeric():
            url_type = "name"

        user_data = await users.fetch_one(url_type, user_id)

        # they should be not banned 
        if not user_data:
            await interaction.followup.send(
                "Player could not be found!",
                ephemeral=True,
            )
            return

        footer_text = (
            f"Reported by {interaction.user.name}#"
            f"{interaction.user.discriminator} ({interaction.user.id})"
        )
        embed = discord.Embed(
            title=f"Reported user: {user_data['username']}",
            url=f"https://akatsuki.gg/u/{user_data['id']}",
        )
        embed.add_field(name="Reason", value=self.reason.value)
        embed.set_thumbnail(url=f"https://a.akatsuki.gg/{user_data['id']}")
        embed.set_footer(text=footer_text)

        channel = self.bot.get_channel(settings.ADMIN_REPORT_CHANNEL_ID)
        if not channel:
            await interaction.followup.send(
                "There was an error sending your report. Please try again later.",
                ephemeral=True,
            )
            return

        await interaction.followup.send("Thank you for your report!", ephemeral=True)
        await channel.send(embed=embed)  # type: ignore

class ReportView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(timeout=None)

    @discord.ui.button(label="Click Here!", style=discord.ButtonStyle.primary, custom_id="report")
    async def report(
        self, 
        interaction: discord.Interaction, 
        _: discord.ui.Button,
    ):
        await interaction.response.send_modal(ReportForm(self.bot))