# Third-party notices

This skill is MIT-licensed (`LICENSE` in https://github.com/bcanfield/headshot-agent). The MIT licence covers the repo's code and docs only.

## insightface models

Face ranking uses insightface's pretrained `buffalo_l` models, which insightface licenses for non-commercial research use only. The MIT licence does not cover them. Commercial use needs a licence from insightface (see https://github.com/deepinsight/insightface#license). `scripts/generate.py` works without them. They are downloaded on first use of `scripts/rank.py`; neither the skill nor the repo redistributes them.

## Prompt sources (CC BY 4.0)

`assets/prompt.txt` is modified: it adapts and rewrites wording from the prompts below, which are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Their wording is also quoted in the repo's `docs/research.md`.

- yijzhu-netizen, [awesome-ai-image-prompts](https://github.com/yijzhu-netizen/awesome-ai-image-prompts). Credit: drawcue.com.
- Anil-matcha, [Awesome-GPT-Image-2.5-API-Prompts](https://github.com/Anil-matcha/Awesome-GPT-Image-2.5-API-Prompts).
- vicmini, [awesome-image-to-image-prompts](https://github.com/vicmini/awesome-image-to-image-prompts).

## MIT-licensed excerpts

The repo's `docs/research.md` quotes short excerpts from [aivideoweb/awesome-gpt-image-2-5-prompts](https://github.com/aivideoweb/awesome-gpt-image-2-5-prompts) and [Pixmind-io/awesome-gpt-image-2-prompts](https://github.com/Pixmind-io/awesome-gpt-image-2-prompts), both MIT.
