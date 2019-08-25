# tg_dump_anal
Telegram dump analysis

```
$ ./tgdumpanal.py --help
usage: tgdumpanal.py [-h] [--directory DIRECTORY | --pickle PICKLE]
                     [--write-pickle WRITE_PICKLE] [--report] [--dump]
                     [--wc WC] [--wc-mask WC_MASK] [--wc-exclude WC_EXCLUDE]
                     [--wc-num WC_NUM]

optional arguments:
  -h, --help            show this help message and exit
  --directory DIRECTORY
                        directory containing message*.html
  --pickle PICKLE       pickle file containing parsed messages
  --write-pickle WRITE_PICKLE
                        specify a filename to write parsed messages to a
                        pickle file
  --report              print report
  --dump                dump all messages to console
  --wc WC               generate wordcloud and store in this PNG filename
  --wc-mask WC_MASK     file containing image mask for wordcloud
  --wc-exclude WC_EXCLUDE
                        file containing words to exclude from wordcloud, one
                        per line
  --wc-num WC_NUM       number of words to include in wordcloud
```
