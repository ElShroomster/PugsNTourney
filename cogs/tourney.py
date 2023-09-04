from discord.ext import commands
import discord
import json

teams_file = 'data/teams.json'
players_file = 'data/players.json'


class Tourney(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.teams = json.load(open(teams_file, 'r'))
        self.players = json.load(open(players_file, 'r'))

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
        return {
            'name': name,
            'leader': leader,
            'members': [leader],
            'invites': [],
            'wins': 0,
            'losses': 0,
            'games': []
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
    async def register(self, ctx, *args):
        if self.is_on_team(ctx.author.id):
            return await ctx.message.reply(f'You are already on the team `{self.get_team_name(ctx.author.id)}`',
                                           mention_author = False)

        if len(args) == 0:
            return await ctx.message.reply(f'Please state a team name:\n'
                                           f'`{self.bot.prefix}register <team_name>`',
                                           mention_author = False)

        team_name = " ".join(args)
        if self.team_exists(team_name):
            return await ctx.message.reply(f'A team with the name `{team_name}` already exists',
                                           mention_author = False)

        self.teams[team_name] = self.create_new_team(team_name, ctx.author.id)
        self.players[str(ctx.author.id)] = team_name
        self.save_teams()
        self.save_players()
        return await ctx.message.reply(f'Team `{team_name}` created. Add players with:\n'
                                       f'{self.bot.prefix}invite <user>',
                                       mention_author = False)

    @commands.command(name = 'invite', aliases = ['add'], usage = 'invite <DiscordID>')
    async def invite(self, ctx, player: discord.User):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(f'You are not on a team',
                                           mention_author = False)

        team = self.get_team(ctx.author.id)
        team_name = team['name']
        if team['leader'] != ctx.author.id:
            return await ctx.message.reply(f'You are not a team leader. Only team leaders can invite players',
                                           mention_author = False)

        if player.id in team['invites']:
            return await ctx.message.reply(f'User has already been invited to `{team_name}`',
                                           mention_author = False)

        if player.id in team['members']:
            return await ctx.message.reply(f'User is already on `{team_name}`',
                                           mention_author = False)

        team['invites'].append(player.id)
        self.update_teams(team['name'], team)

        return await ctx.message.reply(f'<@{player.id}> has been invited to `{team_name}`\n'
                                       f'To accept this invite, they must run `{self.bot.prefix}accept {team_name}`',
                                       mention_author = False)

    @commands.command(name = 'accept', aliases = ['join'])
    async def accept(self, ctx, *args):
        if self.is_on_team(ctx.author.id):
            return await ctx.message.reply(f'You are already on a team\n'
                                           f'Run {self.bot.prefix}leave {self.get_team_name(ctx.author.id)} to leave your team',
                                           mention_author = False)
        team_name = " ".join(args)
        team = self.teams[team_name]
        if ctx.author.id not in team['invites']:
            return await ctx.message.reply(f'You have not received an invite from `{team_name}`',
                                           mention_author = False)

        team['invites'].remove(ctx.author.id)
        team['members'].append(ctx.author.id)
        self.players[str(ctx.author.id)] = team_name
        self.save_players()
        self.update_teams(team_name, team)

        return await ctx.message.reply(f'You have successfully joined `{team_name}`',
                                       mention_author = False)

    @commands.command(name = 'uninvite')
    async def uninvite(self, ctx, player: discord.User):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(f'You are not on a team',
                                           mention_author = False)

        team = self.get_team(ctx.author.id)
        team_name = team['name']
        if team['leader'] != ctx.author.id:
            return await ctx.message.reply(f'You are not a team leader. Only team leaders can uninvite players',
                                           mention_author = False)

        if player.id not in team['invites']:
            return await ctx.message.reply(f'User has not been invited to `{team_name}`',
                                           mention_author = False)

        team['invites'].remove(player.id)
        self.update_teams(team['name'], team)

        return await ctx.message.reply(f'<@{player.id}> has been uninvited from `{team_name}`',
                                       mention_author = False)

    @commands.command(name = 'reject')
    async def reject(self, ctx, *args):
        team_name = " ".join(args)
        team = self.teams[team_name]
        if ctx.author.id not in team['invites']:
            return await ctx.message.reply(f'You have not received an invite from `{team_name}`',
                                           mention_author = False)

        team['invites'].remove(ctx.author.id)
        self.update_teams(team['name'], team)

        return await ctx.message.reply(f'You have rejected `{team_name}`\'is invite',
                                       mention_author = False)

    @commands.command(name = 'leave', usage = 'leave <team_name>')
    async def leave(self, ctx, *args):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(f'You are not on a team\n',
                                           mention_author = False)
        team_name = " ".join(args)
        team = self.teams[team_name]
        if ctx.author.id not in team['members']:
            return await ctx.message.reply(f'You are not in `{team_name}`',
                                           mention_author = False)

        if team['leader'] == ctx.author.id:
            return await ctx.message.reply(f'You are the team leader. Team leaders must use `{self.bot.prefix}disband <team_name>` instead',
                                           mention_author = False)

        team['members'].remove(ctx.author.id)
        self.players.pop(str(ctx.author.id))
        self.save_players()
        self.update_teams(team_name, team)

        return await ctx.message.reply(f'You have successfully left `{team_name}`',
                                       mention_author = False)

    @commands.command(name = 'disband', aliases = ['abandon'], usage = 'disband <team_name>')
    async def disband(self, ctx, *args):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(f'You are not on a team',
                                           mention_author = False)

        arg_name = " ".join(args)

        team = self.get_team(ctx.author.id)
        team_name = team['name']

        if arg_name != team_name:
            return await ctx.message.reply(f'You are not in team `{arg_name}`',
                                           mention_author = False)

        if team['leader'] != ctx.author.id:
            return await ctx.message.reply(f'You are not a team leader. Only team leaders can disband the team',
                                           mention_author = False)

        for member in team['members']:
            self.players.pop(str(member))

        self.teams.pop(team_name)
        self.save_teams()
        self.save_players()

        return await ctx.message.reply(f'Successfully disbanded {team_name}',
                                       mention_author = False)

    @commands.command(name = 'kick', aliases = ['remove'], usage = 'kick <DiscordID>')
    async def kick(self, ctx, player: discord.User):
        if not self.is_on_team(ctx.author.id):
            return await ctx.message.reply(f'You are not on a team',
                                           mention_author = False)

        team = self.get_team(ctx.author.id)
        team_name = team['name']
        if team['leader'] != ctx.author.id:
            return await ctx.message.reply(f'You are not a team leader. Only team leaders can kick players',
                                           mention_author = False)

        if player.id not in team['members']:
            return await ctx.message.reply(f'User is not in `{team_name}`',
                                           mention_author = False)

        team['members'].remove(player.id)
        self.update_teams(team['name'], team)
        self.players.pop(player.id)
        self.save_players()

        return await ctx.message.reply(f'<@{player.id}> has been kicked from `{team_name}`',
                                       mention_author = False)
    # score game


async def setup(bot):
    await bot.add_cog(Tourney(bot))
