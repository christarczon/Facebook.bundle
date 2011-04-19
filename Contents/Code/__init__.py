import httplib
import dateutil.parser
import datetime
import locale
#from babel.dates import format_datetime

PLUGIN_PREFIX      = '/photos/facebook'

FILE_DEFAULT_ART   = 'art-default.jpg'
FILE_DEFAULT_ICON  = 'icon-default.png'
ICON_HOME          = 'home.png'
ICON_ALBUMS        = 'photos.png'
ICON_TAGGED        = 'editprofile.png'
ICON_FRIENDS       = 'list.png'
ICON_FRIEND        = 'genericfriendicon.png'
ICON_WALLPOST      = 'wallpost.png'
ICON_PRIVACY       = 'privacy.png'
ICON_PREFS         = 'note.png'

AUTH_HOST          = 'dcstewieg.no-ip.org'
AUTH_PATH          = '/plex-facebook/accessToken.php?code='
API_HOST           = 'graph.facebook.com'

TEXT_APP_NAME      = L('appName')
TEXT_HOME          = L('home')
TEXT_YOUR_ALBUMS   = L('yourPhotos')
TEXT_YOUR_TAGGED   = L('yourTagged')
TEXT_FRIEND_ALBUMS = L('friendPhotos')
TEXT_FRIEND_TAGGED = L('friendTagged')
TEXT_NO_TITLE      = L('noTitle')
TEXT_FRIENDS       = L('friends')
TEXT_NO_PHOTOS     = L('noPhotos')
TEXT_NO_ALBUMS     = L('noAlbums')
TEXT_ERROR_UPDATING_STATUS = L('errorUpdatingStatus')

PREF_STATUS        = 'showStatusMessage'
PREF_THUMB_QUALITY = 'thumbQuality'
PREF_IMAGE_LIMIT   = 'imageLimit'
PREF_ALBUM_LIMIT   = 'albumLimit'
PREF_RECENT_LIMIT  = 'recentLimit'

IMAGE_INDEXES = { 'Full':0, '180':1, '130':2, '75':3 }

#SKINS = {'MediaStream':{'titleWidth':40,'messageWidth':60,'summary':True},'Refocus':{'titleWidth':30,'messageWidth':50,'summary':False}}

########## SET LANGUAGE HERE ############
#locale.setlocale(locale.LC_ALL, 'fr_FR')

def Start():
  Plugin.AddViewGroup('InfoList', viewMode='InfoList', mediaType='items')
  Plugin.AddViewGroup('List', viewMode='List', mediaType='items')
  MediaContainer.title1 = TEXT_APP_NAME
  MediaContainer.art = R(FILE_DEFAULT_ART)
  MediaContainer.viewGroup = 'InfoList'
  
  #Log(Locale.CurrentLocale)


@handler(PLUGIN_PREFIX, TEXT_APP_NAME)
def Index():
  dir = MediaContainer(mediaType='photos', viewGroup='List', replaceParent=True)
  
  if Dict['AccessToken'] == None:
    dir.Append(Function(InputDirectoryItem(GetAccessToken, L("connectFirstTime"), L("accessCodeInstructions"))))
  else:
    profileJson = FacebookGraphApi('me')
    if 'error' in profileJson:
      dir.Append(Function(InputDirectoryItem(GetAccessToken, L("connectAfterError"), L("accessCodeInstructions"))))
      dir.Append(Function(DirectoryItem(Nothing, profileJson['error']['type'] + ': ' + profileJson['error']['message'])))
    else:
      Dict['Timezone'] = profileJson['timezone'] # Facebook provides the timezone for the profile
      dir = MediaContainer(title2=profileJson['name'], mediaType='photos', viewGroup='List', replaceParent=True)
      
      dir.Append(Function(DirectoryItem(NewsFeed, TEXT_HOME, thumb=R(ICON_HOME))))
      dir.Append(Function(DirectoryItem(Albums, TEXT_YOUR_ALBUMS, thumb=R(ICON_ALBUMS))))
      dir.Append(Function(DirectoryItem(Pictures, TEXT_YOUR_TAGGED, thumb=R(ICON_TAGGED))))  
      dir.Append(Function(DirectoryItem(Friends, TEXT_FRIENDS, thumb=R(ICON_FRIENDS))))
      
      status = GetStatus()
      if status == None:
        status = L("setStatus")
      else:
        status = L("status") + ": " + status
      dir.Append(Function(InputDirectoryItem(SetStatus, status, L("setStatus"), thumb=R(ICON_WALLPOST))))
      
      dir.Append(Function(InputDirectoryItem(GetAccessToken, L("changeConnection"), L("accessCodeInstructions"), thumb=R(ICON_PRIVACY))))
      dir.Append(PrefsItem(title=L("preferences"), thumb=R(ICON_PREFS)))
  
  return dir


def Nothing(sender):
  return Index()


