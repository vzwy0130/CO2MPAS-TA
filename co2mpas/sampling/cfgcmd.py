#!/usr/bin/env pythonw
#
# Copyright 2014-2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""Dice traitlets sub-commands for manipulating configurations"""

from . import baseapp, CmdException
from typing import Sequence, Text, List, Tuple    # @UnusedImport

import os.path as osp
from .._vendor import traitlets as trt


def prepare_matcher(terms, is_regex):
    import re

    def matcher(r):
        if is_regex:
            return re.compile(r, re.I).search
        else:
            return lambda w: r.lower() in w.lower()

    matchers = [matcher(t) for t in terms]

    def match(word):
        return any(m(word) for m in matchers)

    return match


class ConfigCmd(baseapp.Cmd):
    """
    Commands to manage configuration-options loaded from filesystem, cmd-line or defaults.

    Read also the help message for `--config-paths` generic option.
    """

    def __init__(self, **kwds):
            super().__init__(
                subcommands=baseapp.build_sub_cmds(*config_subcmds))


class WriteCmd(baseapp.Cmd):
    """
    Store config defaults into specified path(s); '{confpath}' assumed if none specified.

    SYNTAX
        %(cmd_chain)s [OPTIONS] [<config-path-1>] ...

    - If a path resolves to a folder, the filename '{appname}_config.py' is appended.
    - It OVERWRITES any pre-existing configuration file(s)!
    """

    ## Class-docstring CANNOT contain string-interpolations!
    description = trt.Unicode(__doc__.format(
        confpath=baseapp.default_config_fpaths()[0],
        appname=baseapp.APPNAME))

    examples = trt.Unicode("""
        Generate a config-file at your home folder:
            %(cmd_chain)s ~/my_conf

        To re-use the generated custom config-file alone, use the option
            --config-paths=~/my_conf  ...
        """)

    def run(self, *args):
        ## Prefer to modify `classes` after `initialize()`, or else,
        #  the cmd options would be irrelevant and fatty :-)
        self.classes = self.all_app_configurables()
        args = args or [None]
        for fpath in args:
            self.write_default_config(fpath, self.force)

class PathsCmd(baseapp.Cmd):
    """
    List resolved various paths and actual config-files loaded (descending order).

    This is more accurate that `%(app_cmd)s config show` cmd.
    """
    def run(self, *args):
        if len(args) > 0:
            raise CmdException('Cmd %r takes no arguments, received %d: %r!'
                               % (self.name, len(args), args))

        from . import project
        from . import crypto

        sep = osp.sep

        def format_tuple(path, files: List[Text]):
            endpath = sep if path[-1] != sep else ''
            return '  +--%s%s: %s' % (path, endpath, files or '')

        yield "CONFIG:"
        yield from (format_tuple(p, f) for p, f in self.loaded_config_files)

        yield "PROJECTS:"
        repo = project.ProjectsDB.instance(config=self.config)
        yield "  +--repopath: %s" % repo.repopath_resolved

        yield "GnuPG:"
        gpg = crypto.GpgSpec(config=self.config)
        yield "  +--gnupgexe: %s" % gpg.gnupgexe_resolved
        yield "  +--gnupghome: %s" % gpg.gnupghome_resolved

