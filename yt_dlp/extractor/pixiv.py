from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    int_or_none,
    parse_iso8601,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class PixivIE(InfoExtractor):
    IE_NAME = 'pixiv'
    IE_DESC = 'pixiv ugoira (animated artwork)'
    _VALID_URL = r'https?://(?:www\.)?pixiv\.net/(?:[a-z]{2}/)?artworks/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://www.pixiv.net/en/artworks/149523335',
        'info_dict': {
            'id': '149523335',
            'ext': 'mp4',
            'title': "Chelizi's Earthquake",
            'description': "Chile's national holidays are coming up! \U0001f377\U0001f1e8\U0001f1f1\U0001f61d\n---\n#diives #xingzuotemple",
            'uploader': 'Diives',
            'uploader_id': '4523203',
            'timestamp': 1789075920,
            'upload_date': '20260910',
            'duration': 1.72,
            'age_limit': 0,
            'tags': list,
            'view_count': int,
            'like_count': int,
            'comment_count': int,
        },
        'params': {'skip_download': 'The whole zip archive is needed to build the video'},
    }, {
        'url': 'https://www.pixiv.net/artworks/148975533',
        'only_matching': True,
    }]

    def _call_api(self, path, artwork_id, note, fatal=True):
        response = self._download_json(
            f'https://www.pixiv.net/ajax/{path}', artwork_id, note, fatal=fatal,
            headers={'Referer': 'https://www.pixiv.net/'}, expected_status=404)
        if traverse_obj(response, 'error'):
            return None
        return traverse_obj(response, 'body')

    def _real_extract(self, url):
        artwork_id = self._match_id(url)
        illust = self._call_api(f'illust/{artwork_id}', artwork_id, 'Downloading artwork metadata')
        if not illust:
            self.raise_login_required('Unable to read this artwork without an account')
        if illust.get('illustType') != 2:
            raise ExtractorError('This artwork is a still image, not an ugoira', expected=True)

        ugoira = self._call_api(
            f'illust/{artwork_id}/ugoira_meta', artwork_id, 'Downloading ugoira metadata', fatal=False)
        frames = traverse_obj(ugoira, ('frames', lambda _, v: v['file'] and v['delay'] is not None))
        if not frames:
            self.raise_login_required('Unable to read this ugoira without an account')

        formats = []
        for format_id, key in (('preview', 'src'), ('original', 'originalSrc')):
            zip_url = traverse_obj(ugoira, (key, {url_or_none}))
            if not zip_url:
                continue
            formats.append({
                'url': zip_url,
                'format_id': format_id,
                'ext': 'mp4',
                'protocol': 'ugoira',
                'fragments': [{
                    'path': frame['file'],
                    'duration': frame['delay'] / 1000,
                } for frame in frames],
                'http_headers': {'Referer': 'https://www.pixiv.net/'},
                'quality': 1 if key == 'originalSrc' else 0,
            })

        return {
            'id': artwork_id,
            'formats': formats,
            'duration': sum(frame['delay'] for frame in frames) / 1000,
            'age_limit': 18 if illust.get('xRestrict') else 0,
            **traverse_obj(illust, {
                'title': ('title', {str}),
                'description': ('description', {clean_html}),
                'uploader': ('userName', {str}),
                'uploader_id': ('userId', {str}),
                'timestamp': ('uploadDate', {parse_iso8601}),
                'view_count': ('viewCount', {int_or_none}),
                'like_count': ('likeCount', {int_or_none}),
                'comment_count': ('commentCount', {int_or_none}),
                'tags': ('tags', 'tags', ..., 'tag', {str}, all),
            }),
        }
