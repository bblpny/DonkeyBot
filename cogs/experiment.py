import discord
from discord.ext import commands
from .Server import Server

from tinydb import TinyDB, where
from tinydb.operations import set

import re
import datetime

class ExperimentCog(commands.Cog, Server):
    def __init__(self, client):
        self.client = client
        self.events = TinyDB('database/events.json')
        self.users = TinyDB('database/users.json')

        Server.__init__(self)

        #Experiment channel combo
        self.combo = self.events.get(where('name') == 'experiment')['combo']
    
    #centralized checking code.
    @staticmethod
    def regex_count_search(text, old_school = False):
        if not old_school:
            text = re.sub(
                #urls. this was what i was planning on doing after emotes got patched..
                r'(http|ftp|https)://([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?' r'|'
                #emoji
                r'<:.+?:\d+>' r'|'
                #animated emoji
                r'<a:.+?:\d+>' r'|'
                #mentions
                r'<@.+?\d+>' r'|'
                r'<@!.+?\d+>' r'|'
                #role mentions
                r'<@&.+?\d+>' r'|'
                #channel mentions.
                r'<#.+?\d+>' r'|'
                ,
                #empty string.
                '', text)
        
        print(text)

        return re.search(r'\d+', text)

    @staticmethod
    def regex_count_group(reggie):
        return 0 if reggie is None else reggie.group()

    @staticmethod
    def regex_count(value):
        return ExperimentCog.regex_count_group( 
            ExperimentCog.regex_count_search(value)
            )

    #check if the member is relevant to posting numbers.
    @staticmethod
    def is_relevant_member(member):
        return (not member.bot) and (not member.guild_permissions.manage_messages)

    def get_good_role(self, guild):
        return guild.get_role(
            self.goodRole
            )

    def get_bad_role(self, guild):
        return guild.get_role(
            self.badRole
        )
    
    def get_role_pair(self, guild, good_first=True):
        if good_first:
            return self.get_good_role(guild), \
                self.get_bad_role(guild)
        else:
            return self.get_bad_role(guild), \
                self.get_good_role(guild)

    def has_role(self,guild,member,role=None):
        
        if(role == 'good'):
            role = self.get_good_role(guild)
        elif(role == 'bad'):
            role = self.get_bad_role(guild)

        return role and member.roles and role in member.roles

    async def set_role(self, member, guild, good_true, no_exchange=False):

        add_role, remove_role = self.get_role_pair(guild,good_true)

        if ( not ( add_role in member.roles ) ):

            if (not no_exchange) and \
                (not (remove_role is add_role)) and \
                self.has_role(guild, member, role=remove_role) :
                await member.remove_roles( remove_role )
            
            await member.add_roles( add_role )



    @commands.Cog.listener()
    async def on_member_join(self, member):

        #Give saved roles
        server = self.client.get_guild(self.server)

        roles = [] if self.users.get(where('id') == member.id) is None else self.users.get(where('id') == member.id)['roles']

        for role in roles:
            await member.add_roles(server.get_role(role))

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):

        if (before.channel.id == self.experimentChannel):
            #Write to channel when someone changes the number i guess 
            if self.regex_count(after.content) != self.regex_count(before.content):
                await after.channel.send(after.author.mention + " edited their message\n> " + before.content)
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        
        member = message.author

        #Punish griefers
        if ((message.channel.id == self.experimentChannel) and self.is_relevant_member(member)): #User was not staff or bot
            try:
                #regEx = self.regex_count_search(message.content)
                #firstInt = self.regex_count_group(regEx) # 0 if regEx is None else regEx.group()
                firstInt = self.regex_count(message.content)
                
                await message.channel.send("> " + firstInt + "\n<@" + str(member.id) + ">")
                
                #Remove good role, add bad role
                await self.set_role(member, message.guild, False)

                self.users.upsert({ 'id': member.id, 'roles': [ self.badRole ] }, where('id') == member.id)
            except:
                pass
    
    @commands.Cog.listener()
    async def on_message(self, message):

        member = message.author

        if (message.channel.id == self.experimentChannel):

            canPost = True
    
            #Check for staff members and enforce slowmode
            if (member.guild_permissions.manage_messages and not member.bot):
                
                if (message.guild.get_role(self.badRole) in member.roles):
                    canPost = False
                else:
                    now = datetime.datetime.now()
                    #glaze: I add leet or []
                    if ('experimentTS' in (self.users.get(where('id') == member.id) or [])):

                        last = datetime.datetime.strptime(self.users.get(where('id') == member.id)['experimentTS'], "%Y-%m-%d %H:%M:%S")

                        if ((now - last).total_seconds() >= message.channel.slowmode_delay):
                            self.users.upsert({ 'experimentTS': str(datetime.datetime.strftime(now, "%Y-%m-%d %H:%M:%S")) }, where('id') == member.id)
                        else:
                            canPost = False
                            try:
                                await member.send("That channel has slowmode and you can't bypass it! haha!")
                            except:
                                pass #Cannot send message to this user
                    else:
                        self.users.upsert({ 'experimentTS': str(datetime.datetime.strftime(now, "%Y-%m-%d %H:%M:%S")) }, where('id') == member.id)

            if canPost:
                count = int(self.combo)
                nextCountStr = str(count+1) #Expected next combo

                #Successful combo
                #regEx = self.regex_count_search(message.content)
                #firstInt = self.regex_count_group(regEx) # 0 if regEx is None else regEx.group()
                firstInt = self.regex_count(message.content)

                if (firstInt == nextCountStr):

                    self.combo = count + 1
                    self.events.update(set('combo', str(self.combo)), where('name') == 'experiment')
                    
                    #Give good role to first time participants
                    if not ( self.has_role(message.guild, member, role="good") ):
                        await self.set_role(member, message.guild, True, no_exchange=True)
                        self.users.upsert({ 'id': member.id, 'roles': [ self.goodRole ] }, where('id') == member.id)
                
                #Unsuccessful combo
                elif (not member.bot):
                    #glaze or hack again.
                    best = (message.channel.topic or 'Best: 0').split("Best: ", 1)[1] #Get record from topic

                    countdownMessage = "<@" + str(member.id) + "> broke <#"+str(self.experimentChannel)+"> <:luigisad:406759665058185226>"
                    if (count > int(best)): #If new record, append to message
                        countdownMessage += " **(NEW BEST: " + str(count) + ")**"
                        await message.channel.edit(topic="Best: " + str(count))

                    countdownMessage += "\n> " + message.content

                    #glaze thinks when the experiment breaks it shouldn't ressurect things
                    if count > 1:
                        #Send previous message
                        lastmsg = await message.channel.history(limit=2).flatten()

                        try:
                            countdownMessage += "\nPrevious message:\n> " + lastmsg[1].content
                        except Exception as exception:
                            print(exception)

                    notifChannel = message.guild.get_channel(self.labChannel)
                    await notifChannel.send(countdownMessage)

                    #Remove good role, add bad role
                    await self.set_role(member, message.guild, False)

                    self.users.upsert({ 'id': member.id, 'roles': [ self.badRole ] }, where('id') == member.id)

                    #Delete all messages in the channel
                    messagesDeleted = await message.channel.purge(limit=100)
                    while (len(messagesDeleted) != 0):
                        messagesDeleted = await message.channel.purge(limit=100)

                    #Reset combo
                    self.combo = 0
                    self.events.update(set('combo', str(self.combo)), where('name') == 'experiment')
            else:
                await message.delete()
            
def setup(client):
    client.add_cog(ExperimentCog(client))
