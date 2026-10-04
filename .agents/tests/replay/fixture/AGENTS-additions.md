
## This project

Bramble tracks equipment loans for the events team. The code is in `app/`.

Run the checks with `python3 app/test_bramble.py`. It needs nothing installed
and prints one line per check, then a summary. There is no build step, no
package manager, and no server to start.

`app/bramble.py` holds the rules. The one that matters most is that an item can
never be in two overlapping loans, which is what the old spreadsheet got wrong.
