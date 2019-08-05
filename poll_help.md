```
!poll
  -n(--new is allowed as well) NAME COMMA_SEPARATED_OPTIONS [optional: -m(--allow-multiple)]
      Help: Create a poll.
      Help for -m(--allow-multiple): Allow voting for multiple options.
  OR -e (--end)
      Help: Stop the poll and calculate the results.
  OR -t(--template) TEMPLATE_NAME
      Help: Create a poll from a template
  OR --new-template NAME COMMA_SEPARATED_OPTIONS
      Help: Create a new template
```

code for it
```python
vote_admin_parser = twitchirc.ArgumentParser(prog='!poll', add_help=False)
vap_gr1 = vote_admin_parser.add_mutually_exclusive_group()
# name,COMMA-SEPARATED-VOTES
vap_gr1.add_argument('-n', '--new', help='Create a poll.', dest='new',
                     metavar=('NAME', 'COMMA_SEPARATED_OPTIONS'), nargs=2)
vap_gr1.add_argument('-e', '--end', help='Stop the poll and calculate the results.', dest='end',
                     action='store_true')
vote_admin_parser.add_argument('-m', '--allow-multiple', help='Allow voting for multiple options', dest='multiple',
                               action='store_true', default=False)
vap_gr1.add_argument('-t', '--template', help='Create a poll from a template', dest='new_from_template',
                     metavar='TEMPLATE_NAME')
vap_gr1.add_argument('--new-template', help='Create a new template', dest='new_template', nargs=2,
                     metavar=('(NAME)', '(COMMA SEPARATED OPTIONS)'))
```