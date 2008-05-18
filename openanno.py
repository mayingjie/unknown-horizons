#!/usr/bin/env python

# ###################################################
# Copyright (C) 2008 The OpenAnnoTeam
# team@openanno.org
# This file is part of OpenAnno.
#
# OpenAnno is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the
# Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# ###################################################

import sys
import os

try:
	import settings
	_paths = [settings.path]
except ImportError, e:
	_paths = []
_paths += [ a + '/' + b + '/' + c for a in ('.', '..', '../..') for b in ('.', 'fife', 'FIFE', 'Fife') for c in ('.', 'trunk') ]

fife_path = None
for p in _paths:
	if p not in sys.path:
		# check if we are in a fife dir...
		for pe in [ p + '/' + a for a in ('.', 'engine', 'engine/extensions', 'engine/swigwrappers/python') ]:
			if not os.path.exists(pe):
				break
		else:
			fife_path = p
			print "found fife in:", fife_path

			#add python paths (<fife>/engine/extensions <fife>/engine/swigwrappers/python)
			for pe in [ fife_path + '/' + a for a in ('engine/extensions', 'engine/swigwrappers/python') ]:
				if os.path.exists(pe):
					sys.path.append(pe)

			#add windows paths (<fife>/.)
			os.environ['PATH'] = os.path.pathsep.join(os.environ.get('PATH', '').split(os.path.pathsep) + [ fife_path + '/' + a for a in ('.') ])
			os.path.defpath += os.path.pathsep + os.path.pathsep.join([ fife_path + '/' + a for a in ('.') ])
			break
else:
	print 'FIFE was not found.'
	print "Please create a settings.py file and add a line with: path = '<path to fife>' eg. path = '../../fife/trunk/'"
	exit()

try:
	if not os.environ.get('LD_LIBRARY_PATH', '').startswith(fife_path):
		try:
			import fife
		except ImportError, e:
			os.environ['LD_LIBRARY_PATH'] = os.path.pathsep.join([ p + '/' + a for a in ('ext/minizip', 'ext/install/lib') ] + (os.environ['LD_LIBRARY_PATH'].split(os.path.pathsep) if os.environ.has_key('LD_LIBRARY_PATH') else []))
			print "Restarting OpenAnno with proper LD_LIBRARY_PATH..."
			args = [sys.executable] + sys.argv
			os.execvp(args[0], args)
	else:
		import fife
except ImportError, e:
	print 'FIFE was not found or failed to load'
	print 'Reason: ' + e.message
	print "Please create a settings.py file and add a line with: path = '<path to fife>' eg. path = '../../fife/trunk/'"
	exit()

import re
import shutil
import style
from game import Game
from game.gui.keylistener import KeyListener
from game.dbreader import DbReader
from game import all
from game.engine import Fife

