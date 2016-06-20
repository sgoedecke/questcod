import libtcodpy as libtcod
import math
import textwrap
import shelve

SCREEN_WIDTH = 120
SCREEN_HEIGHT = 80
LIMIT_FPS = 20
MAP_WIDTH = 80
MAP_HEIGHT = 73 #map height is lower to leave room for the UI on the bottom

#sizes and coordinates relevant for the GUI
BAR_WIDTH = 50
HUD_HEIGHT = 7
HUD_Y = SCREEN_HEIGHT - HUD_HEIGHT
PANEL_HEIGHT = SCREEN_HEIGHT
PANEL_WIDTH = SCREEN_WIDTH - (MAP_WIDTH+2)
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT


#stats for message bar - important!
MSG_X = MAP_WIDTH + 2  #where the message panel starts
MSG_WIDTH = PANEL_WIDTH
MSG_HEIGHT = MAP_HEIGHT

#create the list of game messages and their colors, starts empty
game_msgs = []

FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 100

#"$(CURRENT_DIRECTORY)\debug_py.bat" "$(CURRENT_DIRECTORY)" $(FILE_NAME)

#### vibrant color set####
'''
color_dark_wall = libtcod.dark_amber
color_light_wall = libtcod.amber
color_dark_ground = libtcod.desaturated_turquoise
color_light_ground = libtcod.darker_sea
color_dark_river = libtcod.desaturated_azure
color_light_river = libtcod.azure
color_dark_jetty = libtcod.sepia
color_light_jetty = libtcod.dark_sepia
'''
####depressing color set###

color_dark_wall = libtcod.desaturated_orange
color_light_wall = libtcod.darkest_grey
color_dark_ground = libtcod.darker_sepia
color_light_ground = libtcod.Color(170,166,134)
color_dark_river = libtcod.darkest_azure
color_light_river = libtcod.darkest_sky
color_dark_jetty = libtcod.darkest_sepia
color_light_jetty = libtcod.dark_sepia

color_dark_shrub = libtcod.Color(0,50,0)
color_light_shrub = libtcod.darkest_green
color_dark_path = libtcod.light_sepia
color_light_path = libtcod.dark_sepia
###
#depressing -> intermediate
#color_light_ground = libtcod.lightest_yellow
### intermediate color set###
'''
color_dark_wall = libtcod.darker_amber
color_light_wall = libtcod.darkest_grey
color_dark_ground = libtcod.dark_sepia
color_light_ground = libtcod.lightest_lime
color_dark_river = libtcod.darkest_sky
color_light_river = libtcod.darker_sky
color_dark_jetty = libtcod.darkest_sepia
color_light_jetty = libtcod.dark_sepia
'''
######
class Tile:
	#a tile of the map
	def __init__(self, blocked, block_sight = None, river = 0, border = 0, color = 0, shrub = 0, path = 0):
		self.blocked = blocked
		self.river = river
		self.border = border
		self.color = color
		self.shrub = shrub
		self.path = path
		#all tiles start unexplored
		self.explored = False
		#if a tile is blocked, it blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight



class Shout:
	def __init__(self,x,y, color, msg, time, name):
		self.x = x
		self.y = y
		self.color = color
		self.msg = msg
		self.time = time
		self.name = name


	def clear(self):
		for x in range(len(self.msg)):
			libtcod.console_print_ex(con, self.x + x, self.y, libtcod.BKGND_NONE, libtcod.LEFT, " ")

	def draw(self):
		if libtcod.map_is_in_fov(fov_map, self.x, self.y):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_print_ex(con, self.x, self.y, libtcod.BKGND_NONE, libtcod.LEFT, self.msg)
		else:
			self.clear()

	def tick(self):
		self.time -= 1
		if self.time <= 0:
			#remove shout
			self.clear()
			shouts.remove(self)


class Rect:
	#a rectangle on the map. used to characterize a room.
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h
		self.h = h
		self.w = w

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on screen.
	def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None, food = 0, gear = 0, msgcolor = None):
		self.x = x
		self.y = y
		self.char = char
		self.color = color
		self.name = name
		self.blocks = blocks
		self.food = food
		self.gear = gear
		self.dead = False
		if msgcolor == None:	#unless message color specified, set it to self color
			self.msgcolor = self.color
		else:
			self.msgcolor = msgcolor


		self.fighter = fighter
		if self.fighter:  #if it's a fighter, let the fighter component know who owns it
			self.fighter.owner = self

		self.ai = ai
		if self.ai:  #if it's got AI, let the AI component know who owns it
			self.ai.owner = self

	def say(self, msg):
		global game_msgs
		shouts.append(Shout(self.x, self.y - 1,self.color, msg, 10, self.name)) # number is shout length
		#remember to put the shout just above the character
		full_message = self.name + ": " + msg
		#get last line of wrapped message
		last_line = textwrap.wrap(full_message,MSG_WIDTH)
		last_line = last_line[len(last_line)-1]

		if game_msgs[len(game_msgs)- 1][0] != last_line:	#check to make sure the message isn't being repeated
			message(full_message, self.msgcolor)

	def move(self, dx, dy):
		#move by the given amount

		#if the entity is in a river, it gets swept down!
		if is_river(self.x, self.y) and self.y + 3 <= MAP_HEIGHT:
			self.y += 2
			for i in range(3):
				check_for_logs(self.x,self.y-i)

		#check if you can move!
		if self == player and is_border(self.x + dx,self.y+dy)>0: #check if moving to border
			leave_stage(is_border(self.x + dx,self.y+dy)) #leave the stage
			return
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy






	def move_astar(self, target):
		self.clear()
		#Create a FOV map that has the dimensions of the map
		fov = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)

		#Scan the current map each turn and set all the walls as unwalkable
		for y1 in range(MAP_HEIGHT):
			for x1 in range(MAP_WIDTH):
				libtcod.map_set_properties(fov, x1, y1, not map[x1][y1].block_sight, not map[x1][y1].blocked)

		#Scan all the objects to see if there are objects that must be navigated around
		#Check also that the object isn't self or the target (so that the start and the end points are free)
		#The AI class handles the situation if self is next to the target so it will not use this A* function anyway
		for obj in objects:
			if obj.blocks and obj != self and obj != target:
				#Set the tile as a wall so it must be navigated around
				libtcod.map_set_properties(fov, obj.x, obj.y, True, False)

		#Allocate a A* path
		#The 1.41 is the normal diagonal cost of moving, it can be set as 0.0 if diagonal moves are prohibited
		my_path = libtcod.path_new_using_map(fov, 0.0)

		#Compute the path between self's coordinates and the target's coordinates
		libtcod.path_compute(my_path, self.x, self.y, target.x, target.y)

		#Check if the path exists, and in this case, also the path is shorter than 25 tiles
		#The path size matters if you want the monster to use alternative longer paths (for example through other rooms) if for example the player is in a corridor
		#It makes sense to keep path size relatively low to keep the monsters from running around the map if there's an alternative path really far away
		if not libtcod.path_is_empty(my_path) and libtcod.path_size(my_path) < 100:
			#Find the next coordinates in the computed full path
			x, y = libtcod.path_walk(my_path, True)
			if x or y:
				#Set self's coordinates to the next path tile
				self.x = x
				self.y = y
		else:
			#Keep the old move function as a backup so that if there are no paths (for example another monster blocks a corridor)
			#it will still try to move towards the player (closer to the corridor opening)
			self.move_towards(target.x, target.y)

	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)

		#normalize it to length 1 (preserving direction), then round it and
		#convert to integer so the movement is restricted to the map grid
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)

	def distance_to(self, other):
		#return the distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)

	def draw(self):
		#set the color and then draw the character that represents this object at its position
		if libtcod.map_is_in_fov(fov_map, self.x, self.y):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
			#set angry background if angry
			if self.fighter != None and self.name != 'player':
				libtcod.console_set_char_background(con, self.x, self.y, libtcod.light_red, libtcod.BKGND_SET)

	def send_to_back(self):
		#make this object be drawn first, so all others appear above it if they're in the same tile.
		global objects
		objects.remove(self)
		objects.insert(0, self)

	def clear(self):
		#erase the character that represents this object
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

