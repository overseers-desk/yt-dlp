from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    int_or_none,
    js_to_json,
    parse_iso8601,
    str_or_none,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class DeviantArtIE(InfoExtractor):
    IE_NAME = 'deviantart'
    _VALID_URL = r'https?://(?:www\.)?deviantart\.com/(?P<uploader>[\w-]+)/art/(?P<display_id>[^/?#]+-(?P<id>\d+))'
    _TESTS = [{
        'url': 'https://www.deviantart.com/dailydreamsaii/art/Bella-02-%7C-Corsair-%7C-S02E41-1335972479',
        'info_dict': {
            'id': '1335972479',
            'ext': 'mp4',
            'title': 'Bella #02 | Corsair | S02E41',
            'display_id': 'Bella-02-%7C-Corsair-%7C-S02E41-1335972479',
            'description': 'md5:7b0998105001041a39848a00b628032e',
            'duration': 20,
            'uploader': 'dailydreamsaii',
            'uploader_id': '111667222',
            'timestamp': 1781995681,
            'upload_date': '20260620',
            'thumbnail': r're:https?://images-wixmp-.+',
            'tags': list,
            'view_count': int,
            'like_count': int,
            'comment_count': int,
        },
    }]

    def _real_extract(self, url):
        video_id, display_id, uploader = self._match_valid_url(url).group('id', 'display_id', 'uploader')
        webpage = self._download_webpage(url, video_id)

        state = self._parse_json(self._search_json(
            r'window\.__INITIAL_STATE__\s*=\s*JSON\.parse\(', webpage, 'initial state', video_id,
            contains_pattern=r'"(?s:.+)"', transform_source=js_to_json), video_id)
        entities = traverse_obj(state, ('@@entities', {dict})) or {}
        deviation = traverse_obj(entities, ('deviation', video_id, {dict}))
        if not deviation:
            raise ExtractorError('Unable to find deviation data')
        if not deviation.get('isVideo'):
            raise ExtractorError('This deviation is not a video', expected=True)

        formats = traverse_obj(deviation, ('media', 'types', lambda _, v: v['t'] == 'video' and url_or_none(v['b']), {
            'url': 'b',
            'format_id': ('q', {str}),
            'width': ('w', {int_or_none}),
            'height': ('h', {int_or_none}),
            'filesize': ('f', {int_or_none}),
        }))

        thumbnails = []
        base_uri = traverse_obj(deviation, ('media', 'baseUri', {url_or_none}))
        pretty_name = traverse_obj(deviation, ('media', 'prettyName', {str}))
        for thumb in traverse_obj(deviation, ('media', 'types', lambda _, v: base_uri and v['t'] != 'video')):
            path = thumb.get('c')
            if path and not pretty_name:
                continue
            thumbnails.append({
                'id': thumb.get('t'),
                'url': base_uri + path.replace('<prettyName>', pretty_name) if path else base_uri,
                **traverse_obj(thumb, {
                    'width': ('w', {int_or_none}),
                    'height': ('h', {int_or_none}),
                    'filesize': ('f', {int_or_none}),
                }),
            })

        return {
            'id': video_id,
            'display_id': display_id,
            'formats': formats,
            'thumbnails': thumbnails,
            'uploader': traverse_obj(
                entities, ('user', str(deviation.get('author')), 'username', {str})) or uploader,
            'uploader_id': str_or_none(deviation.get('author')),
            'duration': traverse_obj(deviation, (
                'media', 'types', lambda _, v: v['t'] == 'video', 'd', {int_or_none}, any)),
            'age_limit': 18 if deviation.get('isMature') else None,
            **traverse_obj(deviation, {
                'title': ('title', {str}),
                'timestamp': ('publishedTime', {parse_iso8601}),
                'view_count': ('stats', 'views', {int_or_none}),
                'like_count': ('stats', 'favourites', {int_or_none}),
                'comment_count': ('stats', 'comments', {int_or_none}),
            }),
            **traverse_obj(entities, ('deviationExtended', video_id, {
                'description': ('descriptionText', 'excerpt', {str}),
                'tags': ('tags', ..., 'name', {str}, all),
            })),
        }
