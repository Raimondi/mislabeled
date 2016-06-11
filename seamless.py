# -*- coding: utf-8 -*- vim: set et sw=2:
#
# Copyright (c) 2015 by Israel Chauca F. <israelchauca++seamless@gmail.com>
# Copyright (c) 2014 by Filip H.F. "FiXato" Slagter <fixato+weechat@gmail.com>
#
# seamless: Help to forget the relay bot is there.
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

# TODO FIXME NOTE
# TODO:

try:
  import weechat,re
  from random import choice

except Exception:
  print "This script must be run under WeeChat."
  print "Get WeeChat now at: http://www.weechat.org/"
  quit()

SCRIPT_NAME     = "seamless"
SCRIPT_AUTHOR   = 'Israel Chauca F. <israelchauca++seamless@gmail.com>'
SCRIPT_VERSION  = "0.1"
SCRIPT_LICENSE  = "GPL"
SCRIPT_DESC     = "Make it like relay/bridge bots are not even there. " \
    + "Support for ijchain, gitterircbot."

OPTIONS         = {
    'nicks'   : ('', 'nick1 nick2:server1,server2'),
                  }
DEBUG = False

_nicks = []
_bots  = []

# ===================[ weechat options & description ]===================
def init_options():
  for option,value in OPTIONS.items():
    if not weechat.config_is_set_plugin(option):
      weechat.config_set_plugin(option, value[0])
      sync_with_options(None, 'plugins.var.python.' + SCRIPT_NAME \
          + '.' + option, value[0])
    else:
      sync_with_options(None, 'plugins.var.python.' + SCRIPT_NAME + '.' \
          + option, weechat.config_get_plugin(option))
    weechat.config_set_desc_plugin(option, \
        '%s (default: "%s")' % (value[1], value[0]))

def debug(str):
  if DEBUG:
    weechat.prnt("", '%s: %s' % (SCRIPT_NAME, str))

def sync_with_options(pointer, name, value):
  global OPTIONS
  # get optionname
  option = name[len('plugins.var.python.' + SCRIPT_NAME + '.'):]
  # save new value
  OPTIONS[option] = value
  if option == 'nicks':
    update_nicks(value)
  return weechat.WEECHAT_RC_OK

def update_nicks(nicks):
  '''
  "nick1:server1,server2 ..."
  [['nick1',
    ['server1', 'server2',...],
    ],...]
  '''
  global _nicks
  _nicks = []
  for text in nicks.split():
    if ':' in text:
      item = text.split(':', 1)
      item[0] = item[0].split(',')
    else:
      item = [text,[]]
    _nicks.append(item)
    debug('%s' % _nicks)

# ===========================[ Set upt bots ]============================
# Supported relay bots:
# - ijchain
# - gitterircbot

def re_extract(regex, string):
  matches = re.match(regex, string)
  if matches:
    return matches.groups()
  else:
    return []

# ijchain
robot = {}
robot['name'] = 'ijchain'
robot['nick'] = r'^ijchain\d*$'
robot['action_extract_parts'] = lambda x: re_extract(r'^(\S+)\s(.*)', x)
robot['action_join'] = r'^has become available$'
robot['action_part'] = r'^has left$'
robot['privmsg_extract_parts'] = lambda x: re_extract(r'^<([^> ]+)>\s(.*)', x)
_bots.append(robot)

# gitterircbot https://github.com/finnp/gitter-irc-bot
robot = {}
robot['name'] = 'gitterircbot'
robot['nick'] = r'^gitterircbot[0-9_]*$'
robot['privmsg_extract_parts'] = \
    lambda x: re_extract(r'^[(`]([^)` ]+)[)`]\s(.*)', x)
_bots.append(robot)

def add_nick(info, bot, rnick, rtext, result):
  buffer = weechat.buffer_search('==', 'irc.%s.%s' % (info['server'], info['channel']))
  if buffer and not weechat.nicklist_search_nick(buffer, '', rnick):
    result.append(":%s!~%s@%s.%s JOIN %s" % \
        (rnick, rnick, info['nick'], SCRIPT_NAME, info['channel']))