class Fighter:
	#combat-related properties and methods (monster, player, NPC).
	def __init__(self, hp, defense, power, death_function=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.death_function = death_function

	def take_damage(self, damage):
	#apply damage if possible
		if damage > 0:
			self.hp -= damage

	#check for death. if there's a death function, call it
		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				function(self.owner)

	def attack(self, target):
		#a simple formula for attack damage
		damage = self.power - target.fighter.defense

		if damage > 0:
			#make the target take some damage
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.', libtcod.light_gray)
			target.fighter.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!', libtcod.light_gray)


#AI classes

class BasicMonster:
	#AI for a basic monster.
	def take_turn(self):
		#a basic monster takes its turn. If you can see it, it can see you
		monster = self.owner

		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

			#move towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_astar(player)

			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				monster.say("Take that!")
				monster.fighter.attack(player)

class HutParent:
	def __init__(self):
		self.timer = 0
	def take_turn(self):
		monster = self.owner
		self.timer += 1
		if self.timer == 5:
			if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
				monster.say("Go inside.")
		if self.timer == 15:
			if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
				monster.say("Hurry, child!")
class HutChild:
	def __init__(self):
		self.timer = 0
	def take_turn(self):
		global hutDweller
		monster = self.owner
		self.timer += 1
		if self.timer == 3:
			if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
				monster.say("Look, mother!")
		if self.timer == 10:
			if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
				monster.say("There's a man in the river!")
		if self.timer >= 16:
			monster.move_astar(hutDweller)
class BlackLegion:
	#AI for a soldier of the Black Legion
	def __init__(self, target = None):
		global player
		self.target = target
		if self.target == None:
			self.target = player
	def take_turn(self):
		#a basic monster takes its turn. If you can see it, it can see you
		monster = self.owner

#		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
		if 1==1:
			#move towards player if far away
			oldx=monster.x
			oldy=monster.y
			if monster.distance_to(self.target) >= 2:
	#			monster.move_towards(self.target.x,self.target.y)
				monster.move_astar(self.target)				#lag purposes
				if map[monster.x][monster.y].river > 0:
					monster.x = oldx
					monster.y = oldy

				#close enough, attack! (if the player is still alive.)
			else:
				if self.target.fighter != None:
					if self.target.fighter.hp > 0:
						monster.say("Die, scum!")
						monster.fighter.attack(self.target)

			slogan = libtcod.random_get_int(0,0,500)
			if slogan == 1: #small chance of yelling
				monster.say("For the Black Legion!")
			elif slogan == 2:
				monster.say("The day is ours!")
			elif slogan == 3:
				monster.say("Forward!")
class LegionDigger:
	def __init__(self):
		self.timer = 10
	def take_turn(self):
		monster = self.owner
		self.timer += 1
		if self.timer >= 10:
			if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
				slogan = libtcod.random_get_int(0,0,4) #DEBUG - should be 300
				if slogan == 1: #small chance of yelling
					monster.say("Dig, men!")
				elif slogan == 2:
					monster.say("The tunnel must be completed!")
				elif slogan == 3:
					monster.say("Dig faster!")
				self.timer = 0
class LegionTalker:
	def __init__(self):
		self.timer = 0
	def take_turn(self):
		monster = self.owner
		self.timer += 1
		if self.timer == 11:
			monster.say("There's one left - kill him!")


		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			slogan = libtcod.random_get_int(0,0,300) #DEBUG - should be 300
			if slogan == 1: #small chance of yelling
				monster.say("Their siege has been crushed!")
			elif slogan == 2:
				monster.say("Kill the survivor!")
			elif slogan == 3:
				monster.say("No quarter, men!")

			#move towards player if far away - but very slowly
			if slogan < 50:
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(player) >= 2:
					monster.move_astar(player)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy

			#close enough, attack! (if the player is still alive.)
				elif player.fighter.hp > 0:
					monster.say("To die by my hand - what honor!")
					monster.fighter.attack(player)

class BasicTalker:
	#AI for a basic monster.
	def take_turn(self):
		#a basic monster takes its turn. If you can see it, it can see you
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

			#move towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_astar(player)

			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				drunktalk(monster,"Have a great night! *hic*")

class FishermanDad:
	def __init__(self):
		self.player_in_water = True
		self.disposition = 5
		self.despair = False
		self.welcomed = False
	def take_turn(self):
		monster = self.owner
		global quest_giver
		if quest_giver.ending == True:
			return
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			if self.player_in_water == True and libtcod.random_get_int(0,0,50) > 25:	#only shout on some turns if the player is in the river
				monster.say("Over here!")
			if self.welcomed == True and self.despair == True:
				monster.say("All lost...")
			elif self.welcomed == True and self.despair == False and libtcod.random_get_int(0,0,10) == 10:
				monster.say("Good luck.")
		if monster.distance_to(player) <= 3 and self.welcomed == False:	#if next to player
			self.player_in_water = False
			self.welcome_talk()
			return
	def welcome_talk(self):
		global player_has_final_quest
		monster = self.owner
		choice = talk(monster, "That was a close one! Are you alright?", ["Yes, I'm fine.","You saved my life!","Go away, old man."], first_talk = True)
		if choice == 0 or choice == 1:
			choice = talk(monster,"Glad to hear it! How goes the war?",["I can't say.","We lost. The Black Legion are coming, and they will burn this town to the ground.","[Lie] The war goes well. Victory will soon be ours!"])
			if choice == 0 or choice == 2: #good or neutral response
				choice = talk(monster, "Well, I'm sure you've got it under control, sir. I'm too old for politics.",["Fair enough."])
				self.blacksmith_talk()
			elif choice == 1:
				choice = talk(monster, "That is grim news indeed. All lost, all burnt...",["What lies south of here? We all need to flee."])
				choice = talk(monster, "A wide desert, impossible to cross without substantial provisions. Too far for my old bones, I'm afraid. On the other side are the Free Cities, people say.", ["Can you provide anything for me?","I'm sorry."], first_talk = True)
				self.disposition += 1
				self.despair = True
				self.blacksmith_talk()
		elif choice == 2:
			choice = talk(monster,"Well, I'm sorry if I offended you, sir.",["You did."])
			self.disposition -= 3
			self.blacksmith_talk()
		player_has_final_quest = True
	def blacksmith_talk(self):
		global desert_crossing, blacksmith_quest

		self.welcomed = True

		monster = self.owner
		choice = talk(monster,"You ought to see the blacksmith. He can get you sorted out: a sword, maybe tools.",["Where can I find him?"], first_talk = True)
		choice = talk(monster,"The house to the north-west. Oh, and one more thing, sir...",["What is it?"], first_talk = True)
		if self.disposition > 5:
			choice = talk(monster,"Be careful about the blacksmith. He mistrusts soldiers.",["Thank you."], first_talk = True)
		elif self.disposition < 5:
			choice = talk(monster,"The blacksmith is a patriotic man. He'll do his best to help you.",["Of course."], first_talk = True)
		elif self.disposition == 5:
			choice = talk(monster,"Good luck.",["Thanks."])
		desert_crossing = Quest("Cross the desert!","Huh? You crossed the desert? How!?")
		quest_alert("New quest: " + desert_crossing.name, "Go south to cross the desert and find the Free Cities! You'll need to stock up on food and gear first, though.",desert_crossing, first_talk = True)
		blacksmith_quest = Quest("Gear up!", "You saw the blacksmith. He wasn't very helpful...")
		quest_alert("New quest: " + blacksmith_quest.name, "Go find the blacksmith in the house to the north-west and acquire some gear.", blacksmith_quest)

class BlacksmithAi:
	def __init__(self):
		self.fought_player = False
		self.disposition = 5
		self.welcomed = False
		self.pet_dead = False
	def take_turn(self):
		global quest_giver
		if quest_giver.ending == True:
			return
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

			if monster.fighter == None and self.welcomed == False:
				if libtcod.random_get_int(0,0,50) > 45:	#only shout on some turns if the player is in the river
					monster.say("A stranger!")
				if self.welcomed == True and self.fought_player == True:
					monster.say("I'm watching you...")
				elif self.welcomed == True and self.fought_player == False and libtcod.random_get_int(0,0,10) == 10:
					monster.say("Go on, then.")
				if monster.distance_to(player) <= 2 and self.welcomed == False:	#if next to player
					self.welcome_talk()
			elif monster.fighter != None:
				#move towards player if far away
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(player) >= 2:
					monster.move_astar(player)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy

				#close enough, attack! (if the player is still alive.)
				elif player.fighter.hp > 0:
					if self.pet_dead == True:
						monster.say("This is for my cat!")
					else:
						monster.say("Die, thief!")
					monster.fighter.attack(player)

				slogan = libtcod.random_get_int(0,0,500)
				if slogan == 1: #small chance of yelling
					monster.say("You'll never take my property!")
				elif slogan == 2:
					monster.say("Soldier scum!")

	def surrender(self):
		global blacksmith_quest
		monster = self.owner
		choice = talk(monster, "Alright, alright, don't kill me!", ["I'll let you live.","You want mercy? Not from me."], first_talk = True)
		if choice == 0:
			if self.pet_dead == False:
				choice = talk(monster,"Even if you killed me, you wouldn't get my tools. I've hidden them until the war is over. No thieving army is going to confiscate my livelihood!.",["Leave."],first_talk = True)
			if self.pet_dead == True:
				choice = talk(monster,"You'll still never get my tools, you cat-killing soldier bastard.",["Leave."],first_talk = True)
			if blacksmith_quest in quests:
				blacksmith_quest.completed()
		if choice == 1:
			self.die_for_real()

	def die_for_real(self):
		global blacksmith_quest, quests
		monster = self.owner
		message("You killed " + monster.name + "!",libtcod.light_red)
		monster.char = '%'
		monster.color = libtcod.dark_red
		monster.blocks = False
		monster.fighter = None
		monster.ai = None
		monster.name = 'remains of ' + monster.name
		monster.send_to_back()
		monster.dead = True

		if blacksmith_quest in quests:
			blacksmith_quest.completed()
#		if player
#			return
	def welcome_talk(self):
		global blacksmith_pet
		self.welcomed = True
		monster = self.owner
		choice = talk(monster, "Hello! With the army, are you?", ["Yes, I need some gear."], first_talk = True)
		choice = talk(monster,"I'm always happy to help a soldier. Death to the Black Legion! Go pick out what you need from my shed. It's just west of my house",["Okay, thanks.","I don't believe you're that patriotic."], first_talk = True)
		if choice == 0:
			blacksmith_pet.ai.angry = True
			return
		if choice == 1:
			choice = talk(monster,"You calling me a liar, boy?",["Yes, I am.","No, sorry."],first_talk = True)
			if choice == 0:
				self.fight()
			if choice == 1:
				blacksmith_pet.ai.angry = True
				return
	def fight(self):
		global blacksmith_pet
		monster = self.owner
		blacksmith_fighter_component = Fighter(hp=20,defense=1,power=5,death_function = blacksmith_loss)
		monster.fighter = blacksmith_fighter_component
		monster.fighter.owner = monster
		blacksmith_pet.ai.angry = False

class BlacksmithPetAi:
	def __init__(self):
		self.angry = False
		self.alive = True
		self.first_met_player = True
	def take_turn(self):
		global Blacksmith
		global quest_giver
		if quest_giver.ending == True:
			return
		#a basic monster takes its turn. If you can see it, it can see you
		monster = self.owner

		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y) and self.angry == True and self.alive == True:

			#trigger blacksmith gloat
			if self.first_met_player == True:
				self.first_met_player = False
				choice = talk(Blacksmith,"Got you now, bastard! Kill him, my pretty!",["Defend yourself."], first_talk = True)
				monster.clear()		#need this otherwise cat ghost remains

			#move towards player if far away
			oldx=monster.x
			oldy=monster.y
			if monster.distance_to(player) >= 2:
				monster.move_astar(player)
				if map[monster.x][monster.y].river > 0:
					monster.x = oldx
					monster.y = oldy

			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				monster.say("Hiss!")
				monster.fighter.attack(player)

			slogan = libtcod.random_get_int(0,0,20)
			if slogan == 1: #small chance of yelling
				monster.say("Meow!")
		elif libtcod.map_is_in_fov(fov_map,monster.x,monster.y) and self.alive == True:
			slogan = libtcod.random_get_int(0,0,10)
			if slogan == 1: #small chance of yelling
				monster.say("Meow!")

class FishermanSon:
	def __init__(self):
		self.welcomed = False
		self.disposition = 5
		self.timer = 0
		self.timing = False
	def take_turn(self):
		global fishermanMum
		global quest_giver
		if quest_giver.ending == True:
			return
		monster = self.owner
		if monster.distance_to(player) < 2 and self.welcomed == False: #if next to player
			self.welcome_talk()
		if self.timing == True:
			self.timer += 1
			if self.timer >= 10:
				if monster.distance_to(fishermanMum) >= 3:
					monster.move_astar(fishermanMum)
	def welcome_talk(self):
		global farmerSonBoris, farmerSonMaurice, finding_ferny, fishermanMum
		self.welcomed = True
		monster = self.owner
		self.welcomed = True
		choice = talk(monster,"Hello, stranger. What do you want?",["Your mother is looking for you.","What's going on here?"],first_talk = True)
		choice = talk(monster,"Maurice and Boris here won't let me leave. They seem agitated about something.",["What's the problem?"],first_talk = True)
		choice = talk(farmerSonBoris,"The problem is that this fish-eater has his eye on our sister! And he needs to keep his stinking hands to himself.",["Clear off, or I'll run you off.","Not my problem. Bye."],first_talk = True)
		if choice == 0:
			choice = talk(farmerSonMaurice,"Alright, you asked for it!",["Come on, then."])
			farmerSonBoris.ai.fight()
			farmerSonMaurice.ai.fight()
			self.disposition -= 2
		if choice == 1:
			farmerSonBoris.ai.leave()
			farmerSonMaurice.ai.leave()
		if fishermanMum.ai.welcomed == True:
			finding_ferny.completed()
		self.timing = True

class FishermanMum:
	def __init__(self):
		self.timer = 0
		self.welcomed = False
		self.rewarded = False
		self.disposition = 5
	def take_turn(self):
		global finding_ferny, quests, fishermanSon
		global quest_giver
		if quest_giver.ending == True:
			return
		monster = self.owner
		self.timer += 1
		if self.timer == 11:
			monster.say("Hello!")


		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			slogan = libtcod.random_get_int(0,0,30) #DEBUG - should be 300
			if slogan == 1: #small chance of yelling
				if monster.distance_to(fishermanSon) >= 4:
					monster.say("Where's my son?")

		if monster.distance_to(player) < 2:
			if self.welcomed == False: #if next to player
				self.welcome_talk()
			if monster.distance_to(fishermanSon) <= 15 and self.rewarded == False:
				self.reward()

	def reward(self):
		monster = self.owner
		self.rewarded = True
		if self.disposition > 5:
			choice = talk(monster,"Ah, I see Ferny coming now. Thanks for passing on my message. Here, have some fish.",["Thanks."],first_talk = True)
			player.food += 5
		elif self.disposition < 5:
			choice = talk(monster,"Is that Ferny? Did you talk to him? You better not fill his head with military nonsense. I suppose I owe you a reward.",["It was no problem."],first_talk = True)
			player.food += 2
		elif self.disposition == 5:
			choice = talk(monster,"Oh, did you find Ferny already? Have some dried fish. You look like you could use some fattening up.",["Thanks."],first_talk = True)
			player.food += 3
	def welcome_talk(self):
		global finding_ferny, fishermanSon
		monster = self.owner
		self.welcomed = True
		if monster.distance_to(fishermanSon) >= 5:
			choice = talk(monster,"Nice to see a new face in this village. Have you seen my son Ferny?",["Yes.","No. What does he look like?"],first_talk = True)
			if choice == 0:
				choice = talk(monster,"I see. I wish he wouldn't run off like this! If you see him again, tell him to come find me.",["Okay."])
			elif choice == 1:
				choice = talk(monster,"He's fifteen - wait, are you with the army, young man?",["Yes, I'm a soldier.","No, I'm not."])
				if choice == 0:
					self.disposition -= 2
					choice = talk(monster,"Well, my son's sick. Very sick. And he's got a club foot, too. Goodbye!",["Goodbye."],first_talk = True)
				elif choice == 1:
					self.disposition += 1
					choice = talk(monster,"Well, I'll trust you. He's fifteen, a strong lad. With the war and everything, I'm terrified he'll be snapped up by a damned army recruiter - begging your pardon, sir.",["If I see him, I'll tell him you're looking for him."],first_talk = True)
			if fishermanSon.ai.welcomed == False:
				finding_ferny = Quest("Finding Ferny","You successfully found Ferny and told him his mother wants to see him.")
				quest_alert("New quest: " + finding_ferny.name,"Find the fisherwoman's son Ferny and pass on her message.",finding_ferny, first_talk = True)
		else: #ferny is nearby
			choice = talk(monster,"Did you bring my son Ferny back? Thank you, stranger.",["It was no problem."],first_talk = True)
			self.reward()
