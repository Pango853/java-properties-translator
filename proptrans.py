#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
    TODO: NO native2ascii support
          You have convert ASCII properties to UTF-8 at first(native2ascii -reverse), otherwise it won't be translated properly.
    TODO: Support variables ({0})
    TODO: Support CRLF
    TODO: Show error summary at the last
'''

import argparse
from argparse import RawTextHelpFormatter
import ConfigParser
import re
import os
import sys
import datetime
from collections import OrderedDict

import json
import requests
import urllib
from xml.etree import ElementTree

class MSTranslator:

    def get_token(self):
        '''Get the access token from ADM. Note that token will only last for 10 minutes'''

        args = {
            'client_id': self._CLIENT_ID,
            'client_secret': self._CLIENT_SECRET,
            'scope': 'http://api.microsofttranslator.com',
            'grant_type': 'client_credentials'
        }

        oauth_url = 'https://datamarket.accesscontrol.windows.net/v2/OAuth2-13'

        try:
            #make call to get ADM token and parse json
            oauth_rs = json.loads(requests.post(oauth_url, data = urllib.urlencode(args)).content)
            #prepare the token
            token = "Bearer " + oauth_rs['access_token']
        except OSError:
            pass

        return token
    #end get_token

    def __init__(self, client_id, client_secret):
        self._CLIENT_ID = client_id
        self._CLIENT_SECRET = client_secret
        self._token = None
    #end __init__

    def trans(self, lang_code_from, lang_code_to, text):
        if self._token is None:
            self._token = self.get_token()

        #Call to Microsoft Translator Service
        headers = {"Authorization ": self._token}
        url = "http://api.microsofttranslator.com/v2/Http.svc/Translate?text={}&to={}".format(text, lang_code_to)

        translation = None
        try:
            #make request
            response = requests.get(url, headers = headers)
            result = ElementTree.fromstring(response.text.encode('utf-8'))
            translation = result.text
            if translation is None:
                translation = '[FAILED]'
                print('[ERROR] result = %s' % ElementTree.tostring(result))
        except OSError:
            translation = '[FAILED]'

        return translation
    #end get_text_and_translate()

class PDict(OrderedDict):
    def __missing__(self, key):
        return ''

class I18nProperties:

    def __init__(self, path):
        self.filepath = path

    def properties2dict(cls, path):
        pdict = PDict()

        with open(path) as fp:
            is_multi_row = False
            last_key = None

            for ln in fp:
                if is_multi_row:
                    pdict[last_key] += ln
                    if not ln.rstrip().endswith('\\'):
                        is_multi_row = False
                    continue

                matches = re.match('#', ln) or re.match('!', ln)
                if matches is not None:
                    last_key = None
                    continue # skip comments
                else:
                    matches = re.match('(.*?)\s*=\s*(.*)', ln)
                    if matches is not None:
                        last_key = matches.group(1)
                        pdict[last_key] = matches.group(2)
                        
                        if ln.rstrip().endswith('\\'):
                            is_multi_row = True
                    else:
                        if '' != ln.strip():
                            print '[WARN] BAD LINE: "%s"' % ln.rstrip()
        return pdict

    def add(self, lang_code, path):
        if path is None:
            pdict = PDict()
        else:
            pdict = self.properties2dict(path)

        is_complete = False
        with open(self.filepath+'.new', 'w') as fpw, open(self.filepath) as fp:
            is_multi_row = False
            last_key = None
            last_i18values = PDict()
            last_lang = None

            for ln in fp:
                if is_multi_row:
                    last_i18values[last_lang] += ln
                    if not ln.rstrip().endswith('\\'):
                        is_multi_row = False
                    continue

                # parse other languages
                matches = re.match('\[([\w-]+)\]\s*:\s*(.*\W+)', ln)
                if matches is not None:
                    last_lang = matches.group(1)
                    last_i18values[last_lang] = matches.group(2)

                    if ln.rstrip().endswith('\\'):
                        is_multi_row = True

                    continue

                if last_key is not None:
                    # append new lang
                    last_i18values[lang_code] = pdict[last_key] + '\n'

                    fpw.write(last_key + ' = ' + last_i18values[None] or '\n')
                    for k, v in last_i18values.iteritems():
                        if k is not None:
                            fpw.write('[%s] : %s' % (k, v))
                    last_key = None

                matches = re.match('#', ln) or re.match('!', ln)
                if matches is not None:
                    last_key = None
                    fpw.write(ln)
                    continue # skip comments
                else:
                    matches = re.match('(.*?)\s*[=:]\s*(.*\W+)', ln)
                    if matches is not None:
                        last_lang = None
                        last_key = matches.group(1)
                        last_i18values[last_lang] = matches.group(2) # default

                        if ln.rstrip().endswith('\\'):
                            is_multi_row = True
                    else:
                        last_key = None
                        if '' != ln.strip():
                            print '[WARN] BAD LINE: "%s"' % ln.rstrip()
                        else:
                            fpw.write(ln)
            is_complete = True
        #endwith

        # Rename files
        if is_complete:
            os.rename(self.filepath, self.filepath + ('-%s.bak' % datetime.datetime.now().strftime("%Y%m%d%H%M%S")))
            os.rename(self.filepath+'.new', self.filepath)
    #end add()

    def _properties_value2text(self, pvalue):
        ''' TODO: Support newlines'''
        text = re.sub(r'\s*\\\s*(\r|)\n\s*', r' ', pvalue)
        text = re.sub(r'(\\r|)\\n', r'\n', text)
        return text

    def _translate(self, lang_code_from, lang_code_to, text_from, text_to):
        if text_to.strip(): # only translate if not yet exists
            return text_to

        if not text_from.strip(): # prevent translating empty text
            return text_from

        print('< %s' % text_from.rstrip())
        translation = translator.trans(lang_code_from, lang_code_to, self._properties_value2text(text_from.rstrip()))

        text_to = re.sub(r'\r?\n', r'\\\n', translation)
        text_to = re.sub(r'(\\\n$|\\$)', r'\n', text_to) # Remove invalid ending (\)
        if not text_to.endswith('\n'):
            text_to += '\n'
        print('> %s' % text_to)

        return text_to
    #end _translate()

    def translate(self, translator, lang_code_from, lang_code_to):
        print('Translate [%s] based on [%s]...' % (lang_code_to, lang_code_from or '(default)'))
        is_complete = False
        with open(self.filepath+'.new', 'w') as fpw, open(self.filepath) as fp:
            is_multi_row = False
            last_key = None
            last_i18values = PDict()
            last_lang = None

            for ln in fp:
                if is_multi_row:
                    last_i18values[last_lang] += ln
                    if not ln.rstrip().endswith('\\'):
                        is_multi_row = False
                    continue

                # parse other languages
                matches = re.match('\[([\w-]+)\]\s*:\s*(.*\W+)', ln)
                if matches is not None:
                    last_lang = matches.group(1)
                    last_i18values[last_lang] = matches.group(2)

                    if ln.rstrip().endswith('\\'):
                        is_multi_row = True

                    continue

                if last_key is not None:
                    fpw.write(last_key + ' = ' + last_i18values[None] or '\n')
                    for k, v in last_i18values.iteritems():
                        if k is not None:
                            if lang_code_to == k:
                                v = self._translate(lang_code_from, lang_code_to, last_i18values[lang_code_from], v)
                            fpw.write('[%s] : %s' % (k, v))
                    last_key = None

                matches = re.match('#', ln) or re.match('!', ln)
                if matches is not None:
                    last_key = None
                    fpw.write(ln)
                    continue # skip comments
                else:
                    matches = re.match('(.*?)\s*[=:]\s*(.*\W+)', ln)
                    if matches is not None:
                        last_lang = None
                        last_key = matches.group(1)
                        last_i18values[last_lang] = matches.group(2) # default

                        if ln.rstrip().endswith('\\'):
                            is_multi_row = True
                    else:
                        last_key = None
                        if '' != ln.strip():
                            print '[WARN] BAD LINE: "%s"' % ln.rstrip()
                        else:
                            fpw.write(ln)
            is_complete = True
        #endwith

        # Rename files
        if is_complete:
            os.rename(self.filepath, self.filepath + ('-%s.bak' % datetime.datetime.now().strftime("%Y%m%d%H%M%S")))
            os.rename(self.filepath+'.new', self.filepath)

    def gen_ifilepath(cls, filepath, lang_code):
        if lang_code is None:
            newfilepath = re.sub(r'(_[a-zA-Z0-9-]+?)(\.[^\.]+|)$', r'\2', filepath)
            if filepath != newfilepath:
                return newfilepath
            else:
                return re.sub(r'(_i18n|)(\.[^\.]+|)$', r'_NEW\2', filepath)
        else:
            return re.sub(r'(_i18n|)(\.[^\.]+|)$', '_'+ lang_code +r'\2', filepath)
    #end gen_filename()

    def build(self, lang_code=None):
        langs = set()

        newfilepath = self.gen_ifilepath(self.filepath, lang_code)
        print('Build %s...' % newfilepath)
        with open(self.filepath) as fp, open(newfilepath, 'w') as fpw:
            is_multi_row = False
            last_key = None
            last_i18values = PDict()
            last_lang = None

            for ln in fp:
                if is_multi_row:
                    last_i18values[last_lang] += ln
                    if not ln.rstrip().endswith('\\'):
                        is_multi_row = False
                    continue

                # parse other languages
                matches = re.match('\[([\w-]+)\]\s*:\s*(.*\W+)', ln)
                if matches is not None:
                    last_lang = matches.group(1)
                    last_i18values[last_lang] = matches.group(2)
                    langs.add(last_lang)

                    if ln.rstrip().endswith('\\'):
                        is_multi_row = True

                    continue

                if last_key is not None:
                    fpw.write(last_key + ' = ' + last_i18values[lang_code] or '\n')
                    last_key = None

                matches = re.match('#', ln) or re.match('!', ln)
                if matches is not None:
                    last_key = None
                    fpw.write(ln)
                    continue # skip comments
                else:
                    matches = re.match('(.*?)\s*[=:]\s*(.*\W+)', ln)
                    if matches is not None:
                        last_lang = None
                        last_key = matches.group(1)
                        last_i18values[last_lang] = matches.group(2) # default

                        if ln.rstrip().endswith('\\'):
                            is_multi_row = True
                    else:
                        last_key = None
                        if '' != ln.strip():
                            print '[WARN] BAD LINE: "%s"' % ln.rstrip()
                        else:
                            fpw.write(ln)
            is_complete = True
        #endwith

        return langs
    #end build()

    def build_all(self):
        langs = self.build()

        for lang_code in langs:
            self.build(lang_code)

    #end build_all()


if '__main__' == __name__:
    parser = argparse.ArgumentParser(description='''Examples:
        ( echo "#[DEFAULT:ja]" && echo | cat - input/messages_ja.properties ) > messages_i18n.properties

        python proptrans.py messages_i18n.properties add input/messages.properties --lang=en
        python proptrans.py messages_i18n.properties add input/messages_ja.properties --lang=ja
        python proptrans.py messages_i18n.properties add --lang=zh-CHT

        python proptrans.py messages_i18n.properties translate --lang=en
        python proptrans.py messages_i18n.properties translate --base=en --lang=zh-CHT

        python proptrans.py messages_i18n.properties add --lang=zh-CHS
        python proptrans.py messages_i18n.properties translate --base=en --lang=zh-CHS
        python proptrans.py messages_i18n.properties build''', formatter_class=RawTextHelpFormatter)

    parser.add_argument('file', help='base properties file')
    parser.add_argument('cmd', help='command')
    parser.add_argument('--lang', help='target langage code', required=False)
    parser.add_argument('--base', help='translate from specific langage code', required=False, default=None)
    parser.add_argument('addfile', help='add properties file', nargs='?')
    args = parser.parse_args()

    cfg_filepath = 'proptrans.cfg'
    cfg = ConfigParser.SafeConfigParser()
    if os.path.exists(cfg_filepath):
        cfg.read(cfg_filepath)
    else:
        sys.stderr.write('Configuration file(%s) not found!\n' % cfg_filepath)
        sys.exit(2)

    try:
        if 'add' == args.cmd:
            if args.lang is None:
                raise ValueError('--lang is required!')

            pf = I18nProperties(args.file)
            pf.add(args.lang, args.addfile)

        elif 'translate' == args.cmd:
            if args.lang is None:
                raise ValueError('--from is required!')

            translator = MSTranslator(cfg.get('AZURE_DATAMARKET', 'CLIENT_ID'), cfg.get('AZURE_DATAMARKET', 'CLIENT_SECRET'))
            pf = I18nProperties(args.file)
            pf.translate(translator, args.base, args.lang)
        elif 'build' == args.cmd:
            pf = I18nProperties(args.file)
            pf.build_all()
        else:
            parser.print_help()

    except ValueError as e:
        sys.stderr.write('ValueError: %s!\n' % e)
        sys.exit(1)

#endif __main__