class OpenAnno:
	"""OpenAnno class, main game class. Creates the base."""
	def __init__(self):
		all.db = DbReader(':memory:')
		all.db.query("attach ? AS data", ('content/openanno.sqlite'))
		class settings:
			FullScreen          = 0         # configurable
			ScreenWidth         = 1024      # configurable
			ScreenHeight        = 768       # configurable
			BitsPerPixel        = 0         # configurable
			RenderBackend       = "OpenGL"  # configurable
			InitialVolume       = 5.0
			PlaySounds          = 1         # configurable
			SDLRemoveFakeAlpha  = 1
			Font                = 'content/gfx/fonts/samanata.ttf'
			FontSize            = 12
			FontGlyphs          = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,!?-+/():;%&`'*#=[]\""
			LogModules          = ['controller'] #'all' for everything
			PychanDebug         = False
			LogToPrompt         = 1
			LogToFile           = 1
			UsePsyco            = False
			ImageChunkSize      = 256
		self.settings = settings()
		configFile = './openanno-config.sqlite'
		if not os.path.exists(configFile):
			shutil.copyfile('content/config.sqlite', configFile)
		all.db.query("attach ? AS config", (configFile))
		for (name, value) in all.db.query("select name, value from config.config where ((name in ('screen_full', 'sound_enable') and value in ('0', '1')) or (name in ('screen_width', 'screen_height') and value regexp '^[0-9]+$') or (name = 'screen_bpp' and value in ('0', '16', '24', '32')) or (name = 'screen_renderer' and value in ('SDL', 'OpenGL')) or (name = 'sound_volume' and value regexp '^[0-9]+([.][0-9]+)?$'))").rows:
			if name == 'sound_enable':
				self.settings.PlaySounds = int(value)
			if name == 'screen_full':
				self.settings.FullScreen = int(value)
			if name == 'screen_width':
				self.settings.ScreenWidth = int(value)
			if name == 'screen_height':
				self.settings.ScreenHeight = int(value)
			if name == 'screen_bpp':
				self.settings.BitsPerPixel = int(value)
			if name == 'screen_renderer':
				self.settings.RenderBackend = str(value)

		self.fife = Fife()
		#sett settings
		self.fife.init()
		self.engine = self.fife.engine
		all.engine = self.fife.engine
		all.settings = self.settings

		# Load styles here
		for name, stylepart in style.STYLES.items():
			self.fife.pychan.manager.addStyle(name, stylepart)
		self.fife.pychan.loadFonts("content/fonts/samanata.fontdef")

		self.mainmenu = self.fife.pychan.loadXML('content/gui/mainmenu.xml')
		self.mainmenu.stylize('menu')
		self.gamemenu = self.fife.pychan.loadXML('content/gui/gamemenu.xml')
		self.gamemenu.stylize('menu')

		eventMap = {
			'startGame' : self.start_game,
			'settingsLink' : self.showSettings,
			'creditsLink'  : self.showCredits,
			'closeButton'  : self.showQuit,
		}
		self.mainmenu.mapEvents(eventMap)
		self.gamemenu.mapEvents(eventMap)
		self.gui = self.mainmenu
		self.gui.show()
		self.game = None

		self.soundmanager = self.fife.soundmanager

		# play track as background music
		if self.settings.PlaySounds == 1:
			emitter = self.soundmanager.createEmitter()
			id = all.engine.getSoundClipPool().addResourceFromFile('content/audio/music/music.ogg')
			emitter.setSoundClip(id)
			emitter.setLooping(True)
			emitter.play()

		self.fife.pump = self.pump
		self.fife.run()

	def showCredits(self):
		self.fife.pychan.loadXML('content/gui/credits.xml').execute({ 'okButton' : True })

	def showSettings(self):
		resolutions = ["640x480", "800x600", "1024x768", "1440x900"];
		try:
			resolutions.index(str(all.settings.ScreenWidth) + 'x' + str(all.settings.ScreenHeight))
		except:
			resolutions.append(str(all.settings.ScreenWidth) + 'x' + str(all.settings.ScreenHeight))
		dlg = self.fife.pychan.loadXML('content/gui/settings.xml')
		dlg.distributeInitialData({
			'screen_resolution' : resolutions,
			'screen_renderer' : ["OpenGL", "SDL"],
			'screen_bpp' : ["Desktop", "16", "24", "32"]
		})
		dlg.distributeData({
			'screen_resolution' : resolutions.index(str(all.settings.ScreenWidth) + 'x' + str(all.settings.ScreenHeight)),
			'screen_renderer' : 0 if all.settings.RenderBackend == 'OpenGL' else 1,
			'screen_bpp' : int(all.settings.BitsPerPixel / 10), # 0:0 16:1 24:2 32:3 :)
			'screen_fullscreen' : all.settings.FullScreen == 1,
			'sound_enable_opt' : self.settings.PlaySounds == 1
		})
		if(not dlg.execute({ 'okButton' : True, 'cancelButton' : False })):
			return;
		screen_resolution, screen_renderer, screen_bpp, screen_fullscreen, sound_enable_opt = dlg.collectData('screen_resolution', 'screen_renderer', 'screen_bpp', 'screen_fullscreen', 'sound_enable_opt')
		changes_require_restart = False
		if screen_fullscreen != (all.settings.FullScreen == 1):
			all.settings.FullScreen = (1 if screen_fullscreen else 0)
			all.db.query("REPLACE INTO config.config (name, value) VALUES (?, ?)", ('screen_full', all.settings.FullScreen));
			all.engine.getSettings().setFullScreen(all.settings.FullScreen)
			changes_require_restart = True
		if sound_enable_opt != (self.settings.PlaySounds == 1):
			self.settings.PlaySounds = (1 if sound_enable_opt else 0)
			all.db.query("REPLACE INTO config.config (name, value) VALUES (?, ?)", ('sound_enable', self.settings.PlaySounds));
			changes_require_restart = True
		if screen_bpp != int(all.settings.BitsPerPixel / 10):
			all.settings.BitsPerPixel = (0 if screen_bpp == 0 else ((screen_bpp + 1) * 8))
			all.db.query("REPLACE INTO config.config (name, value) VALUES (?, ?)", ('screen_bpp', all.settings.BitsPerPixel));
			all.engine.getSettings().setBitsPerPixel(all.settings.BitsPerPixel)
			changes_require_restart = True
		if screen_renderer != (0 if all.settings.RenderBackend == 'OpenGL' else 1):
			all.settings.RenderBackend = 'OpenGL' if screen_renderer == 0 else 'SDL'
			all.db.query("REPLACE INTO config.config (name, value) VALUES (?, ?)", ('screen_renderer', all.settings.RenderBackend));
			all.engine.getSettings().setRenderBackend(all.settings.RenderBackend)
			changes_require_restart = True
		if screen_resolution != resolutions.index(str(all.settings.ScreenWidth) + 'x' + str(all.settings.ScreenHeight)):
			all.settings.ScreenWidth = int(resolutions[screen_resolution].partition('x')[0])
			all.settings.ScreenHeight = int(resolutions[screen_resolution].partition('x')[2])
			all.db.query("REPLACE INTO config.config (name, value) VALUES (?, ?)", ('screen_width', all.settings.ScreenWidth));
			all.db.query("REPLACE INTO config.config (name, value) VALUES (?, ?)", ('screen_height', all.settings.ScreenHeight));
			all.engine.getSettings().setScreenWidth(all.settings.ScreenWidth)
			all.engine.getSettings().setScreenHeight(all.settings.ScreenHeight)
			changes_require_restart = True
		if changes_require_restart:
			self.fife.pychan.loadXML('content/gui/changes_require_restart.xml').execute({ 'okButton' : True})

	def showQuit(self):
		if self.game is None:
			if(self.fife.pychan.loadXML('content/gui/quitgame.xml').execute({ 'okButton' : True, 'cancelButton' : False })):
				self.fife.quit()
		else:
			if(self.fife.pychan.loadXML('content/gui/quitsession.xml').execute({ 'okButton' : True, 'cancelButton' : False })):
				self.game.__del__()
				self.game = None
				self.gui.hide()
				self.gui = self.mainmenu
				self.gui.show()

	def start_game(self):
		self.gui.hide()
		self.gui = self.gamemenu
		if self.game is None:
			self.game = Game(self, "content/maps/demo.sqlite")

	def createListener(self):
		self.listener = KeyListener(all.engine, all.main)

	def pump(self):
		if self.game is not None and self.game.timer is not None:
			self.game.timer.check_tick()

if __name__ == '__main__':
	all.main = OpenAnno()