class FarmerSonBoris:
	def __init__(self):
		self.fought_player = False
		self.confronted_player = False
		self.fleeing = False
		self.chasing = False
		self.bullying = True
		return
	def take_turn(self):
		global farmerDad
		global quest_giver
		if quest_giver.ending == True:
			return
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			slogan = libtcod.random_get_int(0,0,30) #DEBUG - should be 300
			if slogan == 1 and self.fleeing == False and self.bullying == True: #small chance of yelling
				monster.say("Eat mud, Ferny!")
			if monster.fighter != None: 	#if he's angry!
				#move towards player if far away
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(player) >= 2:
					monster.move_astar(player)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy

				#close enough, attack! (if the player is still alive.)
				elif player.fighter.hp > 0:
					monster.say("Take that!")
					monster.fighter.attack(player)
			if self.fleeing == True:	#if running away, run to Dad
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(farmerDad) >= 4:
					monster.move_astar(farmerDad)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy
				elif monster.distance_to(farmerDad) < 4:
					self.fleeing = False
			elif self.chasing == True:
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(player) >= 2:
					monster.move_astar(player)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy
				elif monster.distance_to(player) <= 2 and not libtcod.map_is_in_fov(fov_map, farmerDad.x, farmerDad.y) and self.confronted_player == False:
					self.confront_player()
	def fight(self):
		self.bullying = False
		monster = self.owner
		boris_fighter_component = Fighter(hp=10,defense=1,power=2,death_function = farmersonboris_loss)
		monster.fighter = boris_fighter_component
		monster.fighter.owner = monster
	def fight_for_real(self):
		global farmerSonMaurice
		farmerSonMaurice.ai.fight_for_real()
		monster = self.owner
		boris_fighter_component = Fighter(hp=20,defense=1,power=3,death_function = monster_death)
		monster.fighter = boris_fighter_component
		monster.fighter.owner = monster
	def leave(self):
		monster = self.owner
		monster.say("This isn't over!")
		self.fleeing = True
	def surrender(self):
		monster = self.owner
		monster.say("I give up!")
		self.fleeing = True
		self.fought_player = True
	def chase(self):
		self.chasing = True
	def confront_player(self):
		self.confronted_player = True
		monster = self.owner
		choice = talk(monster,"Hey! Where are you going with our sister?",["Just for a walk. Give us some privacy, please.","We're going south. Stop us and I'll kill you."],first_talk = True)
		if choice == 0 and self.fought_player == True:
			choice = talk(monster,"I don't trust you one inch, you violent bastard.",["Keen to get another beating?"])
			self.fight_for_real()
		if choice == 0 and self.fought_player == False:
			choice = talk(monster,"Alright. Me and Maurice can be real bastards at times, I know. But we just want what's best for Lisa. Shake on it, brother?",["I'll shake your hand on that."])
			self.leave()
		if choice == 1:
			choice = talk(monster,"That's how it's going to be, then?",["Let's get this over with."])
			self.fight_for_real()

class FarmerSonMaurice:
	def __init__(self):
		self.fought_player = False
		self.fleeing = False
		self.chasing = False
		self.bullying = True
		return
	def take_turn(self):
		global farmerDad
		global quest_giver
		if quest_giver.ending == True:
			return
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			slogan = libtcod.random_get_int(0,0,30) #DEBUG - should be 300
			if slogan == 1 and self.fleeing == False and self.bullying == True: #small chance of yelling
				monster.say("Asshole!")
			if monster.fighter != None: 	#if he's angry!
				#move towards player if far away
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(player) >= 2:
					monster.move_astar(player)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy

				#close enough, attack! (if the player is still alive.)
				elif player.fighter.hp > 0:
					monster.say("Take that!")
					monster.fighter.attack(player)
			if self.fleeing == True:	#if running away, run to Dad
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(farmerDad) >= 4:
					monster.move_astar(farmerDad)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy
				elif monster.distance_to(farmerDad) < 4:
					self.fleeing = False
			elif self.chasing == True:
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(player) >= 4:
					monster.move_astar(player)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy

	def fight(self):
		self.bullying = False
		monster = self.owner
		maurice_fighter_component = Fighter(hp=10,defense=1,power=2,death_function = farmersonmaurice_loss)
		monster.fighter = maurice_fighter_component
		monster.fighter.owner = monster
	def fight_for_real(self):
		monster = self.owner
		maurice_fighter_component = Fighter(hp=20,defense=1,power=3,death_function = monster_death)
		monster.fighter = maurice_fighter_component
		monster.fighter.owner = monster
	def leave(self):
		monster = self.owner
		self.fleeing = True
	def surrender(self):
		monster = self.owner
		monster.say("I give up!")
		self.fleeing = True
	def chase(self):
		self.chasing = True

class FarmerDad:
	def __init__(self):
		self.disposition = 5
		self.welcomed = False
		self.fought_player = False
	def take_turn(self):
		global farmerSonBoris
		global quest_giver
		if quest_giver.ending == True:
			return
		monster = self.owner
		if monster.distance_to(farmerSonBoris) >= 4:
			if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
				slogan = libtcod.random_get_int(0,0,3) #DEBUG - should be 300
				if slogan == 1: #small chance of yelling
					monster.say("Where are my sons?")
		if monster.distance_to(farmerSonBoris) < 4 and monster.distance_to(player) <= 2:
			if self.welcomed == False: #if next to player
				self.welcome_talk()

		if monster.fighter != None:
				#move towards player if far away
				oldx=monster.x
				oldy=monster.y
				if monster.distance_to(player) >= 2:
					monster.move_astar(player)
					if map[monster.x][monster.y].river > 0:
						monster.x = oldx
						monster.y = oldy

				#close enough, attack! (if the player is still alive.)
				elif player.fighter.hp > 0:
					monster.say("Have at you!")
					monster.fighter.attack(player)

	def welcome_talk(self):
		global farmerDaughter, love_quest
		monster = self.owner
		self.welcomed = True
		choice = talk(monster,"A soldier! A fine young man, too. Have you met my sons? My daughter?",["Not yet.","I've met your sons."],first_talk = True)
		choice = talk(monster,"Strong boys, my sons. They'd make fine soldiers. And my daughter - still young, and skilled around the house. I could introduce you.",["Sure.","I'm not looking for romance."],first_talk = True)
		if choice == 0:
			choice = talk(monster,"Lisa! Come meet the soldier! Be on your best behaviour, mind!",["I don't see her."])
		if choice == 1:
			choice = talk(monster,"Well, meet her first, won't you?",["I guess I could."])
			choice = talk(monster,"Lisa! Come meet the soldier! Be on your best behaviour, mind!",["I don't see her."], first_talk = True)
		#alert to the quest
		love_quest = Quest("Love at First Sight","You've recieved a tempting offer from Lisa, the farmer's daughter.")
		quest_alert("New quest: " + love_quest.name, "The farmer wants to introduce you to his daughter Lisa. Talk to her.", love_quest)
		farmerDaughter.ai.called = True

	def fight(self):
		global farmerSonBoris,farmerSonMaurice
		monster = self.owner
		farmer_fighter_component = Fighter(hp=30,defense=1,power=3,death_function = farmer_loss)
		monster.fighter = farmer_fighter_component
		monster.fighter.owner = monster
		self.fought_player = True
		farmerSonBoris.ai.fight_for_real()
		farmerSonMaurice.ai.fight_for_real()

	def surrender(self):
		global farmerSonBoris,farmerSonMaurice
		monster = self.owner
		choice = talk(monster, "Please, spare my life!", ["I'll let you live.","You want mercy? Not from me."], first_talk = True)
		if choice == 0:
			choice = talk(monster,"Just go.",["Leave."],first_talk = True)
			farmerSonBoris.fighter = None
			farmerSonMaurice.fighter = None
			farmerSonBoris.ai.chasing = False
			farmerSonMaurice.ai.chasing = False
		if choice == 1:
			self.die_for_real()

	def die_for_real(self):
		monster = self.owner
		message("You killed " + monster.name + "!",libtcod.light_red)
		monster.char = '%'
		monster.color = libtcod.dark_red
		monster.blocks = False
		monster.fighter = None
		monster.ai = None
		monster.name = 'remains of ' + monster.name
		monster.send_to_back()
		monster.dead = True