def GetStatus(id='me'):
  statusJson = FacebookGraphApi(id + '/statuses', '&limit=1')
  if len(statusJson['data']) == 0:
    return None
  else:
    return statusJson['data'][0]['message']


def SetStatus(sender, query=None):
  if query != None:
    responseJson = FacebookGraphApi('me/feed', params='&message=' + query, method='POST')
    if 'error' in responseJson:
      return MessageContainer(TEXT_ERROR_UPDATING_STATUS, responseJson['error']['message'])
    return Index()
  return None


def NewsFeed(sender, paging=None, pageTitle=None):
  if pageTitle == None:
    pageTitle = sender.itemTitle
  dir = MediaContainer(title2=pageTitle)
  
  if paging == None:
    paging = '&limit=' + Prefs[PREF_RECENT_LIMIT]
  
  recent = FacebookGraphApi('me/home', params=paging)
  
  for item in recent['data']:
    date = FormatDate(item['created_time'])
    who = item['from']['name']
    prefix = who + ' - '
    if item['type'] == 'photo':
      if 'message' in item or 'properties' in item and 'object_id' in item:
        photoJson = FacebookGraphApi(item['object_id'])
        if 'id' in photoJson:
          photoItem = FBPhotoItem(photoJson)
          if 'message' in item:
            photoItem.title = prefix + item['message'].replace('\n', ' ')
          elif 'caption' in item:
            photoItem.title = prefix + item['caption']
          elif 'name' in item:
            photoItem.title = prefix + item['name']
          photoItem.summary = CreateCommentSummary(item)
          dir.Append(photoItem)
      elif 'name' in item:
        dir.Append(Function(DirectoryItem(Albums, prefix + item['name'], thumb=R(ICON_ALBUMS), subtitle=date, summary=CreateCommentSummary(item)), id=item['from']['id'], pageTitle=who))
    elif item['type'] == 'status':
      if Prefs[PREF_STATUS] != 'Summary':
        title = prefix + item['message'].replace('\n', ' ')
      else:
        title = who
      
      summary = None
      if Prefs[PREF_STATUS] != 'Title':
        summary = item['message']
      comments = CreateCommentSummary(item)
      if comments != None:
        if summary == None:
          summary = comments
        else:
          summary += '\n\n' + comments
      dir.Append(Function(DirectoryItem(StatusMessage, title, thumb=R(ICON_WALLPOST), subtitle=date, summary=summary), who=who, message=item['message']))
    #elif item['type'] == 'video':
    #  dir.Append(VideoItem(item['source'], 'VID ' + item['name']))
  if len(recent['data']) == int(Prefs[PREF_RECENT_LIMIT]):
    pagingQuery = recent['paging']['next']
    i = pagingQuery.find('&limit')
    pagingQuery = pagingQuery[i:]
    dir.Append(Function(DirectoryItem(NewsFeed, L('nextPage'), thumb=R(ICON_HOME)), paging=pagingQuery, pageTitle=pageTitle))
  
  return dir


def StatusMessage(sender, who='', message=''):
  MAX_LENGTH = 50
  withLineBreaks = ''
  charsAddedToLine = 0
  
  while True:
    spaceIndex = message.find(' ')
    newlineIndex = message.find('\n')
    skipCharsAtEnd = 1
    
    if newlineIndex > -1 and newlineIndex < spaceIndex:
      index = newlineIndex + 1
      skipCharsAtEnd = 0
    elif spaceIndex == -1:
      index = len(message)
    else:
      index = spaceIndex
      
    if charsAddedToLine + index > MAX_LENGTH:
      withLineBreaks += '\n'
      charsAddedToLine = 0
    elif charsAddedToLine > 0:
      withLineBreaks += ' '
      charsAddedToLine += 1
      
    withLineBreaks += message[0:index]
    if skipCharsAtEnd == 0:
      charsAddedToLine = 0
    else:
      charsAddedToLine += index
    
    if len(message) > index + skipCharsAtEnd + 1:
      message = message[index + skipCharsAtEnd:]
    else:
      break
  
  return MessageContainer(who, withLineBreaks)


def Albums(sender, id='me', paging=None, pageTitle=None):
  if pageTitle == None:
    pageTitle = sender.itemTitle
  dir = MediaContainer(title2=pageTitle)
  
  if paging == None:
    paging = '&limit=' + Prefs[PREF_ALBUM_LIMIT]
  
  albums = FacebookGraphApi(id + '/albums', params=paging)
  
  if len(albums['data']) == 0:
    return MessageContainer(pageTitle, TEXT_NO_ALBUMS)
  else:
    for album in albums['data']:
      date = FormatDate(album['created_time'])
      dir.Append(Function(DirectoryItem(Pictures, album['name'], subtitle=date), id=album['id']))
    if len(albums['data']) == int(Prefs[PREF_ALBUM_LIMIT]):
      pagingQuery = albums['paging']['next']
      i = pagingQuery.find('&limit')
      pagingQuery = pagingQuery[i:]
      dir.Append(Function(DirectoryItem(Albums, L('nextPage'), thumb=R(ICON_ALBUMS)), id=id, paging=pagingQuery, pageTitle=pageTitle))
  
  return dir


