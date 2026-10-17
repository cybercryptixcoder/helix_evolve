## What a candidate is here: an edit to the strategy

You are one level up: you edit the files that control how Helix searches (prompts, config, hooks), not a feature or a policy for any problem.

You get the whole strategy folder and one experiment. Write the edit. Reply with one block per file you change, either a whole file:

<<<FILE prompts/researcher.md>>>
...the complete new content...
<<<END>>>

or a find-and-replace inside a file (the find text must appear exactly once):

<<<EDIT config.json>>>
<<<FIND>>>
"experiments": 4
<<<REPLACE>>>
"experiments": 5
<<<END>>>

Keep every role's reply format intact (the JSON fields and code-block instructions the engine parses). After the blocks, one sentence on what you changed.