class FarmerDaughter:
	def __init__(self):
		self.disposition = 5
		self.called = False
		self.welcomed = False
		self.explained = False
		self.conspired = False
		self.escape_talked = False
		self.final_talked = False
	def take_turn(self):
		global farmerDad
		monster = self.owner
		if self.called == True and self.conspired == False:
			if monster.distance_to(player) > 2:
				monster.move_astar(player)
			if monster.distance_to(player) <= 2 and self.welcomed == False:
				self.welcome_talk()
			if monster.distance_to(player) <= 2 and self.welcomed == True and self.explained == False and not libtcod.map_is_in_fov(fov_map, farmerDad.x, farmerDad.y):
				self.explanation_talk()
		if self.conspired == True and self.escape_talked == False:
			if monster.distance_to(farmerDad) > 3:
				monster.move_astar(farmerDad)
			elif libtcod.map_is_in_fov(fov_map,monster.x, monster.y):
				monster.say("I think I'll wear a white dress...")

			if monster.distance_to(farmerDad) <= 3 and monster.distance_to(player) <= 2 and self.escape_talked == False: #if the player returns
				self.escape_talk()
		if self.escape_talked == True:
			if monster.distance_to(player) > 2:
				monster.move_astar(player)
			if monster.distance_to(player) <= 3 and not libtcod.map_is_in_fov(fov_map, farmerDad.x, farmerDad.y) and self.final_talked == False:
				self.final_talk()

	def welcome_talk(self):
		monster = self.owner
		self.welcomed = True
		choice = talk(monster,"Your eyes, sir... like mountain lakes! I love you!",["Whoa, slow down.","I love you too!"],first_talk = True)
		if choice == 0:
			self.disposition += 1
			choice = talk(monster,"How can I slow down when love urges me on? I am yours, stranger!",["I don't know about this."])
		choice = talk(monster,"If my gracious father agrees, we must be married. Please accept my humble offer. Please.",["I'll think about it, I guess.","Absolutely! You've made me the happiest man alive!"],first_talk = True)
		if choice == 0:
			self.disposition += 1
		choice = talk(monster,"Oh, you must take me for a walk! I long to walk beside you, hand in loving hand!",["If you must.","Follow me, petal!"],first_talk = True)
		if choice == 0:
			self.disposition += 1
	def explanation_talk(self):
		monster = self.owner
		self.explained = True
		if self.disposition >= 8:
			choice = talk(monster,"Finally, we're out of sight of my family. Sorry about all the lovey-dovey stuff - I had to convince my father I was really in love with you.",["You mean you're not?","He didn't take much convincing."],first_talk = True)
			if choice == 0:
				choice = talk(monster,"Nobody falls in love that quickly. Besides, men aren't really my thing.",["So why were you pretending?"])
			elif choice == 1:
				choice = talk(monster,"I could have laid it on even thicker. He's desperate to find me a husband - but I don't want one.",["So what do you want?"])
			choice = talk(monster,"I need to get out of this town. Wherever you're going - take me with you. I can be useful.",["I'm going south. Useful how?"],first_talk = True)
			choice = talk(monster,"You'll need to cross the desert. My father has provisions and tents, just in case. I can steal them for us.",["Sounds good.","Steal from your father?"],first_talk = True)
			if choice == 1:
				choice = talk(monster,"The idiot has been trying to marry me to every guy he sees for years. I'd steal it all if I could.",["Fair enough."])
			self.conspire_talk()
		elif self.disposition <= 8:
			choice = talk(monster,"I have an apology to make. I'm not actually in love with you.",["Okay."],first_talk=True)
			choice = talk(monster,"I need to get out of this town. Wherever you're going - take me with you. I can be useful.",["I'm going south. Useful how?"],first_talk = True)
			choice = talk(monster,"You'll need to cross the desert. I can find us tools.",["Sounds good.","I don't want your help. You lied to me."],first_talk = True)
			if choice == 0:
				self.conspire_talk()
			elif choice == 1:
				choice = talk(monster,"I'm sorry we couldn't help each other.",["So am I."])
	def conspire_talk(self):
		global love_quest, stolen_tools
		self.conspired = True
		monster = self.owner
		choice = talk(monster,"When you're ready to leave, come find me. I'll have a bag packed.",["It might be soon. The Black Legion are coming south."], first_talk = True)
		choice = talk(monster,"I knew they would, sooner or later. I'll be ready.",["Goodbye."])
		love_quest.completed()
		stolen_tools = Quest("Partners in Crime","You've found yourself a travel partner for the journey. Better leave before the farmer notices the theft.")
		quest_alert("New quest: " + stolen_tools.name,"Tell Lisa when you're ready to go and she'll provide gear for the journey. Be careful, though - you'll need more food for the two of you.", stolen_tools)
	def escape_talk(self):
		self.escape_talked = True
		global farmerDad, farmerSonBoris, farmerSonMaurice
		monster = self.owner
		choice = talk(monster,"What is it, my knight?",["Time to leave. Let's get out of here.","Would you care to go for a walk, darling?"],first_talk = True)
		if choice == 0:
			choice = talk(farmerDad,"Hold on a second! Who's leaving? What's going on here?",["Just for a walk, I promise!","I'm taking your daughter away."])
			if choice == 0:
				choice = talk(farmerDad,"You think I'm stupid, soldier boy? I won't let you ruin my daughter's reputation!",["Prepare to fight him."], first_talk = True)
			farmerDad.ai.fight()
		elif choice == 1:
			choice = talk(monster,"Of course, love.",["Let's go, then."])
			farmerSonBoris.ai.chase()
			farmerSonMaurice.ai.chase()
	def final_talk(self):
		self.final_talked = True
		global farmerDad
		monster = self.owner
		if farmerDad.dead == False:
			if farmerDad.ai.fought_player == False:
				choice = talk(monster,"Good work. My father will think we're kissing in the orchard. Let's go - I've got the gear.",["Thanks. Follow me."],first_talk = True)
			elif farmerDad.ai.fought_player == True:
				choice = talk(monster,"Thank you for not killing him. I wish it could have been different...",["Let's get out of here."],first_talk = True)
		elif farmerDad.dead == True:
			choice = talk(monster,"Why did you have to kill him?",["He attacked me. I had no choice.","I'm sorry."],first_talk = True)

class Quest:
	def __init__(self,name, completed_message):
		global quests
		self.name = name
		self.alerted = False
		self.finished = False
		self.completed_message = completed_message
		quests.append(self)
	def clear(self):
		quests.remove(self)
	def completed(self):
		quest_alert("Quest completed: " + self.name, self.completed_message,self)
		self.clear()
		self.finished = True


class QuestGiver:		#DEBUG = the X in Y system doesn't work
	def __init__(self):
		self.time = 0
		self.counting = True
		self.global_time = 0
		self.ending = False
		return
	def tick(self):
		global game_stage, quests, esc, log, desert_crossing
		if self.counting == True:
			self.time += 1
		if self.time == 3 and game_stage == 1:
			#Quest alert - escape!
			if quests == []:
				esc = Quest("Escape!", "You made it into the river! They won't follow you here.") #create the escape quest
				quest_alert("New quest: " + esc.name ,"Your army has been routed. Find a way to survive.",esc)
				self.time = 0
				self.counting = False
		if game_stage == 2:
			#complete escape quest
			if self.time == 0:
				self.counting = True
			if self.time == 2:
				if quests != []:
					quests[0].completed() #since the complete message flushes the background, I can't complete a quest as soon as player arrives at stage
			if self.time >= 5:
				if quests == []:
					log = Quest("Avoid the logs!", "You avoided the logs.")
					quest_alert("New quest: " + log.name , "Try not to hit the logs in the river.", log)
					self.time = 1
					self.counting = False
		if game_stage == 4:
			#complete log quest
			if self.time == 1:
				self.counting = True
			if self.time >= 5:
				if quests!=[]:
					quests[0].completed()
					self.time = 0
					self.counting = False	#debug?
			#tick global time
			self.global_time += 1
			if self.global_time == 300:
				palette_switch_medium()
				quest_alert(desert_crossing.name,"Your time is running out. The Black Legion will finish their tunnel soon.",desert_crossing)
			if self.global_time == 500:
				palette_switch_less_sad()
				quest_alert(desert_crossing.name,"You had better hurry! The Black Legion could arrive at any minute.",desert_crossing)
			if self.global_time == 700:
				palette_switch_sad()
				quest_alert(desert_crossing.name,"Flee! The Black Legion are here!",desert_crossing)
				legion_arrive()
				self.ending = True


###############################
# Map building tools
###############################
####depressing color set###
'''
color_dark_wall = libtcod.desaturated_orange
color_light_wall = libtcod.darkest_grey
color_dark_ground = libtcod.darker_sepia
color_light_ground = libtcod.Color(170,166,134)
color_dark_river = libtcod.darkest_azure
color_light_river = libtcod.darkest_sky
color_dark_jetty = libtcod.darkest_sepia
color_light_jetty = libtcod.dark_sepia
'''
def palette_switch_sad():
	global color_dark_wall, color_light_wall, color_dark_ground, color_light_ground, color_dark_river, color_light_river, color_dark_jetty, color_light_jetty, color_dark_shrub,color_light_shrub,color_dark_path,color_light_path
	global color_river_alt, color_ground_alt

	color_river_alt = libtcod.Color(0,49,72)
	color_ground_alt = libtcod.Color(169,165,133)

	color_dark_wall = libtcod.desaturated_orange		#set colors
	color_light_wall = libtcod.darkest_grey
	color_dark_ground = libtcod.darker_sepia
	color_light_ground = libtcod.Color(170,166,134)
	color_dark_river = libtcod.darkest_azure
	color_light_river = libtcod.darkest_sky
	color_dark_jetty = libtcod.darkest_sepia
	color_light_jetty = libtcod.dark_sepia

	color_dark_shrub = libtcod.Color(0,50,0)
	color_light_shrub = libtcod.darkest_green
	color_dark_path = libtcod.Color(63,130,78)
	color_light_path = libtcod.Color(95,132,86)

def palette_switch_less_sad():
	global color_light_ground, color_light_wall, color_light_river
	global color_river_alt, color_ground_alt

	color_river_alt = libtcod.Color(0,57,115)
	color_ground_alt = libtcod.Color(126,156,116)
	color_light_ground = libtcod.Color(127,157,117)
	color_light_wall = libtcod.Color(106,84,21)
	color_light_river = libtcod.Color(0,53,106)

def palette_switch_medium():
	global color_dark_wall, color_light_wall, color_dark_ground, color_light_ground, color_dark_river, color_light_river, color_dark_jetty, color_light_jetty
	global color_river_alt, color_ground_alt

	color_river_alt = libtcod.Color(0,84,159)
	color_ground_alt = libtcod.Color(63,141,89)

	color_dark_wall = libtcod.darker_amber
	color_light_wall = libtcod.Color(180,138,10)
	color_dark_ground = libtcod.dark_sepia
	color_light_ground = libtcod.Color(64,142,90)
	color_dark_river = libtcod.darkest_sky
	color_light_river = libtcod.Color(0,74,149)
	color_dark_jetty = libtcod.darkest_sepia
	color_light_jetty = libtcod.dark_sepia

def palette_switch_vibrant():
	global color_dark_wall, color_light_wall, color_dark_ground, color_light_ground, color_dark_river, color_light_river, color_dark_jetty, color_light_jetty
	global color_river_alt, color_ground_alt

	color_river_alt = libtcod.Color(0,91,183)
	color_ground_alt = libtcod.Color(0,128,62)

	color_dark_wall = libtcod.dark_amber
	color_light_wall = libtcod.amber
	color_dark_ground = libtcod.desaturated_turquoise
	color_light_ground = libtcod.darker_sea
	color_dark_river = libtcod.desaturated_azure
	color_light_river = libtcod.dark_azure
	color_dark_jetty = libtcod.sepia
	color_light_jetty = libtcod.dark_sepia



def is_in_room(room,entity):
	if entity.x < room.x2 and entity.y < room.y2 and entity.x > room.x1 and entity.y > room.y1:
		return True
	else:
		return False

def clear_room(room):
	global map
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False
def create_room(room):
	global map
	#fill the room with blocked tiles
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = True
			map[x][y].block_sight = True
	#empty the middle of the room
	for x in range(room.x1 + 2, room.x2 - 1):
		for y in range(room.y1 + 2, room.y2 - 1):
			map[x][y].blocked = False
			map[x][y].block_sight = False
	#create door
	door_x = room.x1 +((room.x2 - room.x1)/2)
	map[door_x][room.y1 + 1].blocked = False
	map[door_x][room.y1 + 1].block_sight = False
	if room.w > 9:
		door_x2 = room.x1+((room.x2-room.x1)/2) + 1
		map[door_x2][room.y1 + 1].blocked = False
		map[door_x2][room.y1 + 1].block_sight = False

def create_fort(room):
	global map
	#fill the room with blocked tiles
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = True
			map[x][y].block_sight = True
	#empty the middle of the room and cut away right
	for x in range(room.x1 + 2, room.x2 - 1):
		for y in range(room.y1 + 2, room.y2 - 1):
			map[x][y].blocked = False
			map[x][y].block_sight = False

	for x in range(room.x1 + 8, room.x2):
		for y in range(room.y1 + 2, room.y2 - 1):
			map[x][y].blocked = False
			map[x][y].block_sight = False

def create_lump(room):
	global map
	#fill the room with blocked tiles
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = True
			map[x][y].block_sight = True

def create_shrub(room):
	global map
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = True
			map[x][y].block_sight = True
			map[x][y].shrub = 1

def create_path(x1,y1,x2,y2):
	global map
	libtcod.line_init(x1,y1,x2,y2)
	x,y = libtcod.line_step()
	while x != None:
		map[x][y].blocked = False
		map[x][y].block_sight = False
		map[x][y].path = 1
		x,y = libtcod.line_step()

def create_map_border():
	global map, game_stage
	rim = Rect(0,0,MAP_WIDTH, MAP_HEIGHT)
	for x in range(rim.x1,rim.x2):
		#north border
		map[x][0].border = 2
		#south border
		map[x][rim.h-1].border = 4
	for y in range(rim.y1,rim.y2):
		#west border
		map[0][y].border = 1
		#east border
		map[rim.w-1][y].border = 3

	#make the river impassable in stages 2 and 3 and 4
	if game_stage == 2 or game_stage == 3 or game_stage == 4:
		for y in range(MAP_HEIGHT):
			map[MAP_WIDTH-15][y].border = 3
	if game_stage == 4:
		#make the jetty passable
		for i in range(29,34):	#the y coords of the jetty
			map[MAP_WIDTH-15][MAP_HEIGHT-i].border = 0

