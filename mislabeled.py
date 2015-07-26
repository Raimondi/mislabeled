# -*- coding: utf-8 -*-
#
# Copyright (c) 2015 by Israel Chauca F. <israelchauca++mislabeled@gmail.com>
# Copyright (c) 2014 by Filip H.F. "FiXato" Slagter <fixato+weechat@gmail.com>
#
# mislabeled: a quick WeeChat script to mark users as "mislabeled" and display a
#          warning behind what they post.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# 2015-07-31: 0.1 initial release
#
# requires: WeeChat version 0.3.6 or higher
#
# Based on https://github.com/FiXato/weechat_scripts/blob/master/shutup.py

try:
  import weechat,re
  from random import choice

except Exception:
  print "This script must be run under WeeChat."
  print "Get WeeChat now at: http://www.weechat.org/"
  quit()

SCRIPT_NAME     = "mislabeled"
SCRIPT_AUTHOR   = 'Israel Chauca F. <israelchauca++mislabeled@gmail.com>'
SCRIPT_VERSION  = "0.1"
SCRIPT_LICENSE  = "GPL"
SCRIPT_DESC     = "You can put labels on anyone you want."

OPTIONS         = {
                    'default_label'   : ('mislabeled', 'Default label.'),
                    'items'           : (''          , 'Space-separated regular expressions that will be matched against the nick!ident@host.item. Any user matching will get their message  marked as mislabeled. Can also include a comma-separated list of channels followed by a list of labels for every regular expression separated from each other and the regexp by a colon. Prefix regexp with (?i) if you want it to be case insensitive. Example: "@\S+\.aol\.com$:#comcast,#AT&T:trust (?i)!root@\S+ foobar::avoid" would label messages in channels #comcast and #AT&T from users whose hosts end in *.aol.com with "trust", all users who have any case variation of root as ident regardless of channel would be labeled with the default label; and any user with "foobar" on its nick or host in any channel with the label "avoid".'),
                    'separator'       : ('|'         , 'Character used to separate labels.'),
                    'delimiter_color' : ('cyan'      , 'Color used for the delimiters.'),
                    'label_color'     : ('red'       , 'Color used for labels.'),
                  }
DEBUG = False
label_marker = '<mislabeled_marker:'
label_marker_re = r'(%s)([^>]*)(>)' % label_marker

# ===================[ weechat options & description ]===================
def init_options():
  for option,value in OPTIONS.items():
    if not weechat.config_is_set_plugin(option):
      weechat.config_set_plugin(option, value[0])
      toggle_refresh(None, 'plugins.var.python.' + SCRIPT_NAME + '.' + option, value[0])
    else:
      toggle_refresh(None, 'plugins.var.python.' + SCRIPT_NAME + '.' + option, \
          weechat.config_get_plugin(option))
    weechat.config_set_desc_plugin(option, '%s (default: "%s")' % (value[1], value[0]))

def debug(str):
  if DEBUG:
    weechat.prnt("", '%s: %s' % (SCRIPT_NAME, str))

def update_items(items):
  global mislabeled_items
  mislabeled_items = []
  for item in items.split():
    pattern, chan, lbls = (item.split(':') + ['']*3)[:3]
    channels = [channel.lower() for channel in chan.split(',') if channel]
    labels = [label for label in lbls.split(',') if label]
    if not labels:
      # At leat one label is required.
      labels.append(weechat.config_get_plugin('default_label'))
    mislabeled_items.append([pattern, re.compile(pattern), channels, labels])
  debug('updated items: %s' % str(mislabeled_items))

# TODO remove this
def toggle_refresh(pointer, name, value):
  global OPTIONS
  option = name[len('plugins.var.python.' + SCRIPT_NAME + '.'):] # get optionname
  OPTIONS[option] = value                                        # save new value
  if option == 'items':
    update_items(value)
  return weechat.WEECHAT_RC_OK

def mislabeled_cb(data, modifier, modifier_data, string):
  dict_in = { "message": string }
  cur_labels = []
  message_ht = weechat.info_get_hashtable("irc_message_parse", dict_in)

  hostitem = message_ht['host']
  arguments = message_ht['arguments']
  channel = message_ht['channel']

  # If it's a CTCP other than ACTION, do nothing.
  debug(re.sub(r'\x01', 'x', arguments))
  if not re.match(r'[^:]+:([^\x01]|\x01ACTION\b)', arguments):
    return string
  # Add the marker and keep ACTION on its propper place.
  new_arguments = re.sub(r'^(%s :(\x01ACTION )?)' % channel, \
      r'\1%s' % label_marker + '>', arguments)
  new_string = re.sub(r'%s$' % re.escape(arguments), new_arguments, string)

  for key, item_regexp, channels, labels in mislabeled_items:
    # If there is one or more channels listed for this item regexp, and none of
    # them match the current channel, continue to the next mute item.
    if len(channels) > 0 and channel.lower() not in channels:
      debug("%s doesn't match any of the listed channels: %s" % (channel, channels))
      continue

    # If the hostitem matches the item regular expression, return the new,
    # manipulated, string.
    debug("comparing %s to %s" % (item_regexp.pattern, hostitem))
    if item_regexp.search(hostitem):
      debug("  %s matches %s" % (item_regexp.pattern, hostitem))
      [cur_labels.append(label) for label in labels if label not in cur_labels]
    if cur_labels:
      # we have some tags to use
      debug("  current labels: %s" % ', '.join(cur_labels))
      string = re.sub(label_marker_re, r'\1\2%s\3' % ','.join(cur_labels), new_string)
  return string

def colorize_cb(data, modifier, modifier_data, string):
  matches = re.search(r'<mislabeled_marker:([^>]*)>', string)
  if matches:
    delim_c = weechat.color(weechat.config_get_plugin('delimiter_color'))
    lbl_c = weechat.color(weechat.config_get_plugin('label_color'))
    sep = delim_c + weechat.config_get_plugin('separator') + lbl_c
    labels = sep.join(matches.group(1).split(','))
    string = re.sub(r'<mislabeled_marker:[^>]*>', '%s[%s%s%s]%s ' % \
        (delim_c, lbl_c, labels, delim_c, weechat.color("reset")), string)
  return string

def command_cb(data, buffer, args):
  debug('adding "%s"' % args)
  items = weechat.config_get_plugin('items')
  new_items = '%s %s' % (items, args)
  debug('new_items: %s' % new_items)
  weechat.config_set_plugin('items', new_items)
  return weechat.WEECHAT_RC_OK

# ================================[ main ]===============================
if __name__ == "__main__":
  if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, '', ''):
    version = weechat.info_get("version_number", "") or 0

    if int(version) >= 0x00030600:
      # init options from your script
      init_options()
      # create a hook for your options
      weechat.hook_config( 'plugins.var.python.' + SCRIPT_NAME + '.*', 'toggle_refresh', '' )
    else:
      weechat.prnt("","%s%s %s" % (weechat.prefix("error"),SCRIPT_NAME,": needs version 0.3.6 or higher"))
      weechat.command("","/wait 1ms /python unload %s" % SCRIPT_NAME)

    hook = weechat.hook_modifier("irc_in_privmsg", "mislabeled_cb", "")
    hook = weechat.hook_modifier("weechat_print", "colorize_cb", "")
    hook = weechat.hook_command("mislabeled", "Add an item to the mislabeled list.",
        "pattern[:[channel,list][:label,list]]",
        "A pattern, a colon, an optional comma delimited list of channel names, a colon and an optional comma delimited list of labels",
        "%(nick)", "command_cb", "")
