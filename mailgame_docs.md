# Table of contents

- [The !mailgame command](#the-mailgame-command)
    - [`!mailgame start` subcommand](#mailgame-start-subcommand)
    - [`!mailgame stop` subcommand](#mailgame-stop-subcommand)
    - [`!mailgame draw` subcommand](#mailgame-draw-subcommand)
    - [`!mailgame cancel` subcommand](#mailgame-cancel-subcommand)
    - [`!mailgame timeout` subcommand](#mailgame-timeout-subcommand)
    - [`!mailgame whatif` subcommand](#mailgame-whatif-subcommand)

## The !mailgame command

- Aliases: `!mailbox`.
- Controls every aspect of the mailgame minigame

### `!mailgame start` subcommand

- Starts the guessing period for the minigame
- Optional arguments (feel free to ignore :)
    - `guesses:NUMBER` controls how many guesses a single person/account should have (by default `1`)
    - `winners:NUMBER` controls how many non-perfect guesses should be showed if the bot finds no perfect ones
      (by default `3`)
    - `+find_best` / `-find_best` if disabled (using `-find_best`) the bot will only display perfect guesses
      (enabled by default)
    - `+punish_more` / `-punish_more` if enabled (using `+punish_more`) the bot will disqualify people who guess more
      than they are allowed to, instead of taking their first guess
- Example:
    - `!mailgame start` => `Mail minigame starts now! You get 1 guess. Format is 30 32 29.`

### `!mailgame stop` subcommand

- Stops the guessing period for the minigame. Can also stop automatic timeouts (setup by `!mailgame timeout`)
- Takes no required arguments and no optional arguments
- Examples:
    - (with timeouts set up) `!mailgame stop` => `@you, Stopped automatic timeouts.`
    - (with a game set up) `!mailgame stop` => `Entries are now closed!`
    - (if someone else stopped guessing) `!mailgame stop` => `@you, This game has closed (15s ago).`

### `!mailgame draw` subcommand

- Draws winners from the minigame.

- Required arguments:
    - scores in the same format as guesses (like `30 32 29`)
- If the guessing period isn't over yet by the time you run this command, it will automatically stop the guessing period
  and notify you.
- Automatically saves data about the minigame into the bot's database.
- Examples:
    - (with a game set up) `!mailgame draw 33 33 33`
      => `Mm_sUtilityBot: Best guesses are @maiz (Sub) (3/3 +++), @helen20_ (Sub) (2/3 +-+), @jaengelhart24 (Sub) (2/3 +-+), @chocola5 (2/3 +-+). Saved winners to database. Time taken: 0.02s. ID: 194`
        - `@maiz` - the person who guessed,
        - `(Sub)` - indicates that this person is a subscriber to the channel,
        - `3/3` - they guessed 3 out of 3 scores correctly,
        - `+++` - shows which scores were correct `+` meaning correct, `-` being incorrect.
    - (with a game but no guess matched) `!mailgame draw 33 33 33` => `Noone guessed even remotly right`
    - (with timeouts set up) `!mailgame draw 33 33 33` =>
      `Mm_sUtilityBot: @you, There is no minigame running, however there are automatic timeouts set up. Use "!mailgame cancel" to stop timing out.`

### `!mailgame cancel` subcommand

- Cancels the minigame without any side effects. No data will be saved for a canceled game, just like it never happened.
- Can also cancel timeouts set up by `!mailgame timeout`
- Example:
    - `!mailgame cancel` => `Mm_sUtilityBot: @you, Canceled the ongoing game.`

### `!mailgame timeout` subcommand

- Sets up timeouts for guessing.
- Optional arguments:
    - a message that will be used as a timeout reason
- Timeouts are active until canceled with `!mailgame cancel`!
- Examples:
    - `!mailgame timeout <TIMEOUT REASON>`
      => `Mm_sUtilityBot: @you, Will now time out mailbox game guesses. Use "!mailgame cancel" to stop timing out guesses.`
        - `Mm2PL(a spammer): 33 33 33`
        - `mm_sutilitybot timed out mm2pl for 5s for <TIMEOUT REASON>` The timeout length is
          configurable [here](https://kotmisia.pl/settings/36066935/mailbox_game.timeout_after) (requires login). 
          `0` is an exception, and it will make the bot delete the message instead of timing out the user.

### `!mailgame whatif` subcommand

- Allows for checking how many guesses match given scores
- Unlike other commands this one does not depend on the context it's used.
- Required arguments:
    - Game ID received from running `!mailgame draw`, identifies that specific game
    - scores in the same format as guesses (`30 32 29`)
- Examples:
    - `!mailgame whatif 194 30 32 29`
      => `Mm_sUtilityBot: Best guesses would be @hakaisha89 (2/3 ++-), @0xabad1dea (1/3 +--), @erodeken (1/3 -+-), @phynalphaze (1/3 -+-).`