def is_border(x,y):
	global map
	if y <= MAP_HEIGHT - 1:
		return map[x][y].border
	else:
		return 4 #south border

def create_river(river):
	global map
	#fill the room with blocked tiles
	for x in range(river.x1 + 1, river.x2):
		for y in range(river.y1 + 1, river.y2):
			map[x][y].river = 1
			map[x][y].block_sight = False



def clear_map():
	global map
	map = [[ Tile(False)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]
	initialize_fov()

###################################
# Graphics overlay
###################################

def initialize_overlay():
	global overlay
	overlay = [[0 for y in range(MAP_HEIGHT)] for x in range(MAP_WIDTH)]

def build_overlay_land():
	global overlay
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH-14):
			rand = libtcod.random_get_int(0,0,3)
			if rand == 3:
				overlay[x][y] = 1 #set overlay colour to variant colour

def build_overlay_river():
	global overlay
	for y in range(MAP_HEIGHT):
		for x in range(14):
			rand = libtcod.random_get_int(0,0,3)
			if rand == 3:
				overlay[MAP_WIDTH-x-1][y] = 2 #set overlay colour to variant colour

def tick_overlay_river(): #run the variant colour map down 3 units per tick
	global overlay
	new_overlay = [[0 for y in range(MAP_HEIGHT)] for x in range(MAP_WIDTH)]



	for y in range(MAP_HEIGHT):	#generate the new overlay
		for x in range(15):
			if y+3 < MAP_HEIGHT:
				new_overlay[MAP_WIDTH-x-1][y+3] = overlay[MAP_WIDTH-x-1][y]
			else:
				new_overlay[MAP_WIDTH-x-1][y+3-MAP_HEIGHT] = overlay[MAP_WIDTH-x-1][y]


	for y in range(MAP_HEIGHT):		#paint the new overlay
		for x in range(15):
			overlay[MAP_WIDTH-x-1][y]	= new_overlay[MAP_WIDTH-x-1][y]



####################################
# Instructions for building the map in each stage
####################################

def make_map_stage1():
	global map, objects, shouts, game_stage
	global fov_recompute
	palette_switch_sad()
	fov_recompute = True

	game_stage = 1
	#fill map with "unblocked" tiles
	clear_map()


	#create_river
	river = Rect(MAP_WIDTH-15,-1,15,MAP_HEIGHT+1) #-1 so it starts at top screen
	create_river(river)

	#create objects
	objects = [player] #create list of objects
	shouts = [] #create shouts
	player.x = 45
	player.y = 23

	#create border
	create_map_border()
	#TODO - create castle/structures so it looks less empty!
	#Build the enemy encampment

	wall = Rect(5,6,MAP_WIDTH-19,2)
	create_lump(wall)
	wall2 = Rect(MAP_WIDTH-14,0,2,30)

	for i in range(13):
		camp = Rect(5*i,6,5,4)
		create_lump(camp)

	build_overlay_land()
	build_overlay_river()

	initialize_fov()


def make_map_stage2():
	global map, objects, shouts, game_stage
	global fov_recompute
	palette_switch_less_sad()
	fov_recompute = True

	game_stage = 2
	#fill map with "unblocked" tiles
	clear_map()

	#create_river
	river = Rect(MAP_WIDTH-15,-1,15,MAP_HEIGHT+1) #-1 so it starts at top screen
	create_river(river)

	for i in range(50,MAP_WIDTH-14):  #create mountain range
		room = Rect(0,MAP_HEIGHT-2 -((MAP_WIDTH-15)-i),i,2)
		create_lump(room)
		room3 = Rect(0,MAP_HEIGHT-15 -((MAP_WIDTH-15)-i),i-30,2)
		create_lump(room3)
	room2 = Rect(3,MAP_HEIGHT-3,MAP_WIDTH-17,2)
	create_lump(room2)

	clear_room(Rect(35,53,5,15)) #clear the tunnel

	#create objects
	objects = [player] #create list of objects
	shouts = [] #create shouts
	player.x = MAP_WIDTH - 5
	player.y = 1

	#create border
	create_map_border()
	build_overlay_land()
	build_overlay_river()
	initialize_fov()

def make_map_stage3():
	global map, objects, shouts, game_stage
	global fov_recompute
	palette_switch_medium()	#change to happy colours
	fov_recompute = True
	game_stage = 3
	#fill map with "unblocked" tiles
	clear_map()

	#create_river
	river = Rect(MAP_WIDTH-15,-1,15,MAP_HEIGHT+1) #-1 so it starts at top screen
	create_river(river)

	for i in range(50,MAP_WIDTH-15):  #create mountain range
		room = Rect(0,(MAP_WIDTH-15 -i),i,2)
		create_lump(room)

	room2 = Rect(3,1,MAP_WIDTH-17,2)
	create_lump(room2)
	room2 = Rect(3,0,MAP_WIDTH-17,2)
	create_lump(room2)

	#create hut
	room2 = Rect(20,50,10,10)
	create_room(room2)

	create_path(25,49,10,25)

	for i in range(6):
		for j in range(3):
			shrub = Rect(5+3*i,17+3*j,2,2)
			create_shrub(shrub)

	#create objects
	objects = [player] #create list of objects
	shouts = [] #create shouts
	player.x = MAP_WIDTH - 5
	player.y = 1

	#create border
	create_map_border()
	build_overlay_land()
	build_overlay_river()
	initialize_fov()
	#TODO - create some kind of structures, make so you can't get out of the river
	#		- you're swept past a big mountain range! solves lots of problems

def make_map_stage4():
	global map, objects, shouts, game_stage
	global fov_recompute
	palette_switch_vibrant()
	fov_recompute = True
	game_stage = 4
	#fill map with "unblocked" tiles
	clear_map()

	#create_river
	river = Rect(MAP_WIDTH-15,-1,15,MAP_HEIGHT+1) #-1 so it starts at top screen
	create_river(river)

	#create objects
	objects = [player] #create list of objects
	shouts = [] #create shouts
	player.x = MAP_WIDTH - 5
	player.y = 1

	room1 = Rect(5,5,15,10)		#two-room blacksmith's place
	create_room(room1)
	room2 = Rect(20,5,30,20)	#main room
	create_room(room2)

	room3 = Rect(3,48,18,22)	#farmer's house
	create_room(room3)
	room5 = Rect(4,53,17,2) 	#middle bar
	create_room(room5)


	room4 = Rect(MAP_WIDTH-20,33,6,6)	#fisherman's hut
	create_room(room4)

	#create path
	mid_x = 35
	mid_y = 35
	sec_x = 55
	sec_y = 30
	create_path(MAP_WIDTH-16,MAP_HEIGHT-32,mid_x,mid_y) #hut to farmer's house
	create_path(mid_x,mid_y,14,46)
	create_path(mid_x,mid_y,MAP_WIDTH-26,MAP_HEIGHT-16)
	create_path(mid_x,mid_y,sec_x,sec_y)
	create_path(sec_x,sec_y,MAP_WIDTH-18,30) #secondary hub to fisher hut
	create_path(sec_x,sec_y,MAP_WIDTH-23,4) #secondary hub up north
	create_path(MAP_WIDTH-23,4, 35,4)	#final leg to blacksmith's
	#create jetty

	for i in range(29,34):
		for j in range(11,17):
			map[MAP_WIDTH-j][MAP_HEIGHT-i].color = 1
			map[MAP_WIDTH-j][MAP_HEIGHT-i].river = 0

	#make shrubs

	shrub = Rect(MAP_WIDTH-26,MAP_HEIGHT-14,2,2)
	create_shrub(shrub)

	shrub = Rect(MAP_WIDTH-23,MAP_HEIGHT-14,2,2)
	create_shrub(shrub)

	shrub = Rect(MAP_WIDTH-29,MAP_HEIGHT-14,2,2)
	create_shrub(shrub)

	shrub = Rect(MAP_WIDTH-27,MAP_HEIGHT-12,2,2)
	create_shrub(shrub)

	shrub = Rect(MAP_WIDTH-24,MAP_HEIGHT-12,2,2)
	create_shrub(shrub)

	shrub = Rect(MAP_WIDTH-31,MAP_HEIGHT-12,2,2)
	create_shrub(shrub)

	#create border
	create_map_border()
	build_overlay_land()
	build_overlay_river()
	initialize_fov()


####################################
# Instructions for placing objects in each stage
####################################

def place_objects_stage1():
	global QuestGiver
	QuestGiver.time = 0
	#Place the Black Legion!
#	for i in range(4): #number of enemy soldiers
#		#need these lines in here to create a new one for each object
#		ai_component_soldier = BlackLegion()
#		fighter_component_soldier = Fighter(hp=50, defense=4, power=15, death_function=monster_death)
#		fighter_component_leader = Fighter(hp=200, defense=5, power=25, death_function=monster_death)
#		soldier = Object(10,25+i**2,'#','Black Legion soldier',libtcod.black, blocks = True,
#			fighter = fighter_component_soldier, ai = ai_component_soldier)
#		objects.append(soldier)
	for i in range(2): #number of enemy soldiers
		#need these lines in here to create a new one for each object
		ai_component_soldier = BlackLegion()
		fighter_component_soldier = Fighter(hp=50, defense=4, power=15, death_function=monster_death)

		soldier = Object(2*i + 1,60,'#','Black Legion soldier',libtcod.black, blocks = True,
			fighter = fighter_component_soldier, ai = ai_component_soldier, msgcolor = libtcod.light_grey)
		objects.append(soldier)
	for i in range(2): #number of enemy soldiers
		#need these lines in here to create a new one for each object
		ai_component_soldier = BlackLegion()
		fighter_component_soldier = Fighter(hp=50, defense=4, power=15, death_function=monster_death)

		soldier = Object(2*i + 25,MAP_HEIGHT-27,'#','Black Legion soldier',libtcod.black, blocks = True,
			fighter = fighter_component_soldier, ai = ai_component_soldier, msgcolor = libtcod.light_grey)
		objects.append(soldier)

#	for i in range(2): #number of enemy soldiers
#		#need these lines in here to create a new one for each object
#		ai_component_soldier = BlackLegion()
#		fighter_component_soldier = Fighter(hp=50, defense=4, power=15, death_function=monster_death)
#
#		soldier = Object(2*i + 45,MAP_HEIGHT-43,'#','Black Legion soldier',libtcod.black, blocks = True,
#			fighter = fighter_component_soldier, ai = ai_component_soldier)
#		objects.append(soldier)

	for i in range(2): #number of enemy soldiers
		#need these lines in here to create a new one for each object
		ai_component_soldier = BlackLegion()
		fighter_component_soldier = Fighter(hp=50, defense=4, power=15, death_function=monster_death)

		soldier = Object(2*i + 5,MAP_HEIGHT-3,'#','Black Legion soldier',libtcod.black, blocks = True,
			fighter = fighter_component_soldier, ai = ai_component_soldier, msgcolor = libtcod.light_grey)
		objects.append(soldier)

	#place the lieutenant
	fighter_component_leader = Fighter(hp=200, defense=5, power=25, death_function=monster_death)
	leader = Object(MAP_WIDTH/2, 30,'@','Black Legion Lieutenant',libtcod.darkest_flame, blocks = True,fighter = fighter_component_leader, ai = LegionTalker(), msgcolor = libtcod.dark_sepia)
	objects.append(leader)


	#Place the corpses
	for i in range (20):
		x = libtcod.random_get_int(0,30,MAP_WIDTH-20)
		y = libtcod.random_get_int(0,0,MAP_HEIGHT-5)
		if not is_blocked(x,y):
			corpse = Object(x,y,"%","A dead body.",libtcod.dark_red,blocks=False)
			objects.append(corpse)
			corpse.send_to_back()

