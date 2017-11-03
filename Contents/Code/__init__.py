# -*- coding: utf-8 -*-
BASE_URL = 'http://music.naver.com'

ARTIST_SEARCH_URL = BASE_URL + '/search/search.nhn?query=%s&target=artist'
ARTIST_INFO_URL = BASE_URL + '/artist/intro.nhn?artistId=%s'
ARTIST_ALBUM_URL = BASE_URL + '/artist/album.nhn?artistId=%s&isRegular=Y&sorting=popular'
ARTIST_PHOTO_URL = BASE_URL + '/artist/photo.nhn?artistId=%s'
ARTIST_PHOTO_LIST_URL = BASE_URL + '/artist/photoListJson.nhn?artistId=%s'

ALBUM_SEARCH_URL = BASE_URL + '/search/search.nhn?query=%s&target=album'
ALBUM_INFO_URL = BASE_URL + '/album/index.nhn?albumId=%s'

VARIOUS_ARTISTS_POSTER = 'http://userserve-ak.last.fm/serve/252/46209667.png'

RE_ARTIST_ID = Regex('artistId=(\d+)')
RE_ALBUM_ID = Regex('albumId=(\d+)')

def Start():
  HTTP.CacheTime = CACHE_1WEEK

########################################################################  
class NaverMusicAgent(Agent.Artist):
  name = 'Naver Music'
  languages = [Locale.Language.Korean, Locale.Language.English]
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang, manual):

    # Handle a couple of edge cases where artist search will give bad results.
    if media.artist == '[Unknown Artist]': 
      return
    if media.artist == 'Various Artists':
      results.Append(MetadataSearchResult(id = 'Various%20Artists', name= 'Various Artists', thumb = VARIOUS_ARTISTS_POSTER, lang  = lang, score = 100))
      return
    
    # Search for artist.
    Log('Artist search: ' + media.artist)
    if manual:
      Log('Running custom search...')

    artists = self.score_artists(media, lang, SearchArtists(media.artist))
    Log('Found ' + str(len(artists)) + ' artists...')

    for artist in artists:
      results.Append( MetadataSearchResult(id=artist['id'], name=artist['name'], lang=artist['lang'], score=artist['score']) )

  def score_artists(self, media, lang, artists):
    for i, artist in enumerate(artists):
      id = artist['id']
      name = artist['name']

      score = 80 if i == 0 else 50

      artists[i]['score'] = score
      artists[i]['lang'] = lang
      Log.Debug('id: %s name: %s score: %d lang: %s' % (id, name, score, lang))
    return artists

  def update(self, metadata, media, lang):
    url = ARTIST_INFO_URL % metadata.id
    try: 
      html = HTML.ElementFromURL(url)
    except:
      raise Ex.MediaExpired

    metadata.title = html.xpath('//h2')[0].text
    #metadata.year = html.xpath('//dt[@class="birth"]/following-sibling::dd')[0].text
    node = html.xpath('//p[@class="dsc full"]')
    if node:
      metadata.summary = String.DecodeHTMLEntities(String.StripTags(node[0].text).strip())

    # poster
    if metadata.title == 'Various Artists':
      metadata.posters[VARIOUS_ARTISTS_POSTER] = Proxy.Media(HTTP.Request(VARIOUS_ARTISTS_POSTER))
    else:
      img_url = html.xpath('//span[@class="thmb"]//img')[0].get('src')
      metadata.posters[img_url] = Proxy.Media(HTTP.Request(img_url))

    # genre
    metadata.genres.clear()
    try:
      for genre in html.xpath('//strong[@class="genre"])[0].text.split(','):
        metadata.genres.add(genre.strip())
    except:
      pass

    # artwork
    if Prefs['artwork']:
      url = ARTIST_PHOTO_URL % metadata.id
      try: 
        data = JSON.ObjectFromURL(url)
      except:
        raise Ex.MediaExpired

      for i, pic in enumerate(data['photoList']):
        metadata.art[pic['original']] = Proxy.Preview(HTTP.Request(pic['thumbnail']), sort_order=(i+1))

########################################################################  
class NaverMusicAlbumAgent(Agent.Album):
  name = 'Naver Music'
  languages = [Locale.Language.Korean, Locale.Language.English]
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang, manual):    
    if media.parent_metadata.id is None:
      return

    # Search for album.
    Log('Album search: ' + media.title)
    if manual:
      Log('Running custom search...')

    albums = self.score_albums(media, lang, SearchAlbums(media.parent_metadata.title, media.title))
    Log('Found ' + str(len(albums)) + ' albums...')

    for album in albums:
      results.Append( MetadataSearchResult(id=album['id'], name=album['name'], lang=album['lang'], score=album['score']) )

    if len(albums) > 0:
      return

    Log('2nd try...')
    albums = self.score_albums(media, lang, GetAlbumsByArtist(media.parent_metadata.id), legacy=True)
    Log('Found ' + str(len(albums)) + ' albums...')

    for album in albums:
      results.Append( MetadataSearchResult(id=album['id'], name=album['name'], lang=album['lang'], score=album['score']) )

  def score_albums(self, media, lang, albums, legacy=False):

    for i, album in enumerate(albums):
      id = album['id']
      name = album['name']

      if legacy:
        score = 80 if name in media.title else 50
      else:
        score = 80 if i == 0 else 50

      albums[i]['score'] = score
      albums[i]['lang'] = lang
      Log.Debug('id: %s name: %s score: %d lang: %s' % (id, name, score, lang))
    return albums

  def update(self, metadata, media, lang):
    Log.Debug('query album: '+metadata.id)
    url = ALBUM_INFO_URL % metadata.id
    try: 
      html = HTML.ElementFromURL(url)
    except:
      raise Ex.MediaExpired

    metadata.title = html.xpath('//h2')[0].text

    date_s = html.xpath('//dt[@class="date"]/following-sibling::dd')[0].text
    try:
      metadata.originally_available_at = Datetime.ParseDate(date_s)
    except:
      pass

    try:
      metadata.summary = String.DecodeHTMLEntities(String.StripTags(html.xpath('//p[contains(@class, "intro_desc")]')[0].text).strip())
    except:
      pass

    # poster
    img_url = html.xpath('//meta[@property="og:image"]')[0].get('content')
    metadata.posters[img_url] = Proxy.Media(HTTP.Request(img_url))

    # genre
    metadata.genres.clear()
    for genre in html.xpath('//dt[@class="type"]/following-sibling::dd')[0].text.split(','):
      metadata.genres.add(genre.strip())

