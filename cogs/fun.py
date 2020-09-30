import discord
from discord.ext import tasks, commands
from .Server import Server

from tinydb import TinyDB, where
from tinydb.operations import set

import datetime
from datetime import date
from random import seed
from random import choice
import time

class FunCog(commands.Cog, Server):

    def __init__(self, client):
        self.client = client
        self.events = TinyDB('database/events.json')
        self.users = TinyDB('database/users.json')

        Server.__init__(self)

        self.noon = datetime.datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)

        lastCoolGuy = self.events.get(where('name') == 'coolguy')['last']
        self.lastCoolGuy = datetime.datetime.strptime(lastCoolGuy.replace("-",""), "%Y%m%d").date()

        self.activeUsers = self.events.get(where('name') == 'coolguy')['activeUsers']

        self.CheckBirthday.start()
    
    @tasks.loop(hours=24)
    async def CheckBirthday(self):

        userBirthdays = self.users.search(where('birthday').exists())

        for user in userBirthdays:
            if (user['birthday'] == str(datetime.datetime.now().date())):
                general = self.client.get_guild(self.server).get_channel(self.generalChannel)
                await general.send("**Happy Birthday <@" + str(user['id']) + ">!** :birthday: :tada:")

    @staticmethod
    def is_cool_candidate(member):
        return member and (not member.bot) and (not member.guild_permissions.manage_messages)

    @staticmethod
    def pick_from_array(choices, member_resolver=None, skip_these=None):
        mutable = choices
        while (len(mutable)):
            pick = choice(mutable)
            resolved = ( pick and member_resolver.get_member(pick) ) \
                if member_resolver else pick

            if (not resolved) or \
                (skip_these and (resolved in skip_these) or \
                (not FunCog.is_cool_candidate(resolved)) ):

                if (not resolved):
                    print('failed to resolve a member with id:' + str(pick))

                # rather than a huge copy of the member list we'll make a clone 
                # of it only when we need to (which hopefully is rare)
                if (mutable is choices):
                    mutable = choices[0:]

                # remove the choice so that it is not picked again.
                mutable.remove(pick)
                pick = None
            else:
                return resolved

        return None
            



    @commands.Cog.listener()
    async def on_message(self, message):

        #Temp remove messages with content in drawing arena
        if (message.channel.id == 750753280694550539 and message.content != ""):
            await message.delete()
        
        member = message.author

        #Add non-staff to list of active users
        if (not member.bot and (str(member.id) not in self.activeUsers and not member.guild_permissions.manage_messages)):
            self.activeUsers.append(str(member.id))
            self.events.update(set('activeUsers', self.activeUsers), where('name') == 'coolguy')

        #Cool guy raffle once a day
        now = datetime.datetime.now()
        if (now > self.noon and (date.today() > self.lastCoolGuy)) or \
            (message.content == '!newguy'):

            #Set date
            self.lastCoolGuy = date.today()
            self.events.update(set('last', str(self.lastCoolGuy)), where('name') == 'coolguy')

            coolGuyRole = message.guild.get_role(self.coolGuyRole)

            #Remove last cool guy(s)
            coolGuys = [] if coolGuyRole.members is None else coolGuyRole.members
            for coolGuy in coolGuys:
                await coolGuy.remove_roles(coolGuyRole)

            #New cool guys
            winners = list()

            print( 'active users are ('+str(len(self.activeUsers))+'):\n' + \
                ('\n'.join( self.activeUsers )) )

            found = self.pick_from_array(
                self.activeUsers,
                member_resolver=message.guild)
            
            if found:
                winners.append(found)

            while (2 != len(winners)):
                found = self.pick_from_array(
                    message.guild.members,
                    skip_these=winners
                )
                if found:
                    winners.append(found)
                else:
                    break

            for winner in winners:
                await winner.add_roles(coolGuyRole)
            
            general = message.guild.get_channel(self.generalChannel)
            await general.send(
                "No one won the cool guy raffle." if 0 == len(winners) else
                (winners[0].mention + " won the cool guy raffle!") if 1 == len(winners) else \
                (', '.join(winner.mention for winner in winners[:-1])) + \
                " and " +winners[-1].mention + \
                "won the cool guy raffle!")

            #Reset active users
            self.activeUsers = []
            self.events.update(set('activeUsers', self.activeUsers), where('name') == 'coolguy')

def setup(client):
    client.add_cog(FunCog(client))