def place_objects_stage2():
	global QuestGiver
	QuestGiver.time = 0
	global fov_recompute
	fov_recompute = True
	for i in range(3): #number of enemy soldiers
		#need these lines in here to create a new one for each object
		ai_component_soldier = BlackLegion()
		fighter_component_soldier = Fighter(hp=50, defense=4, power=15, death_function=monster_death)

		soldier = Object(10+libtcod.random_get_int(0,0,2),5+2*i,'#','Black Legion soldier',libtcod.black, blocks = True,
			fighter = fighter_component_soldier, ai = ai_component_soldier, msgcolor = libtcod.light_grey)
		objects.append(soldier)

	#the dig site
	dig_chief = Object(34,55,'@','Black Legion lieutenant',libtcod.black,blocks = True,fighter = None, ai = LegionDigger(), msgcolor = libtcod.dark_sepia)
	objects.append(dig_chief)
	digger1 = Object(dig_chief.x+2,dig_chief.y,'#','Black Legion engineer',libtcod.black,blocks = True,fighter = None, ai = None)
	digger2 = Object(dig_chief.x+2,dig_chief.y+1,'#','Black Legion engineer',libtcod.black,blocks = True,fighter = None, ai = None)
	digger3 = Object(dig_chief.x+3,dig_chief.y + 2,'#','Black Legion engineer',libtcod.black,blocks = True,fighter = None, ai = None)
	objects.append(digger1)
	objects.append(digger2)
	objects.append(digger3)




	for i in range(10): #number of logs
		randx = libtcod.random_get_int(0,0,10)
		log = Object(MAP_WIDTH-randx,25+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)
		log2 = Object(MAP_WIDTH-randx + 1,25+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)
		log3 = Object(MAP_WIDTH-randx + 2,25+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)

		objects.append(log)
		objects.append(log2)
		objects.append(log3)
		log.send_to_back()
		log2.send_to_back()
		log3.send_to_back()


def place_objects_stage3():
	global fov_recompute, hutDweller
	global QuestGiver
	QuestGiver.time = 0
	fov_recompute = True
	for i in range(15): #number of logs
		randx = libtcod.random_get_int(0,0,10)
		log = Object(MAP_WIDTH-randx,5+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)
		log2 = Object(MAP_WIDTH-randx + 1,5+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)
		log3 = Object(MAP_WIDTH-randx + 2,5+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)

		objects.append(log)
		objects.append(log2)
		objects.append(log3)
		log.send_to_back()
		log2.send_to_back()
		log3.send_to_back()

	#hut dwellers
	hutParent = Object(32,57,'@','A woodcutter',libtcod.violet,blocks = True, fighter = None, ai = HutParent())
	hutChild = Object(32,55,'}','A child',libtcod.violet,blocks = True, fighter = None, ai = HutChild())
	objects.append(hutParent)
	objects.append(hutChild)
	hutDweller = Object(22,52,' ',' ',libtcod.black,blocks = False)

def place_objects_stage4():
	global fov_recompute
	global QuestGiver

	global Blacksmith, blacksmith_pet, fishermanDad, fishermanMum, fishermanSon, farmerSonBoris, farmerSonMaurice, farmerDad, farmerDaughter

	QuestGiver.time = 0
	fov_recompute = True

	for i in range(10): #number of logs
		randx = libtcod.random_get_int(0,0,10)
		log = Object(MAP_WIDTH-randx,5+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)
		log2 = Object(MAP_WIDTH-randx + 1,5+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)
		log3 = Object(MAP_WIDTH-randx + 2,5+6*i,'=','A drifting log',libtcod.darkest_sepia, blocks = False)

		objects.append(log)
		objects.append(log2)
		objects.append(log3)
		log.send_to_back()
		log2.send_to_back()
		log3.send_to_back()

	for k in range(20):
		for i in range(15): #place the log jam
			log = Object(MAP_WIDTH-i,MAP_HEIGHT-k,'=','A drifting log',libtcod.darkest_sepia, blocks = False)
			objects.append(log)
			log.send_to_back()

	#place humans

	fishermanDad = Object(MAP_WIDTH-13,MAP_HEIGHT-31, '@', 'Fergus the Fisherman',libtcod.peach, blocks = True,fighter = None, ai = FishermanDad())
	objects.append(fishermanDad)
	Blacksmith = Object(22,4, '@', 'Boris the Blacksmith',libtcod.darker_grey, blocks = True,fighter = None, ai = BlacksmithAi())
	objects.append(Blacksmith)

	blacksmith_pet = Object(8,8, '{', 'A snarling cat',libtcod.black, blocks = True,fighter = Fighter(hp = 10, defense = 0, power = 4, death_function = blacksmith_pet_death), ai = BlacksmithPetAi(), msgcolor = libtcod.dark_orange)
	objects.append(blacksmith_pet)

	fishermanMum = Object(MAP_WIDTH-19,MAP_HEIGHT-41, '@', 'Fiona the Fisherwoman',libtcod.magenta, blocks = True,fighter = None, ai = FishermanMum())
	objects.append(fishermanMum)
	fishermanSon = Object(MAP_WIDTH-26,MAP_HEIGHT-3, '}', 'Ferny the Fisherman\'s Son',libtcod.magenta, blocks = True,fighter = None, ai = FishermanSon())
	objects.append(fishermanSon)

	farmerSonBoris = Object(MAP_WIDTH-26,MAP_HEIGHT-4, '}', 'Boris the Farmer\'s Son',libtcod.darkest_sea, blocks = True,fighter = None, ai = FarmerSonBoris())
	objects.append(farmerSonBoris)
	farmerSonMaurice = Object(MAP_WIDTH-25,MAP_HEIGHT-5, '}', 'Maurice the Farmer\'s Son',libtcod.darkest_turquoise, blocks = True,fighter = None, ai = FarmerSonMaurice())
	objects.append(farmerSonMaurice)

	farmerDad = Object(10,MAP_HEIGHT-6, '@', 'Horace the Farmer',libtcod.darkest_sea, blocks = True,fighter = None, ai = FarmerDad())
	objects.append(farmerDad)

	farmerDaughter = Object(8,MAP_HEIGHT -5, '@', "Lisa the Farmer\'s Daughter", libtcod.magenta, blocks = True, fighter = None, ai = FarmerDaughter())
	objects.append(farmerDaughter)

def legion_arrive():
	#place the black legion!
	current_objects = []
	for object in objects:
		current_objects.append(object)
	#measure current objects (before soldiers are dumped everywhere)

	i = 0
	for ent in current_objects: #number of enemy soldiers
#		print object
		#need these lines in here to create a new one for each object
		if ent.ai != None:
			i += 1
			ai_component_soldier = BlackLegion(target = ent)
			fighter_component_soldier = Fighter(hp=50, defense=4, power=15, death_function=monster_death)

			soldier = Object(3*i + 5,1,'#','Black Legion soldier',libtcod.black, blocks = True,
				fighter = fighter_component_soldier, ai = ai_component_soldier, msgcolor = libtcod.light_grey)
			objects.append(soldier)
			if ent != player:	#give everyone the same figh
				generic_fighter_component = Fighter(hp=10,defense=0,power=3,death_function=monster_death)
				ent.fighter = generic_fighter_component
				ent.fighter.owner = ent
	#make the player-killer one
	ai_component_soldier = BlackLegion()
	fighter_component_soldier = Fighter(hp=50, defense=4, power=15, death_function=monster_death)
	soldier = Object(3*i + 7,1,'#','Black Legion soldier',libtcod.black, blocks = True,
	fighter = fighter_component_soldier, ai = ai_component_soldier, msgcolor = libtcod.light_grey)
	objects.append(soldier)
	return

#################################
# General tools
#################################

def leave_stage(border):

	if game_stage == 1:
		if border == 1: #west
			border_menu("You cannot leave here.",["Turn back."],25,1)
		elif border == 2: #north
			border_menu("To the north is war and terror. Turn back!",["Turn back."],25,1)
		elif border == 3: #east
			border_menu("The cliffs this side of the river are impassable.",["Turn back."],25,1)
		elif border == 4: #south
			message("You are swept down the river! Things look a little brighter.", libtcod.light_blue)
			make_map_stage2()
			place_objects_stage2()
	elif game_stage == 2:
		if border == 1: #west
			border_menu("You cannot leave here.",["Turn back."],25,1)
		elif border == 2: #north
			border_menu("To the north is war and terror. Turn back!",["Turn back."],25,1)
		elif border == 3: #east
			border_menu("The cliffs this side of the river are impassable.",["Turn back."],25,1)
		elif border == 4: #south
			message("You are swept down the river again! The landscape is idyllic.", libtcod.light_blue)
			make_map_stage3()
			place_objects_stage3()
	elif game_stage == 3:
		if border == 1: #west
			border_menu("You cannot leave here.",["Turn back."],25,1)
		elif border == 2: #north
			border_menu("To the north is war and terror. Turn back!",["Turn back."],25,1)
		elif border == 3: #east
			border_menu("The cliffs this side of the river are impassable.",["Turn back."],25,1)
		elif border == 4: #south
			message("You are swept down the river again!", libtcod.light_blue)
			make_map_stage4()
			place_objects_stage4()
	elif game_stage == 4:
		if border == 1: #west
			border_menu("You cannot leave here.",["Turn back."],25,1)
		elif border == 2: #north
			border_menu("To the north is war and terror. Turn back!",["Turn back."],25,1)
		elif border == 3: #east
			border_menu("The cliffs this side of the river are impassable.",["Turn back."],25,1)
		elif border == 4: #south
			desert_journey()
#		return

def is_blocked(x, y):
	#first test the map tile
	if map[x][y].blocked:
		return True

	#now check for any blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True

	return False

def is_river(x,y):
	#check if the map tile is a river
	if map[x][y].river == 1:
		return True
	else:
		return False

def is_shrub(x,y):
	if map[x][y].shrub == 1:
		return True
	else:
		return False

def is_path(x,y):
	if map[x][y].path == 1:
		return True
	else:
		return False

def player_move_or_attack(dx, dy):
	global fov_recompute
	fov_recompute = True

	#the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy

	#try to find an attackable object there
	target = None
	for object in objects:
		if object.x == x and object.y == y:
			target = object
			break

	#attack if target found, move otherwise
	if target is not None and target.fighter is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)




def check_for_logs(x,y):	#check for logs
	if is_log(x,y):
		hit_log()

def is_log(x,y):
	for object in objects:
		if object.char == '=' and x == object.x and y == object.y:
			return True

def hit_log():
	message("Ouch! You hit a log!", libtcod.light_red)
	player.fighter.take_damage(5)


def desert_journey():
	#player attempts to set out across the desert
	global desert_crossing, player, farmerDaughter
	if farmerDaughter.distance_to(player) <= 3:
		choice = quest_menu(desert_crossing,"You and Lisa gaze south across a seemingly endless desert. Are you sure you two are ready to begin the trip? You only have " + str(player.food+5) + " days worth of food and " + str(player.gear+5) + " bags of gear. Remember, you'll need food for both of you.",["Yes, I want to set out.","No, I'm not ready."],desert_crossing)
		if choice == 1:
			return
		if choice == 0:
			quest_alert(desert_crossing.name,"You died in the desert.",desert_crossing, first_talk = True)
			player_death(player)
	else:
		choice = quest_menu(desert_crossing,"You gaze south across a seemingly endless desert. Are you sure you're ready to begin the trip? You only have " + str(player.food) + " days worth of food and " + str(player.gear) + " bags of gear.",["Yes, I want to set out.","No, I'm not ready."],desert_crossing)
		if choice == 1:
			return
		if choice == 0:
			quest_alert(desert_crossing.name,"You died in the desert.",desert_crossing, first_talk = True)
			player_death(player)

def player_death(player):

	#the game ended!
	global game_state, game_stage
	message('You died!', libtcod.dark_red)
	game_state = 'dead'

	#for added effect, transform the player into a corpse!
	player.char = '%'
	player.color = libtcod.red
	death_menu("You have died.\n")
	if game_stage == 4:
		death_report()
		main_menu()
		main_menu()
	else:
		main_menu()

def monster_death(monster):
	#transform it into a nasty corpse! it doesn't block, can't be
	#attacked and doesn't move
	message(monster.name.capitalize() + ' is dead!', libtcod.light_red)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

def blacksmith_pet_death(monster):
	global Blacksmith
	message("You killed the blacksmith's pet cat!", libtcod.light_red)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai.angry = False
	monster.ai.alive = False
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()
	if Blacksmith.dead == False:
		Blacksmith.ai.fight()
		Blacksmith.ai.pet_dead = True

