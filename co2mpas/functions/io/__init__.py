
import pathlib
from .dill import *
from .excel import *
import logging
import pandas as pd
import lmfit
from types import MethodType
from .. import _iter_d, _get
from pip.operations.freeze import freeze
import datetime
from co2mpas._version import version
log = logging.getLogger(__name__)


def get_cache_fpath(fpath):
    fpath = pathlib.Path(fpath)
    cache_folder = fpath.parent.joinpath('.co2mpas_cache')
    try:
        cache_folder.mkdir()
    except:
        pass

    return str(cache_folder.joinpath('%s.dill' % fpath.name))


def check_cache_fpath_exists(fpath, cache_fpath):
    cache_fpath = pathlib.Path(cache_fpath)
    if cache_fpath.exists():
        inp_stats = pathlib.Path(fpath).stat()   ## Will scream if INPUT does not exist.
        cache_stats = cache_fpath.stat()
        if inp_stats.st_mtime <= cache_stats.st_mtime:
            return True
    return False


def check_file_format(fpath, extensions=('.xlsx',)):
    return fpath.lower().endswith(extensions)


def convert2df(data, data_descriptions, start_time):

    res = {'graphs': data['graphs']} if 'graphs' in data else {}

    res.update(_cycle2df(data, data_descriptions))

    res.update(_scores2df(data))

    res.update(_comparison2df(data))

    res.update(_proc_info2df(data, start_time))

    return res


def _comparison2df(data):
    res = {}

    for k, v in _iter_d(data.get('comparison', {}), depth=3):
        r = _get(res, *k, default=list)
        for i, j in v.items():
            d = {'param_id': i}
            d.update(j)
            r.append(d)
    if res:
        res = {'comparison': _dd2df(res, 'param_id', depth=3, axis=1)}

    return res


def _proc_info2df(data, start_time):
    res = (_co2mpas_info2df(start_time), _freeze2df())

    df, max_l = _pipe2list(data.get('pipe', {}))

    if df:
        df = pd.DataFrame(df)
        setattr(df, 'name', 'pipe')
        res += (df,)

    return {'proc_info': res}


def _co2mpas_info2df(start_time):

    time_elapsed = (datetime.datetime.today() - start_time).total_seconds()

    df = pd.DataFrame([
        {'Parameter': 'CO2MPAS version', 'Value': version},
        {'Parameter': 'Simulation started',
         'Value': start_time.strftime('%Y/%m/%d-%H:%M:%S')},
        {'Parameter': 'Time elapsed', 'Value': '%.3f sec' % time_elapsed}],
    )
    df.set_index(['Parameter'], inplace=True)
    setattr(df, 'name', 'info')
    return df


def _freeze2df():
    d = dict(v.split('==') for v in freeze())
    d['version'] = 'version'
    df = pd.DataFrame([d])
    df.set_index(['version'], inplace=True)
    setattr(df, 'name', 'versions')
    return df


def _pipe2list(pipe, i=0, source=()):
    res = []
    f = lambda x: (x,) if isinstance(x, str) else x
    max_l = i
    idx = {'nodes L%d' % i: str(v) for i, v in enumerate(source)}
    for k, v in pipe.items():
        k = f(k)
        d = {'nodes L%d' % i: str(k)}

        if 'error' in v:
            d['error'] = v['error']
        d.update(idx)
        res.append(d)

        if 'sub_pipe' in v:
            l, ml = _pipe2list(v['sub_pipe'], i=i+1, source=source + (k,))
            max_l = max(max_l, ml)
            res.extend(l)

    return res, max_l


def _cycle2df(data, data_descriptions):
    res = {}

    for i in {'nedc', 'wltp_h', 'wltp_l', 'wltp_p'}.intersection(data):

        v = {k: _data2df(v, data_descriptions) for k, v in data[i].items()}
        v = {k: v for k, v in v.items() if v}
        targets = v.pop('targets', None)
        if targets:
            _merge_targets(v, targets)
        res[i] = v

    return res


def _scores2df(data):
    dfs, edf = {}, {}
    cycles = ('ALL', 'WLTP-H', 'WLTP-L')
    for k, m in sorted(data.get('selection_scores', {}).items()):

        d = _get_selection_raw(k, m['best'])
        m = m['scores']
        for i in cycles:
            df = dfs[i] = dfs.get(i, [])
            df.append(_get_scores_raw(d, m.get(i, {})))

            df = edf[i] = edf.get(i, {})
            _extend_errors_raws(df, k, m.get(i, {}), cycles[1:])

    idx = ['model_id', 'from', 'selected', 'passed', 'selected_models']
    c = [n for n in cycles if n in dfs]
    frames = [pd.DataFrame(dfs[k]).set_index(idx) for k in c]
    df = pd.concat(frames, axis=1, keys=cycles)

    for k, v in list(edf.items()):
        for n, m in list(v.items()):
            if m:
                v[n] = pd.DataFrame(m).set_index(['model_id', 'param_id'])
            else:
                v.pop(n)
        if not v:
            edf.pop(k)
            continue
        c = [n for n in cycles if n in v]
        edf[k] = pd.concat([v[n] for n in c], axis=1, keys=c)

    c = [n for n in cycles if n in edf]
    edf = pd.concat([edf[k] for k in c], axis=1, keys=c)

    setattr(df, 'name', 'selections')
    setattr(edf, 'name', 'scores')

    return {'selection_scores': (df, edf)}


