import datetime
import textwrap
from urllib import parse
import discord

from app import scorewatch, settings

from discord.ext import commands
from app.constants import Status, VoteType
from app.repositories import scores, sw_requests, sw_votes, users


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
                textwrap.dedent(
                    """\
                    You must provide a valid Akatsuki profile URL.
                    Valid syntax: `https://akatsuki.gg/u/999`
                    """
                ),
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

    @discord.ui.button(
        label="Click Here!", style=discord.ButtonStyle.primary, custom_id="report"
    )
    async def report(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ):
        await interaction.response.send_modal(ReportForm(self.bot))


class ScorewatchVoteButton(discord.ui.Button):
    def __init__(
        self, score_id: int, vote_type: VoteType, bot: commands.Bot, *args, **kwargs
    ):
        self.bot = bot
        self.vote_type = vote_type
        self.score_id = score_id
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if not isinstance(interaction.channel, discord.Thread):
            return

        role = interaction.guild.get_role(settings.AKATSUKI_SCOREWATCH_ROLE_ID)  # type: ignore
        if not role:
            return  # ???????

        if not role in interaction.user.roles:  # type: ignore
            await interaction.followup.send(
                "You don't have permission to vote on this request!",
                ephemeral=True,
            )
            return

        request_data = await sw_requests.fetch_one(self.score_id)
        if not request_data:  # perhaps we can add removing requests?
            await interaction.followup.send(
                "This request no longer exists!",
                ephemeral=True,
            )
            return

        if request_data["request_status"] in Status.resolved_statuses():
            await interaction.followup.send(
                "This request has already been resolved!",
                ephemeral=True,
            )
            return

        prev_vote = await sw_votes.fetch_one(
            request_data["request_id"], interaction.user.id
        )
        if prev_vote:
            await interaction.followup.send(
                "You have already voted on this request!",
                ephemeral=True,
            )
            return

        await sw_votes.create(
            request_data["request_id"],
            interaction.user.id,
            self.vote_type,
        )

        upvotes = await sw_votes.fetch_all(
            request_data["request_id"],
            VoteType.UPVOTE,
        )
        downvotes = await sw_votes.fetch_all(
            request_data["request_id"],
            VoteType.DOWNVOTE,
        )
        all_votes = {vote["vote_user_id"]: vote for vote in upvotes + downvotes}

        users_mentions = {
            member.id: member.mention for member in role.members  # type: ignore
        }

        left_to_vote = set()
        for user_id, user_mention in users_mentions.items():
            if user_id not in all_votes:
                left_to_vote.add(user_mention)

        msg_content = textwrap.dedent(
            f"""\
                Hey, <@&{settings.AKATSUKI_SCOREWATCH_ROLE_ID}>! A new upload request has been submitted.

                **Remember you can only vote once!**

                **Vote with the reactions below!**
                **{len(all_votes)}**/{len(users_mentions)} voted!
                List of people left to vote:
                {', '.join(left_to_vote)}
            """,
        )

        old_thread_msg = await interaction.channel.fetch_message(
            request_data["thread_message_id"]
        )
        await old_thread_msg.edit(content=msg_content)
        await interaction.followup.send(
            f"Your vote has been recorded!",
            ephemeral=True,
        )

        if len(all_votes) != len(users_mentions):
            return

        # we have all the votes, let's resolve this request
        # TODO: what should we do if there is a tie?
        if len(upvotes) > len(downvotes):
            status = Status.ACCEPTED
        else:
            status = Status.DENIED

        await sw_requests.partial_update(
            request_data["score_id"],
            status.value,
            datetime.datetime.utcnow(),
        )

        score_data = await scores.fetch_one(
            request_data["score_id"], request_data["score_relax"]
        )

        if not score_data:
            await interaction.channel.send(
                "Couldn't find this play!",
            )
            return

        updated_embed = await scorewatch.format_request_embed(
            self.bot, score_data, request_data, status
        )
        if isinstance(updated_embed, str):
            await interaction.channel.send(updated_embed)
            return

        await old_thread_msg.edit(embed=updated_embed)

        await interaction.channel.send(
            textwrap.dedent(
                f"""\
                    All votes have been casted and the request has been closed!
                    The request has been marked as **{status}**!
                """,
            ),
        )

        if status == Status.DENIED:
            return  # we don't need to do anything else

        await interaction.channel.send(
            "Generating scorewatch metadata, it will show up in a moment...",
        )

        async with interaction.channel.typing():
            metadata = await scorewatch.generate_normal_metadata(score_data)

            if isinstance(metadata, str):
                await interaction.channel.send(metadata)
                return

            await interaction.channel.send(
                "\n".join(
                    (
                        "**Title:**",
                        f"```{metadata['title']}```",
                        "",
                        "**Description:**",
                        f"```{metadata['description']}```",
                        "",
                        "**Thumbnail:**",
                    ),
                ),
                file=discord.File(
                    metadata["file"],
                ),
            )


class ScorewatchButtonView(discord.ui.View):
    def __init__(self, score_id: int, bot: commands.Bot):
        self.bot = bot
        self.score_id = score_id
        super().__init__(timeout=None)

        self.accept_btn = ScorewatchVoteButton(
            self.score_id,
            VoteType.UPVOTE,
            self.bot,
            style=discord.ButtonStyle.green,
            label="Accept",
            custom_id="accept",
        )
        self.add_item(self.accept_btn)

        self.deny_btn = ScorewatchVoteButton(
            self.score_id,
            VoteType.DOWNVOTE,
            self.bot,
            style=discord.ButtonStyle.red,
            label="Deny",
            custom_id="deny",
        )
        self.add_item(self.deny_btn)