def blacksmith_loss(monster):
	global Blacksmith
	Blacksmith.fighter = None
	Blacksmith.ai.fought_player = True
	Blacksmith.ai.surrender()

def farmer_loss(monster):
	global farmerDad, farmerSonBoris,farmerSonMaurice
	farmerDad.fighter = None
	if farmerSonBoris.dead == False and farmerSonMaurice.dead == False:
		farmerDad.ai.surrender()
	else:
		farmerDad.ai.die_for_real()

def farmersonboris_loss(monster):
	global farmerSonBoris
	farmerSonBoris.fighter = None
	farmerSonBoris.ai.fought_player = True
	farmerSonBoris.ai.surrender()

def farmersonmaurice_loss(monster):
	global farmerSonMaurice
	farmerSonMaurice.fighter = None
	farmerSonMaurice.ai.fought_player = True
	farmerSonMaurice.ai.surrender()

def message(new_msg, color = libtcod.white):
	global game_msgs
	#split the message if necessary, among multiple lines
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
 	if len(game_msgs) + len(new_msg_lines) >= MSG_HEIGHT:
		for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room for the new one
		#DEBUG - THIS ISNT WORKING

#			game_msgs = []
			del game_msgs[0]

	for line in new_msg_lines:
	#add the new line as a tuple, with the text and the color
		game_msgs.append( (line, color) )

def get_names_under_mouse():
	global mouse

	#return a string with the names of all objects under the mouse
	(x, y) = (mouse.cx, mouse.cy)
	#create a list with the names of all objects at the mouse's coordinates and in FOV
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	names = ', '.join(names)  #join the names, separated by commas
	return names.capitalize()				#TODO - could add flavour text here

def border_menu(header, options, width, map = 0, talking = True):
	global fov_recompute

#	libtcod.console_clear(con) #ADDED - this line stops message ghosts from remaining
#	fov_recompute = True
#	render_all()
#	libtcod.console_flush()

	img = libtcod.image_load('./img/alert_background.png')
	#show the background image, at twice the regular console resolution
	libtcod.image_blit_2x(img, 0, MAP_WIDTH/4 + 5, MAP_HEIGHT/4 + 13)
	menu(header, options, width, map, talking)

def menu(header, options, width, map = 0, talking = False):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

	#calculate total height for the header (after auto-wrap)
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0

	#calculate lines for options, with wrap
	height = 0
	msgs = []
	for line in options:
		new_msg_lines = textwrap.wrap(line, MSG_WIDTH)
		for bit in new_msg_lines:
			msgs.append(bit)
		height = len(msgs) + header_height

	if height == 0:
		height = 3 #must be an alert menu with no options

	#create an off-screen console that represents the menu's window
	window = libtcod.console_new(width, height)

	#print the header, with auto-wrap
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		option_msgs = []
		new_msg_lines = textwrap.wrap(option_text, MSG_WIDTH)
		for line in new_msg_lines:
			#add the new line as a tuple, with the text and the color
			option_msgs.append( line )
			#show the game's title, and some credits!
		if options != [""]:
			text = '(' + chr(letter_index) + ') ' + option_msgs[0]
			libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
			if len(option_msgs)>1:
				i=1
				for k in range(len(option_msgs)-1):
					y += 1
					libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, "    " + option_msgs[i])
					i += 1
			else:
				y += 1
		letter_index += 1

	#blit the contents of "window" to the root console
	if map == 0:
		x = SCREEN_WIDTH/2 - width/2
		y = SCREEN_HEIGHT/2 - height/2
	elif map == 1:
		x = MAP_WIDTH/2 - width/2
		y = MAP_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

	#present the root console to the player and wait for a key-press
	libtcod.console_flush()

	key = libtcod.console_wait_for_keypress(True)
#	while key.vk != libtcod.KEY_NONE: #wait until no key is pressed before accepting new input
#		libtcod.sys_sleep_milli(500) #PAUSE HALF A SECOND so last keypress doesn't carry over to this menu
#		return # no key pressed
#	key.vk = libtcod.KEY_NONE #clear key.vk
	if talking == True: #run bugfix thing if in a conversation
		libtcod.sys_wait_for_event(libtcod.EVENT_KEY_RELEASE, key, libtcod.Mouse(), True) #wait until key_up happens

#	key = libtcod.console_wait_for_keypress(True)

	if key.vk == libtcod.KEY_ENTER and key.lalt:  #(special case) Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	if key.vk == libtcod.KEY_ESCAPE:  #(special case) Alt+Enter: toggle fullscreen
		return

	#convert the ASCII code to an index; if it corresponds to an option, return it
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None


def handle_keys():
	global playerx, playery
	global fov_map, fov_recompute
	global keys

	key = libtcod.console_wait_for_keypress(True) # [[for turnbased]]
#	key = libtcod.console_check_for_keypress() #for realtime
	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#alt enter means toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit' #exit game

	if game_state == 'playing':
		#movement keys
		if libtcod.console_is_key_pressed(libtcod.KEY_UP):
			player_move_or_attack(0, -1)

		elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
			player_move_or_attack(0, 1)

		elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
			player_move_or_attack(-1,0)

		elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
			player_move_or_attack(1,0)
		else:
			return 'didnt-take-turn'

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#render a bar (HP, experience, etc). first calculate the width of the bar
	bar_width = int(float(value) / maximum * total_width)

	#render the background first
	libtcod.console_set_default_background(hud, back_color)
	libtcod.console_rect(hud, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

	#now render the bar on top
	libtcod.console_set_default_background(hud, bar_color)
	if bar_width > 0:
		libtcod.console_rect(hud, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)

	#finally, some centered text with the values
	libtcod.console_set_default_foreground(hud, libtcod.white)
	libtcod.console_print_ex(hud, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
		name + ': ' + str(value) + '/' + str(maximum))

def render_all():
	global fov_map, color_dark_wall, color_light_wall
	global color_dark_ground, color_light_ground
	global fov_recompute
	global desert_crossing, player_has_final_quest, quests
	global overlay

	if fov_recompute:
		#recompute FOV if needed (the player moved or something)
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

		#go through all tiles, and set their background color according to the FOV
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = libtcod.map_is_in_fov(fov_map, x, y)
				wall = map[x][y].block_sight
				if not visible:
					#if it's not visible right now, the player can only see it if it's explored
					if map[x][y].explored:
						if map[x][y].color == 1:
							libtcod.console_set_char_background(con, x, y, color_dark_jetty, libtcod.BKGND_SET)
						elif wall and is_shrub(x,y) == 0:
							libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
						elif is_river(x,y) == 1:
							libtcod.console_set_char_background(con,x,y,color_dark_river,libtcod.BKGND_SET)
						elif is_shrub(x,y) ==1:
							libtcod.console_set_char_background(con,x,y,color_dark_shrub,libtcod.BKGND_SET)
						elif is_path(x,y) == 1:
							libtcod.console_set_char_background(con,x,y,color_dark_path,libtcod.BKGND_SET)
						else:
							libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)

				else:
					#it's visible
					if map[x][y].color == 1:
							libtcod.console_set_char_background(con, x, y, color_light_jetty, libtcod.BKGND_SET)
					elif wall and is_shrub(x,y) == 0:
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
					elif is_river(x,y) == 1:
						if overlay[x][y] == 0:
							libtcod.console_set_char_background(con,x,y,color_light_river,libtcod.BKGND_SET)
						elif overlay[x][y] == 2:
							libtcod.console_set_char_background(con,x,y,color_river_alt,libtcod.BKGND_SET)
					elif is_shrub(x,y) ==1:
						libtcod.console_set_char_background(con,x,y,color_light_shrub,libtcod.BKGND_SET)
					elif is_path(x,y) == 1:
						libtcod.console_set_char_background(con,x,y,color_light_path,libtcod.BKGND_SET)
					else:
						if overlay[x][y] == 0:
							libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
						elif overlay[x][y] == 1:
							libtcod.console_set_char_background(con, x, y, color_ground_alt, libtcod.BKGND_SET )
					#since it's visible, explore it
					map[x][y].explored = True



	#draw all objects in the list
	for object in objects:
		object.draw()

	#draw shouts
	for shout in shouts:
		if shout.time > 0:
			shout.draw()

	#re-draw player
		player.draw()

	#draw border
	render_border(con,libtcod.gray)

	#blit the contents of "con" to the root console
	libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

	#prepare to render the HUD
	libtcod.console_set_default_background(hud, libtcod.black)
	libtcod.console_clear(hud)

	#show the player's stats
	if player.fighter.hp < 0:
		player.fighter.hp = 0

	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
		libtcod.light_red, libtcod.darker_red)

	if player_has_final_quest == True:	#if the desert crossing quest has begun		###DEBUG!!!! DESERT CROSSING NOT INITIALIZED
		libtcod.console_print_ex(hud, BAR_WIDTH+2 , 1, libtcod.BKGND_NONE, libtcod.LEFT, "Food: " + str(player.food))
		libtcod.console_print_ex(hud, BAR_WIDTH+2, 2, libtcod.BKGND_NONE, libtcod.LEFT, "Gear: " + str(player.gear))

	#show active quests
	i=0
	for quest in quests:
		i += 1
		libtcod.console_set_default_foreground(hud, libtcod.gold)
		libtcod.console_print_ex(hud, BAR_WIDTH+2+10 , i, libtcod.BKGND_NONE, libtcod.LEFT, quest.name)


	#populate panel
	#print the game messages, one line at a time
	libtcod.console_clear(panel) #avoid ghosty ghosts!!!
	y = 1
	while len(game_msgs) >= MSG_HEIGHT:
		del game_msgs[0]
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1

	#display names of objects under the mouse
#	libtcod.console_set_default_foreground(hud, libtcod.light_gray)
#	libtcod.console_print_ex(hud, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())


#	for y in range(SCREEN_HEIGHT):  #DEBUG - paint panel red
#		for x in range(PANEL_WIDTH):
#			libtcod.console_set_char_background(panel, x, y, libtcod.red, libtcod.BKGND_SET )

	#blit the contents of "panel" to the root console
	libtcod.console_blit(panel, 0, 0, PANEL_WIDTH, SCREEN_HEIGHT, 0, MAP_WIDTH, 0)



	#blit the contents of "hud" to the root console
	libtcod.console_blit(hud, 0, 0, SCREEN_WIDTH, HUD_HEIGHT, 0, 0, HUD_Y)

def render_border(console, color):
	global objects
#	width = libtcod.console_get_width(console) -20
#	height = libtcod.console_get_height(console) -20
	room = Rect(0,0,MAP_WIDTH-1, MAP_HEIGHT-1)
	for x in range(0,room.w):	#top bar
		libtcod.console_print_ex(con, x, 0, libtcod.BKGND_NONE, libtcod.LEFT, " ")
		libtcod.console_set_char_background(con, x, 0, color, libtcod.BKGND_SET)
	for x in range(0,room.w+1):	#bottom bar
		libtcod.console_print_ex(con, x, room.h, libtcod.BKGND_NONE, libtcod.LEFT, " ")
		libtcod.console_set_char_background(con, x, room.h, color, libtcod.BKGND_SET)
	for x in range(0,room.h):	#left bar
		libtcod.console_print_ex(con, 0, x, libtcod.BKGND_NONE, libtcod.LEFT, " ")
		libtcod.console_set_char_background(con, 0, x, color, libtcod.BKGND_SET)
	for x in range(0,room.h):	#right bar
		libtcod.console_print_ex(con, room.w, x, libtcod.BKGND_NONE, libtcod.LEFT, " ")
		libtcod.console_set_char_background(con, room.w, x, color, libtcod.BKGND_SET)

def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	# create FOV map

	fov_map =  libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

	libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)


