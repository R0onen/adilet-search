# Everyday questions about the added acts

`queries.jsonl`: 55 questions (45 Russian, 10 Kazakh) in everyday wording about 24 of the 32 acts that the deployed index holds beyond the 8 main codes: family, criminal and civil procedure, enforcement, consumer protection, road traffic, housing, bankruptcy, collection, microcredit, citizenship, migration, health, social protection, land, personal data, notaries, LLPs, mortgage, children's rights, registration of real estate, education, penal enforcement and the Digital Code.

Each row has the question, its language and `relevant`: the article or articles that answer it (`titles` repeats their titles for reading). A result counts as right when any of them is returned.

## How it was made

- The articles were chosen from the corpus by their titles, one to five per act, for subjects people commonly ask about. The search system was not used to choose them.
- The questions were then written with an LLM assistant in the words a person would use, avoiding the wording of the title, and each label was checked against the article's title.
- Nobody outside the project and no lawyer has reviewed the set. The Kazakh questions need a native speaker's check.

## What it is for

The 195 synthetic test questions cover only the 8 codes. This set shows whether search finds the right article in the added acts. It is small and written by the project itself: use it as a sanity check, not as a benchmark. It was not used for training or for tuning the dictionary of everyday words.

Run: `python ml/scripts/eval_api_everyday.py <label> out.jsonl` against a running stack.
