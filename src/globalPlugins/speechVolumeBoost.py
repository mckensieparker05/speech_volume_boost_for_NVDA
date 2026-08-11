# -*- coding: utf-8 -*-
# A part of Speech Volume Boost for NVDA
# Copyright (C) 2026
# Released under the GNU General Public License, version 2 or later.

"""Amplifies NVDA speech volume universally, for any synthesizer.

The plugin intercepts every chunk of 16-bit speech PCM as it is fed to
``nvwave.WavePlayer`` in the main NVDA process and scales the samples by a
user-configurable gain. Because every synthesizer (eSpeak NG, OneCore, SAPI5,
32-bit SAPI hosts, third party synth drivers) funnels its audio through
``WavePlayer.feed``, a single hook covers them all.
"""

from __future__ import annotations

import array
import ctypes
import threading

import addonHandler
import config
import globalPluginHandler
import nvwave
import ui
import wx

from logHandler import log
from scriptHandler import script
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel

addonHandler.initTranslation()

CONFIG_SECTION = "speechVolumeBoost"

#: Gain in percent: 100 means unchanged, values above 100 amplify the signal.
MAX_GAIN = 400
GAIN_STEP = 10

CONFIG_SPEC = {
	"enabled": "boolean(default=True)",
	"gain": f"integer(default=100, min=0, max={MAX_GAIN})",
}
config.conf.spec[CONFIG_SECTION] = CONFIG_SPEC

_ORIGINAL_FEED_ATTR = "_speechVolumeBoost_originalFeed"
_PATCHED_ATTR = "_speechVolumeBoost_feedPatched"
_PATCH_LOCK = threading.Lock()


def _getConfigValue(key, default=None):
	try:
		return config.conf[CONFIG_SECTION][key]
	except KeyError:
		return default


def _setConfigValue(key, value):
	config.conf[CONFIG_SECTION][key] = value


def _saveConfig():
	try:
		config.conf.save()
	except Exception:
		log.exception("speechVolumeBoost: error saving configuration")


def _isSpeechPlayer(player):
	try:
		return getattr(player, "_purpose", None) == nvwave.AudioPurpose.SPEECH
	except Exception:
		return False


def _toBytes(data, size=None):
	"""Convert the various data forms passed to WavePlayer.feed into bytes."""
	if data is None:
		return None
	if isinstance(data, bytes):
		return data
	if isinstance(data, ctypes.Array):
		return bytes(data)
	try:
		addr = getattr(data, "value", None)
		if addr is None:
			addr = int(data)
	except (TypeError, ValueError):
		return None
	if not addr or size is None:
		return None
	return ctypes.string_at(addr, size)


def _applyGain(raw, gainPercent):
	"""Scale 16-bit little endian PCM samples by a gain in percent."""
	if gainPercent == 100 or not raw:
		return raw
	try:
		samples = array.array("h")
		samples.frombytes(raw)
	except (ValueError, TypeError):
		return None
	if gainPercent == 0:
		return bytes(len(samples) * samples.itemsize)
	gain = gainPercent / 100.0
	for i in range(len(samples)):
		value = samples[i] * gain
		if value > 32767:
			value = 32767
		elif value < -32768:
			value = -32768
		else:
			value = int(value)
		samples[i] = value
	return samples.tobytes()


def _patchedFeed(self, data, size=None, onDone=None):
	originalFeed = getattr(nvwave.WavePlayer, _ORIGINAL_FEED_ATTR)
	if callable(size) and onDone is None:
		onDone = size
		size = None
	try:
		if (
			_getConfigValue("enabled", True)
			and _isSpeechPlayer(self)
			and getattr(self, "bitsPerSample", 16) == 16
		):
			raw = _toBytes(data, size)
			if raw:
				processed = _applyGain(raw, _getConfigValue("gain", 100))
				if processed is not None:
					return originalFeed(self, processed, len(processed), onDone)
	except Exception:
		log.exception("speechVolumeBoost: error while boosting audio")
	return originalFeed(self, data, size, onDone)


def _installFeedHook():
	with _PATCH_LOCK:
		if getattr(nvwave.WavePlayer, _PATCHED_ATTR, False):
			return
		setattr(nvwave.WavePlayer, _ORIGINAL_FEED_ATTR, nvwave.WavePlayer.feed)
		nvwave.WavePlayer.feed = _patchedFeed
		setattr(nvwave.WavePlayer, _PATCHED_ATTR, True)


