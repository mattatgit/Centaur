"""Presentation of build names. Release and project metadata use the full version."""
import re


BUILD = r'\d+\.\d+\.\d+(?:-preview)?\+[0-9a-fA-F]{7,40}'


def compact_version(version):
    if not re.fullmatch(BUILD, version):
        return version
    semver, commit = version.split('+')
    major, minor, patch = semver.removesuffix('-preview').split('.')
    number = f'{major}.{minor}' if patch == '0' else f'{major}.{minor}.{patch}'
    return f'V{number} {commit[:7]}'


def project_build_mentions(text, project_name):
    if not project_name:
        return text
    reference = rf'(?<![\w/]){re.escape(project_name)} v(?P<version>{BUILD})(?![\w+-])'
    return re.sub(reference, lambda match: project_name + ' ' + compact_version(match['version']), text)
