from discord.ext import commands
import discord
import json

teams_file = 'data/teams.json'
players_file = 'data/players.json'
max_teams_default = 64
max_players_default = 2
allowed_channels = [1148349535538659388]
announce_channel = 1148349498293244067
manager_roles = [1061287805399085086]


class Tourney(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.teams = json.load(open(teams_file, 'r'))
        self.players = json.load(open(players_file, 'r'))
        self.max_players = max_players_default
        self.max_teams = max_teams_default
        self.allowed_channels = allowed_channels
        self.manager_roles = manager_roles
        self.announce_channel = announce_channel
        self.curr_id = 0

    def save_teams(self):
        json.dump(self.teams, open(teams_file, 'w'))

    def save_players(self):
        json.dump(self.players, open(players_file, 'w'))

    def refresh_teams(self):
        self.teams = json.load(open(teams_file, 'r'))
        return self.teams

    def refresh_players(self):
        self.players = json.load(open(players_file, 'r'))
        return self.players

    def is_on_team(self, discord_id):
        discord_id = str(discord_id)
        return discord_id in self.players

    def get_team_name(self, discord_id):
        discord_id = str(discord_id)
        if not self.is_on_team(discord_id):
            return None
        for team in self.teams.values():
            if int(discord_id) in team['members']:
                return team['name']
        return None

    def team_exists(self, team_name):
        return team_name in self.teams

    def get_team(self, discord_id):
        if not self.is_on_team(discord_id):
            return None
        return self.teams[self.get_team_name(discord_id)]

    def create_new_team(self, name, leader):
        self.curr_id += 1
        return {
            'name': name,
            'leader': leader,
            'members': [leader],
            'invites': [],
            'wins': 0,
            'losses': 0,
            'games': [],
            'sign_up_position': len(self.teams),
            'id': self.curr_id
            # each element should be in the format {
            # 'team_1': 'name',
            # 'team_2': 'name',
            # 'winner': 'name',
            # 'team_1_wins': 0,
            # 'team_2_wins': 0
            # }
        }

    def update_teams(self, team_name, team):
        self.teams[team_name] = team
        self.save_teams()

    @commands.command(name = 'register', aliases = ['create'])
    @commands.cooldown(rate = 1, per = 300)
    async def register(self, ctx, *args):
        if self.is_on_team(ctx.author.id):
            return await ctx.message.reply(embed = self.get_embed(f'You are already on the team `{self.get_team_name(ctx.author.id)}`'),
                                           mention_author = False)

        if len(args) == 0:
            return await ctx.message.reply(embed = self.get_embed(f'Please state a team name:\n'
                                           f'`{self.bot.prefix}register <team_name>`'),
                                           mention_author = False)

        team_name = " ".join(args)
        if self.team_exists(team_name):
            return await ctx.message.reply(embed = self.get_embed(f'A team with the name `{team_name}` already exists'),
                                           mention_author = False)

        if len(self.teams) > self.max_teams:
            await ctx.message.reply(embed = self.get_embed(f'There are already `{self.max_teams}` in the tournament.\n'
                                    f'You have been waitlisted (waitlists will be updated when teams drop out)'),
                                           mention_author = False)

        self.teams[team_name] = self.create_new_team(team_name, ctx.author.id)
        self.players[str(ctx.author.id)] = team_name
        self.save_teams()
        self.save_players()

        await self.announce(ctx, f"Team `{team_name}` created by <@{ctx.author.id}>")

        return await ctx.message.reply(embed = self.get_embed(f'Team `{team_name}` created. Add players with:\n'
                                       f'{self.bot.prefix}invite <user>'),
                                       mention_author = False)

    @commands.command(name = 'invite', aliases = ['add'], usage = 'invite <DiscordID>')
    @commands.cooldown(rate = 3, per = 300)
    async def invite(self, ctx, player: discord.User):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(embed = self.get_embed(f'You are not on a team'),
                                           mention_author = False)

        team = self.get_team(ctx.author.id)
        team_name = team['name']
        if team['leader'] != ctx.author.id:
            return await ctx.message.reply(embed = self.get_embed(f'You are not a team leader. Only team leaders can invite players'),
                                           mention_author = False)

        if player.id in team['invites']:
            return await ctx.message.reply(embed = self.get_embed(f'User has already been invited to `{team_name}`'),
                                           mention_author = False)

        if player.id in team['members']:
            return await ctx.message.reply(embed = self.get_embed(f'User is already on `{team_name}`'),
                                           mention_author = False)

        if len(team['members']) + len(team['invites']) >= self.max_players:
            return await ctx.message.reply(embed = self.get_embed(f'Team is full `({self.max_players} / {self.max_players})`\n'
                                           f'to make space, either uninvite or kick members'),
                                           mention_author = False)

        team['invites'].append(player.id)
        self.update_teams(team['name'], team)

        return await ctx.message.reply(embed = self.get_embed(f'<@{player.id}> has been invited to `{team_name}`\n'
                                       f'To accept this invite, they must run `{self.bot.prefix}accept {team_name}`'),
                                       mention_author = False)

    @commands.command(name = 'accept', aliases = ['join'])
    @commands.cooldown(rate = 3, per = 300)
    async def accept(self, ctx, *args):
        if self.is_on_team(ctx.author.id):
            return await ctx.message.reply(embed = self.get_embed(f'You are already on a team\n'
                                           f'Run {self.bot.prefix}leave {self.get_team_name(ctx.author.id)} to leave your team'),
                                           mention_author = False)
        team_name = " ".join(args)
        team = self.teams[team_name]
        if ctx.author.id not in team['invites']:
            return await ctx.message.reply(embed = self.get_embed(f'You have not received an invite from `{team_name}`'),
                                           mention_author = False)

        team['invites'].remove(ctx.author.id)
        team['members'].append(ctx.author.id)
        self.players[str(ctx.author.id)] = team_name
        self.save_players()
        self.update_teams(team_name, team)

        await self.announce(ctx, f"<@{ctx.author.id}> joined `{team_name}`")

        return await ctx.message.reply(embed = self.get_embed(f'You have successfully joined `{team_name}`'),
                                       mention_author = False)

    @commands.command(name = 'uninvite')
    async def uninvite(self, ctx, player: discord.User):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(embed = self.get_embed(f'You are not on a team'),
                                           mention_author = False)

        team = self.get_team(ctx.author.id)
        team_name = team['name']
        if team['leader'] != ctx.author.id:
            return await ctx.message.reply(embed = self.get_embed(f'You are not a team leader. Only team leaders can uninvite players'),
                                           mention_author = False)

        if player.id not in team['invites']:
            return await ctx.message.reply(embed = self.get_embed(f'User has not been invited to `{team_name}`'),
                                           mention_author = False)

        team['invites'].remove(player.id)
        self.update_teams(team['name'], team)

        return await ctx.message.reply(embed = self.get_embed(f'<@{player.id}> has been uninvited from `{team_name}`'),
                                       mention_author = False)

    @commands.command(name = 'reject')
    async def reject(self, ctx, *args):
        team_name = " ".join(args)
        team = self.teams[team_name]
        if ctx.author.id not in team['invites']:
            return await ctx.message.reply(embed = self.get_embed(f'You have not received an invite from `{team_name}`'),
                                           mention_author = False)

        team['invites'].remove(ctx.author.id)
        self.update_teams(team['name'], team)

        return await ctx.message.reply(embed = self.get_embed(f'You have rejected `{team_name}`\'is invite'),
                                       mention_author = False)

    @commands.command(name = 'leave', usage = 'leave <team_name>')
    @commands.cooldown(rate = 3, per = 300)
    async def leave(self, ctx, *args):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(embed = self.get_embed(f'You are not on a team'),
                                           mention_author = False)
        team_name = " ".join(args)
        team = self.teams[team_name]
        if ctx.author.id not in team['members']:
            return await ctx.message.reply(embed = self.get_embed(f'You are not in `{team_name}`'),
                                           mention_author = False)

        if team['leader'] == ctx.author.id:
            return await ctx.message.reply(embed = self.get_embed(f'You are the team leader. Team leaders must use `{self.bot.prefix}disband <team_name>` instead'),
                                           mention_author = False)

        team['members'].remove(ctx.author.id)
        self.players.pop(str(ctx.author.id))
        self.save_players()
        self.update_teams(team_name, team)

        await self.announce(ctx, f"<@{ctx.author.id}> left `{team_name}`")

        return await ctx.message.reply(embed = self.get_embed(f'You have successfully left `{team_name}`'),
                                       mention_author = False)

    @commands.command(name = 'disband', aliases = ['abandon'], usage = 'disband <team_name>')
    async def disband(self, ctx, *args):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(embed = self.get_embed(f'You are not on a team'),
                                           mention_author = False)

        arg_name = " ".join(args)

        team = self.get_team(ctx.author.id)
        team_name = team['name']

        if arg_name != team_name:
            return await ctx.message.reply(embed = self.get_embed(f'You are not in team `{arg_name}`'),
                                           mention_author = False)

        if team['leader'] != ctx.author.id:
            return await ctx.message.reply(embed = self.get_embed(f'You are not a team leader. Only team leaders can disband the team'),
                                           mention_author = False)

        for member in team['members']:
            self.players.pop(str(member))

        for team_2 in self.teams.values():
            if team_2['sign_up_position'] > team['sign_up_position']:
                team_2['sign_up_position'] -= 1
                self.teams[team_2['name']] = team_2

        self.teams.pop(team_name)
        self.save_teams()
        self.save_players()

        await self.announce(ctx, f"`{team_name}` has been disbanded by <@{ctx.author.id}>")

        return await ctx.message.reply(embed = self.get_embed(f'Successfully disbanded {team_name}'),
                                       mention_author = False)

    @commands.command(name = 'kick', aliases = ['remove'], usage = 'kick <DiscordID>')
    async def kick(self, ctx, player: discord.User):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(embed = self.get_embed(f'You are not on a team'),
                                           mention_author = False)

        team = self.get_team(ctx.author.id)
        team_name = team['name']
        if team['leader'] != ctx.author.id:
            return await ctx.message.reply(embed = self.get_embed(f'You are not a team leader. Only team leaders can kick players'),
                                           mention_author = False)

        if player.id not in team['members']:
            return await ctx.message.reply(embed = self.get_embed(f'User is not in `{team_name}`'),
                                           mention_author = False)

        team['members'].remove(player.id)
        self.update_teams(team['name'], team)
        self.players.pop(player.id)
        self.save_players()

        await self.announce(ctx, f"`{team_name}` has been kicked from the tourney by <@{ctx.author.id}>")

        return await ctx.message.reply(embed = self.get_embed(f'<@{player.id}> has been kicked from `{team_name}`'),
                                       mention_author = False)

    @commands.command(name = 'info', aliases = ['i'])
    async def info(self, ctx, player: discord.User):
        if not self.is_on_team(player.id):
            return await ctx.message.reply(embed = self.get_embed(f'User is not on a team'),
                                           mention_author = False)

        return await ctx.message.reply(embed = self.info_embed(self.get_team(player.id)),
                                       mention_author = False)

    def info_embed(self, team):
        string = ''
        string += f'Name: {team["name"]}, ID: {team["id"]}\n'
        string += f'Wins: {team["wins"]}\n'
        string += f'Losses: {team["loses"]}\n'
        string += f'Members: {["<@" + x + ">" for x in team["members"]]}\n'
        string += f'Invites: {["<@" + x + ">" for x in team["invites"]]}\n'
        string += f'Sign Up Position: {team["sign_up_position"]}\n'
        return self.get_embed(string)

    @commands.command(name = 'setmaxplayers')
    async def set_max_players(self, ctx, max_players):
        if not any([discord.utils.get(ctx.guild.roles, id = x) in ctx.author.roles for x in self.manager_roles]):
            return await ctx.message.reply(embed = self.get_embed(f'You are not a manager. Only managers can set max players'),
                                           mention_author = False)

        max_players = int(max_players)
        self.max_players = max_players
        return await ctx.message.reply(embed = self.get_embed(f'Max players set to {self.max_players}'),
                                       mention_author = False)

    @commands.command(name = 'setmaxteams')
    async def set_max_teams(self, ctx, max_teams):
        if not any([discord.utils.get(ctx.guild.roles, id = x) in ctx.author.roles for x in self.manager_roles]):
            return await ctx.message.reply(embed = self.get_embed(f'You are not a manager. Only managers can set max teams'),
                                           mention_author = False)

        max_teams = int(max_teams)
        self.max_teams = max_teams
        return await ctx.message.reply(embed = self.get_embed(f'Max teams set to {self.max_teams}'),
                                       mention_author = False)

    @commands.command(name = 'cleargames')
    async def clear_games(self, ctx):
        if not any([discord.utils.get(ctx.guild.roles, id = x) in ctx.author.roles for x in self.manager_roles]):
            return await ctx.message.reply(embed = self.get_embed(f'You are not a manager. Only managers can clear games'),
                                           mention_author = False)

        for team in self.teams:
            team['games'] = []
            self.teams[team['name']] = team

        return await ctx.message.reply(embed = self.get_embed(f'Successfully cleared all games'),
                                       mention_author = False)

    @commands.command(name = 'kickteam')
    async def kick_team(self, ctx, *args):
        if not any([discord.utils.get(ctx.guild.roles, id = x) in ctx.author.roles for x in self.manager_roles]):
            return await ctx.message.reply(embed = self.get_embed(f'You are not a manager. Only managers can clear games'),
                                           mention_author = False)

        team_name = " ".join(args)
        if team_name not in self.teams.keys():
            return await ctx.message.reply(embed = self.get_embed(f'Team {team_name} does not exist'),
                                           mention_author = False)

        for team_2 in self.teams.values():
            if team_2['sign_up_position'] > self.teams['team_name']['sign_up_position']:
                team_2['sign_up_position'] -= 1
                self.teams[team_2['name']] = team_2
        self.teams.pop(team_name)
        self.save_teams()

        return await ctx.message.reply(embed = self.get_embed(f'Successfully removed team {team_name}'),
                                       mention_author = False)

    async def announce(self, ctx, message):
        channel = discord.utils.get(ctx.guild.channels, id = self.announce_channel)
        return await channel.send(message)

    def get_embed(self, description):
        return discord.Embed(
            description = description
        ).set_footer(text = 'Tourney bot by Shroomie')


    # score game
    # view teams lb


async def setup(bot):
    await bot.add_cog(Tourney(bot))