class ShowCmd(baseapp.Cmd):
    """
    Print configurations (defaults | files | merged) before any validations.

    SYNTAX
        %(cmd_chain)s [OPTIONS] [--source=(merged | default)] [<class-1> ...]
        %(cmd_chain)s [OPTIONS] --source file

    - Use --verbose to view config-params on all intermediate classes.
    - Similarly, you may also add `--show-config` global option
      on any command to view more targeted results.
    - Might not print accurately the defaults/merged for all(!) traits.
    """

    source = trt.FuzzyEnum(
        'defaults files merged'.split(), default_value='merged', allow_none=False,
        help="""Show configuration parameters in code, stored on disk files, or merged."""
    ).tag(config=True)

    def __init__(self, **kwds):
            import pandalone.utils as pndlu

            kwds.setdefault('cmd_aliases', {
                ('s', 'source'): ('ShowCmd.source',
                                  pndlu.first_line(ShowCmd.source.help))
            })
            kwds.setdefault('encrypt', True)  # Encrypted ALL freshly edited pconfigs.
            kwds.setdefault('raise_config_file_errors', False)
            super().__init__(**kwds)

    def initialize(self, argv=None):
        ## Copied from `Cmd.initialize()`.
        #
        self.parse_command_line(argv)
        static_config, persist_config = self.load_configurables_from_files()
        self._validate_cipher_traits_against_config_files(static_config, persist_config)
        if persist_config:
            static_config.merge(persist_config)
        static_config.merge(self.cli_config)
        ## Stop from applying file-configs - or any trait-validations will scream.

        self._loaded_config = static_config

    def _yield_file_configs(self, config, classes=None):
        assert not classes, (classes, "should be empty")

        for k, v in config.items():
            yield k
            try:
                for kk, vv in v.items():
                    yield '  +--%s = %s' % (kk, vv)
            except:
                yield '  +--%s' % v

    def _yield_configs_and_defaults(self, config, class_names, merged: bool):
        from boltons.setutils import IndexedSet as iset

        ## Prefer to modify `class_names` after `initialize()`, or else,
        #  the cmd options would be irrelevant and fatty :-)
        self.classes = self.all_app_configurables()

        ## Merging works only if all class_names visited.
        show_own_traits_only = not (self.verbose or merged)

        classes = list(self._classes_with_config_traits())
        if class_names:
            ## On specific class_names show all inherited traits.
            show_own_traits_only = False

            ## Preserve order and report misses.
            #
            class_names = iset(class_names)
            all_classes = {cls.__name__: cls
                           for cls
                           in classes}
            all_cls_names = all_classes.keys()
            unknown_names = class_names - all_cls_names
            matched_names = class_names & all_cls_names
            classes = [all_classes[cname] for cname in matched_names]
            if unknown_names:
                self.log.warning('Unknown classes given: %s', ', '.join(unknown_names))

        for cls in classes:
            clsname = cls.__name__
            if class_names and clsname not in class_names:
                continue

            cls_printed = False

            cls_traits = (cls.class_own_traits(config=True)
                          if show_own_traits_only else
                          cls.class_traits(config=True))
            for name, trait in sorted(cls_traits.items()):
                key = '%s.%s' % (clsname, name)
                if merged and key in config:
                    val = config[clsname][name]
                else:
                    val = repr(trait.default())

                if not cls_printed:
                    base_classes = ', '.join(p.__name__ for p in cls.__bases__)
                    yield '%s(%s)' % (clsname, base_classes)
                    cls_printed = True
                yield '  +--%s = %s' % (name, val)

    def run(self, *args):
        source = self.source.lower()
        if source == 'files':
            if len(args) > 0:
                raise CmdException("Cmd '%s --source files' takes no arguments, received %d: %r!"
                                   % (self.name, len(args), args))

            func = self._yield_file_configs
        elif source == 'defaults':
            func = lambda cfg, classes: self._yield_configs_and_defaults(
                cfg, classes, merged=False)
        elif source == 'merged':
            func = lambda cfg, classes: self._yield_configs_and_defaults(
                cfg, classes, merged=True)
        else:
            raise AssertionError('Impossible enum: %s' % source)

        config = self._loaded_config

        yield from func(config, args)


class DescCmd(baseapp.Cmd):
    """
    Describe config-params with their name '<class>.<param>' containing search-strings (case-insensitive).

    SYNTAX
        %(cmd_chain)s [OPTIONS] <search-term--1> [<search-term--2> ...]
        
    - Use --verbose to view config-params on all intermediate classes.
    """

    examples = trt.Unicode("""
        To list just what matched:
            %(cmd_chain)s --list 'criteria'
            %(cmd_chain)s -l --cls 'config'
            %(cmd_chain)s -l --regex  '^t.+cmd'
        To view help on specific parameters:
            %(cmd_chain)s wait
            %(cmd_chain)s -e 'rec.+wait'

        To view help on full classes:
            %(cmd_chain)s -ecl 'rec.+wait'
    """)

    list = trt.Bool(
        help="Just list any matches."
    ).tag(config=True)

    cls = trt.Bool(
        help="Match and print full classes only."
    ).tag(config=True)

    regex = trt.Bool(
        help="Search terms as regex."
    ).tag(config=True)

    def __init__(self, **kwds):
        import pandalone.utils as pndlu

        kwds.setdefault(
            'cmd_flags', {
                ('l', 'list'): (
                    {type(self).__name__: {'list': True}},
                    pndlu.first_line(type(self).list.help)
                ),
                ('e', 'regex'): (
                    {type(self).__name__: {'regex': True}},
                    pndlu.first_line(type(self).regex.help)
                ),
                ('c', 'cls'): (
                    {type(self).__name__: {'cls': True}},
                    pndlu.first_line(type(self).cls.help)
                ),
            }
        )
        super().__init__(**kwds)

    def run(self, *args):
        from toolz import dicttoolz as dtz

        if len(args) == 0:
            raise CmdException('Cmd %r takes at least one <search-term>!'
                               % self.name)

        ## Prefer to modify `class_names` after `initialize()`, or else,
        #  the cmd options would be irrelevant and fatty :-)
        self.classes = self.all_app_configurables()
        all_classes = list(self._classes_with_config_traits())

        if self.cls:
            search_map = {cls.__name__: cls
                   for cls in all_classes}

            def printer(ne, cls):
                return cls.class_get_help()

        else:
            search_map = {
                '%s.%s' % (cls.__name__, attr): (cls, trait)
                for cls in all_classes
                for attr, trait in
                (cls.class_traits
                 if self.verbose
                 else cls.class_own_traits)(config=True).items()}

            def printer(name, v):
                cls, attr = v
                return cls.class_get_trait_help(attr)

        match = prepare_matcher(args, self.regex)
        res_map = dtz.keyfilter(match, search_map)

        for name, v in sorted(res_map.items()):
            if self.list:
                yield name
            else:
                yield printer(name, v)

config_subcmds = (
    WriteCmd,
    PathsCmd,
    ShowCmd,
    DescCmd,
)
