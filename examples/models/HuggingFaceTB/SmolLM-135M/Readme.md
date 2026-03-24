Contributed by: Geert Heyman

Integrated and tested by: Istemi Ekin Akkus

This folder contains the property computation code for evaluating the [HuggingFace HuggingFaceTB/SmolLM-135M](https://huggingface.co/HuggingFaceTB/SmolLM-135M) model on the [GPQA](https://huggingface.co/datasets/Idavidrein/gpqa) benchmark.

The code uses the Huggingface fork of [`llm-eval` package](git+https://github.com/huggingface/lm-evaluation-harness.git@7949275).

It tries to reproduce the GPQA column for this model on the Open LLM leaderboard: https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard#/?search=HuggingFaceTB%2FSmolLM-135M
