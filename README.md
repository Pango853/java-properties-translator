# java-properties-translator

Properties file translation tool using Microsoft Translation.


Example:

$ ( echo "#[DEFAULT:ja]" && echo | cat - input/messages_ja.properties ) > messages_i18n.properties

$ python proptrans.py messages_i18n.properties add input/messages.properties --lang=en
$ python proptrans.py messages_i18n.properties add input/messages_ja.properties --lang=ja
$ python proptrans.py messages_i18n.properties add --lang=zh-CHT

$ python proptrans.py messages_i18n.properties translate --lang=en
$ python proptrans.py messages_i18n.properties translate --base=en --lang=zh-CHT

$ python proptrans.py messages_i18n.properties add --lang=zh-CHS
$ python proptrans.py messages_i18n.properties translate --base=en --lang=zh-CHS
$ python proptrans.py messages_i18n.properties build