def seamless_cb(data, modifier, modifier_data, string):
  info = weechat.info_get_hashtable("irc_message_parse", { "message": string })
  info['server'] = modifier_data
  channel = info['channel']
  buf_p = weechat.buffer_search('==', \
      'irc.' + info['server'] + '.' + channel)
  if not buf_p:
    debug('no buffer for %s' % \
        'irc.' + info['server'] + '.' + info['channel'])
    return string
  text = info.get('text', info['arguments'].split(' :', 1)[1])
  action = re.match(r'^\x01.*\x01', text)
  if action:
    # CTCP
    if not re.match(r'^\x01ACTION\b', text):
      # A CTCP other than ACTION, do nothing.
      return string
    text = re.sub(r'^\x01ACTION |\x01$', '', text)
    prefix = 'action_'
  else:
    # Regular PRIVMSG
    prefix = 'privmsg_'
  for nick,servers in _nicks:
    if servers and not (info['server'] in servers):
      continue
    nick_re = (r'^%s' % re.escape(nick))
    if not re.match(nick_re, info['nick']):
      continue
    debug('%s is a valid server.' % info['server'])
    debug('%s matches %s' % (nick_re, nick))
    debug(string)
    for bot in _bots:
      result = reformat(string, info, bot, prefix, text)
      if result:
        return result
  return string

def reformat(string, info, bot, prefix, text):
  channel = info['channel']
  nick = info['nick']
  result = []
  parts = bot[prefix + 'extract_parts'](text)
  if not parts:
    # could not extract relayed nick and text, so do nothing.
    return result
  rnick, rtext = parts
  debug("nick: %s, text: %s" % (rnick, rtext))
  if prefix + 'quit' in bot and re.match(bot[prefix + 'quit'], rtext):
    # QUIT might remove the nick from unrelated rooms if it's duplicated
    # result.append(":%s!~%s@%s.%s QUIT :%s" % \
    #     (rnick, rnick, nick, SCRIPT_NAME, rtext))
    result.append(":%s!~%s@%s.%s PART %s :%s" % \
        (rnick, rnick, nick, SCRIPT_NAME, channel, rtext))
  elif prefix + 'part' in bot and re.match(bot[prefix + 'part'], rtext):
    result.append(":%s!~%s@%s.%s PART %s :%s" % \
        (rnick, rnick, nick, SCRIPT_NAME, channel, rtext))
  elif prefix + 'join' in bot and re.match(bot[prefix + 'join'], rtext):
    result.append(":%s!~%s@%s.%s JOIN %s" % \
        (rnick, rnick, nick, SCRIPT_NAME, channel))
  else:
    if prefix == 'action_':
      add_nick(info, bot, rnick, rtext, result)
      result.append(":%s!~%s@%s.%s PRIVMSG %s :\x01ACTION %s\x01" % \
          (rnick, rnick, nick, SCRIPT_NAME, channel, rtext))
    else:
      add_nick(info, bot, rnick, rtext, result)
      result.append(":%s!~%s@%s.%s PRIVMSG %s :%s" % \
          (rnick, rnick, nick, SCRIPT_NAME, channel, rtext))
  debug('result: %s' % result)
  return "\n".join(result)

# ================================[ main ]===============================
if __name__ == "__main__":
  if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, \
      SCRIPT_LICENSE, SCRIPT_DESC, '', ''):
    version = weechat.info_get("version_number", "") or 0

    if int(version) >= 0x00030600:
      # init options from your script
      init_options()
      # create a hook for your options
      weechat.hook_config( \
          'plugins.var.python.' + SCRIPT_NAME + '.*', 'sync_with_options', '' )
      hook = weechat.hook_modifier("irc_in_privmsg", "seamless_cb", "")
    else:
      weechat.prnt("","%s%s %s" % \
          (weechat.prefix("error"), SCRIPT_NAME, \
          ": needs version 0.3.6 or higher"))
      weechat.command("","/wait 1ms /python unload %s" % SCRIPT_NAME)