def _get_selection_raw(model_id, data):
    d = {
        'from': None,
        'passed': None,
        'selected': False,
        'selected_models': None,
        'model_id': model_id
    }
    d.update(data)
    return d


def _get_scores_raw(idx, data):
    d = {
        'score': None,
        'n': None,
        'success': None,
        'models': data.get('models', None)
    }
    d.update(data.get('score', {}))
    d.update(idx)
    return d


def _extend_errors_raws(res, model_id, data, cycles):
    for i in cycles:
        r = res[i] = res.get(i, [])
        errors = data.get('errors', {}).get(i, {})
        limits = data.get('limits', {}).get(i, {})
        for k, v in errors.items():

            d = {
                'up_limit': limits.get('up_limit', {}).get(k, None),
                'dn_limit': limits.get('dn_limit', {}).get(k, None),
                'score': v,
                'param_id': k,
                'model_id': model_id
            }

            r.append(d)

    return res


def _merge_targets(data, targets):
    _map = lambda x: 'target %s' % x

    def _sort(x):
        x = stlp(x)[-1]
        if x.startswith('target '):
            return (x[7:], 1)
        return (x, 0)

    for k, v in targets.items():
        if v.empty:
            continue

        if 'time_series' == k:
            v.rename(columns=_map, inplace=True)
            axis = 1
        elif 'parameters' == k:
            v.rename(index=_map, inplace=True)
            axis = 0
        else:
            continue

        for i in ['predictions', 'calibrations', 'inputs']:
            if i in data and k in data[i] and not data[i][k].empty:
                data[i][k] = pd.concat([data[i][k], v], axis=axis, copy=False)
                c = sorted(data[i][k].axes[axis], key=_sort)
                data[i][k] = data[i][k].reindex_axis(c, axis=axis, copy=False)


def _parse_name(name, _standard_names=None):
    """
    Parses a column/row name.

    :param name:
        Name to be parsed.
    :type name: str

    :return:
        The parsed name.
    :rtype: str
    """

    if _standard_names and name in _standard_names:
        return _standard_names[name]

    name = name.replace('_', ' ')

    return name.capitalize()


def check_writeable(data):
    """
    Checks if a data is writeable.

    :param data:
        Data to be checked.
    :type data: str, float, int, dict, list, tuple

    :return:
        If the data is writeable.
    :rtype: bool
    """

    if isinstance(data, dict):
        for v in data.values():
            if not check_writeable(v):
                return False
        return True
    elif isinstance(data, (list, tuple)):
        for v in data:
            if not check_writeable(v):
                return False
        return True
    elif not (hasattr(data, '__call__') or isinstance(data, MethodType)):
        return True
    return False


def _str_data(data):
    if isinstance(data, np.ndarray):
        data = list(data)
    elif isinstance(data, lmfit.Parameters):
        data = data.valuesdict()
    return str(data)


def _data2df(data, data_descriptions):
    res = {}

    for k, v in data.items():
        if 'time_series' == k:
            res[k] = _time_series2df(v, data_descriptions)
        elif 'parameters' == k:
            res[k] = _parameters2df(v, data_descriptions)

    return res


def _parameters2df(data, data_descriptions):
    df = []

    for k, v in sorted(data.items()):
        if check_writeable(v):
            d = {
                'Parameter': _parse_name(k, data_descriptions),
                'Model Name': k,
                'Value': _str_data(v)
            }
            df.append(d)
    if df:
        df = pd.DataFrame(df)
        df.set_index(['Parameter', 'Model Name'], inplace=True)
        return df
    else:
        return pd.DataFrame()


def _time_series2df(data, data_descriptions):
    if data:
        it = sorted(data.items())
        index = [(_parse_name(k, data_descriptions), k) for k, v in it]
        index = pd.MultiIndex.from_tuples(index)
        return pd.DataFrame(np.array([v for k, v in it]).T, columns=index)
    return pd.DataFrame()


def _dd2df(dd, index, depth=0, axis=1):
    for k, v in _iter_d(dd, depth=depth):
        _get(dd, *k[:-1])[k[-1]] = pd.DataFrame(v).set_index(index)

    for d in range(depth - 1, -1, -1):
        for k, v in _iter_d(dd, depth=d):
            keys, frames = zip(*sorted(v.items()))
            df = pd.concat(frames, axis=1, keys=keys)
            if k:
                _get(dd, *k[:-1])[k[-1]] = df
            else:
                dd = df
    return dd
