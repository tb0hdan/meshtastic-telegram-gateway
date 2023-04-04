# -*- coding: utf-8 -*-
""" Github module for getting firmware info """

from github import Github


def get_firmware_info(token) -> list:
    """
    Get firmware info from Github

    :param token:
    :return:
    """
    gh_connection = Github(token)

    repo = gh_connection.get_repo('meshtastic/firmware')

    releases = []
    for release in repo.get_releases():
        # only proper naming
        if not release.title.startswith("Meshtastic Firmware"):
            continue
        # only v2
        if not release.tag_name.startswith("v2"):
            continue
        # only non-revoked
        if 'Revoked' in release.title:
            continue
        for asset in release.get_assets():
            if not asset.name.startswith('firmware'):
                continue
            current_release = {'created_at': release.created_at,
                               'tag_name': release.tag_name,
                               'html_url': release.html_url,
                               'download_url': asset.browser_download_url}
            releases.append(current_release)
    return releases
