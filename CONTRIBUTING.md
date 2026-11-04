# Contributing

Issues and pull requests are welcome: bug fixes, new evaluation sets, other languages, other tag
vocabularies.

- Contributions are accepted under the Apache License 2.0 (code) and CC BY-SA 4.0 (data), the same terms
  as the repository.
- Before committing a notebook, strip its outputs and Colab metadata:
  `python tools/strip_notebooks.py notebooks/<name>.ipynb`. Colab stores your account name and id in
  the notebook metadata.
- Never commit tokens, API keys or personal data. Keep secrets in Colab's secret store or environment
  variables (for example `WIKI_UA` for the Wikivoyage collector).
- A new result should come with the notebook or script that produces it and should not change an
  existing result file.
