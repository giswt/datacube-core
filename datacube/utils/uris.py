import os

import pathlib
import re
from copy import deepcopy
from urllib.parse import urlparse, parse_qsl
from urllib.request import url2pathname

URL_RE = re.compile(r'\A\s*[\w\d\+]+://')


def is_url(url_str):
    """
    Check if url_str tastes like a url (starts with blah://)

    >>> is_url('file:///etc/blah')
    True
    >>> is_url('http://greg.com/greg.txt')
    True
    >>> is_url('s3:///etc/blah')
    True
    >>> is_url('/etc/blah')
    False
    >>> is_url('C:/etc/blah')
    False
    """
    try:
        return URL_RE.match(url_str) is not None
    except TypeError:
        return False


def uri_to_local_path(local_uri):
    """
    Transform a URI to a platform dependent Path.

    :type local_uri: str
    :rtype: pathlib.Path

    For example on Unix:
    'file:///tmp/something.txt' -> '/tmp/something.txt'

    On Windows:
    'file:///C:/tmp/something.txt' -> 'C:\\tmp\\test.tmp'

    .. note:
        Only supports file:// schema URIs
    """
    if not local_uri:
        return None

    components = urlparse(local_uri)
    if components.scheme != 'file':
        raise ValueError('Only file URIs currently supported. Tried %r.' % components.scheme)

    path = url2pathname(components.path)

    if components.netloc:
        if os.name == 'nt':
            path = '//{}{}'.format(components.netloc, path)
        else:
            raise ValueError('Only know how to use `netloc` urls on Windows')

    return pathlib.Path(path)


def mk_part_uri(uri, idx):
    """ Appends fragment part to the uri recording index of the part
    """
    return '{}#part={:d}'.format(uri, idx)


def get_part_from_uri(uri):
    """
    Reverse of mk_part_uri

    returns None|int|string
    """

    def maybe_int(v):
        if v is None:
            return None
        try:
            return int(v)
        except ValueError:
            return v

    opts = dict(parse_qsl(urlparse(uri).fragment))
    return maybe_int(opts.get('part', None))


def as_url(maybe_uri):
    if is_url(maybe_uri):
        return maybe_uri
    else:
        return pathlib.Path(maybe_uri).absolute().as_uri()


def default_base_dir():
    """Return absolute path to current directory. If PWD environment variable is
       set correctly return that, note that PWD might be set to "symlinked"
       path instead of "real" path.

       Only return PWD instead of cwd when:

       1. PWD exists (i.e. launched from interactive shell)
       2. Contains Absolute path (sanity check)
       3. Absolute ath in PWD resolves to the same directory as cwd (process didn't call chdir after starting)
    """
    cwd = pathlib.Path('.').resolve()

    pwd = os.environ.get('PWD')
    if pwd is None:
        return cwd

    pwd = pathlib.Path(pwd)
    if not pwd.is_absolute():
        return cwd

    try:
        pwd_resolved = pwd.resolve()
    except IOError:
        return cwd

    if cwd != pwd_resolved:
        return cwd

    return pwd


def without_lineage_sources(doc, spec, inplace=False):
    """ Replace lineage.source_datasets with {}

    :param dict doc: parsed yaml/json document describing dataset
    :param spec: Product or MetadataType according to which `doc` to be interpreted
    :param bool inplace: If True modify `doc` in place
    """

    if not inplace:
        doc = deepcopy(doc)

    doc_view = spec.dataset_reader(doc)

    if 'sources' in doc_view.fields:
        doc_view.sources = {}

    return doc


def normalise_path(p, base=None):
    """Turn path into absolute path resolving any `../` and `.`

       If path is relative pre-pend `base` path to it, `base` if set should be
       an absolute path. If not set, current working directory (as seen by the
       user launching the process, including any possible symlinks) will be
       used.
    """
    assert isinstance(p, (str, pathlib.Path))
    assert isinstance(base, (str, pathlib.Path, type(None)))

    def norm(p):
        return pathlib.Path(os.path.normpath(str(p)))

    if isinstance(p, str):
        p = pathlib.Path(p)

    if isinstance(base, str):
        base = pathlib.Path(base)

    if p.is_absolute():
        return norm(p)

    if base is None:
        base = default_base_dir()
    elif not base.is_absolute():
        raise ValueError("Expect base to be an absolute path")

    return norm(base / p)