def _uninstallFeedHook():
	with _PATCH_LOCK:
		if not getattr(nvwave.WavePlayer, _PATCHED_ATTR, False):
			return
		originalFeed = getattr(nvwave.WavePlayer, _ORIGINAL_FEED_ATTR, None)
		if originalFeed is not None:
			nvwave.WavePlayer.feed = originalFeed
		delattr(nvwave.WavePlayer, _PATCHED_ATTR)
		try:
			delattr(nvwave.WavePlayer, _ORIGINAL_FEED_ATTR)
		except AttributeError:
			pass


class SpeechVolumeBoostSettingsPanel(SettingsPanel):
	title = _("Speech Volume Boost")

	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.enableCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("Enable speech volume &boost"))
		)
		self.enableCheckBox.SetValue(bool(_getConfigValue("enabled", True)))
		self.gainSlider = sHelper.addLabeledControl(
			_("&Gain (100 is unchanged, 400 is four times louder)"),
			wx.Slider,
			minValue=0,
			maxValue=MAX_GAIN,
			value=int(_getConfigValue("gain", 100)),
			style=wx.SL_HORIZONTAL | wx.SL_LABELS,
		)
		self.gainSlider.SetMinSize(self.scaleSize((300, -1)))

	def onSave(self):
		_setConfigValue("enabled", self.enableCheckBox.IsChecked())
		_setConfigValue("gain", self.gainSlider.GetValue())
		_saveConfig()


def _registerSettingsPanel():
	try:
		from gui.settingsDialogs import NVDASettingsDialog, SpeechSettingsPanel
		index = NVDASettingsDialog.categoryClasses.index(SpeechSettingsPanel) + 1
	except (ImportError, ValueError):
		index = 0
	if SpeechVolumeBoostSettingsPanel not in NVDASettingsDialog.categoryClasses:
		NVDASettingsDialog.categoryClasses.insert(index, SpeechVolumeBoostSettingsPanel)


def _unregisterSettingsPanel():
	try:
		from gui.settingsDialogs import NVDASettingsDialog
		if SpeechVolumeBoostSettingsPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(SpeechVolumeBoostSettingsPanel)
	except ImportError:
		pass


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Speech Volume Boost")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		_installFeedHook()
		_registerSettingsPanel()

	def terminate(self, *args, **kwargs):
		_unregisterSettingsPanel()
		_uninstallFeedHook()
		super().terminate(*args, **kwargs)

	@script(
		description=_("Toggles speech volume boost"),
		gesture="kb:NVDA+alt+g",
	)
	def script_toggleBoost(self, gesture):
		state = not bool(_getConfigValue("enabled", True))
		_setConfigValue("enabled", state)
		_saveConfig()
		if state:
			ui.message(_("Speech volume boost enabled"))
		else:
			ui.message(_("Speech volume boost disabled"))

	@script(
		description=_("Increases the speech volume boost gain by 10 percent"),
		gesture="kb:NVDA+alt+shift+g",
	)
	def script_increaseGain(self, gesture):
		self._adjustGain(GAIN_STEP)

	@script(
		description=_("Decreases the speech volume boost gain by 10 percent"),
		gesture="kb:NVDA+alt+control+g",
	)
	def script_decreaseGain(self, gesture):
		self._adjustGain(-GAIN_STEP)

	@script(
		description=_("Reports the speech volume boost state and gain"),
		gesture="kb:NVDA+alt+control+shift+g",
	)
	def script_reportBoost(self, gesture):
		state = bool(_getConfigValue("enabled", True))
		gain = int(_getConfigValue("gain", 100))
		if state:
			stateText = _("enabled")
		else:
			stateText = _("disabled")
		ui.message(
			_("Speech volume boost {state}, gain {percent} percent").format(
				state=stateText,
				percent=gain,
			)
		)

	def _adjustGain(self, amount):
		gain = int(_getConfigValue("gain", 100)) + amount
		gain = max(0, min(MAX_GAIN, gain))
		_setConfigValue("gain", gain)
		_saveConfig()
		ui.message(_("Speech volume boost gain: {percent} percent").format(percent=gain))