########################################################################  
def SearchArtists(artist):
  url = ARTIST_SEARCH_URL % String.Quote(artist.encode('utf-8'))
  try: 
    html = HTML.ElementFromURL(url)
  except:
    raise Ex.MediaExpired

  artists = []
  for node in html.xpath('//dt/a'):
    id = RE_ARTIST_ID.search(node.get('href')).group(1)
    artists.append({'id':id, 'name':node.get('title')})
  return artists

def SearchAlbums(artist, album):
  if artist in album:
    q_str = album
  else:
    q_str = album+' '+artist

  url = ALBUM_SEARCH_URL % String.Quote(q_str.encode('utf-8'))
  try: 
    html = HTML.ElementFromURL(url)
  except:
    raise Ex.MediaExpired

  album = []
  for node in html.xpath('//dt/a'):
    id = RE_ALBUM_ID.search(node.get('href')).group(1)
    album.append({'id':id, 'name':node.get('title')})
  return album

def GetAlbumsByArtist(artist, albums=[]):
  url = ARTIST_ALBUM_URL % artist
  try: 
    html = HTML.ElementFromURL(url)
  except:
    raise Ex.MediaExpired

  album = []
  for node in html.xpath('//a[contains(@class, "NPI=a:name")]'):
    id = RE_ALBUM_ID.search(node.get('href')).group(1)
    album.append({'id':id, 'name':node.get('title')})
  return album