def Pictures(sender, id='me', paging=None, albumTitle=None):
  if albumTitle == None:
    albumTitle = sender.itemTitle
  dir = MediaContainer(title2=albumTitle)
  
  if paging == None:
    paging = '&limit=' + Prefs[PREF_IMAGE_LIMIT]
  
  photos = FacebookGraphApi(id + '/photos', params=paging)
  
  if len(photos['data']) == 0:
    return MessageContainer(albumTitle, TEXT_NO_PHOTOS)
  else:
    for photo in photos['data']:
      dir.Append(FBPhotoItem(photo))
    if len(photos['data']) == int(Prefs[PREF_IMAGE_LIMIT]):
      pagingQuery = photos['paging']['next']
      i = pagingQuery.find('&limit')
      pagingQuery = pagingQuery[i:]
      dir.Append(Function(DirectoryItem(Pictures, L('nextPage'), thumb=R(ICON_ALBUMS)), id=id, paging=pagingQuery, albumTitle=albumTitle))
  
  return dir


def Friends(sender):
  dir = MediaContainer(title2=sender.itemTitle)
  
  friends = FacebookGraphApi('me/friends')
  for friend in friends['data']:
    dir.Append(Function(DirectoryItem(Friend, friend['name'], thumb=R(ICON_FRIEND)), id=friend['id']))
  
  dir.Sort('title')
  
  return dir


def Friend(sender, id=None):
  dir = MediaContainer(title2=sender.itemTitle)
  
  dir.Append(Function(DirectoryItem(Albums, TEXT_FRIEND_ALBUMS), id=id))
  dir.Append(Function(DirectoryItem(Pictures, TEXT_FRIEND_TAGGED), id=id))
  
  return dir


def CreateCommentSummary(commentJsonParent):
  comments = None
  
  if 'comments' in commentJsonParent and 'data' in commentJsonParent['comments']:
    comments = ''
    first = True
    for comment in commentJsonParent['comments']['data']:
      if first:
        first = False
      else:
        comments += '\n\n'
      
      if comment['from']:
        comments += comment['from']['name'] + '\n'
      comments += '%s\n"%s"' % (FormatDate(comment['created_time'], showDayOfWeek=False), comment['message'])
    
  return comments
    

def FBPhotoItem(apiObj):
  url = apiObj['images'][0]['source']
  if 'name' in apiObj:
    title = apiObj['name']
  else:
    title = TEXT_NO_TITLE
  
  # Picture is available in hi-res if first image doesn't match source
  if apiObj['height'] == apiObj['images'][0]['height']:
    thumbOffset = 0
  else:
    thumbOffset = 1
  
  # Find thumb URL based on user preference
  if Prefs[PREF_THUMB_QUALITY] == 'Full Hi-Res':
    thumbUrl = url
  else:
    imagesIndex = IMAGE_INDEXES[Prefs[PREF_THUMB_QUALITY]] + thumbOffset
    if imagesIndex < len(apiObj['images']):
      thumbUrl = apiObj['images'][imagesIndex]['source']
    else:
      thumbUrl = apiObj['picture'] # Shouldn't happen, fallback in case Facebook changes things
  
  subtitle = FormatDate(apiObj['created_time'])
  
  return PhotoItem(url, title, subtitle=subtitle, thumb=thumbUrl, summary=CreateCommentSummary(apiObj))


def FacebookGraphApi(path, params='', method='GET'):
  conn = httplib.HTTPSConnection(API_HOST)
  fullPath = '/' + path + '?access_token=' + Dict['AccessToken'] + params
  Log(fullPath)
  conn.putrequest(method, fullPath)
  conn.endheaders()
  response = conn.getresponse()
  content = response.read()
  conn.close()
  json = JSON.ObjectFromString(content)
  if 'error' in json:
    json['data'] = [ ]
  return json;


def FormatDate(isoDate, showDayOfWeek=True):
  date = dateutil.parser.parse(isoDate) + datetime.timedelta(hours=Dict['Timezone'])
  if showDayOfWeek:
    return date.strftime('%A, %B %e, %Y, %l:%M%p')
  else:
    return date.strftime('%B %e, %Y, %l:%M%p')


def GetAccessToken(sender, query=None):
  
  if query != None:
    conn = httplib.HTTPSConnection(AUTH_HOST)
    conn.putrequest('GET', AUTH_PATH + query)
    conn.endheaders()
    response = conn.getresponse()
    token = response.read()
    conn.close()
    
    if token == '':
      return MessageContainer(L('invalidAccessCode'), L('accessCodeInstructions'))
    else:
      Dict['AccessToken'] = token
    
    # Old non-SSL method
    #response = HTTP.Request("http://dcstewieg.no-ip.org/plex-facebook/accessToken.php?code=" + query)
    #Dict['AccessToken'] = response
  
  return Index()