import datetime
import io
import textwrap
from typing import Any
from urllib import parse

import discord
from discord.ext import commands

from app.common import settings
from app.constants import Status
from app.constants import VoteType
from app.repositories import scores
from app.repositories import sw_requests
from app.repositories import sw_votes
from app.repositories import users
from app.usecases import scorewatch


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
                    """,
                ),
                ephemeral=True,
            )
            return

        user_id = parsed_url.path[3:].split("?")[0]  # remove args.
        url_type = "id"
        if not user_id.isnumeric():
            url_type = "name"

        user_data = await users.fetch_one(url_type, user_id)

        # they shouldn't be banned, yet.
        if not user_data:
            await interaction.followup.send(
                "Player could not be found!",
                ephemeral=True,
            )
            return

        footer_text = f"Reported by {interaction.user.name} ({interaction.user.id})"
        embed = discord.Embed(
            title=f"Reported user: {user_data['username']}",
            url=f"https://akatsuki.gg/u/{user_data['id']}",
        )
        embed.add_field(name="Reason", value=self.reason.value)
        embed.set_thumbnail(url=f"https://a.akatsuki.gg/{user_data['id']}")
        embed.set_footer(text=footer_text)

        channel = self.bot.get_channel(settings.ADMIN_REPORT_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            # valid case when channel doesn't exist anymore
            await interaction.followup.send(
                "There was an error sending your report. Please try again later.",
                ephemeral=True,
            )
            return

        await interaction.followup.send("Thank you for your report!", ephemeral=True)
        await channel.send(embed=embed)


class ReportView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Click Here!",
        style=discord.ButtonStyle.primary,
        custom_id="report",
    )
    async def report(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(ReportForm(self.bot))


class ScorewatchVoteButton(discord.ui.Button):
    def __init__(
        self,
        score_id: int,
        vote_type: VoteType,
        bot: commands.Bot,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.bot = bot
        self.vote_type = vote_type
        self.score_id = score_id
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        if not isinstance(interaction.channel, discord.Thread):
            return None

        assert interaction.guild is not None
        role = interaction.guild.get_role(settings.AKATSUKI_SCOREWATCH_ROLE_ID)
        assert role is not None

        assert isinstance(interaction.user, discord.Member)
        if role not in interaction.user.roles:
            await interaction.followup.send(
                "You don't have permission to vote on this request!",
                ephemeral=True,
            )
            return None

        request_data = await sw_requests.fetch_one(self.score_id)
        if not request_data:
            await interaction.followup.send(
                "This request no longer exist!",
                ephemeral=True,
            )
            return None

        if request_data["request_status"].value in Status.resolved_statuses():
            await interaction.followup.send(
                "This request has already been resolved!",
                ephemeral=True,
            )
            return None

        prev_vote = await sw_votes.fetch_one(
            request_data["request_id"],
            interaction.user.id,
        )
        if prev_vote:
            await interaction.followup.send(
                "You have already voted on this request!",
                ephemeral=True,
            )
            return None

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

        users_mentions = {member.id: member.mention for member in role.members}

        left_to_vote = set()
        for user_id, user_mention in users_mentions.items():
            if user_id not in all_votes:
                left_to_vote.add(user_mention)

        accepted_mentions = [users_mentions[user["vote_user_id"]] for user in upvotes]
        denied_mentions = [users_mentions[user["vote_user_id"]] for user in downvotes]

        msg_content = textwrap.dedent(
            f"""\
                Hey, <@&{settings.AKATSUKI_SCOREWATCH_ROLE_ID}>! A new upload request has been submitted.

                **Remember you can only vote once!**

                **Vote with the buttons below!**
                **{len(all_votes)}**/{len(users_mentions)} voted!

                Votes to accept:
                {', '.join(accepted_mentions)}
                Votes to deny:
                {', '.join(denied_mentions)}
                List of people left to vote:
                {', '.join(left_to_vote)}
            """,
        )

        old_thread_msg = await interaction.channel.fetch_message(
            request_data["thread_message_id"],
        )
        await old_thread_msg.edit(content=msg_content)
        await interaction.followup.send(
            f"You have successfully voted on this request!",
            ephemeral=True,
        )

        if len(all_votes) != len(users_mentions):
            return None

        # we have all the votes, let's resolve this request
        if len(upvotes) == len(downvotes):
            status = Status.TIED
        elif len(upvotes) > len(downvotes):
            status = Status.ACCEPTED
        else:
            status = Status.DENIED

        await sw_requests.partial_update(
            request_data["score_id"],
            status.value,
            datetime.datetime.now(datetime.UTC),
        )

        score_data = await scores.fetch_one(
            request_data["score_id"],
            request_data["score_relax"],
        )

        if not score_data:
            await interaction.channel.send(
                "Could not find this score!",
            )
            return None

        updated_embed = await scorewatch.format_request_embed(
            self.bot,
            score_data,
            request_data,
            status,
        )
        if isinstance(updated_embed, str):
            await interaction.channel.send(updated_embed)
            return None

        await old_thread_msg.edit(embed=updated_embed)

        await interaction.channel.send(
            textwrap.dedent(
                f"""\
                    All votes have been cast and the request has been closed!
                    The request has been marked as **{status}**!
                """,
            ),
        )

        if status == Status.DENIED:
            return None  # we don't need to do anything else

        if status == Status.TIED:
            await interaction.channel.send(
                "The request was tied, so it should be manually resolved "
                f"by <@&{settings.AKATSUKI_SCOREWATCH_ROLE_ID}> members.",
            )
            return None

        await interaction.channel.send(
            "Generating score upload metadata, it will show up in a moment...",
        )

        async with interaction.channel.typing():
            upload_data = await scorewatch.generate_score_upload_resources(score_data)

            if isinstance(upload_data, str):
                await interaction.channel.send(upload_data)
                return None

            await interaction.channel.send(
                "\n".join(
                    (
                        "**Title:**",
                        f"```{upload_data['title']}```",
                        "",
                        "**Description:**",
                        f"```{upload_data['description']}```",
                        "",
                        "**Thumbnail:**",
                    ),
                ),
                file=discord.File(
                    io.BytesIO(upload_data["image_data"]),
                    filename="thumbnail.jpg",
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