def main_menu():
	img = libtcod.image_load('./img/menu_blank.png')

	while not libtcod.console_is_window_closed():
		#show the background image, at twice the regular console resolution
		libtcod.image_blit_2x(img, 0, 0, 0)

		#show the game's title, and some credits!
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,
			'YOU WILL DIE IN THE DESERT')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER,
			'a tale of courage')

		#show options and wait for the player's choice
		choice = menu('', ['Continue','Play a new game', 'Quit'], 24)
		if choice == 0:
#			try:
#				load_game()
#				play_game()
#			except:
#				menu("No saved game found!",[],24, talking = True)
			load_game()
			play_game()
		elif choice == 1:  #new game
			new_game()
			play_game()
		elif choice == 2:  #quit
			quit()

def pause_menu():
	img = libtcod.image_load('./img/pause_background.png')

	while not libtcod.console_is_window_closed():
		#show the background image, at twice the regular console resolution
		libtcod.image_blit_2x(img, 0, MAP_WIDTH/4 - 15, MAP_HEIGHT/4)

		#show the game's title, and some credits!
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, MAP_WIDTH/2, (MAP_HEIGHT/2-10), libtcod.BKGND_NONE, libtcod.CENTER, "Game Paused")

		#show options and wait for the player's choice
		choice = menu('', ["Resume game","Save and quit"], 50,1, talking = False)

		if choice == 0:  #new game
			return False
		elif choice == 1:  #quit
			save_game()
			return True
def talk(char, prompt, options, first_talk = False):
	global fov_recompute

	libtcod.console_clear(con) #ADDED - this line stops message ghosts from remaining
	fov_recompute = True
	render_all()
	libtcod.console_flush()

	prompt = char.name + " says: " + prompt
	prompt_msgs = []

	img = libtcod.image_load('./img/talk_background.png')
	Talking = True
	while Talking == True:
		#show the background image, at twice the regular console resolution
		libtcod.image_blit_2x(img, 0, MAP_WIDTH/4 - 15, MAP_HEIGHT/4)
		#split the message if necessary, among multiple lines
		new_msg_lines = textwrap.wrap(prompt, MSG_WIDTH)
		prompt_msgs = [] #clear so doesn't re-print
		for line in new_msg_lines:
			#add the new line as a tuple, with the text and the color
			prompt_msgs.append( line )
			#show the game's title, and some credits!

		libtcod.console_set_default_foreground(0, char.msgcolor) #set the talk colour to the character's colour

		i = 0
		for line in prompt_msgs:
			libtcod.console_print_ex(0, MAP_WIDTH/2, (MAP_HEIGHT/2-10) + i, libtcod.BKGND_NONE, libtcod.CENTER, line)
			i += 1


		#show options and wait for the player's choice
		choice = menu('', options, 50,1, talking = first_talk)

		if choice != None:
			Talking = False
			return choice

def death_menu(header, options=["Continue."], width = 20, map = 0, talking = True):
	global fov_recompute

	libtcod.console_clear(con) #ADDED - this line stops message ghosts from remaining
	fov_recompute = True
	render_all()
	libtcod.console_flush()

	img = libtcod.image_load('./img/death_background.png')
	#show the background image, at twice the regular console resolution
	libtcod.image_blit_2x(img, 0, SCREEN_WIDTH/4 + 9, SCREEN_WIDTH/4 + 5)
	choice = None
	while choice == None:
		choice = menu(header, options, width, map, True)

def death_report(options=["Continue."], width = 40, map = 0, talking = True):
	global fov_recompute

	libtcod.console_clear(con) #ADDED - this line stops message ghosts from remaining
	fov_recompute = True
	fov_recompute = True
	render_all()
	libtcod.console_flush()

	#build header
	header = ""
	for object in objects:
		if object.ai != None and object.name != "Black Legion soldier":
			if object.dead == True:
				header = header + object.name + " died at your hand.\n\n"
			else:
				header = header + object.name + " was killed by the Black Legion.\n\n"


	img = libtcod.image_load('./img/death_report_background.png')
	#show the background image, at twice the regular console resolution
	libtcod.image_blit_2x(img, 0, SCREEN_WIDTH/4, 20)

	choice = None
	while choice == None:
		choice = menu(header, options, width, map, True)



def quest_menu(quest, prompt, options, first_talk = False):
	global fov_recompute

	libtcod.console_clear(con) #ADDED - this line stops message ghosts from remaining
	fov_recompute = True
	render_all()
	libtcod.console_flush()

	prompt_msgs = []

	img = libtcod.image_load('./img/quest_background.png')
	Talking = True
	while Talking == True:
		#show the background image, at twice the regular console resolution
		libtcod.image_blit_2x(img, 0, MAP_WIDTH/4 - 10, MAP_HEIGHT/4)
		#split the message if necessary, among multiple lines
		new_msg_lines = textwrap.wrap(prompt, MSG_WIDTH)
		prompt_msgs = [] #clear so doesn't re-print
		for line in new_msg_lines:
			#add the new line as a tuple, with the text and the color
			prompt_msgs.append( line )
			#show the game's title, and some credits!

		libtcod.console_set_default_foreground(0, libtcod.white)

		i = 0
		for line in prompt_msgs:
			libtcod.console_print_ex(0, MAP_WIDTH/2, (MAP_HEIGHT/2-10) + i, libtcod.BKGND_NONE, libtcod.CENTER, line)
			i += 1


		#show options and wait for the player's choice
		choice = menu('', options, 50,1, talking = first_talk)

		if choice != None:
			Talking = False
			return choice

def quest_alert(header,text,quest, first_talk = True):
	global quests
	global fov_recompute
	quest.alerted = True
	img = libtcod.image_load('./img/quest_background.png')
		#show the background image, at twice the regular console resolution

	libtcod.console_clear(con) #ADDED - this line stops message ghosts from remaining
	fov_recompute = True
	render_all()
	libtcod.console_flush()


	message(text,libtcod.gold)

	t=0
	while not libtcod.console_is_window_closed() and t==0:
		libtcod.image_blit_2x(img, 0, MAP_WIDTH/4 - 10, MAP_HEIGHT/4)

		#show the title and text
		libtcod.console_set_default_foreground(0, libtcod.gold)

		#split the message if necessary, among multiple lines
		new_msg_lines = textwrap.wrap(text, MSG_WIDTH)
		prompt_msgs = []
		for line in new_msg_lines:
			#add the new line as a tuple, with the text and the color
			prompt_msgs.append( line )
			#show the game's title, and some credits!



		i = 0
		for line in prompt_msgs:
			libtcod.console_print_ex(0, MAP_WIDTH/2, (MAP_HEIGHT/2-10) + i, libtcod.BKGND_NONE, libtcod.CENTER, line)
			i += 1

		libtcod.console_print_ex(0, MAP_WIDTH/2, MAP_HEIGHT/2-12, libtcod.BKGND_NONE, libtcod.CENTER,
			header)


		choice = menu('', ["Continue."], 40,1, talking = first_talk)

		if choice != None:
			t=1
			return choice

def welcome_message():
	if game_stage == 1:
			message('You look around and see the bodies of your fellow soldiers. The battle is not going well...', libtcod.white)

def new_game():
	global player, game_msgs, game_state, game_stage
	global quests, quest_giver
	global player_has_final_quest

	#initialize questgiver
	quest_giver = QuestGiver()
	player_has_final_quest = False
	quests = []

	game_stage = 1
	#create object representing the player
	fighter_component = Fighter(hp=30, defense=2, power=8, death_function=player_death)

	player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component, food = 0, gear = 0)


	initialize_overlay()
	#generate map
	make_map_stage1()
	place_objects_stage1()
	initialize_fov()


#
#	palette_switch_vibrant()
#	make_map_stage4()												#START AT STAGE 4
#	place_objects_stage4()
#	initialize_fov()
#	game_msgs = ["asds","asdsa"]
#	log = Quest("Logs!", "Good work! Keep it up.")
#


	game_state = 'playing'
	game_msgs = []

	#welcome message
	welcome_message()

def save_game():
	file = shelve.open('savegame','n')
	file['map']=map
	file['objects']=objects
	file['player_index'] = objects.index(player)
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['quests']=quests
	file['game_stage']=game_stage
	file['quest_giver']=quest_giver
	file['shouts']=shouts
	file['player_has_final_quest'] = player_has_final_quest
	file['overlay'] = overlay

#	if game_stage == 4:
#		file['farmerSonBoris'] = farmerSonBoris
#		file['farmerSonMaurice'] = farmerSonMaurice
#		file['fishermanDad'] = fishermanDad
#		file['fishermanSon'] = fishermanSon
#		file['fishermanMum'] = fishermanMum
#		file['farmerDad'] = farmerDad
#		file['farmerDaughter'] = farmerDaughter
#		file['Blacksmith'] = Blacksmith
#		file['blacksmith_pet'] = blacksmith_pet
	file.close()

def load_game():
	global map, objects, player, game_msgs, game_state, quests, quest_giver, shouts, player_has_final_quest, game_stage, overlay

	file = shelve.open('savegame')
	objects = file['objects']
	player = objects[file['player_index']]  #get index of player in objects list and access it
	quests = file['quests']
#	game_msgs = file['game_msgs']
	game_msgs = []
	game_state = file['game_state']
	quest_giver = file['quest_giver']
	game_stage = file['game_stage']
	map = file['map']
	shouts = file['shouts']
	player_has_final_quest = file['player_has_final_quest']
	overlay = file['overlay']

#	if game_stage == 4:
#		global farmerSonBoris, farmerSonMaurice,fishermanDad,fishermanSon,fishermanMum,farmerDad,farmerDaughter,Blacksmith,blacksmith_pet
#		farmerSonBoris = file['farmerSonBoris']
#		farmerSonMaurice = file['farmerSonMaurice']
#		fishermanDad = file['fishermanDad']
#		fishermanSon = file['fishermanSon']
#		fishermanMum = file['fishermanMum']
#		farmerDad = file['farmerDad']
#		farmerDaughter = file['farmerDaughter']
#		Blacksmith = file['Blacksmith']
#		blacksmith_pet = file['blacksmith_pet']

	file.close()
	message("Your eyes blink open. Did you zone out for a second?")
	palette_switch_sad()
	if game_stage == 1:
		new_game()
		play_game()
	if game_stage == 2:
		palette_switch_less_sad()
		make_map_stage2()
		place_objects_stage2()
		play_game()
	elif game_stage == 3:
		palette_switch_medium()
		make_map_stage3()
		place_objects_stage3()
		play_game()
	elif game_stage == 4:
		quest_giver.global_time = 0
		quests = [] #make sure no previous quests carry over
		palette_switch_vibrant()
		make_map_stage4()
		place_objects_stage4()
		play_game()

	initialize_fov()

def play_game():
	global key, mouse, quest_giver

	time = 0

	player_action = None

	mouse = libtcod.Mouse()
	key = libtcod.Key()

	while not libtcod.console_is_window_closed():
#		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)

		libtcod.console_clear(panel) #ADDED - this line stops message ghosts from remaining when scrollup
		render_all()
		libtcod.console_flush()


		#erase all objects at their old locations, before they move
		for object in objects:
			object.clear()
		#handle keys and exit if needed
		player_action = handle_keys()
		if player_action == 'exit': #if user presses Esc
			if pause_menu():	#if menu hits quit
				main_menu()
		#let monsters take their turn
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()
		#tick the shouts
		for shout in shouts:
			shout.tick()
		quest_giver.tick() #tick the questgiver

		tick_overlay_river() #make sure the river is running in the graphics overlay

		#DEBUG




########################################
#  Init and main loop
########################################

#terminal10x10_gs_tc.png  - nice, chunky font. sentences read well.
#arial10x10.png
#terminal16x16_gs_ro
#custom10x10.png
#libtcod.console_set_custom_font('consolas12x12_gs_tc.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
#libtcod.console_set_custom_font('terminal12x12_gs_ro.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_set_custom_font('./img/custom10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'You Will Die In The Desert', False)
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT) #create main console

libtcod.sys_set_fps(LIMIT_FPS)

#create panel for HUD
panel = libtcod.console_new(PANEL_WIDTH, PANEL_HEIGHT)
hud = libtcod.console_new(SCREEN_WIDTH, HUD_HEIGHT)



main_menu()
