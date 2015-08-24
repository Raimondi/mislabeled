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
SCRIPT_DESC     = "Make it like relay/bridge bots are not even there. Support for ijchain, gitterircbot."

OPTIONS         = {
    'items'   : ('',
      'bot1:server1,#chan1,#chan2:server2,* bot2:server1,#chan1,#chan2:server2,#chan3'),
    'aliases' : ('', 'bot1:regex_for_alternate_nicks [bot2:regex_for_alternate_nicks]'),
                  }
DEBUG = False
label_marker = '<seamless_marker:'
label_marker_re = r'(%s)([^>]*)(>)' % label_marker

# ===================[ weechat options & description ]===================
def init_options():
  for option,value in OPTIONS.items():
    if not weechat.config_is_set_plugin(option):
      weechat.config_set_plugin(option, value[0])
      toggle_refresh(None, 'plugins.var.python.' + SCRIPT_NAME + '.' + option, \
          value[0])
    else:
      toggle_refresh(None, 'plugins.var.python.' + SCRIPT_NAME + '.' + option, \
          weechat.config_get_plugin(option))
    weechat.config_set_desc_plugin(option, \
        '%s (default: "%s")' % (value[1], value[0]))

def debug(str):
  if DEBUG:
    weechat.prnt("", '%s: %s' % (SCRIPT_NAME, str))

def update_aliases(aliases):
  global seamless_aliases
  alist = re.split(r'[: ]+', aliases)
  seamless_aliases = dict(zip(alist[0::1], alist[1::2]))

def update_items(items):
  '''
  [{'bot': {bot},
    'servers': [[server, [channels]],...]
    },...]
  '''
  global seamless_items
  seamless_items = []
  for text in items.split():
    bot_name, text = text.split(':', 1)
    if not bot_name in bots:
      continue
    entry = {'bot': bots[bot_name]}
    servers = [[x.split(',', 1)[0], x.split(',')[1:]] for x in text.split(':')]
    entry['servers'] = servers
    entry['all_channels'] = len(servers) == 1 and servers[0] == '*'
    seamless_items.append(entry)

def toggle_refresh(pointer, name, value):
  global OPTIONS
  # get optionname
  option = name[len('plugins.var.python.' + SCRIPT_NAME + '.'):]
  # save new value
  OPTIONS[option] = value
  if option == 'aliases':
    update_aliases(value)
  if option == 'items':
    update_items(value)
  return weechat.WEECHAT_RC_OK

bots = {}

# ijchain
robot = {}
robot['name'] = 'ijchain'
robot['nick'] = r'^ijchain\d*$'
robot['act_split_text'] = lambda x: re.match(r'^(\S+)\s(.*)', x).groups()
robot['act_join'] = r'^has become available$'
robot['act_quit'] = r'^has left$'
robot['priv_split_text'] = lambda x: re.match(r'^<([^> ]+)>\s(.*)', x).groups()
bots['ijchain'] = robot

# gitterircbot https://github.com/finnp/gitter-irc-bot
robot = {}
robot['name'] = 'gitterbot'
robot['nick'] = r'^gitterircbot[0-9_]*$'
robot['priv_split_text'] = \
    lambda x: re.match(r'^[(`]([^>` ]+)[)`]\s(.*)', x).groups()

bots['gitterbot'] = robot

def seamless_cb(data, modifier, modifier_data, string):
  dict_in = { "message": string }
  message_ht = weechat.info_get_hashtable("irc_message_parse", dict_in)
  message_ht['server'] = modifier_data
  channel = message_ht['channel']
  for item in seamless_items:
    do_it = False
    bot = item['bot']
    for server, channels in item['servers']:
      if server == modifier_data and \
          (item['all_channels'] or channel in channels):
        debug('Match with server "%s" and channel "%s"' % (server, channel))
        do_it = True
        break
    if not do_it:
      continue
    nick = message_ht['nick']
    nick_pat = re.compile(seamless_aliases.get(item['bot']['name'], '^\x00$'))
    nick_matched = re.match(nick_pat, nick)
    if re.match(bot['nick'], nick) or re.match(nick_pat, nick):
      return transform(string, message_ht, bot)
  return string

def transform(string, ht, bot):
  debug(string)
  host = ht['host']
  arguments = ht['arguments']
  channel = ht['channel']
  text = ht.get('text', arguments.split(' :', 1)[1])
  buf_p = weechat.buffer_search('==', \
      'irc.' + ht['server'] + '.' + ht['channel'])
  if not buf_p:
    debug('no buffer for %s' % \
        'irc.' + ht['server'] + '.' + ht['channel'])
    return string
  if re.match(r'^\x01.*\x01', text):
    # CTCP
    debug('action: %s' % text)
    if not re.match(r'^\x01ACTION\b', text):
      # A CTCP other than ACTION, do nothing.
      return string
    text = re.sub(r'^\x01ACTION |\x01$', '', text)
    rnick, rtext = bot['act_split_text'](text)
    debug("nick: %s, text: %s" % (rnick, rtext))
    if 'act_quit' in bot and re.match(bot['act_quit'], rtext):
      string = ":%s!~%s@%s QUIT :%s" % \
          (rnick, rnick, ht['nick'], rtext)
    elif 'act_part' in bot and re.match(bot['act_part'], rtext):
      string = ":%s!~%s@%s PART %s :%s" % \
          (rnick, rnick, ht['nick'], channel, rtext)
    elif 'act_join' in bot and re.match(bot['act_join'], rtext):
      string = ":%s!~%s@%s JOIN %s" % \
          (rnick, rnick, ht['nick'], channel)
    else:
      string = ":%s!~%s@%s PRIVMSG %s :\x01ACTION %s\x01" % \
          (rnick, rnick, ht['nick'], channel, rtext)
  else:
    # Regular PRIVMSG
    debug('privmsg: %s' % text)
    rnick, rtext = bot['priv_split_text'](text)
    debug("nick: %s, text: %s" % (rnick, rtext))
    if 'priv_quit' in bot and re.match(bot['priv_quit'], rtext):
      string = ":%s!~%s@%s QUIT :%s" % \
          (rnick, rnick, ht['nick'], rtext)
    elif 'priv_part' in bot and re.match(bot['priv_part'], rtext):
      string = ":%s!~%s@%s PART %s :%s" % \
          (rnick, rnick, ht['nick'], channel, rtext)
    elif 'priv_join' in bot and re.match(bot['priv_join'], rtext):
      string = ":%s!~%s@%s JOIN %s" % \
          (rnick, rnick, ht['nick'], channel)
    else:
      string = ":%s!~%s@%s PRIVMSG %s :%s" % \
          (rnick, rnick, ht['nick'], channel, rtext)
  debug('string: %s' % string)
  return string

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
          'plugins.var.python.' + SCRIPT_NAME + '.*', 'toggle_refresh', '' )
      hook = weechat.hook_modifier("irc_in_privmsg", "seamless_cb", "")
    else:
      weechat.prnt("","%s%s %s" % \
          (weechat.prefix("error"), SCRIPT_NAME, \
          ": needs version 0.3.6 or higher"))
      weechat.command("","/wait 1ms /python unload %s" % SCRIPT_NAME)

