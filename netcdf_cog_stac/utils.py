import os
import urllib.parse


def path_or_url_join(*strings: str):
    strings_head = strings[0].rstrip('/')
    if urllib.parse.urlparse(strings_head).scheme:
        return '/'.join((strings_head,) + strings[1:])
    else:
        return os.path.join(*strings)
